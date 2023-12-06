import json
import logging
import re
from hashlib import md5

import requests
from django.conf import settings
from django.contrib.auth.views import redirect_to_login
from django.core.cache import cache
from django.http import JsonResponse, HttpResponse
from django.views.generic import TemplateView
from sentry_sdk import capture_exception
from django.utils.translation import gettext_lazy as _

from customer.models import CustomerMatch, Customer
from datastore.models.pexip import Conference
from datastore.utils.pexip import sync_conference_from_alias
from policy.models import (
    CustomerPolicy,
    CustomerPolicyState,
    ClusterPolicy,
    ExternalPolicyLog,
)
from policy.response import PexipPolicyResponse, PEXIP_DEFAULT_RESPONSE
from policy_rule.models import get_active_rule
from provider.exceptions import ResponseTimeoutError
from statistics.parser.utils import clean_target
from customer.view_mixins import LoginRequiredMixin, CustomerMixin
from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from provider.models.provider import Cluster


logger = logging.getLogger(__name__)

# Try to get conference data if not already synced. Note Pexip can be really slow (10+ seconds) so it may
# hold up a lot of traffic if queues are full. If disabled no overrides are possible (e.g. lower quality)
# but rejecting unauthorized calls works anyway as long as alias matches rules
ENABLE_FETCH_MISSING_CONFERENCE = False


class PolicyReportView(LoginRequiredMixin, CustomerMixin, TemplateView):
    template_name = 'base_vue.html'

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated or not request.user.is_staff:
            return redirect_to_login(request.get_full_path())
        return super().dispatch(request, *args, **kwargs)


def _log_request_response(cluster: 'Cluster', request_params, response_params, ip: str, type: str):
    from debuglog.models import PexipPolicyLog

    _rparams = response_params or {}
    if _rparams.get('status') == 'success' and _rparams.get('result'):
        action = 'override'
    else:
        action = _rparams.get('action') or ''

    return PexipPolicyLog.objects.store(
        content=json.dumps(
            {
                'request': request_params,
                'response': response_params,
            },
            indent=1,
        ),
        type=type,
        action=action,
        service_type=(response_params or {}).get('result', {}).get('service_type') or '',
        cluster_id=cluster.pk,
        ip=ip,
    )


def policy_service_response(request, secret_key=None):

    from policy_script.models import get_cluster_policy_response

    cluster_policy = ClusterPolicy.objects.get(secret_key=secret_key)
    ip = request.META.get('REMOTE_ADDR') or '0.0.0.0'

    def _get_response_data(response):
        if isinstance(response, HttpResponse):
            try:
                return json.loads(response.content)
            except ValueError:
                return {'body': response.content}
        elif isinstance(response, PexipPolicyResponse):
            return response.get_response_data()
        else:
            return response

    def _log(response, response_data):
        _log_request_response(cluster_policy.cluster, request.GET.dict(), response_data, ip, 'service')
        return response

    response = get_policy_service_response(
        cluster_policy, request.GET.copy(), secret_key=secret_key, ip=ip
    )

    response_data = _get_response_data(response)

    new_response, has_response = get_cluster_policy_response(
        cluster_policy.cluster,
        request.GET.copy(),
        response_data,
        cluster_policy=cluster_policy,
    )
    if has_response:
        response = response_data = new_response

    if isinstance(response, HttpResponse):
        return _log(response, response_data)
    if hasattr(response, 'get_httpresponse'):
        return _log(response.get_httpresponse(), response_data)
    return JsonResponse(_log(response, response_data))


def match_policy_service(cluster_policy, params):

    cluster = cluster_policy.cluster

    obj = dict(params)
    obj['local_alias'] = clean_target(params['local_alias'])
    obj['remote_alias'] = clean_target(params.get('remote_alias') or '')

    conference = Conference.objects.match(obj, cluster=cluster)
    gateway_rule = get_active_rule(cluster, **params.dict())
    customer = None
    needs_auth = False
    match = None

    if conference:
        customer = conference.get_customer()
        if conference.match_id:
            needs_auth = needs_auth or conference.match.require_authorization
            match = conference.match

    if not customer:
        customer = CustomerMatch.objects.get_customer_for_pexip(obj=obj, cluster=cluster)

    if not match:
        match = CustomerMatch.objects.get_match(obj=obj, cluster=cluster)
        if match:
            customer = customer or match.customer
            needs_auth = needs_auth or match.require_authorization

    enable_fetch_missing = ENABLE_FETCH_MISSING_CONFERENCE or settings.TEST_MODE

    if not conference and not gateway_rule and (customer or match) and enable_fetch_missing:
        # No synced conference. Try to fetch from server every 10 secs unless a gateway rule matches
        try:
            is_ip_url = re.search(r'@\d+\.\d+\.\d+\.\d+', obj['local_alias'])  # probably spam
            if not is_ip_url:
                conference = load_conference_from_server(cluster, obj['local_alias'])
        except Exception:
            if settings.DEBUG or settings.TEST_MODE:
                raise
            capture_exception()

    return customer, conference, gateway_rule, needs_auth


