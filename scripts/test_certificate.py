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
    studio_endpoint = Endpoint.objects.filter(manufacturer=Endpoint.MANUFACTURER.POLY_STUDIO_X).first().get_api()
    with open('multi_ca_certificates.pem', 'r') as certfile:
        certificate_content = certfile.read()

    # print(group_endpoint.set_configuration([{'key': ('Audio', 'DefaultVolume'), 'value': '10'}, ]))
        print(certificate_content)
        print(studio_endpoint.add_ca_certificates(certificate_content))
