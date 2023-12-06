from typing import Type

from django.contrib.auth.models import User
from django.db import connection
from address.models import AddressBook, Group, Item, EPMSource, CMSUserSource, ManualSource, CMSCoSpaceSource, \
    VCSSource, ManualLinkSource, Source
from conferencecenter.tests.base import ConferenceBaseTest
from endpoint.models import Endpoint
from endpoint.consts import CONNECTION
from organization.models import OrganizationUnit
from customer.models import Customer

def run():
    studioX_api = Endpoint.objects.filter(manufacturer=Endpoint.MANUFACTURER.POLY_HDX).first().get_api()
    # studioX_api.login()
    # studioX_api.set_password('admin', 'admin')
    # result = studioX_api.install_firmware('update_server_url')
    # result = studioX_api.set_configuration([{ 'key': ['device', 'auth', 'localAdminPassword', 'set'], 'value': '1' }])
    result = studioX_api._fetch_status_data_file()
    # print(result)
    print(result.content)
    # result = studioX_api.test_login()