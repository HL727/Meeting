from typing import Type

from django.contrib.auth.models import User

from address.models import AddressBook, Group, Item, EPMSource, CMSUserSource, ManualSource, CMSCoSpaceSource, \
    VCSSource, ManualLinkSource, Source
from conferencecenter.tests.base import ConferenceBaseTest
from endpoint.models import Endpoint
from endpoint.consts import CONNECTION
from organization.models import OrganizationUnit
from customer.models import Customer

def run():
    # cisco_endpoint, cisco_created = Endpoint.objects.get_or_create( customer=Customer.objects.first(), ip='172.21.16.10', hostname='172.21.16.10',  api_port=443, track_ip_changes=False, username='admin', password='admin123', connection_type= 1, manufacturer=Endpoint.MANUFACTURER.CISCO_CE, )
    # print(cisco_created)
    # group_endpoint, group_created = Endpoint.objects.get_or_create( customer=Customer.objects.first(), ip='172.21.16.30', hostname='172.21.16.30',  api_port=443, track_ip_changes=False, username='admin', password='admin123', connection_type=CONNECTION.DIRECT, manufacturer=Endpoint.MANUFACTURER.POLY_GROUP, )
    # print(group_endpoint)

    # studiox_endpoint, studiox_created = Endpoint.objects.get_or_create( customer=Customer.objects.first(), ip='172.21.16.35', hostname='172.21.16.35',  api_port=443, track_ip_changes=False, username='admin', password='admin123', connection_type=CONNECTION.DIRECT, manufacturer=Endpoint.MANUFACTURER.POLY_STUDIO_X, )
    # print(studiox_created)
    # cisco_endpoint, cisco_created = Endpoint.objects.get_or_create( customer=Customer.objects.first(), ip='172.21.16.10', hostname='172.21.16.10', api_port=443,  track_ip_changes=False, username='admin', password='admin123', connection_type= 1, manufacturer=Endpoint.MANUFACTURER.CISCO_CE, )
    # print(cisco_created)
    # group_endpoint, group_created = Endpoint.objects.get_or_create( customer=Customer.objects.first(), ip='172.21.16.30', hostname='172.21.16.30', api_port=443, track_ip_changes=False, username='admin', password='admin123', connection_type=CONNECTION.DIRECT, manufacturer=Endpoint.MANUFACTURER.POLY_GROUP, )
    # print(group_endpoint)
    # trio_endpoint, trio_created = Endpoint.objects.get_or_create( customer=Customer.objects.first(), ip='172.21.16.100', hostname='172.21.16.100',  api_port=443, track_ip_changes=False, username='admin', password='admin123', connection_type=CONNECTION.DIRECT, manufacturer=Endpoint.MANUFACTURER.POLY_TRIO, )
    # print(trio_created)
    hdx_endpoint, hdx_created = Endpoint.objects.get_or_create( customer=Customer.objects.first(), ip='172.21.16.102', hostname='172.21.16.102',  api_port=443, track_ip_changes=False, username='admin', password='admin123', connection_type=CONNECTION.DIRECT, manufacturer=Endpoint.MANUFACTURER.POLY_HDX, )
    print(hdx_created)

    # studiox_endpoint, studiox_created = Endpoint.objects.get_or_create( customer=Customer.objects.first(), ip='172.21.16.35', hostname='172.21.16.35', api_port=8525, track_ip_changes=False, username='admin', password='admin123', connection_type=CONNECTION.DIRECT, manufacturer=Endpoint.MANUFACTURER.POLY_STUDIO_X, )
    # print(studiox_created)
    # group_endpoint = Endpoint.objects.filter(manufacturer=Endpoint.MANUFACTURER.POLY_STUDIO_X).first().get_api()

    # # print(group_endpoint.set_configuration([{'key': ('Audio', 'DefaultVolume'), 'value': '10'}, ]))

    # print(group_endpoint.set_configuration([{'key': ['device', 'local', 'language'], 'value': 'ARABIC'}]))
# from rest_framework.test import APIClient

# def test_set_configuration():
#     data = {
#         'settings': [{'key': ['Audio', 'DefaultVolume'], 'value': '10'}, ],
#     }
#     client = APIClient()
#     # response = client.post('http://localhost/json-api/v1/endpoint/1/set_configuration/', data)
#     print("hello")