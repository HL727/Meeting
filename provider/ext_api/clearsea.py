import requests
from django.utils.timezone import now
from ..exceptions import AuthenticationError, ResponseError
from datetime import timedelta
from sentry_sdk import capture_exception
from django.utils.translation import gettext_lazy as _

import logging
logger = logging.getLogger(__name__)

import json
from .base import ProviderAPI


class ClearSeaAPI(ProviderAPI):

    def get_base_url(self):
        return 'https://%s:8181' % self.provider.hostname

    def login(self, force=False):

        if self.provider.has_session and not force:
            return True

        response = requests.get('https://%s:8181/api/v1/access-token/' % self.provider.hostname, params={
            'grant_type': 'password',
            'username': self.provider.username,
            'password': self.provider.password,
        }, verify=self.verify_certificate)

        try:
            session_id = response.json().get('access_token')
        except Exception:
            session_id = None

        if not session_id:
            raise AuthenticationError(response.text)
        else:
            self.provider.session_id = session_id
            self.provider.session_expires = now() + timedelta(hours=10)
            self.provider.save()
        return True

    def get_data(self, meeting):
        override_function = getattr(ClearSeaAPI, 'override_get_data', None)
        if override_function:
            return override_function(self, meeting)
        return {}

    def get_url(self, path):
        return '%s/api/v2/rest/%s' % (self.get_base_url(), path.lstrip('/'))

    def _response_error(self, message, response):
        raise ResponseError('%s: %s (%s)' % (message, response.status_code, response.text), response)

    def book(self, csea_instance, uri=None):

        meeting = csea_instance.meeting
        assert meeting.provider_ref

        data = {
            'type': 'User',
            'userID': csea_instance.username,
            'description': 'Clearsea user [%s]' % csea_instance.pk,
        }

        if csea_instance.provider.groupname:
            data['groupName'] = csea_instance.provider.groupname

        if self.customer.clearsea_group_name:
            data['groupName'] = self.customer.clearsea_group_name

        response = self.post('/service/accounts/', json.dumps(data))

        if response.status_code == 201:
            # get extension
            response = self.get('/service/accounts/', params={'userID': csea_instance.username})
            if not response.status_code == 200:
                return self._response_error(_('Unable to get extension of user'), response)

            try:
                csea_instance.extension = response.json()['results'][0]['extension']
                csea_instance.save()
            except Exception:
                return self._response_error(_('Unable to get extension of user'), response)
        else:
            try:
                if 'A user already exists' in response.json().get('errorMessage'):
                    if csea_instance.increase_index():
                        return self.book(csea_instance)
                    else:
                        return self._response_error('Too many dulicated users with prefix %s' % csea_instance.username, response)
            except ValueError:
                pass
            return self._response_error('Invalid code when creating clearsea-user', response)

        data = {
            'userID': data['userID'],
            'dialString': meeting.dialstring,
        }
        response = self.post('/service/endpoints/', json.dumps(data))

        if response.status_code == 201:
            csea_instance.activate()
        else:
            return self._response_error('Invalid code when registering endpoint', response)

        return response

    def unbook(self, csea_instance):

        if not csea_instance.backend_active:
            return

        response = self.delete('/service/accounts/%s' % csea_instance.username)

        if response.status_code in (204, 404):
            csea_instance.deactivate()
        else:
            return self._response_error('Invalid code when deleting clearsea-user', response)
        return response

    def get_info(self, csea_instance):

        if not csea_instance.backend_active:
            return None

        response = self.get('/service/accounts/%s' % csea_instance.username)
        result = response.json()
        if result:

            endpoints = self.get('/service/endpoints', params={'userID': csea_instance.username})
            result['endpoints'] = endpoints.json().get('results')
        return result

    def check_login_status(self, response):
        if response.status_code == 401:
            raise AuthenticationError(response.text, response)

    def get_params(self):
        return {
            'access_token': self.provider.session_id,
        }

    @staticmethod
    def unbook_expired():
        last_day = now() - timedelta(days=2)

        from provider.models.provider_data import ClearSeaAccount

        unbooked = 0

        for c in ClearSeaAccount.objects.filter(backend_active=True, meeting__backend_active=False, meeting__ts_stop__lt=last_day).select_related('meeting', 'provider', 'meeting__customer'):

            try:
                c.provider.get_api(c.meeting.customer).unbook(c)
            except Exception:
                capture_exception()
            else:
                unbooked += 1

        return unbooked



