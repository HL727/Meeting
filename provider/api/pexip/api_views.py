from datetime import timedelta

from django.conf import settings
from django.http import Http404, JsonResponse
from django.utils.timezone import now
from django.utils.translation import gettext as _
from drf_yasg.utils import swagger_auto_schema
from sentry_sdk import capture_exception
from rest_framework import viewsets, mixins
from rest_framework.decorators import action
from rest_framework.response import Response

from datastore.models.pexip import Conference, EndUser
from endpoint.view_mixins import CustomerRelationMixin
from license.api_helpers import license_validate_add
from numberseries.models import NumberRangeDummy
from provider.api.generic.mixins import DynamicAPIMixin
from provider.api.pexip.serializers import ConferenceSerializer, ConferenceUpdateSerializer, \
    ConferenceBulkCreateSerializer, EndUserSerializer, UpdateEndUserSerializer

from provider.exceptions import ResponseError, NotFound, DuplicateError, MessageResponseError
from customer.view_mixins import CustomerAPIMixin
from provider.ext_api.pexip import PexipAPI
from provider.models.pexip import PexipEndUser
from shared.utils import partial_update_or_create, get_changed_fields


class ConferenceViewSet(DynamicAPIMixin, CustomerAPIMixin, viewsets.GenericViewSet):

    serializer_class = ConferenceSerializer
    queryset = Conference.objects.none()

    def _get_api(self, force_reload=False, allow_cached_values=True) -> PexipAPI:
        api = super()._get_api(force_reload=force_reload, allow_cached_values=allow_cached_values)
        assert isinstance(api, PexipAPI)
        return api

    def dispatch(self, request, *args, **kwargs):
        try:
            provider = self._get_customer().get_provider()
            if not provider.is_pexip:
                return JsonResponse({'error': 'Customer has no pexip connection'}, status=404)
        except AttributeError:  # not logged in
            pass
        return super().dispatch(request, *args, **kwargs)

    def get_object(self, pk=None, reload=None) -> Conference:

        api = self._get_api()

        pk = int(pk or self.kwargs['pk'])

        try:
            conference = Conference.objects.get_active(api.cluster, pk)
        except Conference.DoesNotExist:
            reload = True
            conference = None

        if reload:
            from datastore.utils.pexip import sync_single_conference_full
            conference = sync_single_conference_full(api, pk)

        if not conference:
            raise Http404()

        self._check_tenant_customer(conference.tenant.tid if conference.tenant_id else '')
        return conference

    def _handle_error(self, e):

        if isinstance(e.args[1], dict):
            errors = e.args[1]
        elif isinstance(e, DuplicateError):
            errors = {
                'aliases': _('Den angivna URIn används redan'),
            }
        elif isinstance(e, ResponseError) and e.get_all_errors():
            errors = e.get_all_errors()
        else:
            errors = {'error': 'Error'}  # TODO

        return {
            'status': 'error',
            'errors': errors
        }

    def _update_aliases(self, aliases_data):
        api = self._get_api()
        obj = self.get_object()

        result = []
        valid = True

        aliases_data = list(aliases_data)

        existing = {a['id']: a for a in obj.to_dict()['aliases']}
        keep = {a['id'] for a in aliases_data if a.get('id')}

        remove = [existing[aid] for aid in (set(existing) - keep)]
        remove_aliases = {r['alias']: r for r in remove}

        for alias_data in aliases_data:

            cur_id = alias_data.get('id')

            # try to update existing using alias value instead of remove + add
            if cur_id not in existing and alias_data['alias'] in remove_aliases:
                cur_id = remove_aliases.pop(alias_data['alias'])['id']

            if cur_id and cur_id in existing:  # update
                try:
                    if get_changed_fields(existing[cur_id], alias_data):
                        api.update_alias(cur_id, alias_data)
                except DuplicateError as e:
                    valid = False
                    result.append({'error': str(e)})
                    continue
                result.append(alias_data)
                continue

            try:
                api.add_alias({
                    'alias': alias_data['alias'],
                    'description': alias_data.get('description', ''),
                    'conference': obj.resource_uri,
                })
            except DuplicateError as e:
                valid = False
                result.append({'error': str(e)})
            else:
                result.append(alias_data)

        for alias in remove_aliases.values():
            api.delete_alias(alias['id'])

        return result, valid

    @action(detail=False, methods=['POST'])
    @swagger_auto_schema(request_body=ConferenceBulkCreateSerializer, responses={201: ConferenceBulkCreateSerializer})
    def bulk_create(self, request):

        serializer = ConferenceBulkCreateSerializer(data=request.data,
                                                    context=self.get_serializer_context())
        if not serializer.is_valid():
            return Response(data=serializer.errors, status=400)

        license_validate_add('core:enable_core')

        api = self._get_api()
        response = []

        conference_serializer = ConferenceSerializer(context=serializer.context)
        conference_serializer.parent = serializer

        generation_method = serializer.validated_data.get('call_id_generation_method')

        if serializer.validated_data.get('call_id_generation_method') == 'increase' and serializer.validated_data.get('start_call_id'):
            number_range = NumberRangeDummy(serializer.validated_data['start_call_id'])
        else:
            number_range = api.get_static_room_number_range()

        send_email = serializer.validated_data.get('send_email')

        has_valid = False

        for data in serializer.validated_data['conferences']:
            aliases = data.get('aliases') or []
            call_id = data.get('call_id')

            if call_id or (aliases and any(a['alias'].isdigit() for a in aliases)):
                pass
            elif generation_method == 'random':
                call_id = number_range
                data['random_call_id'] = True
            elif generation_method == 'increase':
                call_id = number_range

            api_data = {
                **data,
                'call_id': call_id,
                'aliases': [a for a in aliases if a.get('alias')],
                'tenant': api.customer.get_pexip_tenant_id(),
            }

            try:
                cospace_id = api.add_cospace(data=api_data, sync=False)
            except ResponseError as e:
                data.update(self._handle_error(e))
                response.append(data)
                continue

            has_valid = True

            if send_email and data.get('primary_owner_email_address'):
                from provider import tasks
                tasks.send_email_for_cospace.delay(api.customer.pk, cospace_id, emails=[data['primary_owner_email_address']])

            conference_serializer.save_organization(cospace_id, data)

            new_data = self.get_object(cospace_id, reload=True).to_dict()
            new_data['status'] = 'ok'
            response.append(new_data)

        if not has_valid:
            return Response({'conferences': response}, status=400)
        return Response({'conferences': response}, status=201)

    def delete(self, request, pk=None):

        obj = self.get_object()

        try:
            self._get_api().delete_cospace(obj.cid)
        except Exception as e:
            return self._error_response(e)

        return Response({'status': 'ok'}, status=200)

    def patch(self, request, pk=None):
        return self.update(request, pk=pk, partial=True)

    def get_serializer_context(self, **kwargs):
        if getattr(self, 'swagger_fake_view', False):
            return super().get_serializer_context()

        if kwargs.get('conference'):
            kwargs.setdefault('cluster', kwargs['conference'].provider)
        else:
            kwargs.setdefault('cluster', self._get_customer().get_api().cluster)

        return {
            'customer': self._get_customer(),
            'api': self._get_api(),
            **super().get_serializer_context(),
            **kwargs,
        }

    def update(self, request, pk=None, **kwargs):
        obj = self.get_object()

        serializer = ConferenceUpdateSerializer(data=request.data, partial=kwargs.pop('partial', False),
                                                context=self.get_serializer_context(conference=obj))
        if not serializer.is_valid():
            return Response(data=serializer.errors, status=400)

        api = self._get_api()

        data = serializer.validated_data.copy()

        aliases = data.pop('aliases', None)

        try:
            if data:
                api.update_cospace(obj.cid, serializer.get_api_data())
        except Exception as e:
            return self._error_response(e)

        if aliases is not None:
            result, valid = self._update_aliases(aliases)
            if not valid:
                return Response({'error': {'aliases': result}}, status=400)

        if 'organization_unit' in data or 'organization_path' in data:
            serializer.save_organization(obj.cid, data)

        return Response(self.get_object(reload=True).to_dict())

    def create(self, request, *args, **kwargs):
        serializer = ConferenceSerializer(data=request.data, context=self.get_serializer_context())
        if not serializer.is_valid():
            return Response(data=serializer.errors, status=400)

        license_validate_add('core:enable_core')

        api = self._get_api()

        data = serializer.validated_data.copy()

        number_range = api.get_static_room_number_range()

        if serializer.validated_data.get('call_id_generation_method') == 'random':
            data['random_call_id'] = True
            data['call_id'] = number_range
        elif serializer.validated_data.get('call_id_generation_method') == 'increase':
            data['call_id'] = number_range

        try:
            cospace_id = api.add_cospace({
                **data,
                'tenant': self._get_customer().get_pexip_tenant_id(),
            })
        except Exception as e:
            return self._error_response(e)

        if 'organization_unit' in data or 'organization_path' in data:
            serializer.save_organization(cospace_id, data)

        return Response(self.get_object(cospace_id, reload=True).to_dict(), status=201)

    def get_single_object_data(self, object):
        from meeting.models import Meeting
        from statistics.models import Call
        from meeting.serializers import MeetingSerializer
        from statistics.serializers import CallSerializer

        api = self._get_api()

        booked_meeting = Meeting.objects.filter(provider_ref2=object.cid).order_by('-ts_created').first()

        all_calls = Call.objects.filter(cospace=object.name, server__cluster=api.cluster,
                                        ts_start__gt=now() - timedelta(days=14)).order_by('-ts_start')

        todays_calls = all_calls.filter(ts_start__gte=now().replace(hour=0, minute=0))
        latest_calls = todays_calls[:10] if todays_calls.count() >= 3 else all_calls[:3]

        return {
            'ongoing_calls': api.get_clustered_calls(cospace=object.name, include_legs=False)[0],
            'booked_meeting': MeetingSerializer(booked_meeting).data if booked_meeting else None,
            'latest_calls': CallSerializer(latest_calls, many=True).data if latest_calls else [],
        }

    def retrieve(self, request, pk=None):

        object = self.get_object()

        try:
            extra_context = self.get_single_object_data(object)
        except Exception:
            if settings.TEST_MODE:
                raise
            capture_exception()
            extra_context = {}

        return Response({
            **object.to_dict(),
            'members': object.get_members(),
            **extra_context,
        })

    def _error_response(self, exception):
        try:
            raise exception
        except NotFound as e:
            return Response(data={
                'status': 'error',
                'error': str(e)
            }, status=404)
        except DuplicateError as e:
            return Response(
                data={'status': 'error', 'error': e.get_all_errors() or str(e.get_message())},
                status=400,
            )
        except ResponseError as e:
            return Response(
                data={
                    'status': 'error',
                    'errors': e.get_all_errors(),
                    'error': str(e.get_message()),
                },
                status=400,
            )
        except Exception as e:
            if settings.DEBUG or settings.TEST_MODE:
                raise
            capture_exception()
            return Response(data={
                'status': 'error',
                'error': str(e)
            }, status=500)


