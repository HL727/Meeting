from datetime import timedelta
from ipaddress import IPv4Interface

from defusedxml.cElementTree import fromstring as safe_xml_fromstring
from django.conf import settings
from django.db import models
from django.http import Http404, HttpResponse
from django.utils.functional import cached_property
from django.utils.timezone import now
from django.utils.translation import gettext_lazy as _
from drf_yasg.utils import swagger_auto_schema
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from sentry_sdk import capture_exception

from endpoint.consts import CONNECTION
from endpoint.docs import (
    BasicResponseSerializer,
    CallControlResponseSerializer,
    CustomerDomainsResponseSerializer,
    EmptyBodySerializer,
    EndpointListFilterSerializer,
    EndpointSetConfigurationSerializer,
    EndpointStatusFlagSerializer,
    EndpointStatusSerializer,
    FilterBodySerializer,
    InstallFirmwareSerializer,
    IpNetResponseSerializer,
    PasswordsResponseSerializer,
    ReportBodySerializer,
    ReportSerializer,
    ResponseSerializer,
    SetCustomerDomainsSerializer,
    SetIpNetSerializer,
    SetPasswordsSerializer,
    SipAliasSerializer,
)
from endpoint.view_mixins import CustomerRelationMixin, get_customer_from_request
from endpoint_provision.api_views import _provision
from endpoint_provision.models import EndpointProvision
from endpoint_provision.serializers import ProvisionBodySerializer
from license import lock_license
from license.api_helpers import license_validate_add
from meeting.models import Meeting
from meeting.serializers import MeetingSerializer
from provider.exceptions import (
    AuthenticationError,
    NotFound,
    ResponseConnectionError,
    ResponseError,
)
from room_analytics.models import EndpointHeadCount
from shared.exceptions import format_exception
from shared.mixins import CreateRevisionViewSetMixin

from .ext_api.parser.xapi import XAPICommandParser
from .models import (
    CustomerAutoRegisterIpNet,
    CustomerDefaultPassword,
    CustomerDomain,
    CustomerSettings,
    Endpoint,
    EndpointSIPAlias,
)
from .serializers import (
    CallControlSerializer,
    CustomerSettingsSerializer,
    EndpointBookingsSerializer,
    EndpointBulkUpdateSerializer,
    EndpointCommandsFileSerializer,
    EndpointExcelExportSerializer,
    EndpointLegSerializer,
    EndpointListSerializer,
    EndpointSerializer,
    EndpointUpdateSerializer,
    RunCommandSerializer,
    StatusUpResponseSerializer,
    StatusUpSerializer,
)


