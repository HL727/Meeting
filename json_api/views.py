import hashlib
import os
from time import time

from django.conf import settings
from django.core.serializers.json import DjangoJSONEncoder
from django.db.models import Q
from django.http import HttpResponse, Http404
from django.http.response import HttpResponseBadRequest, JsonResponse
from django.views.generic.base import View

from provider.exceptions import NotFound, ResponseError
from organization.models import CoSpaceUnitRelation, OrganizationUnit
from customer.view_mixins import LoginRequiredMixin, CustomerMixin
from provider.models.pexip import PexipSpace
from shared.context_processors import get_license_status
from shared.utils import partial_update_or_create

KEY_MUTE_AUDIO = 'rxAudioMute'
KEY_MUTE_VIDEO = 'rxVideoMute'


def create_json_response(data, status=200):
    return HttpResponse(DjangoJSONEncoder().encode(data), content_type='application/json', status=status)


class AbstractCustomerApi(LoginRequiredMixin, CustomerMixin, View):

    allow_cached_values = True

    def _get_results(self, q, customer, offset, limit=None):
        raise NotImplementedError('This must be overridden in subclass!')

    def get(self, request, *args, **kwargs):
        customer = self._get_customer(request)

        if not customer:
            return HttpResponseBadRequest()

        data = {}

        try:
            offset = int(request.GET.get('offset') or 0)
        except ValueError:
            offset = 0

        try:
            limit = int(request.GET.get('limit') or 20)
        except ValueError:
            limit = 20

        q = request.GET.get('q') or request.GET.get('search') or ''

        results, count = self._get_results(q=q, customer=customer, offset=offset, limit=limit if limit != -1 else None)

        data['results'] = results
        data['count'] = count
        data['q'] = q or ''
        data['page_from'] = offset + 1
        data['page_to'] = offset + len(results)

        url = request.GET.copy()
        if count > offset + len(results):
            url['offset'] = offset + len(results)
            data['next'] = request.build_absolute_uri() + url.urlencode()

        if offset:
            url['offset'] = max(0, offset - 10)
            data['previous'] = url.urlencode()

        return create_json_response(data)

    def _get_api(self, force_reload=False, allow_cached_values=False):
        return super()._get_api(allow_cached_values=self.allow_cached_values)


class CallLegs(LoginRequiredMixin, CustomerMixin, View):

    def get(self, request, *args, **kwargs):
        customer = self._get_customer(request)

        if not customer:
            return HttpResponseBadRequest()

        call_ids = []
        if kwargs.get('call_id'):
            call_ids.append(kwargs['call_id'])
        if request.GET.get('call_ids'):
            call_ids.extend(request.GET.get('call_ids', '').split(','))

        provider, api, tenant_id = self._get_dynamic_provider_api(allow_cached_values=True)

        if call_ids and call_ids[0] == '*':
            call_ids = [c['id'] for c in api.get_clustered_calls(tenant=tenant_id)[0]]

        result = []

        for call_id in call_ids:
            if not call_id or '/' in call_id:
                continue

            try:
                call_legs = api.get_clustered_call_legs(call_id, cospace=request.GET.get('cospace'))
            except NotFound:
                call_legs = []
            else:
                for l in call_legs:
                    self._check_tenant_customer(l.get('tenant'))
                result.extend(call_legs)

        result = self.maybe_transform_from_pexip(result, api)

        return create_json_response({
            'results': result,
        })

    def maybe_transform_from_pexip(self, result, api=None):
        try:
            if not (api or self._get_api()).provider.is_pexip:
                return result
        except AttributeError:
            return result

        return [{
            **l,
            'remote': l.get('remote_alias') or l.get('remote'),
            'name': l.get('display_name') or l.get('remote') or l.get('remote_alias') or '',
        } for l in result]


class CallLegDetails(LoginRequiredMixin, CustomerMixin, View):
    def get(self, request, *args, **kwargs):
        customer = self._get_customer(request)

        if not customer:
            return HttpResponseBadRequest()

        leg_id = request.GET.get('call_leg_id')
        if not leg_id:
            raise Http404()

        try:
            call_leg, api = self._get_api().get_clustered_call_leg(leg_id)
        except NotFound:
            return create_json_response({
                'result': {},
                'status': 'error',
                'reason': 'notfound',
            })

        self._check_tenant_customer(call_leg.get('tenant'))

        return create_json_response({
            'result': call_leg
        })


