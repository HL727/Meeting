from io import BytesIO
from os import path

from rest_framework.test import APITestCase
from django.contrib.auth.models import User

root = path.dirname(path.abspath(__file__))


class TestExcelAPIViews(APITestCase):

    def setUp(self):
        self.user = User.objects.create_user(username='test', password='test')
        self.client.login(username='test', password='test')

    def test_xls_input(self):

        data = {
            'file': open(path.join(root, 'data', 'testfile.xls'), 'rb'),
        }
        response = self.client.post('/json-api/v1/excel/read/', data=data)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()), 10)
        self.assertEqual(response.json()[2], [1,2,3,'a','b','c'])

    def test_xlsx_input(self):

        data = {
            'file': open(path.join(root, 'data', 'testfile.xlsx'), 'rb'),
        }
        response = self.client.post('/json-api/v1/excel/read/', data=data)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()), 10)
        self.assertEqual(response.json()[2], [1,2,3,'a','b','c'])

    def test_xlxs_output(self):

        data = {
            'rows': [
                [1, 2, 3, 4, 5, 6],
                [1, 2, 3, 4, 5, 6],
            ]
        }
        response = self.client.post('/json-api/v1/excel/write/', data=data, format='json')

        self.assertEqual(response.status_code, 200)

        from openpyxl import load_workbook
        wb = load_workbook(BytesIO(response.content))
        rows = list(wb.active.rows)
        self.assertEqual(sum(1 for x in rows), 2)
        self.assertEqual([c.value for c in rows[1]], data['rows'][1])


