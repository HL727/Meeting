from os import path

from ..consts import MANUFACTURER
from .test_cisco_ce import TaskTestCase, TestAPIViews, TestPassiveEndpoint

root = path.dirname(path.abspath(__file__))


class PolyStudioXMixin:
    manufacturer = MANUFACTURER.POLY_STUDIO_X

    def setUp(self):
        super().setUp()
        self.endpoint.manufacturer = self.manufacturer
        self.endpoint.save()


class TestStudioXAPIViews(PolyStudioXMixin, TestAPIViews):
    def test_update_basic_data(self):
        super().test_update_basic_data()

    def test_api_list(self):
        super().test_api_list()

    def test_api_get_status(self):
        super().test_api_get_status()

    def test_api_get_status_data(self):
        super().test_api_get_status_data()

    def test_api_get_configuration_data(self):
        super().test_api_get_configuration_data()

    def test_api_call_history(self):
        super().test_api_call_history()

    def test_api_get_dial_info(self):
        super().test_api_get_dial_info()

    def test_provision_status(self):
        super().test_provision_status()

    def test_api_get_commands_data(self):
        super().test_api_get_commands_data()

    def test_api_get_valuespace_data(self):
        super().test_api_get_valuespace_data()


class TestStudioXPassiveEndpoint(PolyStudioXMixin, TestPassiveEndpoint):
    def setUp(self):
        super().setUp()
        self.endpoint.connection_type = self.endpoint.CONNECTION.PASSIVE
        self.endpoint.save()

    def test_all(self):
        super().test_all()


class PolyStudioTaskTestCase(PolyStudioXMixin, TaskTestCase):
    def test_update_status(self):
        super().test_update_status()
