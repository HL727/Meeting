

from endpoint.tests.base import EndpointBaseTest
from endpoint_branding.models import EndpointBrandingFile, EndpointBrandingProfile

gif = 'data:image/gif;base64,R0lGODlhAQABAIAAAP///wAAACwAAAAAAQABAAACAkQBADs='


class EndpointBrandingTestCase(EndpointBaseTest):

    def setUp(self):
        super().setUp()

        self.profile = EndpointBrandingProfile.objects.create(customer=self.customer, name='test')

    def test_list(self):
        response = self.client.get('/json-api/v1/endpointbranding/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()), 1)

    def test_api_create(self):

        response = self.client.post('/json-api/v1/endpointbranding/', {'name': 'test'})
        self.assertEqual(response.status_code, 201)
        self.assertEqual(len(EndpointBrandingFile.objects.exclude(file='')), 0)

        response = self.client.post('/json-api/v1/endpointbranding/', {'name': 'test', 'files': [
            {'type': EndpointBrandingFile.BrandingType.Background, 'file': gif}
        ]}, format='json')
        self.assertEqual(response.status_code, 201)
        self.assertEqual(len(EndpointBrandingFile.objects.exclude(file='')), 1)

    def test_api_update(self):

        response = self.client.patch('/json-api/v1/endpointbranding/{}/'.format(self.profile.pk), {'name': 'test', 'files': [
            {'type': EndpointBrandingFile.BrandingType.Background, 'file': gif}
        ]}, format='json')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(EndpointBrandingFile.objects.exclude(file='')), 1)