class EndpointViewSet(CreateRevisionViewSetMixin, CustomerRelationMixin, viewsets.ModelViewSet):

    serializer_class = EndpointSerializer
    queryset = Endpoint.objects.all().select_related('status')

    def get_serializer_class(self):
        if self.action == 'list':
            return EndpointListSerializer
        return EndpointSerializer

    def get_object(self) -> Endpoint:
        return super().get_object()  # type: ignore

    def get_queryset(self) -> models.QuerySet[Endpoint]:

        queryset = super().get_queryset()

        if self.action in ('list', 'incoming'):
            return self.filter_list_queryset(queryset)

        return queryset.select_related('status')

    def filter_list_queryset(self, queryset):

        query_serializer = EndpointListFilterSerializer(
            context=self.get_serializer_context(), data=self.request.query_params
        )
        query_serializer.is_valid(raise_exception=True)

        query_params = query_serializer.validated_data

        if query_params.get('firmware'):
            queryset = queryset.filter(
                status__software_version__startswith=query_params.get('firmware')
            )

        if query_params.get('product_name'):
            queryset = queryset.filter(product_name__icontains=query_params.get('product_name'))

        if query_params.get('mac_address'):
            queryset = queryset.filter(mac_address=query_params.get('mac_address'))

        if query_params.get('serial_number'):
            queryset = queryset.filter(serial_number=query_params.get('serial_number'))

        if query_params.get('ip'):
            queryset = queryset.filter(ip=query_params.get('ip'))

        if query_params.get('org_unit'):
            # TODO validate id and include ancestors
            queryset = queryset.filter(org_unit=query_params.get('org_unit'))

        if query_params.get('location'):
            queryset = queryset.filter(location__icontains=query_params.get('location'))

        if query_params.get('only_new') is True:
            queryset = queryset.filter(ts_created__gt=now() - timedelta(hours=2))
        elif 'only_new' in self.request.query_params and query_params.get('only_new') is False:
            queryset = queryset.filter(ts_created__lt=now() - timedelta(hours=2))

        if self.action == 'list':
            queryset = queryset.exclude(connection_type=CONNECTION.INCOMING)
        elif self.action == 'incoming':
            queryset = queryset.filter(connection_type=CONNECTION.INCOMING)

        return queryset.select_related('status')

    @cached_property
    def api(self):
        return self.get_object().get_api()

    @swagger_auto_schema(query_serializer=EndpointListFilterSerializer)
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    def retrieve(self, request, *args, **kwargs):
        endpoint = self.get_object()
        endpoint.set_status(ts_last_opened=now())
        serializer = self.get_serializer(endpoint)
        return Response(serializer.data)

    @lock_license('epm:endpoint')
    def create(self, request, *args, **kwargs):
        license_validate_add('epm:endpoint')
        return super().create(request, *args, **kwargs)

    @action(detail=False, methods=['GET'])
    def incoming(self, request):
        return self.list(request)

    @action(detail=False, methods=['POST'])
    @swagger_auto_schema(request_body=EndpointSerializer(many=True), responses={200: EndpointSerializer(many=True)})
    def bulk_create(self, request):

        serializer = EndpointSerializer(data=request.data, many=True, context=self.get_serializer_context())
        serializer.is_valid(raise_exception=True)

        with lock_license('epm:endpoint'):
            license_validate_add('epm:endpoint', len(serializer.validated_data))
            self._save_bulk_create(serializer)

        return Response(serializer.data, status=201)

    def _save_bulk_create(self, serializer: EndpointSerializer):
        instances = serializer.save(customer=self._get_customer())

        update_queue = []
        for endpoint in instances:
            EndpointProvision.objects.log(endpoint, 'create', self.request.user)
            if endpoint.has_direct_connection:
                update_queue.append(endpoint.pk)

        if update_queue:
            from . import tasks
            tasks.update_all_data.delay(update_queue)

    @action(detail=False, methods=['PUT', 'PATCH'])
    @swagger_auto_schema(request_body=EndpointUpdateSerializer(many=True, partial=True), responses={201: EndpointSerializer(many=True)})
    def bulk_update(self, request):

        update_serializer = EndpointUpdateSerializer(data=request.data, partial=request.method == "PATCH",
                                                     context=self.get_serializer_context())

        update_serializer.is_valid(raise_exception=True)

        endpoint_ids = update_serializer.validated_data.pop('endpoints')

        endpoints = self.get_queryset().filter(pk__in=endpoint_ids)
        endpoints.update(**update_serializer.validated_data)

        if update_serializer.validated_data.get('password'):
            from endpoint.tasks import update_all_data
            update_all_data.delay(list(endpoints.values_list('id', flat=True)))

        serializer = EndpointSerializer(endpoints, many=True, context=self.get_serializer_context())

        return Response(serializer.data, status=201)

    @action(detail=False, methods=['DELETE', 'POST'])
    @swagger_auto_schema(request_body=EndpointBulkUpdateSerializer(many=True, partial=True), responses={})
    def bulk_delete(self, request):

        endpoints = self.get_queryset().filter(pk__in=request.data.get('endpoints', ()))
        deleted = list(endpoints.values_list('id', flat=True))

        endpoints.delete()

        return Response({'deleted': deleted}, status=204)

    @action(detail=False, methods=['POST'])
    @swagger_auto_schema(request_body=ReportBodySerializer, responses={200: ReportSerializer})
    def report(self, request):
        import concurrent.futures

        serializer = ReportBodySerializer(data=request.data, context=self.get_serializer_context())
        serializer.is_valid(raise_exception=True)

        result = {}

        from .ext_api.cisco_ce import CiscoCEProviderAPI

        def _get_data(api: 'CiscoCEProviderAPI'):
            try:
                return api.endpoint, api.get_status_data()
            except Exception as e:
                return api.endpoint, e

        endpoints = self.get_queryset().filter(pk__in=request.data['endpoints'])
        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
            for endpoint, status in executor.map(_get_data, [e.get_api() for e in endpoints]):
                if isinstance(status, Exception):
                    if settings.TEST_MODE:
                        raise status
                else:
                    for value in request.data['values']:
                        result.setdefault(endpoint.id, {})['/'.join(value)] = status.findtext(
                            '/'.join(value)
                        )

        return Response(result)

    @action(detail=True, methods=['GET'])
    @swagger_auto_schema(
        request_body=None,
        query_serializer=StatusUpSerializer,
        responses={200: StatusUpResponseSerializer},
    )
    def is_up(self, request, pk=None):
        endpoint = self.get_object()

        serializer = StatusUpSerializer(
            data=request.query_params, context=self.get_serializer_context()
        )
        serializer.is_valid(raise_exception=True)

        if endpoint.status.has_warnings or endpoint.status.status == Endpoint.STATUS.UNKNOWN:
            return Response(
                {'status': 'WARNING'}, status=serializer.validated_data.get('warnings_code') or 200
            )

        if endpoint.status.status >= 1:
            return Response({'status': 'OK'})

        return Response(
            {
                'status': 'ERROR',
            },
            status=serializer.validated_data.get('error_code') or 200,
        )

    @action(detail=False, methods=['GET', 'POST'])
    @swagger_auto_schema(request_body=None)
    def export(self, request):

        if request.method == "GET":
            request.data['endpoints'] = [e for x in request.GET.getlist('endpoints') for e in x.split(',')]
        serializer = EndpointExcelExportSerializer(data=request.data, context=self.get_serializer_context())

        serializer.is_valid(raise_exception=True)

        response = HttpResponse(serializer.validated_data['fd'])
        response['Content-Type'] = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        response['Content-Disposition'] = 'attachment; filename="{}"'.format(serializer.validated_data['filename'])
        return response

    @action(detail=False, methods=['POST'])
    @swagger_auto_schema(request_body=ProvisionBodySerializer, responses={200: BasicResponseSerializer})
    def provision(self, request):

        serializer = ProvisionBodySerializer(data=request.data, context=self.get_serializer_context())
        serializer.is_valid(raise_exception=True)

        endpoints = self.get_queryset().filter(pk__in=request.data['endpoints'])
        provision, result = _provision(self.request.user, self._get_customer(), request.data, endpoints)
        return Response({'status': 'OK', 'id': provision.pk})

    @action(detail=False, methods=['POST'])
    def parse_xapi(self, request):

        text = request.data.get('input', '')
        try:
            return Response(XAPICommandParser(text).parse())
        except ValueError as e:
            return Response({'error': str(e)}, status=400)

    @action(detail=False)
    @swagger_auto_schema(responses={200: FilterBodySerializer})
    def filters(self, request):

        result = {
            'manufacturer': self.get_queryset().distinct().values_list('manufacturer', flat=True),
            'product_name': self.get_queryset().distinct().values_list('product_name', flat=True),
            'firmware': self.get_queryset().distinct().values_list('status__software_version', flat=True),
            'location': self.get_queryset().distinct().values_list('location', flat=True),
        }
        return Response(result)

    @action(detail=True)
    @swagger_auto_schema(
        responses={200: EndpointStatusSerializer}, query_serializer=EndpointStatusFlagSerializer()
    )
    def status(self, request, pk=None):
        if self.get_object().is_incoming:
            data = {'status': -10}
        else:
            allow_cached = request.GET.get('cached')
            if allow_cached and allow_cached not in ('false', '0'):
                cached_file = self.api.get_cached_status_data_file(age=7 * 24 * 60 * 60)
                if allow_cached == 'force' and not cached_file:
                    return Response({'message': 'No cached version exists'}, status=404)
                status_data = self.api.get_status_data(fd=cached_file)
            else:
                status_data = None
            data = self.get_object().update_status(raise_exceptions=False, status_data=status_data)

        return Response(data)

    @action(detail=True)
    @swagger_auto_schema(responses={200: MeetingSerializer})
    def active_meeting_details(self, request, pk=None):
        if not self.get_object().status.active_meeting:
            return Response({'message': _('Har inget aktivt möte')}, status=404)

        data = MeetingSerializer(self.get_object().status.active_meeting.meeting).data

        return Response(data)

    @action(detail=True, methods=['POST'])
    @swagger_auto_schema(request_body=CallControlSerializer, responses={200: CallControlResponseSerializer})
    def call_control(self, request, pk=None):

        serializer = CallControlSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=400)

        try:
            result = self.api.call_control(serializer.validated_data['action'],
                                                              serializer.validated_data['argument'])
        except ResponseConnectionError as e:
            return Response({
                'message': str(e),
            }, status=503)
        except (AuthenticationError, ResponseError) as e:
            return Response({
                'message': str(e),
            }, status=400)
        except Exception as e:
            if settings.DEBUG or settings.TEST_MODE:
                raise
            capture_exception()
            return Response({
                'message': str(e),
            }, status=500)

        return Response({
            'result': result,
            'status': self.api.get_status(),
        })

    @action(detail=True)
    @swagger_auto_schema(responses={200: None}, query_serializer=EndpointStatusFlagSerializer())
    def status_data(self, request, pk=None):
        try:
            fd = None
            if request.GET.get('cached') not in ('false', '0', None, ''):
                fd = self.api.get_cached_status_data_file(age=7 * 24 * 60 * 60)
                if not fd and request.GET.get('cached') == 'force':
                    return Response({'error': 'No cached file exists'}, status=404)
            if not fd:
                fd = self.api.get_status_data_file()
            data = self.api.get_status_data(fd=fd)
        except (AuthenticationError, ResponseError) as e:
            return Response({'error': str(e)}, status=503)
        except Exception as e:
            if not settings.DEBUG:
                capture_exception()
            return Response({'error': str(e)}, status=500)
        else:
            return Response(
                {'data': data.tuple_items(), 'age': (now() - fd.ts_update).total_seconds()}
            )

    @action(detail=True)
    @swagger_auto_schema(responses={200: None})
    def head_count(self, request, pk=None):
        from room_analytics import graph

        endpoint = self.get_object()

        try:
            hours = min(int(request.GET.get('hours', 48)), 48)
        except ValueError:
            hours = 48

        latest_ts = EndpointHeadCount.objects.filter(endpoint=endpoint).order_by('-ts').values_list('ts', flat=True).first()
        if not latest_ts:
            return Response({})

        return Response({
            'count': graph.get_head_count_graph([endpoint], latest_ts - timedelta(hours=hours), latest_ts, as_json=True),
        })

    @action(detail=True)
    @swagger_auto_schema(responses={200: None})
    def dial_info(self, request, pk=None):

        try:
            data = self.api.get_dial_info()
        except (AuthenticationError, ResponseError):
            pass
        else:
            return Response(data)

        return Response({}, status=503)

    @action(detail=True)
    @swagger_auto_schema(responses={200: None})  # TODO serializer docs
    def provision_status(self, request, pk=None):

        try:
            configuration = self.api.get_configuration_data()
            status = self.api.get_status_data()
        except (AuthenticationError, ResponseError):
            return Response({}, status=503)

        result = {
            'dial_settings': self.api.get_dial_info(configuration_data=configuration),
            'addressbook': self.api.get_addressbook_status(configuration_data=configuration),
            'passive': self.api.get_passive_status(configuration_data=configuration),
            'event': self.api.check_events_status(status_data=status),
            'analytics': self.api.get_analytics_status(configuration_data=configuration),
        }
        return Response(result)

    @action(detail=False)
    @swagger_auto_schema(responses={200: EndpointBookingsSerializer(many=True)})
    def all_bookings(self, request):

        meetings = Meeting.objects.get_active().filter(endpoints__isnull=False, customer=self._get_customer())
        data = EndpointBookingsSerializer(meetings, many=True).data

        return Response(data)

    @action(detail=True)
    @swagger_auto_schema(responses={200: EndpointBookingsSerializer(many=True)})
    def bookings(self, request, pk=None):
        data = EndpointBookingsSerializer(self.get_object().get_bookings(), many=True).data

        return Response(data)

    @action(detail=True)
    @swagger_auto_schema(responses={200: EndpointLegSerializer(many=True)})
    def calls(self, request, pk=None):
        from statistics.models import Leg, Server

        server = Server.objects.get_endpoint_server(self.get_object().customer)
        qs = Leg.objects \
            .filter(server=server, ts_start__gte=now() - timedelta(days=7), endpoint=self.get_object()) \
            .values('ts_start', 'ts_stop', 'local', 'remote', 'guid', 'call__guid') \
            .order_by('-ts_start')[:10]

        return Response(EndpointLegSerializer(qs, many=True).data)

    @action(detail=True, methods=['POST'])
    @swagger_auto_schema(request_body=SipAliasSerializer)
    def set_sip_aliases(self, request, pk=None):

        SipAliasSerializer(data=request.data, context=self.get_serializer_context()).is_valid(raise_exception=True)

        endpoint = self.get_object()

        sips = request.data.getlist('sip') if hasattr(request.data, 'getlist') else request.data.get('sip') or ()
        if isinstance(sips, str):
            sips = [sips]

        for sip in sips:
            EndpointSIPAlias.objects.get_or_create(endpoint=endpoint, sip=sip)
        EndpointSIPAlias.objects.filter(endpoint=endpoint).exclude(sip__in=sips).delete()

        return Response(self.get_serializer(endpoint).data)

    @action(detail=True)
    @swagger_auto_schema(responses={200: None})
    def call_history(self, request, pk=None):
        try:
            data = self.api.get_call_history()
        except ResponseConnectionError:
            data = []
        except (AuthenticationError, ResponseError) as e:
            return Response({'error': str(e)}, status=503)

        return Response(data)

    @action(detail=True, url_path='call_debug/(?P<history_id>[^/.]+)')
    @swagger_auto_schema(responses={200: None})
    def call_debug(self, request, pk=None, history_id=None):
        from xml.etree import ElementTree as ET

        try:
            node = self.api.get_call_history_data(history_id or '')
            data = ET.tostring(node)
        except NotFound:
            raise Http404()
        except ResponseConnectionError:
            data = {}

        return Response({'content': data})

    @action(detail=True)
    @swagger_auto_schema(responses={200: None}, query_serializer=EndpointStatusFlagSerializer())
    def configuration_data(self, request, pk=None):
        try:
            fd = None
            if request.GET.get('cached') not in ('false', '0', None, ''):
                fd = self.api.get_cached_configuration_data_file(age=7 * 24 * 60 * 60)
                if not fd and request.GET.get('cached') == 'force':
                    return Response({'error': 'No cached file exists'}, status=404)
            if not fd:
                fd = self.api.get_configuration_data_file()
            data = self.api.get_configuration_data(fd=fd, require_valuespace=True).tuple_items()
        except AuthenticationError as e:
            return Response({'error': str(e) or 'Authentication failed'}, status=400)
        except (AuthenticationError, ResponseError) as e:
            return Response({'error': str(e)}, status=503)
        else:
            return Response({'data': data, 'age': (now() - fd.ts_update).total_seconds()})

    @action(detail=True)
    @swagger_auto_schema(responses={200: None})
    def valuespace_data(self, request, pk=None):
        try:
            data = self.api.get_valuespace_data()
        except AuthenticationError as e:
            return Response({'error': str(e) or 'Authentication failed'}, status=400)
        except (AuthenticationError, ResponseError) as e:
            return Response({'error': str(e)}, status=503)
        else:
            return Response(data)

    @action(detail=True)
    @swagger_auto_schema(responses={200: None})
    def commands_data(self, request, pk=None):
        try:
            fd, valuespace = self.api.get_commands_data_file()
            data = self.api.get_commands_data(fd=fd, valuespace=valuespace).tuple_items()
        except (AuthenticationError, ResponseError) as e:
            return Response({'error': str(e)}, status=503)
        else:
            return Response({'data': data, 'age': (now() - fd.ts_update).total_seconds()})

    @commands_data.mapping.post
    @swagger_auto_schema(request_body=EndpointCommandsFileSerializer)
    def set_commands_data(self, request, pk=None):
        try:
            EndpointCommandsFileSerializer(data=request.data).is_valid(raise_exception=True)
            valuespace_data = request.data['valuespace'].read()
            command_data = request.data['command'].read()
        except (KeyError, AttributeError):
            raise Response(
                {'valuespace': ['Field is required'], 'command': ['Field is required']}, status=400
            )

        try:
            from endpoint.ext_api.parser import cisco_ce

            valuespace = cisco_ce.ValueSpaceParser(safe_xml_fromstring(valuespace_data)).parse()
            cisco_ce.CommandParser(safe_xml_fromstring(command_data), valuespace).parse()
        except Exception as e:
            return Response(
                {'valuespace': 'Could not parse file: {}'.format(format_exception(e))}, status=400
            )

        from endpoint_data.models import EndpointCurrentState
        EndpointCurrentState.objects.store(
            self.get_object(), command=command_data, valuespace=valuespace_data
        )
        return self.commands_data(request, pk=pk)

    def _run_task(self, **kwargs):
        task, result = EndpointProvision.objects.run_single(self._get_customer(), self.get_object(), self.request.user, **kwargs)
        return result

    def _delay_task(self, constraint=None, **kwargs):
        if constraint == 'night':
            kwargs['constraint'] = EndpointProvision.NIGHT
        return EndpointProvision.objects.provision(self._get_customer(), self.get_object(), self.request.user, **kwargs)

    @action(detail=True, methods=['POST'])
    @swagger_auto_schema(request_body=EmptyBodySerializer, responses={200: BasicResponseSerializer})
    def backup(self, request, pk=None):

        self._run_task(backup=True)

        return Response({'status': 'OK'})

    @action(detail=True, methods=['POST'])
    @swagger_auto_schema(request_body=InstallFirmwareSerializer, responses={200: BasicResponseSerializer})
    def install_firmware(self, request, pk=None):

        serializer = InstallFirmwareSerializer(data=request.data, context=self.get_serializer_context())
        serializer.is_valid(raise_exception=True)

        self._delay_task(firmware=serializer.validated_data['firmware'], constraint=serializer.validated_data.get('constraint'))

        return Response({'status': 'OK', 'message': 'Running in background'})

    @action(detail=True, methods=['POST'])
    @swagger_auto_schema(request_body=RunCommandSerializer, responses={200: ResponseSerializer})
    def run_command(self, request, pk=None):

        serializer = RunCommandSerializer(data=request.data, context=self.get_serializer_context())
        serializer.is_valid(raise_exception=True)

        try:
            data = self._run_task(commands=[serializer.validated_data])
        except ResponseConnectionError as e:
            return Response(
                {
                    'response': str(e),
                    'error': '{}. The command has been added to the queue and will be run the next time the system is online'.format(
                        e
                    ),
                },
                status=400,
            )
        except ResponseError as e:
            return Response({'response': str(e), 'error': str(e)}, status=400)

        if isinstance(data, list) and data:
            data = data[0]
        return Response({'response': data})

    @action(detail=True, methods=['POST'])
    @swagger_auto_schema(request_body=EndpointSetConfigurationSerializer, responses={200: ResponseSerializer})
    def set_configuration(self, request, pk=None):

        serializer = EndpointSetConfigurationSerializer(data=request.data, context=self.get_serializer_context())
        serializer.is_valid(raise_exception=True)

        try:
            data = self._run_task(configuration=request.data['settings'])
        except ResponseError as e:
            return Response({'response': str(e), 'error': str(e)}, status=400)
        return Response({'response': data})

    def perform_create(self, serializer):

        from rest_framework.exceptions import ValidationError
        password = serializer.validated_data.get('password') or ''
        if not password and serializer.instance:
            password = serializer.instance.password
        endpoint = serializer.save(password=password,
                                   customer=get_customer_from_request(self.request))

        try:
            if endpoint.has_direct_connection:
                endpoint.update_all_data()
            EndpointProvision.objects.log(endpoint, 'create', self.request.user)

        except (ResponseError, AuthenticationError) as e:
            EndpointProvision.objects.log(endpoint, 'create', self.request.user, error=True,
                                          result='Failed: {}'.format(str(e) or str(e.__class__.__name__)))
            if serializer.validated_data.get('validate_connection'):
                if isinstance(e, AuthenticationError):
                    raise ValidationError({'username': 'Authentication failed: {}'.format(e).rstrip(' :')})
                raise ValidationError({'ip': 'Could not connect to system: {}'.format(e)})

    def perform_update(self, serializer):

        from rest_framework.exceptions import ValidationError

        try:
            password = serializer.validated_data.get('password') or ''
            if not password and serializer.instance:
                password = serializer.instance.password

            endpoint = serializer.save(password=password)
            if endpoint.has_direct_connection:
                endpoint.update_all_data()
            EndpointProvision.objects.log(serializer.instance, 'update', self.request.user)
            return endpoint
        except (ResponseError, AuthenticationError) as e:
            EndpointProvision.objects.log(serializer.instance, 'update', self.request.user, error=True,
                                          result='Failed: {}'.format(str(e) or str(e.__class__.__name__)))

            if serializer.validated_data.get('validate_connection'):
                if isinstance(e, AuthenticationError):
                    raise ValidationError({'username': 'Authentication failed: {}'.format(e).rstrip(' :')})
                raise ValidationError({'ip': 'Could not connect to system: {}'.format(e)})

    def perform_destroy(self, instance):

        message = 'ID: {}, Name: {}, IP: {}'.format(instance.pk, instance, instance.ip)
        EndpointProvision.objects.log(instance, 'delete', self.request.user,
                                      result=message)
        instance.delete()


