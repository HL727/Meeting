import secrets
from typing import Any, Dict

from django.db.models import Q
from django.http import FileResponse
from django.utils.dateparse import parse_datetime
from drf_yasg.utils import swagger_auto_schema
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from endpoint.ext_api.cisco_ce import CiscoCEProviderAPI
from endpoint.ext_api.parser.xapi import XAPICommandParser
from endpoint.models import CustomerDefaultPassword
from endpoint.view_mixins import CustomerRelationMixin
from endpoint_branding.models import EndpointBrandingProfile
from endpoint_provision.docs import EndpointTaskListFilterSerializer
from endpoint_provision.models import (
    EndpointFirmware,
    EndpointProvision,
    EndpointTask,
    EndpointTemplate,
)
from endpoint_provision.serializers import (
    EndpointFirmwareCopySerializer,
    EndpointFirmwareSerializer,
    EndpointTaskListSerializer,
    EndpointTaskSerializer,
    EndpointTemplateSerializer,
)


class EndpointFirmwareViewSet(CustomerRelationMixin, viewsets.ModelViewSet):

    serializer_class = EndpointFirmwareSerializer
    queryset = EndpointFirmware.objects.all()

    def get_global_queryset(self):
        return EndpointFirmware.objects.filter(Q(customer=self._get_customer()) | Q(is_global=True))

    def get_queryset(self):
        if self.action in ('list', 'download', 'retrieve') or self.request.user.is_staff:
            return self.get_global_queryset()
        return super().get_queryset().filter(customer=self._get_customer())

    @action(detail=True)
    def download(self, request, pk=None):
        response = FileResponse(self.get_object().file)
        response['Content-Disposition'] = 'attachment; filename={}'.format(self.get_object().orig_file_name)
        return response

    @swagger_auto_schema(
        request_body=EndpointFirmwareCopySerializer,
        responses={200: EndpointTaskListSerializer(many=True)},
    )
    @action(detail=True, methods=['POST'])
    def copy(self, request, pk=None):
        serializer = EndpointFirmwareCopySerializer(
            data=request.data, context=self.get_serializer_context()
        )
        serializer.is_valid(raise_exception=True)

        obj = self.get_object()

        result = []
        for model in serializer.validated_data['models']:
            if self.get_global_queryset().filter(version=obj.version, model=model):
                continue
            cur = obj.copy(
                customer=self._get_customer(),
                model=model,
                is_global=bool(serializer.validated_data.get('is_global')),
            )
            result.append(cur)

        return Response(self.get_serializer(result, many=True).data)

    def perform_create(self, serializer):
        serializer.save(customer=self._get_customer(),
                        orig_file_name=serializer.validated_data['file'].name)


class EndpointTemplateViewSet(CustomerRelationMixin, viewsets.ModelViewSet):

    serializer_class = EndpointTemplateSerializer
    queryset = EndpointTemplate.objects.all()


