from ..exceptions import ResponseError, AuthenticationError

import json
from .base import ProviderAPI

import logging
logger = logging.getLogger(__name__)


MAX_ITEMS = 10000


class SeeviaAPI(ProviderAPI):

    def request(self, *args, **kwargs):
        kwargs['auth'] = (self.provider.username, self.provider.password)
        kwargs['headers'] = {
                'Accept': 'application/json',
                'Content-Type': 'application/json',
                }

        return super().request(*args, **kwargs)

    def login(self, force=False):

        return True

    def check_login_status(self, response):
        if '/accounts/login/' in response.headers.get('location', '') or response.status_code in (401, 403):
            raise AuthenticationError(response.text)

    def check_response_errors(self, response):
        super().check_response_errors(response)
        if response.status_code == 404:
            raise self.error('Resource not found', response)

    def get_base_url(self):
        return 'https://%s' % self.provider.hostname

    def get_url(self, path):
        return '%s/%s' % (self.get_base_url(), path.lstrip('/'))

    def list_dir(self, dir_id):
        """
        returns all folders and, if less than 100, all items.
        pagination is broken after 50 pages, use self.get_contacts to get all contacts
        """

        result_folders, result_entries = [], []

        for i in range(100 // 20):
            response = self.get('organizations/{}'.format(dir_id), params={'page': i + 1})
            objects = response.json()['entries']

            folders = [e for e in objects if e.get('type') in ('organization', 'folder')]
            entries = [self._populate_contact_numbers(e) for e in objects if e.get('type') not in ('organization', 'folder')]

            result_folders.extend(folders)
            result_entries.extend(entries)

            if len(objects) < 20:  # complete pages, return entries
                return result_folders, result_entries

        return result_folders, None

    def _populate_contact_numbers(self, entry):
        if not entry.get('numbers'):
            return entry

        for number in entry['numbers']:
            if number.get('type') == 'sip' and 'sip' not in entry:
                entry['sip'] = number.get('uri')
            elif number.get('type') == 'h323' and 'h323' not in entry:
                entry['h323'] = number.get('uri')
        return entry

    def get_contacts(self, dir_id):
        """returns all contacts"""
        response = self.get('organizations/{}/contacts'.format(dir_id))

        entries = []

        for entry in response.json()['entries']:
            if entry.get('type') in ('organization', 'folder'):
                continue

            self._populate_contact_numbers(entry)
            entries.append(entry)

        return entries

    def get_items(self, dir_id):

        folders, entries = self.list_dir(dir_id)
        if entries is None:
            entries = self.get_contacts(dir_id)

        return folders, entries

    def recursive_get(self, dir_id):
        "folder, children, items"

        def _rec(folder, parent_id):
            folders, entries = self.get_items(parent_id)

            return folder, [_rec(f, f['id']) for f in folders], entries

        return _rec(None, dir_id)

    def create_entry(self, dir_id, name, uri, **kwargs):

        data = {
            'name': name,
            'numbers': [{
                'protocol': 'sip',
                'number': uri,
        }],
            'type': 'meetingroom',
            'visibility': 'usefolderrules',
            'enableQR': False
        }

        data.update(kwargs)

        response = self.post('organizations/{}/contacts'.format(dir_id), data=json.dumps(data))

        if response.status_code not in (201,):
            raise ResponseError('Entry not created: {}'.format(response.text), response)

        return response.json()

    def update_entry(self, id, new_data):

        response = self.post('contacts/{}'.format(id), data=json.dumps(new_data))

        if response.status_code not in (200,):
            raise ResponseError('Entry not updated: {}'.format(response.text), response)

        return response.json()

    def get_entry(self, id):

        response = self.get('contacts/{}'.format(id))

        if response.status_code not in (200,):
            raise ResponseError('Entry not created: {}'.format(response.text), response)

        return response.json()

    def delete_entry(self, id):

        response = self.delete('contacts/{}'.format(id))

        if response.status_code not in (200,):
            raise ResponseError('Entry not deleted: {}'.format(response.text), response)

        return response.json()
