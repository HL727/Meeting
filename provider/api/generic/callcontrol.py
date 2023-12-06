from time import sleep

from django.http import JsonResponse
from drf_yasg.utils import swagger_auto_schema
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.exceptions import NotFound
from rest_framework.response import Response
from sentry_sdk import capture_exception

from provider.api.generic.cospace import GenericCoSpaceViewSet
from provider.api.generic.mixins import DynamicAPIMixin
from provider.api.generic.serializers import (
    GenericCallSerializer,
    GenericCallLegSerializer,
    GenericCreateCallLegSerializer,
    CallControlFlagSerializer,
)
from provider.exceptions import NotFound as provider_NotFound, ResponseError
from shared.exceptions import format_exception


class CatchResponseErrorsMixin:
    # TODO move to generic settings.EXCEPTION_HANDLER instead
    # Default: rest_framework.views.exception_handler
    def dispatch(self, request, *args, **kwargs):
        """Handle not found-errors"""
        try:
            return super().dispatch(request, *args, **kwargs)
        except provider_NotFound:
            return JsonResponse({'error': 'Not found'}, status=404)
        except ResponseError as e:
            capture_exception()
            return JsonResponse({'error': e.get_message()}, status=500)
        except Exception as e:
            capture_exception()
            return JsonResponse({'error': format_exception(e)}, status=500)