class CustomerSettingsViewSet(CustomerRelationMixin, viewsets.ModelViewSet):

    queryset = CustomerSettings.objects.all()
    serializer_class = CustomerSettingsSerializer

    def check_permissions(self, request):
        super().check_permissions(request)

        not_allowed = {'passwords'}

        if not request.user.is_staff and (request.method != 'GET' or self.action in not_allowed):
            self.permission_denied(
                request,
                message='Only admin may change settings',
            )

    def list(self, request, *args, **kwargs):
        return self.retrieve(request, *args, **kwargs)

    def get_object(self):
        return CustomerSettings.objects.get_for_customer(self._get_customer())

    create = NotImplemented

    def perform_update(self, serializer):

        serializer.save()
        if 'ip_nets' in serializer.validated_data:
            self._set_ip_nets(serializer.validated_data['ip_nets'])
        if 'domains' in serializer.validated_data:
            self._set_domains(serializer.validated_data['domains'])
        if 'passwords' in serializer.validated_data:
            self._set_passwords(serializer.validated_data['passwords'])

    @action(detail=False, methods=['GET'])
    @swagger_auto_schema(responses={200: PasswordsResponseSerializer(many=True)})
    def passwords(self, request, pk=None):
        passwords = CustomerDefaultPassword.objects.filter(customer=self._get_customer())
        return Response(passwords.values('index', 'password'))

    @action(detail=False, methods=['POST'])
    @swagger_auto_schema(request_body=SetPasswordsSerializer, responses={200: PasswordsResponseSerializer(many=True)})
    def set_passwords(self, request, pk=None):
        SetPasswordsSerializer(data=request.data, context=self.get_serializer_context()).is_valid(raise_exception=True)
        self._set_passwords(request.data.get('passwords') or [])
        return self.passwords(request)

    def _set_passwords(self, passwords):

        customer = self._get_customer()
        i = -1
        for i, password in enumerate(passwords):
            CustomerDefaultPassword.objects.update_or_create(customer=customer, index=i, password=password)

        CustomerDefaultPassword.objects.filter(customer=customer, index__gt=i).delete()

    @action(detail=False, methods=['GET'])
    @swagger_auto_schema(responses={200: CustomerDomainsResponseSerializer(many=True)})
    def domains(self, request, pk=None):
        domains = CustomerDomain.objects.filter(customer=self._get_customer())
        return Response(domains.values('domain'))

    @action(detail=False, methods=['POST'])
    @swagger_auto_schema(request_body=SetCustomerDomainsSerializer, responses={200: CustomerDomainsResponseSerializer(many=True)})
    def set_domains(self, request, pk=None):
        self._set_domains(request.data.get('domains', []))
        return self.domains(request)

    def _set_domains(self, domains):

        customer = self._get_customer()

        valid = set()
        for domain in domains:
            obj = CustomerDomain.objects.get_or_create(customer=customer, domain=domain)[0]
            valid.add(obj.pk)

        CustomerDomain.objects.filter(customer=customer).exclude(pk__in=valid).delete()

    @action(detail=False, methods=['GET'])
    @swagger_auto_schema(responses={200: IpNetResponseSerializer(many=True)})
    def ip_nets(self, request, pk=None):
        ip_nets = CustomerAutoRegisterIpNet.objects.filter(customer=self._get_customer())
        return Response(ip_nets.values('index', 'ip_net'))

    @action(detail=False, methods=['POST'])
    @swagger_auto_schema(request_body=SetIpNetSerializer, responses={200: IpNetResponseSerializer(many=True)})
    def set_ip_nets(self, request, pk=None):
        SetIpNetSerializer(data=request.data, context=self.get_serializer_context()).is_valid(raise_exception=True)
        self._set_ip_nets(request.data.get('ip_nets') or [])
        return self.ip_nets(request)

    def _set_ip_nets(self, ip_nets):

        customer = self._get_customer()
        i = -1
        for ip_net in ip_nets:

            try:
                ip = IPv4Interface(ip_net.replace('*.*', '.0.0/20').replace('.*', '.0/24'))
            except ValueError:
                continue

            i += 1

            CustomerAutoRegisterIpNet.objects.update_or_create(customer=customer, index=i, defaults=dict(ip_net=ip.network))

        CustomerAutoRegisterIpNet.objects.filter(customer=customer, index__gt=i).delete()



