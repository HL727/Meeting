from __future__ import annotations

import json
from typing import Mapping, Any, Optional, TYPE_CHECKING, Set, Tuple, Dict

from django.http import JsonResponse

from policy_auth.models import PolicyAuthorizationOverride, PolicyAuthorization, match_regexp

if TYPE_CHECKING:
    from provider.models.provider import Cluster

PEXIP_DEFAULT_RESPONSE = {'status': 'success', 'action': 'continue'}  # Use pexip inbuild logic


class PexipPolicyResponse:

    status = 'OK'

    def __init__(
        self,
        conference=None,
        params=None,
        customer=None,
        cluster=None,
        overrides=None,
        fallback_response=None,
    ):
        self.conference = conference or None
        self.customer = customer
        self.cluster = cluster
        self.params = params or {}
        self.overrides = overrides or []
        self.reason = ''
        self.fallback_response = fallback_response or PEXIP_DEFAULT_RESPONSE

    def override(self, values):
        if values:
            self.overrides.append(values)
        return self

    def reject(self, reason=''):
        self.status = 'REJECT'
        self.reason = reason
        return self

    def check_auth(self, params):

        override = PolicyAuthorizationOverride.objects.match(self.customer, params, cluster=self.cluster)
        if override:
            return self.override(override.settings_override or {})

        authorization = PolicyAuthorization.objects.match(self.customer, params, cluster=self.cluster)

        if authorization:
            authorization.use()
            return self.override(authorization.settings_override or {})

        self.reject('Conference requires authorization')
        return False

    def clean_result(self, response: Mapping[str, Any]):
        context = {
            'cluster': self.cluster,
        }
        return clean_pexip_response(response, context)

    def get_response_data(self):
        if self.status in ('REJECT', 'REJECT_AUTH'):
            return {'status': 'success', 'action': 'reject', '_reason': self.reason}
        assert self.status == 'OK'

        result = json.loads(self.conference.full_data or '{}') if self.conference else {}

        if not result and not self.overrides:
            return self.clean_result(self.fallback_response)  # let pexip do everything

        if self.overrides:
            for o in self.overrides:
                if any(str(v).startswith('/') for v in o.values()):  # regexp
                    cur = o.copy()
                    for k, v in cur.items():
                        match, result[k] = match_regexp(v, self.params.get(k, result.get(k)))
                else:
                    result.update(o)

        if not result.get('name'):
            return self.clean_result(
                self.fallback_response
            )  # not enough data to return full result. TODO: log

        return self.clean_result(
            {
                'status': 'success',
                'action': 'continue',
                'result': result,
            }
        )

    def get_httpresponse(self):
        data = self.get_response_data()
        return JsonResponse(data or PEXIP_DEFAULT_RESPONSE)


def clean_pexip_response(
    response: Mapping[str, Any], context: Mapping[str, Any]
) -> Mapping[str, Any]:
    """
    Clean full pexip policy response. Pexip does not log any validation errors,
    instead it just silently drops the policy response
    """

    if not response.get('result'):
        return response

    cleaned = clean_pexip_response_result(response['result'], context)

    result: Dict[str, Any] = {
        **response,
        'result': cleaned,
    }
    result.setdefault('_cleaned_result', [])
    result['_cleaned_result'].extend(k for k in response['result'] if k not in cleaned)
    return result


def clean_pexip_response_result(
    result: Mapping[str, Any], context: Mapping[str, Any]
) -> Mapping[str, Any]:

    """Clean result part of pexip policy response"""

    cluster: Optional[Cluster] = context.get('cluster')

    cleaned = {k: v for k, v in result.items() if v not in (None, '')}
    if 'tag' in cleaned and 'service_tag' not in cleaned:
        cleaned['service_tag'] = cleaned.pop('tag')

    if 'tag' not in cleaned and 'service_tag' not in cleaned:
        # FIXME empty tag works currently, but a generated service_tag is probably better
        cleaned['tag'] = ''

    from datastore.models import pexip as ds

    ivr_theme_id = None

    if isinstance(cleaned.get('ivr_theme'), dict):
        if cleaned['ivr_theme'].get('name'):
            cleaned['ivr_theme_name'] = cleaned['ivr_theme']['name']
        else:
            ivr_theme_id = cleaned['ivr_theme'].get('id')

    if 'ivr_theme' in cleaned:
        try:
            ivr_theme_id = ivr_theme_id or int(cleaned['ivr_theme'].strip('/').split('/')[-1])
            theme_name = ds.Theme.objects.filter(tid=ivr_theme_id, provider=cluster).values_list(
                'name', flat=True
            )[0]
            cleaned['ivr_theme_name'] = theme_name
        except (AttributeError, ValueError, KeyError, IndexError):
            cleaned.pop('ivr_theme')

    return cleaned