class GenericCallViewSet(CatchResponseErrorsMixin, DynamicAPIMixin, viewsets.ViewSet):
    basename = 'call'
    serializer_class = GenericCallSerializer
    lookup_value_regex = '[^/]+'  # otherwise cant match the number in "lookup.123"

    def get_object(self, pk=None):

        try:
            call, api = self._get_api(allow_cached_values=True)\
                .get_clustered_call(pk or self.kwargs['pk'], cospace=self.request.GET.get('cospace'))[0]
        except (IndexError, provider_NotFound):
            raise NotFound()

        self._check_tenant_customer(call.get('tenant', ''))

        return self.transform(call, api)

    @classmethod
    def transform(cls, call, api):
        if api.cluster.is_pexip:
            return cls.transform_from_pexip(call, api)
        elif api.cluster.is_acano:
            return cls.transform_from_acano(call, api)
        elif api.cluster.is_vcs:
            return cls.transform_from_vcs(call, api)
        return call

    @classmethod
    def get_recording_support(cls, call, api):
        result = {
            'support_streaming': False,
            'support_recording': False,
        }
        try:
            if api.customer.get_recording_api():
                result['support_recording'] = True
        except (AttributeError, NotFound):
            pass

        try:
            if api.customer.get_streaming_api():
                result['support_streaming'] = True
        except (AttributeError, NotFound):
            pass

        return result

    @classmethod
    def transform_from_acano(cls, call, api):
        return {
            **cls.get_recording_support(call, api),
            'support_dialout': True,
            'support_control': True,
            'support_video_mute': True,
            'support_lock': True,
            **call,
        }

    @classmethod
    def transform_from_pexip(cls, call, api):
        is_gateway = call.get('service_type') == 'gateway'

        return {
            **cls.get_recording_support(call, api),
            'support_dialout': not is_gateway,
            'support_control': not is_gateway,
            'support_video_mute': not is_gateway,
            'support_lock': not is_gateway,
            **call,
            'cospace': call.get('name') or '',
            'ts_start': call.get('ts_start') or call['start_time'],  # TODO convert start_time timezone
        }

    @classmethod
    def transform_from_vcs(cls, call, api):
        return {
            'support_dialout': False,
            'support_control': False,
            'support_streaming': False,
            'support_recording': False,
            'support_lock': False,
            'name': call.get('protocol'),
            'id': call.get('uuid'),
            'participants': call.get('participants'),
        }

    def list(self, request):

        search = request.GET.get('search') or ''
        try:
            offset = int(request.GET.get('offset') or 0)
            limit = int(request.GET.get('limit') or 20)
            if limit < 1:
                limit = 1000
        except ValueError:
            return Response({'error': 'Invalid integer'}, status=400)

        provider, api, tenant_id = self._get_dynamic_provider_api(allow_cached_values=True)
        if provider.is_cluster:
            result, count = api.get_clustered_calls(filter=search, tenant=tenant_id, offset=offset, limit=limit)
        elif not api:
            result, count = [], 0
        else:
            result, count = api.get_calls(filter=search, tenant=tenant_id, offset=offset, limit=limit)

        result = [self.transform(c, api) for c in result]

        return Response({
            'results': result,
            'count': count,
            'search': search,
            'page_from': offset + 1,
            'page_to': offset + len(result),
        })

    def _get_full_call(self):
        call = self.get_object()

        provider, api, tenant_id = self._get_dynamic_provider_api(allow_cached_values=True)

        cospace = None
        if call.get('cospace_id'):
            cospace = api.get_cospace(call.get('cospace_id'))
        elif call.get('cospace_name') or call.get('cospace'):
            name = call.get('cospace_name') or call.get('cospace')
            try:
                cospaces = api.find_cospaces(call.get('cospace_name') or call.get('cospace'), tenant=tenant_id)[0]
                cospace = [c for c in cospaces if c.get('name') == name][0]
            except IndexError:
                pass

        return {
            **call,
            'cospace_data': GenericCoSpaceViewSet.transform(cospace, api=api) if cospace else {},
            'legs': self._get_legs(call),
        }

    def _get_legs(self, call):
        provider, api, tenant_id = self._get_dynamic_provider_api(allow_cached_values=True)
        if provider.is_cluster:
            legs = api.get_clustered_call_legs(call['id'])
        else:
            legs = api.get_call_legs(call['id'])[0]

        return [GenericCallLegViewSet.transform(leg, api) for leg in legs]

    def retrieve(self, request, pk=None):
        return Response(self._get_full_call())

    @action(detail=True, methods=['GET'])
    def status(self, request, pk=None):
        return Response(self.get_object())

    @action(detail=True, methods=['GET'])
    def legs(self, request, pk=None):
        call = self.get_object()

        legs = self._get_legs(call)

        return Response(legs)

    @action(detail=True, methods=['POST', 'DELETE'])
    def lock(self, request, pk=None):
        call = self.get_object()

        api = self._get_api()
        if request.method == "POST":
            api.set_call_lock(call['id'], True)
        elif request.method == "DELETE":
            api.set_call_lock(call['id'], False)

        return self.retrieve(request, pk=pk)

    @action(detail=True, methods=['POST', 'DELETE'])
    def record(self, request, pk=None):
        call = self.get_object()

        api = self._get_api()
        try:
            rec_api = api.customer.get_recording_api()
        except AttributeError:
            return Response({'error': 'No recording provider available'}, status=400)

        return self._handle_stream_record(request, call, rec_api)

    @action(detail=True, methods=['POST', 'DELETE'])
    def stream(self, request, pk=None):
        call = self.get_object()

        api = self._get_api()
        try:
            rec_api = api.customer.get_streaming_api()
        except AttributeError:
            return Response({'error': 'No recording provider available'}, status=400)

        return self._handle_stream_record(request, call, rec_api)

    def _handle_stream_record(self, request, call, rec_api):

        api = self._get_api(allow_cached_values=True)

        cospace = self._get_full_call().get('cospace_data') or {}

        kwargs = {}
        if request.method == 'POST':
            rec_api.adhoc_record(
                api, call['id'], local_alias=cospace.get('uri'), cospace=cospace, **kwargs
            )
        elif request.method == 'DELETE':
            rec_api.adhoc_stop_record(
                api, call['id'], local_alias=cospace.get('uri'), cospace=cospace, **kwargs
            )
        else:
            return Response({'error': 'Invalid method'}, status=400)

        return self.retrieve(request)

    @action(detail=True, methods=['POST'])
    def set_all_mute(self, request, pk=None):
        call = self.get_object()

        self._get_api().set_all_participant_mute(call['id'], request.data.get('value'))
        return Response(self.get_object())

    @action(detail=True, methods=['POST'])
    def set_all_video_mute(self, request, pk=None):
        call = self.get_object()

        if self._get_api().cluster.is_pexip:
            return Response({'error': 'Not available for Pexip'}, status=400)

        self._get_api().set_all_participant_video_mute(call['id'], request.data.get('value'))
        return Response(self.get_object())

    def destroy(self, request, *args, **kwargs):
        call = self.get_object()

        for subcall, api in self._get_api().get_clustered_call(call['id']):
            api.hangup_call(subcall['id'])

        return Response(status=status.HTTP_204_NO_CONTENT)


