from datetime import datetime
from typing import Union, TYPE_CHECKING, Optional

from ipaddress import IPv4Address, IPv6Address

from django.db.models.fields import GenericIPAddressField, CharField, AutoField, DateTimeField
from django.db.models.fields.related import ForeignKey

if TYPE_CHECKING:
    from provider.models.provider import Cluster
    from customer.models import Customer


class ProviderAPICompatible:

    pk: Optional[int]
    id: Optional[Union[int, AutoField]]

    api_host: Union[str, CharField]
    ip: Union[IPv4Address, IPv6Address, str, GenericIPAddressField]
    hostname: str

    cluster_id: Optional[int]
    cluster: Union['ProviderAPICompatible', 'Cluster', None, ForeignKey]

    session_id: Union[str, CharField]
    session_expires: Union[Optional[datetime], DateTimeField]

    def get_api(self, customer: 'Customer' = None, allow_cached_values=False):
        """
        :rtype: RestProviderAPI | BookMeetingProviderAPI
        """
        raise NotImplementedError()

    def get_clustered(self, include_self=True, only_call_bridges=True):
        return [self]