class EndpointTaskViewSet(CustomerRelationMixin, viewsets.ReadOnlyModelViewSet):

    serializer_class = EndpointTaskListSerializer
    queryset = EndpointTask.objects.all().order_by('-ts_created').select_related('endpoint')

    def get_serializer_class(self):
        if self.action == 'retrieve':
            return EndpointTaskSerializer
        return self.serializer_class

    @swagger_auto_schema(query_serializer=EndpointTaskListFilterSerializer, responses={200: EndpointTaskListSerializer(many=True)})
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    @swagger_auto_schema(query_serializer=EndpointTaskListFilterSerializer, responses={200: EndpointTaskListSerializer(many=True)})
    @action(detail=False, methods=['GET'])
    def latest(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    def get_queryset(self):
        queryset = super().get_queryset()
        if self.request.GET.get('endpoint'):
            queryset = queryset.filter(endpoint=self.request.GET.get('endpoint'))
        if self.request.GET.get('provision'):
            queryset = queryset.filter(provision=self.request.GET.get('provision'))
        if self.request.GET.get('changed_since'):
            queryset = queryset.filter(ts_last_change__gte=self.request.GET.get('changed_since'))
        if self.request.GET.get('status'):
            queryset = queryset.filter(status=self.request.GET.get('status'))
        if self.request.GET.get('order_by') == 'change':
            queryset = queryset.order_by('-ts_last_change')
        if self.action in ('list', 'latest'):
            return queryset[:500]  # todo pagination
        return queryset

    @action(detail=True, methods=['POST'])
    @swagger_auto_schema(responses={200: EndpointTaskListSerializer(many=True)})
    def cancel(self, request, pk):
        obj = self.get_object()
        try:
            obj.cancel()
        except ValueError as e:
            return Response({'error': str(e)}, status=400)

        return Response(EndpointTaskSerializer(obj, context=self.get_serializer_context()).data)

    @action(detail=True, methods=['POST'])
    @swagger_auto_schema(responses={200: EndpointTaskListSerializer(many=True)})
    def retry(self, request, pk):
        obj = self.get_object()
        try:
            obj.retry()
        except ValueError as e:
            return Response({'error': str(e)}, status=400)
        return Response(EndpointTaskSerializer(obj, context=self.get_serializer_context()).data)


class TempTask:
    id = None
    api = None
    result = ''


def _provision(user, customer, data, endpoints):

    result = {}
    configuration = []
    commands = []
    constraint = None
    extra_properties: Dict[str, Dict[str, Any]] = {}

    if data.get('constraint') == 'night':
        constraint = EndpointProvision.NIGHT

    if data.get('repeat'):
        extra_properties['repeat'] = {'enable': True}

    if data.get('schedule'):
        extra_properties['schedule'] = {'ts': parse_datetime(data['schedule'])}

    def _get_instance(model, pk, allow_global=False):
        "support both raw pk values and serializer loaded instances"
        if isinstance(pk, model):
            return pk
        customer_cond = Q(customer=customer)
        if allow_global:
            customer_cond |= Q(is_global=True)
        return model.objects.get(customer_cond, pk=pk)

    def _get_many_instances(model, pks):
        return [_get_instance(model, pk) for pk in pks]

    if data.get('addressbook'):
        from address.models import AddressBook
        address_book = _get_instance(AddressBook, data['addressbook'])
        result['address_book'] = address_book

    if data.get('firmware'):
        firmware = _get_instance(EndpointFirmware, data['firmware'], allow_global=True)
        result['firmware'] = firmware

    if data.get('statistics'):
        result['statistics'] = True

    if data.get('passive'):
        result['passive'] = True
        if data.get('passive_chain'):
            extra_properties.setdefault('passive', {})['chain'] = True

    if data.get('clear_room_controls'):
        result['clear_room_controls'] = True

    if data.get('room_controls_delete_operation'):
        result['room_controls_delete_operation'] = True

    if data.get('room_controls'):
        from roomcontrol.models import RoomControl
        result['room_controls'] = ','.join(str(obj.pk) for obj in _get_many_instances(RoomControl, data['room_controls']))

    if data.get('room_control_templates'):
        from roomcontrol.models import RoomControlTemplate
        result['room_control_templates'] = ','.join(str(obj.pk) for obj in _get_many_instances(RoomControlTemplate, data['room_control_templates']))

    if data.get('configuration'):
        configuration.extend(data.get('configuration') or [])

    if data.get('template'):
        from endpoint_provision.models import EndpointTemplate
        result['template'] = _get_instance(EndpointTemplate, data['template'])

    if data.get('branding_profile'):
        result['branding_profile'] = _get_instance(EndpointBrandingProfile, data['branding_profile'])

    if data.get('head_count') is not None:
        result['room_analytics'] = True
        extra_properties.setdefault('room_analytics', {})['head_count'] = bool(data['head_count'])

    if data.get('presence') is not None:
        result['room_analytics'] = True
        extra_properties.setdefault('room_analytics', {})['presence'] = bool(data['presence'])

    if result.get('room_analytics'):  # disable bulk provision for personal room analytics
        if len(endpoints) == 1 and 'allow_personal_room_analytics' not in data:
            extra_properties.setdefault('room_analytics', {})['allow_personal'] = True
        elif data.get('allow_personal_room_analytics'):
            extra_properties.setdefault('room_analytics', {})['allow_personal'] = True

    if data.get('ca_certificates'):
        result['ca_certificates'] = True

    if data.get('dial_info'):
        dial_info = data['dial_info']
        if len(endpoints) == 1:
            for endpoint in endpoints:
                endpoint.get_api().save_dial_info(dial_info)

        versions = set(e.status.software_version for e in endpoints)

        if dial_info.get('sip_proxy_password'):
            dial_info['sip_proxy_password'] = CiscoCEProviderAPI._get_sip_proxy_password(
                dial_info['sip_proxy_password'], customer, dial_info
            )

        if dial_info.get('current'):
            result['dial_info'] = dial_info
        else:
            configuration.extend(
                CiscoCEProviderAPI.get_update_dial_info_configuration(dial_info, customer, versions)
            )

        if dial_info.get('register') and customer.get_api().cluster.is_pexip:
            from endpoint.tasks import register_devices

            register_devices.delay([e.pk for e in endpoints], dial_info)

    if data.get('set_password'):

        if data.get('current_password'):
            extra_properties.setdefault('password', {})['validate_current_password'] = data[
                'current_password'
            ]

        if data.get('standard_password'):
            password = CustomerDefaultPassword.objects.filter(
                customer=customer
            ).values_list('password', flat=True).first()
        else:
            password = data.get('password')

        if password == '__generated__':
            result['password'] = secrets.token_urlsafe(8)
        if password:
            result['password'] = password

    if data.get('events'):
        result['events'] = True

    if data.get('commands'):
        commands.extend(data['commands'])

    if data.get('xapi_text'):
        parsed = XAPICommandParser(data['xapi_text']).parse()
        commands.extend(parsed.get('commands') or [])
        configuration.extend(parsed.get('configuration') or [])

    if configuration:
        result['configuration'] = configuration

    if extra_properties:
        result['extra_properties'] = extra_properties

    if commands:
        result['commands'] = commands

    if data.get('delay'):
        result['delay'] = True

    provision, result = EndpointProvision.objects.provision(customer=customer, endpoints=endpoints,
                                                            user=user, constraint=constraint, **result)
    return provision, result