def get_policy_service_response(cluster_policy, params, secret_key=None, ip=None):

    if not params.get('local_alias') or params.get('call_direction') == 'non_dial':
        return PEXIP_DEFAULT_RESPONSE

    cluster = cluster_policy.cluster

    customer, conference, gateway_rule, needs_auth = match_policy_service(cluster_policy, params)

    external_response = get_external_response(cluster_policy, params, ip=ip)
    if external_response:
        is_continue = external_response.get('status') == 'success' and (
            external_response.get('action') == 'continue' and not external_response.get('result')
        )

        if not is_continue:
            return external_response

    response = PexipPolicyResponse(
        conference, params, customer, cluster, fallback_response=external_response
    )

    def _log(**kwargs):
        # TODO move log to response handler
        ExternalPolicyLog.objects.create(
            customer=customer,
            conference=conference.name if conference else '-- unknown VMR --',
            gateway_rule=gateway_rule.name if gateway_rule else '-- no matching rule --',
            local_alias=params and params.get('local_alias') or '',
            remote_alias=params and params.get('remote_alias') or '',
            limit=0,
            needs_auth=needs_auth,
            cluster=cluster,
            **kwargs,
        )

    def _log_auth(auth_success):
        _log(
            action=ClusterPolicy.REJECT if not auth_success else ClusterPolicy.LOG,
            message='Authorization for {} ({}) needed. Result: {}. Remote: {}, customer {}'.format(
                conference.name if conference else _('Unknown VMR'),
                params and params.get('local_alias') or '',
                'SUCCESS' if auth_success else 'REJECT',
                params and params.get('remote_alias') or '',
                customer,
                )
        )

    if needs_auth and params.get('call_direction') == 'dial_in':
        auth_success = response.check_auth(params)
        try:
            _log_auth(auth_success)
        except Exception:
            if settings.DEBUG or settings.TEST_MODE:
                raise
            capture_exception()

    if not conference and gateway_rule:
        gateway_rule.log_hit()
        if cluster_policy.enable_gateway_rules:
            _log(message=(
                'Policy rule {} matched remote {}, local {}. Overriding response'.format(
                    gateway_rule,
                    params.get('remote_alias'),
                    params.get('local_alias'),
                )
            ))
            response.override(gateway_rule.get_response(params))
        else:
            _log(message=(
                'Policy rule {} matched remote {}, local {}. Override disabled, record hit count'.format(
                    gateway_rule,
                    params.get('remote_alias'),
                    params.get('local_alias'),
                )
            ))
            try:  # TODO remove after test
                gateway_rule.get_response()
            except Exception:
                capture_exception()

    if not customer:
        return response

    customer_policy = CustomerPolicy.objects.get_active(customer=customer)
    if not customer_policy:
        return response

    state = customer_policy.get_state(cluster)
    status = state.participant_status if state else CustomerPolicyState.OK

    if status == CustomerPolicyState.OK:
        return response

    if status == CustomerPolicyState.HARD_LIMIT:
        action = customer_policy.hard_limit_action if customer_policy.hard_limit_action != -1 else cluster_policy.hard_limit_action
        if action <= 0:
            return response

        return action_response(response, action, customer_policy, conference, gateway_rule, params, state, needs_auth=needs_auth)

    if status == CustomerPolicyState.SOFT_LIMIT:
        action = customer_policy.soft_limit_action if customer_policy.soft_limit_action != -1 else cluster_policy.soft_limit_action
        if action <= 0:
            return response

        return action_response(response, action, customer_policy, conference, gateway_rule, params, state, needs_auth=needs_auth)

    return response