class CallLegSetLayout(LoginRequiredMixin, CustomerMixin, View):
    def post(self, request, *args, **kwargs):
        customer = self._get_customer(request)

        if not customer:
            return HttpResponseBadRequest()

        leg_id = request.POST.get('leg_id')
        if not leg_id:
            raise Http404()

        layout = request.POST.get('layout')

        call_leg, api = self._get_api().get_clustered_call_leg(leg_id)
        self._check_tenant_customer(call_leg.get('tenant'))

        api.update_call_leg(leg_id, {
            'chosenLayout': layout,
        })

        return create_json_response({
            'status': 'OK'
        })


class CallLegHangup(LoginRequiredMixin, CustomerMixin, View):
    def post(self, request, *args, **kwargs):
        customer = self._get_customer(request)

        if not customer:
            return HttpResponseBadRequest()

        leg_id = request.GET.get('call_leg_id') or request.POST.get('leg_id')
        if not leg_id:
            raise Http404()

        call_leg, api = self._get_api().get_clustered_call_leg(leg_id)
        self._check_tenant_customer(call_leg.get('tenant'))

        api.hangup_call_leg(call_leg['id'])

        return create_json_response({
            'status': 'OK'
        })


class AbstractMuter(LoginRequiredMixin, CustomerMixin, View):
    def post(self, request, *args, **kwargs):
        resource_id = request.POST.get('id')

        if not resource_id:
            raise Http404()

        mute = request.POST.get('mute')
        key_name = self._get_key_name()
        try:
            self._perform_api_call(resource_id, key_name, mute)
        except ResponseError:
            return HttpResponseBadRequest('Could not mute call leg.')
        else:
            return create_json_response({
                'status': 'OK'
            })

    def _get_key_name(self):
        raise NotImplementedError('Must implement in sublass!')

    def _perform_api_call(self, resource_id, key_name, mute):
        raise NotImplementedError('Must implement in sublass!')


class AbstractCallLegMuter(AbstractMuter):
    def _perform_api_call(self, resource_id, key_name, mute):
        customer = self._get_customer(self.request)

        if not customer:
            return HttpResponseBadRequest()

        call_leg, api = self._get_api().get_clustered_call_leg(resource_id)
        self._check_tenant_customer(call_leg.get('tenant'))

        api.update_call_leg(call_leg['id'], {
            key_name: mute,
        })

    def _get_key_name(self):
        raise NotImplementedError('Must implement in sublass!')


class CallLegMuteAudio(AbstractCallLegMuter):
    def _get_key_name(self):
        return KEY_MUTE_AUDIO


class CallLegMuteVideo(AbstractCallLegMuter):
    def _get_key_name(self):
        return KEY_MUTE_VIDEO


class AbstractCallAllMuter(AbstractMuter):
    def _perform_api_call(self, resource_id, key_name, mute):
        customer = self._get_customer(self.request)

        if not customer:
            return HttpResponseBadRequest()

        for call, api in self._get_api().get_clustered_call(resource_id):

            self._check_tenant_customer(call.get('tenant'))

            api.update_call_participants(call['id'], {
                key_name: mute,
            })

    def _get_key_name(self):
        raise NotImplementedError('Must implement in sublass!')


class CallMuteAllAudio(AbstractCallAllMuter):
    def _get_key_name(self):
        return KEY_MUTE_AUDIO


class CallMuteAllVideo(AbstractCallAllMuter):
    def _get_key_name(self):
        return KEY_MUTE_VIDEO


startup_time = int(time())  # fallback


def get_version_hash(allow_fallback=True):

    version_hash = str(int(startup_time)) if allow_fallback else ''

    staticfiles_path = os.path.join(settings.STATIC_ROOT, 'staticfiles.json')
    if os.path.exists(staticfiles_path):
        try:
            with open(staticfiles_path, 'rb') as fd:
                version_hash = hashlib.md5(fd.read()).hexdigest()
        except Exception:
            pass

    return version_hash


def session_status(request):

    version_hash = get_version_hash()

    return JsonResponse(
        {
            'status': 'OK',
            'username': request.user.username if request.user.is_authenticated else None,
            'version_hash': version_hash,
            'is_authenticated': request.user.is_authenticated,
            'license': get_license_status(request) if request.user.is_authenticated else {},
        }
    )
