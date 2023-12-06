from __future__ import annotations

from typing import TYPE_CHECKING, Optional, Tuple, List, Iterable, Dict

from django.utils.functional import cached_property

from address.models import AddressBook
from endpoint_data.models import EndpointDataFile, EndpointDataFileBase
from endpoint_provision.models import EndpointTask
from provider.exceptions import AuthenticationError

from .base import EndpointProviderAPI
from .parser.cisco_ce import NestedXMLResult
from .parser.types import Command, ParsedCommandTuple, PathMeta

if TYPE_CHECKING:
    pass

DEFAULT_SESSION_ID = 'basic'


class PolyBaseProviderAPI(EndpointProviderAPI):

    _login = False
    _configuration_buffer = None
    current_user = None

    def get_url(self, path: str):
        return '%s/rest/%s' % (self.get_base_url(), path.lstrip('/'))

    def check_login_status(self, response):
        if response.status_code in (401, 403):
            raise AuthenticationError('Not logged in', response)
        return True

    def get_session(self, **kwargs):
        trio_login = kwargs.pop('trio_login', None)
        session = super().get_session(**kwargs)
        if self.endpoint.session_id and not trio_login:
            if 'Trio' in self.endpoint.product_name:
                session.cookies['session'] = self.endpoint.session_id
            else:
                session.cookies['session_id'] = self.endpoint.session_id
            # session.cookies['session_id'] = self.endpoint.session_id
        return session

    def logout(self, force=False):
        print('Login not Implemented', self.__class__.__name__)

    def format_mac_address(self, mac):
        return self.endpoint.format_mac_address(mac)

    def get_commands_data(
        self, fd: Optional[EndpointDataFile] = None, valuespace: Optional[EndpointDataFile] = None
    ) -> NestedXMLResult[ParsedCommandTuple]:

        if not fd:
            pass  # fd, valuespace = self.get_commands_data_file()

        return self.get_mock_commands()

    def get_mock_commands(self):
        return NestedXMLResult(
            [
                ParsedCommandTuple(
                    'XML',
                    PathMeta(path=['xml']),
                    [],
                    Command(['xml'], {'name': {'type': 'text'}, 'content': {'type': 'text'}}),
                )
            ]
        )

    def get_cached_commands_data_file(
        self,
        allow_similar=False,
    ) -> Tuple[Optional[EndpointDataFileBase], Optional[EndpointDataFileBase]]:

        return None, None

    def get_commands_data_file(
        self, force=False
    ) -> Tuple[EndpointDataFileBase, Optional[EndpointDataFileBase]]:

        return EndpointDataFileBase(), None

    configuration_key_map: Dict[str, str] = {
        # key: polycomConfig.xsd name, value: web interface value
    }

    @cached_property
    def configuration_key_map_reversed(self):
        return {v: k for k, v in self.configuration_key_map.items()}

    def fetch_configuration_values(self, keys: List[str]):
        """
        Fetches all configuration keys and values from api.

        Polycom system uses some internal configuration map between its web interface and
        real name in polycomConfig.xsd, so some keys must be translated using
        cls.configuration_key_map
        """

        translated_keys = [self.configuration_key_map.get(k) or k for k in keys]
        response = self.post('config', {'names': self.remove_redundant_settings(translated_keys)})
        result = {}
        if response.status_code != 200:
            raise self.error('Invalid status', response)

        backwards_configuration_key_map = self.configuration_key_map_reversed
        for item in response.json().get('vars', []):

            if item.get('result') == 'NOERROR':
                real_name = backwards_configuration_key_map.get(item['name']) or item['name']
                result[real_name] = item['value']

        return result

    def remove_redundant_settings(self, keys: Iterable[str]) -> List[str]:
        return list(keys)

    def update_statistics(self, limit=1000):
       raise NotImplementedError()

    @staticmethod
    def get_update_address_book_configuration(address_book: AddressBook):
        # FIXME set ldap directory settings
        raise NotImplementedError()

    def set_address_book(self, address_book: AddressBook, task: EndpointTask = None):
        config = self.get_update_address_book_configuration(address_book)
        if not config:
            raise NotImplementedError()
        return self.set_configuration(config, task=task)

    def set_events(self):

        # FIXME
        raise NotImplementedError()