def load_conference_from_server(cluster: 'Cluster', local_alias: str) -> Optional[Conference]:
    cache_key = 'pexip.local_sync.{}'.format(md5(local_alias.encode('utf-8')).hexdigest())
    lock_key = 'pexip.local_sync_provider.{}'.format(cluster.pk)
    lock = None
    if not cache.get(cache_key):
        try:
            lock = cache.lock(lock_key, timeout=3.1)
            if not lock.acquire(blocking_timeout=3, blocking=True):
                logger.warning('Missing conference alias for policy response, but a pending request already exists')
                return None  # Don't try again after timeout. Remote timeout limit will be reached anyhow

        except Exception:
            if hasattr(cache, 'lock') and settings.TEST_MODE:
                raise
            lock = None

    conference = None
    if (not cache.get(cache_key) or settings.TEST_MODE):
        try:
            conference = sync_conference_from_alias(cluster.get_api(Customer.objects.first()),
                                                    local_alias)
        except ResponseTimeoutError:
            logger.warning('Timeout before getting conference response for missing alias')
        except Exception:
            if settings.TEST_MODE:
                raise
            capture_exception()
        cache.set(cache_key, 1, 10)  # reuse 404
    if lock:
        try:
            lock.release()
        except Exception:  # lock expired
            pass
    return conference


service_type_required_fields = {
    'conference': ['name', 'service_tag', 'service_type'],
    'lecture': ['name', 'service_tag', 'service_type'],
    'gateway': ['local_alias', 'name', 'outgoing_protocol', 'remote_alias', 'service_tag', 'service_type'],
    'two_stage_dialing': ['name', 'service_tag', 'service_type'],
    'test_call': ['name', 'service_tag', 'service_type'],
}


def action_response(response, action_id, customer_policy=None, conference=None, gateway_rule=None, params=None, state=None, needs_auth=False):

    def _log():
        ExternalPolicyLog.objects.create(
            customer=customer_policy.customer,
            conference=conference.name if conference else '-- unknown VMR --',
            gateway_rule=gateway_rule.name if gateway_rule else '-- no matching rule --',
            local_alias=params and params.get('local_alias') or '',
            remote_alias=params and params.get('remote_alias') or '',
            action=action_id,
            needs_auth=needs_auth,
            limit=state.participant_status,
            cluster=state.cluster if state else None,
            message='Action: {}. {} reached for customer {}, Call from {} to {} ({}). Current participants are {} (total value {}), limit is {}'.format(
                dict(ClusterPolicy.ACTIONS).get(action_id, 'unknown'),
                dict(CustomerPolicyState.STATES).get(state.participant_status, 'Unknown limit'),
                customer_policy.customer,
                params and params.get('local_alias') or '',
                params and params.get('remote_alias') or '',
                conference.name if conference else _('Unknown VMR'),
                state.active_participants if state else None,
                state.participant_value if state else None,
                customer_policy and customer_policy.participant_limit,
            )
        )

    def _try_log():
        try:
            _log()
        except Exception:
            if settings.DEBUG or settings.TEST_MODE:
                raise
            capture_exception()

    if action_id <= 0:
        return response

    _try_log()

    if action_id <= ClusterPolicy.LOG:
        return response

    if action_id <= ClusterPolicy.AUDIO_ONLY:
        return response.override({'call_type': 'audio'})

    if action_id <= ClusterPolicy.QUALITY_SD:
        return response.override({'max_pixels_per_second': 'sd'})

    if action_id <= ClusterPolicy.QUALITY_720P:
        return response.override({'max_pixels_per_second': 'hd'})

    if action_id == ClusterPolicy.REJECT:
        return response.reject('Hard limit')

    raise ValueError('Invalid action id: {}'.format(action_id))


def get_external_response(cluster_policy, params, ip=None):

    policies = list(cluster_policy.get_external_policies(cluster_policy.pk))

    for ep in policies:
        if params.get('call_direction') == 'dial_in':
            target_alias = params.get('local_alias') or ''
        else:
            target_alias = params.get('remote_alias') or ''

        if not re.match(ep.target_alias_match, target_alias):
            continue

        try:
            response = requests.get(
                ep.build_request_url({**params, '_original_ip': ip or '', '_external_id': ep.id}),
                timeout=3,
            )
        except Exception:
            continue
        else:
            error = response.status_code != 200

        if error:
            # TODO log
            continue
        try:
            data = response.json()
        except ValueError:
            continue

        if data.get('status') not in ('success', 'reject'):
            continue
        if data.get('action') == 'reject':
            return data

        if data and data.get('result') and ep.settings_override:
            data['result'].update(ep.settings_override)

        return data

    return None
