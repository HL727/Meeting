from __future__ import annotations

from datetime import timedelta
from typing import TYPE_CHECKING, Dict, Optional

from django.conf import settings
from django.db.models import Q
from django.utils.timezone import now

from endpoint import consts
from provider.exceptions import AuthenticationError, ResponseError
from shared.utils import partial_update

if TYPE_CHECKING:
    from customer.models import Customer
    from endpoint.models import Endpoint


class EndpointEventBase:
    def __init__(self, customer=None, endpoint_secret=None) -> None:

        self.customer = customer
        self.endpoint_secret = endpoint_secret

    def get_identification(self) -> Dict[str, str]:
        raise NotImplementedError()

    def get_endpoint(self) -> Endpoint:
        from endpoint.models import Endpoint, all_endpoint_secrets

        identification = self.get_identification()

        mac_address = identification.get('MACAddress', '').upper()
        serial = identification.get('SerialNumber')

        secrets = all_endpoint_secrets()

        extra_filter = {}
        if self.endpoint_secret:
            extra_filter['event_secret_key'] = self.endpoint_secret
        elif settings.EPM_EVENT_ENDPOINT_SECRET:
            raise Endpoint.DoesNotExist()
        if self.customer:
            extra_filter['customer'] = self.customer

        endpoint_id = secrets.get(mac_address) or secrets.get(serial)
        if endpoint_id:
            try:
                return Endpoint.objects.filter(pk=endpoint_id, **extra_filter)[0]
            except IndexError:
                pass

        extra_filter.pop('event_secret_key', '')

        endpoint = (
            Endpoint.objects.filter(mac_address=mac_address)
            .filter(Q(serial_number='') | Q(serial_number__iexact=serial))
            .filter(**extra_filter)
            .first()
        )

        if not endpoint:
            raise Endpoint.DoesNotExist()
        if self.endpoint_secret and endpoint.event_secret_key != self.endpoint_secret:
            raise AuthenticationError('Invalid secret key')

        return endpoint

    def _handle_ip_change(self, endpoint: Endpoint) -> None:
        if endpoint.track_ip_changes:
            new_ip = self.get_identification().get('IPAddress')
            if new_ip and endpoint.ip != new_ip:
                endpoint.ip = new_ip
                endpoint.save(update_fields=['ip'])

    def handle_event(self):
        pass

    def create_endpoint(self, customer: Customer, request_ip: Optional[str] = None) -> Endpoint:
        from endpoint.models import CustomerAutoRegisterIpNet, CustomerSettings, Endpoint
        from endpointproxy.models import EndpointProxy

        identification = self.get_identification()
        settings = CustomerSettings.objects.get_for_customer(customer)

        proxy = EndpointProxy.objects.get_for_ip(request_ip, customer=customer) if request_ip else None

        ip_net = None
        if request_ip:
            ip_net = CustomerAutoRegisterIpNet.objects.get_for_ip(request_ip, customer=customer)

        if not settings.use_standard_password and not ip_net:
            connection_type = Endpoint.CONNECTION.INCOMING
        elif not settings.use_standard_password:
            connection_type = Endpoint.CONNECTION.PASSIVE
        elif proxy:
            connection_type = Endpoint.CONNECTION.PROXY
        else:
            connection_type = Endpoint.CONNECTION.DIRECT

        endpoint = Endpoint.objects.create(customer=customer, ip=identification.get('IPAddress'),
                                           username='admin', mac_address=identification.get('MACAddress') or '',
                                           title=identification.get('SystemName') or '',
                                           serial_number=identification.get('SerialNumber') or '',
                                           connection_type=connection_type,
                                           proxy=proxy,
                                           manufacturer=Endpoint.MANUFACTURER.CISCO_CE,
                                           password='__try__' if settings.use_standard_password else ''
                                           )

        endpoint.set_status(status=Endpoint.STATUS.ONLINE, software_version=identification.get('SWVersion') or '')

        if not settings.use_standard_password:
            return endpoint

        try:
            endpoint.update_all_data()
        except AuthenticationError:
            endpoint.connection_type = Endpoint.CONNECTION.PASSIVE
        except ResponseError:
            if request_ip:
                try:
                    endpoint.ip = request_ip
                    endpoint.update_all_data()
                except (ResponseError, AuthenticationError):
                    endpoint.ip = identification.get('IPAddress')
                    endpoint.connection_type = Endpoint.CONNECTION.PASSIVE
                    endpoint.save()

        return endpoint

    def get_self_type(self):
        return ''