class GenericCallLegViewSet(CatchResponseErrorsMixin, DynamicAPIMixin, viewsets.ViewSet):
    basename = 'leg'
    serializer_class = GenericCallLegSerializer
    lookup_value_regex = '[^/]+'  # otherwise cant match the number in "lookup.123"

    def get_object(self, pk=None, force=False):

        force_kwargs = {'allow_cached_values': False} if force else {}
        leg, api = self._get_api(**force_kwargs).get_clustered_call_leg(pk or self.kwargs['pk'])

        if not leg:
            raise NotFound()

        self._check_tenant_customer(leg.get('tenant', ''))

        return self.transform(leg, api)

    @staticmethod
    def transform(leg, api):
        if api.cluster.is_pexip:
            return GenericCallLegViewSet.transform_from_pexip(leg)
        if api.cluster.is_acano:
            return GenericCallLegViewSet.transform_from_acano(leg)
        return leg

    @staticmethod
    def transform_from_acano(leg):
        return {
            **leg,
            'audio_muted': leg.get('is_muted', False),
        }

    @staticmethod
    def transform_from_pexip(leg):
        return {
            **leg,
            'name': leg.get('name') or leg.get('display_name'),
            'local': leg.get('local_alias'),
            'remote': leg.get('remote_alias'),
            'ts_start': leg.get('ts_start') or leg.get('connect_time'),  # TODO convert connect_time timezone
            'audio_muted': leg.get('is_muted', False),
            'is_moderator': leg.get('role') == 'chair',
        }

    def list(self, request):

        search = request.GET.get('search') or ''
        call_id = request.GET.get('call') or ''
        try:
            limit = int(request.GET.get('limit') or 20)
        except ValueError:
            return Response({'error': 'Invalid integer'}, status=400)

        provider, api, tenant_id = self._get_dynamic_provider_api(allow_cached_values=True)

        result = api.get_clustered_call_legs(call_id, filter=search, tenant=tenant_id, limit=limit)
        if api.cluster.is_pexip:
            result = [self.transform(c, api) for c in result]

        return Response({
            'results': result,
        })

    def retrieve(self, request, pk=None):
        leg = self.get_object(force=request.GET.get('full') in ('1', 'true', 'True'))
        return Response(leg)

    def destroy(self, request, *args, **kwargs):
        leg = self.get_object()

        leg, api = self._get_api().get_clustered_call_leg(leg['id'])
        api.hangup_call_leg(leg['id'])

        return Response(status=status.HTTP_204_NO_CONTENT)

    @swagger_auto_schema(request_body=GenericCreateCallLegSerializer())
    def create(self, request):
        serializer = GenericCreateCallLegSerializer(data=request.data, context=self.get_serializer_context())
        serializer.is_valid(raise_exception=True)

        data = serializer.validated_data  # TODO validate tenant

        api = self._get_api()
        local = data.pop('local', None)
        call_id = data.pop('call_id', None)

        if local and not call_id:
            if api.provider.is_acano:
                calls, count = api.get_clustered_calls(cospace=local, tenant=api.get_tenant_id(api.customer))
                if calls:
                    call_id = calls[0]['id']
                else:
                    cospace = api.get_cospace(local)
                    self._check_tenant_customer(cospace['tenant'])
                    call_id = api.add_call(local, name=cospace['name'])
            elif api.provider.is_pexip:
                result, count = api.find_cospaces({'aliases__alias': local})
                if not result:
                    raise NotFound()
                self._check_tenant_customer(result[0]['tenant'])
                local = api.get_sip_uri(cospace=result[0])

        if api.provider.is_pexip:
            if data.get('role') == 'moderator':
                data['role'] = 'chair'

        if data.get('call_type') == 'streaming' and api.provider.is_pexip:
            data.pop('call_type')
            leg_id = api.start_stream(
                call_id or local, data.pop('remote'), data.pop('remote_presentation', None), **data
            )
        else:
            automatic = data.pop('automatic_routing', None)
            if automatic:
                data['routing'] = 'routing_rule'
            elif automatic is False:
                data['routing'] = 'manual'

            leg_id = api.add_call_leg(call_id or local, data.pop('remote'), **data)

        for i in range(3):
            if i:
                sleep(0.5)
            try:
                return Response(self.get_object(pk=leg_id, force=True))
            except provider_NotFound:
                pass
            except ResponseError as e:
                return Response({'error': format_exception(e)}, status=400)

        return Response({'id': leg_id})

    @action(detail=True, methods=['POST'])
    def set_mute(self, request, pk=None):

        leg = self.get_object()

        serializer = CallControlFlagSerializer(
            data=request.data, context=self.get_serializer_context()
        )
        serializer.is_valid(raise_exception=True)
        self._get_api().set_participant_mute(leg['id'], serializer.validated_data.get('value'))

        sleep(.3)  # if .3 is not enough, solve it some other way. Can congest the server otherwise
        return Response(self.get_object(force=True))

    @action(detail=True, methods=['POST'])
    def set_moderator(self, request, pk=None):
        leg = self.get_object()
        serializer = CallControlFlagSerializer(
            data=request.data, context=self.get_serializer_context()
        )
        serializer.is_valid(raise_exception=True)
        self._get_api().set_participant_moderator(leg['id'], serializer.validated_data.get('value'))
        sleep(.3)  # if .3 is not enough, solve it some other way. Can congest the server otherwise
        return Response(self.get_object(force=True))

    def get_serializer_context(self):

        context = super().get_serializer_context()
        return {
            **context,
            'api': self._get_api(),
        }