class EndUserViewSet(DynamicAPIMixin, CustomerAPIMixin, CustomerRelationMixin, mixins.UpdateModelMixin, viewsets.ReadOnlyModelViewSet):

    serializer_class = EndUserSerializer
    queryset = EndUser.objects.none()

    def _get_api(self, force_reload=False, allow_cached_values=True) -> PexipAPI:
        api = super()._get_api(force_reload=force_reload, allow_cached_values=allow_cached_values)
        assert isinstance(api, PexipAPI)
        return api

    def dispatch(self, request, *args, **kwargs):
        try:
            provider = self._get_customer().get_provider()
            if not provider.is_pexip:
                return JsonResponse({'error': 'Customer has no pexip connection'}, status=404)
        except AttributeError:  # not logged in
            pass
        return super().dispatch(request, *args, **kwargs)

    def get_serializer_class(self):
        if self.action in ('update', 'partial_update'):
            return UpdateEndUserSerializer
        return self.serializer_class

    def get_object(self, pk=None, reload=None) -> EndUser:

        api = self._get_api()

        pk = int(pk or self.kwargs['pk'])

        try:
            user = EndUser.objects.get_active(api.cluster, pk)
        except EndUser.DoesNotExist:
            reload = True
            user = None

        if reload:
            from datastore.utils.pexip import sync_single_user_full
            user = sync_single_user_full(api, pk)

        if not user:
            raise Http404()

        self._check_tenant_customer(user.tenant.tid if user.tenant_id else '')
        return user

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop('partial', False)
        self.get_object()
        serializer = UpdateEndUserSerializer(data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)

        tenant = serializer.validated_data.get('tenant')
        self._check_tenant_customer(tenant)

        from customer.models import Customer

        customer = Customer.objects.find_customer(
            pexip_tenant_id=tenant, cluster=self._get_api().cluster
        )

        if tenant is not None:
            partial_update_or_create(
                PexipEndUser,
                cluster=self._get_api().cluster,
                external_id=self.get_object().uid,
                defaults={
                    'customer': customer,
                },
            )

        response_serializer = EndUserSerializer(self.get_object(reload=True),
                                                context=self.get_serializer_context())

        return Response(response_serializer.data)
