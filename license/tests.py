import json
from typing import List

from django.test import TestCase

from license.models import License
from license.validator import LicenseValidator


class LicenseTest(TestCase):
    def test_license(self):

        value = '''{"addons": [
                    {
                        "type": "epm:endpoint",
                        "value": 100,
                        "valid_from": "2021-02-09",
                        "valid_until": "2023-02-09"
                    },
                    {
                        "type": "epm:endpoint_addon",
                        "value": 50,
                        "valid_from": "2021-02-09",
                        "valid_until": "2023-02-09"
                    }
                ], "flags": {
                }}'''

        license = License.objects.sync_active(value)

        flags = license.validator.get_flags()
        self.assertEqual(flags, {})

        full = license.validator.parse_full()
        with self.assertRaises(TypeError):
            full['settings'][1] = 1

    def test_sync_settings(self):
        License.objects.sync_from_settings()

    def _get_validator(self, addons: List[dict]):
        return LicenseValidator(json.dumps({'addons': addons}))

    def test_addons(self):

        validator = self._get_validator(
            [
                {
                    "type": "epm:endpoint",
                    "value": 100,
                    "valid_from": "2021-02-09",
                    "valid_until": "2023-02-09",
                }
            ]
        )
        self.assertEqual(validator.parse_full().get_quantity('epm:endpoint'), 100)

        self.assertEquals(validator.parse_full().get_status('epm:endpoint').status, 'ok')
        self.assertEquals(validator.parse_full().get_status('epm:endpoint').allow_another, True)

        validator = self._get_validator(
            [
                {
                    "type": "epm:endpoint",
                    "value": 100,
                    "valid_from": "2021-02-09",
                    "valid_until": "2021-02-09",
                }
            ]
        )
        self.assertEqual(validator.parse_full().get_quantity('epm:endpoint'), 0)
        self.assertEquals(validator.parse_full().get_status('epm:endpoint').status, 'ok')
        self.assertEquals(validator.parse_full().get_status('epm:endpoint').allow_another, False)
