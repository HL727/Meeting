import ipaddress
from typing import List, Union, Optional, Sequence

from django.conf import settings

IpList = List[Union[ipaddress.IPv4Address, ipaddress.IPv6Address]]
NetworkList = List[Union[ipaddress.IPv4Network, ipaddress.IPv6Network]]


class XForwardedForMiddleware:
    def __init__(self, get_response=None):
        self.get_response = get_response
        self.last_trusted_ips = None
        self.trusted_ips = self.load_trusted_ips()

    def load_trusted_ips(self):
        if self.last_trusted_ips != settings.TRUSTED_IPS:
            self.trusted_ips = RealIPLookup.load_trusted_ips(settings.TRUSTED_IPS)
            self.last_trusted_ips = settings.TRUSTED_IPS
        return self.trusted_ips

    def populate_real_ip(self, request):

        # TODO lookup REMOTE_ADDR to see that it is actually traefik?
        self.load_trusted_ips()

        real_ip = RealIPLookup(
            self.trusted_ips,
            request.META.get('HTTP_X_REAL_IP'),
            request.META.get('HTTP_X_FORWARDED_FOR'),
        ).get_real_ip()

        if real_ip:
            request.META['ORIG_REMOTE_ADDR'] = request.META['REMOTE_ADDR']
            request.META['REMOTE_ADDR'] = str(real_ip)

    def __call__(self, request):
        self.populate_real_ip(request)
        return self.get_response(request)


class RealIPLookup:
    def __init__(
        self,
        trusted_ips: Union[Sequence[str], NetworkList] = None,
        x_real_ip: Optional[str] = '',
        x_forwarded_for: Optional[str] = '',
    ):
        self.trusted_ips: NetworkList = self.load_trusted_ips(trusted_ips)
        self.x_forwarded_for = x_forwarded_for or ''
        self.x_real_ip = x_real_ip or ''

    @classmethod
    def load_trusted_ips(
        cls,
        trusted_ips: Union[
            Sequence[str], Sequence[Union[ipaddress.IPv4Network, ipaddress.IPv6Network]]
        ],
    ) -> NetworkList:
        if trusted_ips and not isinstance(
            trusted_ips[0], (ipaddress.IPv4Network, ipaddress.IPv6Network)
        ):
            return [ipaddress.ip_network(net) for net in trusted_ips]

        return trusted_ips or []

    def get_real_ip(self) -> Optional[Union[ipaddress.IPv4Address, ipaddress.IPv6Address]]:
        valid_ips = self.get_valid_real_ips()
        if valid_ips:
            return valid_ips[0]
        return None

    def get_valid_real_ips(self) -> IpList:

        forwarded = self.get_trusted_forwarded_for(self.x_forwarded_for)

        if not self.x_real_ip:
            return forwarded

        # X-Real-IP has precedence if not the last X-Forwarded-For
        try:
            x_real_ip = ipaddress.ip_address(self.x_real_ip)
        except ValueError:
            pass
        else:
            if not forwarded or x_real_ip != forwarded[-1]:
                return [x_real_ip] + forwarded

        return forwarded

    def get_trusted_forwarded_for(self, x_forwarded_for: str) -> IpList:

        if not self.trusted_ips or not (x_forwarded_for or '').strip():
            return []

        try:
            forwarded = [
                ipaddress.ip_address(addr.strip()) for addr in x_forwarded_for.strip().split(',')
            ]
        except ValueError:
            return []

        trusted = None

        for i, ip in enumerate(reversed(forwarded)):
            if not any(ip in trusted for trusted in self.trusted_ips):
                break

            trusted = i

        if trusted is None:
            return []
        return forwarded[-trusted - 2 :]

