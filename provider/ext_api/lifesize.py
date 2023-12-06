import requests
from django.utils.timezone import now
from ..exceptions import AuthenticationError, ResponseError
from datetime import timedelta

import json
from .base import ProviderAPI, BookMeetingProviderAPI

import logging
logger = logging.getLogger(__name__)


class LifeSizeAPI(BookMeetingProviderAPI, ProviderAPI):

    def login(self, force=False):

        if self.provider.has_session and not force:
            return True

        s = requests.Session()
        s.verify = self.verify_certificate

        login_url = 'https://%s/accounts/login/' % self.ip
        response = s.get(login_url)

        csrf_token = response.cookies['csrftoken']

        data = {
            'csrfmiddlewaretoken': csrf_token,
            'username': self.provider.username,
            'password': self.provider.password,
        }

        response = s.post(login_url, data, allow_redirects=False, headers={'Referer': login_url})
        if not response.headers.get('location'):
            raise AuthenticationError(response.text)
        else:

            response = s.get('https://%s/uvcmcu/rest/new' % self.ip, verify=self.verify_certificate)
            json_response = response.json()

            if not json_response.get('session'):
                raise AuthenticationError(response.text)

            self.provider.session_id = json_response['session']
            self.provider.session_expires = now() + timedelta(hours=12)
            self.provider.save()

        return True

    def get_url(self, path=None):
        if path:
            raise ValueError('No path should be given to lifesize!')
        return '%s/uvcmcu/rest/request/%s' % (self.get_base_url(), self.provider.session_id)

    def check_login_status(self, response):
        if '/accounts/login/' in response.headers.get('location', ''):
            raise AuthenticationError()
        try:
            json_data = response.json()
        except Exception:
            pass
        else:
            if json_data.get('_rv') == -1 and json_data.get('message') == 'No such session':
                raise AuthenticationError(response.text)

    def get_data(self, meeting, **kwargs):
        override_function = getattr(LifeSizeAPI, 'override_get_data', None)
        if override_function:
            return override_function(self, meeting)

        return {
            'event': meeting.get_ical_file_contents(),
            'conferenceId': meeting.provider_ref2,
            'transId': meeting.pk,  # TODO unique id per request
        }

    def book(self, meeting, uri=None):

        if meeting.provider_ref2:
            uuid = meeting.provider_ref2
        else:
            data = {
                'call': 'Scheduler_getUUID',
                'params': {},
            }
            response = self.post('', json.dumps(data))

            uuid = response.json().get('buffer')
            if not uuid:
                raise ResponseError('uuid not in response: %s' % response.text, response)
            meeting.provider_ref2 = uuid

        if meeting.provider_ref:
            conferenceid = meeting.provider_ref
        else:
            data = {
                'call': 'Scheduler_getNextConferenceIdLong',
                'params': {},
            }
            response = self.post('', json.dumps(data))

            conferenceid = response.json().get('conferenceId')
            if not conferenceid:
                raise ResponseError('conferenceid not in response: %s' % response.text, response)

            meeting.provider_ref = conferenceid

        data = {
            'call': 'Scheduler_saveEventLongStrict',
            'params': self.get_data(meeting),
        }

        result = self.post('', json.dumps(data)).json()

        if result.get('_rv') >= 0:

            meeting.activate()
        else:
            data = {'call': 'Scheduler_getSaveErrorAsString', 'params': {'saveError': result.get('_rv')}}
            result = self.post('', json.dumps(data))
            raise ResponseError(result.json().get('buffer'), result)

        return result

    def get_info(self, meeting):

        if not meeting.backend_active:
            return

        data = {
            'call': 'Scheduler_getEventByUid',
            'params': {'uid': meeting.provider_ref2},
        }

        result = self.post('', json.dumps(data))
        return result.json()

    def unbook(self, meeting):

        if not meeting.backend_active:
            return

        if meeting.existing_ref:
            meeting.deactivate()
            return

        data = {
            'call': 'Scheduler_removeEvents',
            'params': {'uids': meeting.provider_ref2},
        }
        result = self.post('', json.dumps(data))

        if result.json().get('_rv') >= 0:
            meeting.deactivate()
        return result

    def webinar(self, meeting):
        raise NotImplementedError('Lifesize customers does not support webinar yet!')