class PassiveEndpointProvisionEvent(EndpointEventBase):
    def handle_event(self):
        endpoint = self.get_endpoint()
        status_kwargs = (
            {'status': consts.STATUS.ONLINE}
            if endpoint.status.status != consts.STATUS.IN_CALL
            else {}
        )
        endpoint.set_status(ts_last_provision=now(), **status_kwargs)
        self._handle_ip_change(endpoint)
        return endpoint


class TMSEventBase(EndpointEventBase):

    identification_path = './Identification'

    def __init__(self, xml: bytes, customer=None, endpoint_secret=None) -> None:
        from endpoint.ext_api.cisco_ce import CiscoCEProviderAPI

        self.root = CiscoCEProviderAPI.load_status_xml(xml)
        self.ns = {'s': 'http://www.tandberg.net/2004/11/SystemManagementService/'}
        super().__init__(customer=customer, endpoint_secret=endpoint_secret)

    def get_identification(self):

        result = {}
        ns = self.ns

        identification = self.root.find(self.identification_path, ns)
        if identification is not None:
            for node in identification:
                result[node.tag.split('}')[-1]] = (node.text or '').strip()

        if not any(result.values()):
            raise AuthenticationError('Empty identification')
        return result


class TMSEvent(TMSEventBase):

    identification_path = './Identification'

    def get_event_path(self) -> str:

        if self.root.tag in ('Event', 'Status', 'Configuration'):
            for node in self.root:
                if not node.tag == 'Identification':
                    return '{}/{}'.format(self.root.tag, node.tag)

        return self.root.tag

    def get_event_type(self) -> str:
        if self.root.tag == 'Event':
            for node in self.root:
                if node.tag != 'Identification':
                    return node.tag
        return self.root.tag

    def handle_event(self) -> Endpoint:
        from room_analytics.parse import store_cisco_ce

        endpoint = self.get_endpoint()

        event_type = self.get_event_type()

        store_cisco_ce(self.root, endpoint)

        self._handle_ip_change(endpoint)

        if not endpoint.status.software_version and self.get_identification().get('SWVersion'):
            endpoint.set_status(software_version=self.get_identification()['SWVersion'])

        if not endpoint.title and self.get_identification().get('SystemName'):
            partial_update(endpoint, {'title': self.get_identification()['SystemName']})

        def _update_call_status(is_in_call: bool):

            if is_in_call:
                endpoint.set_status(status=consts.STATUS.IN_CALL, ts_last_event=now())
            else:
                endpoint.set_status(status=consts.STATUS.ONLINE, ts_last_event=now())

        was_in_call = endpoint.is_in_call

        if event_type == 'Status' and self.root.find('./Call') is not None:
            call_status = self.root.findtext('./Call/Status') or ''
            _update_call_status(call_status == 'Connected')
        else:
            endpoint.set_status(status=consts.STATUS.ONLINE, ts_last_event=now())

        if event_type in ('CallDisconnect', 'CallSuccessful'):
            _update_call_status(event_type == 'CallSuccessful')

            endpoint.get_api().get_statistics_event_parser().parse_call_event(self.root.find('./{}'.format(event_type)))

        if event_type in ('CallDisconnect',):
            if endpoint.has_direct_connection:
                from endpoint.tasks import update_endpoint_statistics

                update_endpoint_statistics.delay(endpoint.pk, limit=2)

        if event_type in ('BootEvent', 'Standby') or was_in_call:  # Standby really needed?
            if endpoint.meetings.filter(ts_stop__gt=now() - timedelta(days=7)):
                from endpoint import tasks

                tasks.sync_endpoint_bookings_locked_delay(endpoint.pk)

        if event_type == 'BootEvent':
            from endpoint import tasks

            tasks.update_all_data(endpoint.pk)

        return endpoint


class TMSSoapEvent(TMSEventBase, PassiveEndpointProvisionEvent):

    identification_path = './/s:PostEvent/s:Identification'

    def get_event_type(self) -> Optional[str]:

        event = self.root.findtext('.//s:PostEvent/s:Event', None, self.ns)
        return event


class TMSPostedDocumentEvent(TMSEventBase):

    identification_path = './Identification'

    def get_event_type(self):

        return (self.root.findtext('./Location') or '').lstrip('/') or 'PostedDocument'

    def handle_event(self) -> Endpoint:
        endpoint = self.get_endpoint()
        self._handle_ip_change(endpoint)
        return endpoint
