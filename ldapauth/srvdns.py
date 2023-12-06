from time import monotonic
from urllib.parse import urlparse

import dns.resolver
from django.conf import settings
from sentry_sdk import capture_exception


class LdapSrvPool:
    def __init__(self, proto: str, uri: str):
        self.proto = proto

        if '//' not in uri:
            uri = '//{}'.format(uri)
        self.uri_parts = urlparse(uri)
        self.cache = (0, [])

    def resolve_servers(self, proto=None):

        if self.cache[0] and self.cache[0] > monotonic():
            return self.cache[1]

        if proto is None:
            proto = self.proto

        if ':' in self.uri_parts.netloc:
            return [self.uri_parts.netloc]  # already contains port. Treat as final

        result = [self.uri_parts.netloc]
        try:
            answer = dns.resolver.resolve(
                '_{}._tcp.{}'.format(proto, self.uri_parts.hostname),
                rdtype=dns.rdatatype.SRV,
                lifetime=3,
            )
            result = ['{}:{}'.format(str(srv.target).rstrip('.'), srv.port) for srv in answer]
        except dns.resolver.NXDOMAIN:
            if proto == 'ldaps':
                return [s.replace(':389', '') for s in self.resolve_servers('ldap')]
        except Exception:
            if settings.DEBUG or settings.TEST_MODE:
                raise
            self.cache = (monotonic() + 60 * 60, [self.uri_parts.netloc])

        self.cache = (monotonic() + 3, result)
        return result

    @property
    def uris(self):
        try:
            servers = self.resolve_servers()
        except Exception:
            capture_exception()
            servers = [self.uri_parts.netloc]
        return ['{}://{}'.format(self.proto, server) for server in servers]

    def __str__(self):
        return ' '.join(self.uris)

    def __call__(self, request=None):
        return str(self)

    def __contains__(self, item):
        return item in str(self)
