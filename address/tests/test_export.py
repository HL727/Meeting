from address.tests.test_sync import AddressBookTestBase


class AddressBookExportTestCase(AddressBookTestBase):

    def test_export(self):
        self.book.export()
        self.client.get('/json-api/address_book/{}/export/'.format(self.book.id))
