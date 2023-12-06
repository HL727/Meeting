from typing import Tuple, Dict

from django.conf import settings
from django.http import Http404
from drf_yasg.utils import swagger_auto_schema
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from sentry_sdk import capture_exception

from endpoint.view_mixins import CustomerRelationMixin
from license import get_license
from license.api_helpers import license_validate_add
from numberseries.models import NumberRangeDummy
from provider.api.acano.serializers import CoSpaceSerializer, CoSpaceBulkCreateSerializer, \
    CoSpaceCreateSerializer
from provider.api.generic.mixins import DynamicAPIMixin
from provider.exceptions import ResponseError, NotFound, MessageResponseError
from provider.ext_api.acano import AcanoDistributedRunner
from provider.models.acano import CoSpace
from django.utils.translation import ugettext as _

from customer.view_mixins import CustomerAPIMixin
from shared.utils import partial_update_or_create
from supporthelpers.forms import CoSpaceForm


class CoSpaceViewSet(DynamicAPIMixin, CustomerAPIMixin, CustomerRelationMixin, viewsets.GenericViewSet):

    serializer_class = CoSpaceSerializer
    queryset = CoSpace.objects.none()

    def _get_api(self, force_reload=False, allow_cached_values=True):
        return super()._get_api(force_reload=force_reload, allow_cached_values=allow_cached_values)

    def _handle_error(self, e, data=None):
        errors = {}

        if 'duplicateCoSpaceUri' in e.args[1].text:
            errors['uri'] = [_('Den angivna URIn används redan')]
            if not data or not data.get('uri') or data.get('uri') == data.get('call_id'):
                errors['call_id'] = [_('Den angivna URIn används redan')]
        if 'duplicateCoSpaceId' in e.args[1].text:
            errors['call_id'] = [_('Det angivna callID används redan')]
        if 'userDoesNotExist' in e.args[1].text:
            errors['owner_jid'] = [_('Fel vid angivande ägare')]

        return {
            'status': 'error',
            'errors': errors
        }

    def get_object(self, pk=None, reload=None, include_members=True) -> dict:

        pk = pk or self.kwargs['pk']
        form = CoSpaceForm(cospace=pk)
        cospace = form.load(self._get_customer(), include_members=include_members)
        if not cospace:
            raise Http404()

        self._check_tenant_customer(cospace.get('tenant') or '')
        return cospace

    def retrieve(self, request, pk=None):
        return Response(self.get_object())

    def get_serializer_context(self, **kwargs):
        if getattr(self, 'swagger_fake_view', False):
            return super().get_serializer_context()

        kwargs.setdefault('cluster', self._get_api().cluster)

        return {
            'customer': self._get_customer(),
            'api': self._get_api(),
            **super().get_serializer_context(),
            **kwargs,
        }

    def _save_with_form(self, data, cospace_id=None):
        try:
            form = CoSpaceForm(data, cospace=cospace_id, customer=self._get_customer())
            if form.is_valid():
                cospace_id, errors = form.save(creator=self.request.user.email)
            else:
                errors = form.errors
                cospace_id = None

            if errors:
                return cospace_id, Response(data=errors, status=400)
        except Exception as e:
            return None, self._error_response(e)
        else:
            return cospace_id, None

    @swagger_auto_schema(request_body=CoSpaceCreateSerializer, responses={201: CoSpaceSerializer})
    def create(self, request, *args, **kwargs):
        serializer = CoSpaceCreateSerializer(data=request.data, context=self.get_serializer_context())

        if not serializer.is_valid():
            return Response(data=serializer.errors, status=400)

        license_validate_add('core:enable_core')

        api = self._get_api()

        data = serializer.get_form_data()
        number_range = api.get_static_room_number_range()

        if serializer.validated_data.get('call_id_generation_method') == 'random':
            data['call_id'] = number_range.random()
        elif serializer.validated_data.get('call_id_generation_method') == 'increase':
            data['call_id'] = number_range.use()

        data['tenant'] = self._get_customer().acano_tenant_id

        cospace_id, response = self._save_with_form(data)
        if response:
            return response

        if 'organization_unit' in data or 'organization_path' in data:
            serializer.save_organization(cospace_id, data)

        return Response(self.get_object(cospace_id), status=201)

    def update(self, request, pk=None, **kwargs):
        obj = self.get_object(include_members=False)

        serializer = CoSpaceSerializer(data=request.data, partial=kwargs.pop('partial', False),
                                       context=self.get_serializer_context())
        if not serializer.is_valid():
            return Response(data=serializer.errors, status=400)

        data = serializer.get_form_data()

        cospace_id, response = self._save_with_form(data, cospace_id=obj['cospace'])
        if response:
            return response

        if 'organization_unit' in data or 'organization_path' in data:
            serializer.save_organization(obj['cospace'], data)

        return Response(self.get_object(reload=True))

    def partial_update(self, request, *args, **kwargs):
        kwargs['partial'] = True
        return self.update(request, *args, **kwargs)

    @action(detail=False, methods=['POST'])
    @swagger_auto_schema(request_body=CoSpaceBulkCreateSerializer, responses={201: CoSpaceBulkCreateSerializer})
    def bulk_create(self, request):
        serializer = CoSpaceBulkCreateSerializer(data=request.data,
                                                    context=self.get_serializer_context())
        if not serializer.is_valid():
            return Response(data=serializer.errors, status=400)

        license_validate_add('core:enable_core')

        api = self._get_api()
        response = []

        random_call_id = serializer.validated_data.get('call_id_generation_method') == 'random'
        if serializer.validated_data.get('call_id_generation_method') == 'increase' and serializer.validated_data.get('start_call_id'):
            number_range = NumberRangeDummy(serializer.validated_data['start_call_id'])
        else:
            number_range = api.get_static_room_number_range()

        send_email = serializer.validated_data.get('send_email')

        cospace_serializer = CoSpaceSerializer(context=serializer.context)
        cospace_serializer.parent = serializer

        objects = [self._prepare_single_api_dict(api, cospace, number_range, random_call_id)
                   for cospace in serializer.validated_data['cospaces']]

        def _handle_single(api, args: Tuple[Dict, Dict]):

            result, api_data = args
            if not self._add_cospace(api, api_data, result):
                return result

            self._set_owner_email(api, result)
            full_data = self._update_data_from_server(api, result)

            if send_email and result.get('owner_email') or full_data.get('owner_email'):
                from provider import tasks

                tasks.send_email_for_cospace.delay(
                    api.customer.pk,
                    result['id'],
                    emails=[result.get('owner_email') or full_data.get('owner_email')],
                )

            cospace_serializer.save_organization(result['id'], result)

            if result.get('owner_jid'):
                if not self._set_owner(api, result):
                    response.append(result)
                    return

            result['status'] = 'ok'
            return result

        response = AcanoDistributedRunner(api, _handle_single, objects, ordered_result=True).as_list()

        if not any(r['status'] == 'ok' for r in response):  # all errors
            return Response({'cospaces': response}, status=400)
        return Response({'cospaces': response}, status=201)

    def _prepare_single_api_dict(self, api, data, number_range, random_call_id=False) -> Tuple[Dict, Dict]:
        api_data = {
            'name': data.get('name', '') or data.get('title', ''),
            'uri': data.get('uri', ''),
            'callId': data.get('call_id', ''),
            'passcode': data.get('passcode', ''),
        }

        api.populate_call_id(api_data, number_range, random=random_call_id)
        return data, api_data

    def _add_cospace(self, api, api_data, result):

        try:
            result['id'] = api.add_cospace(data=api_data, sync=False)
        except ResponseError as e:
            result.update(self._handle_error(e, result))
            if result.get('call_id') and not result.get('uri'):
                result['uri'] = result['call_id']
            return False

        return True

    def _update_data_from_server(self, api, result):
        real_data = api.get_cospace(result['id'])

        result.update({
            'call_id': real_data.get('callId'),
            'uri': real_data.get('uri'),
            'id': result['id'],
        })

        return real_data

    def _set_owner_email(self, api, result):
        if not result.get('owner_email'):
            return

        partial_update_or_create(
            CoSpace,
            provider=api.cluster,
            provider_ref=result['id'],
            defaults={'customer': self.customer, 'owner_email': result['owner_email']},
        )

    def _set_owner(self, api, result):
        try:
            api.update_cospace(result['id'], {'ownerJid': result.get('owner_jid')})
        except NotFound as e:
            result.update(**self._handle_error(e))
            return False

        return True

    def _error_response(self, exception):
        try:
            raise exception
        except NotFound as e:
            return Response(data={
                'status': 'error',
                'error': str(e)
            }, status=404)
        except MessageResponseError as e:
            return Response(data={
                'status': 'error',
                'error': str(e.get_message())
            }, status=400)
        except Exception as e:
            if settings.DEBUG or settings.TEST_MODE:
                raise
            capture_exception()
            return Response(data={
                'status': 'error',
                'error': str(e)
            }, status=500)
