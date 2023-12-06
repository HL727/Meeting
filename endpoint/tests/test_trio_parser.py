import json
from os import path

from defusedxml.cElementTree import parse as safe_xml_parse
from django.test import TestCase

from ..ext_api.parser import poly_x as polyx_parser

root = path.dirname(path.abspath(__file__))


class TestGroupParser(TestCase):
    def _get_file(self, path):
        return safe_xml_parse(open(root + '/data/' + path)).getroot()

    def _get_plain_file(self, path):
        return open(root + '/data/' + path).read()

    def test_parser(self):

        # TODO correct parsers

        valuespace = polyx_parser.PolyXValueSpaceParser(
            self._get_file('trio_8800/Config/polycomConfig.xsd')
        ).parse()

        status = polyx_parser.PolyXStatusParser(json.dumps({'test.sub.key': 'value'})).parse()

        # TODO export config
        configuration_values = {}
        # configuration_values = poly_group_parser.PolyGroupConfigurationValueParser(
        # self._get_plain_file('trio_8800/exportConfiguration.profile'),
        # ).parse()

        configuration = polyx_parser.PolyXConfigurationParser(
            self._get_file('trio_8800/Config/polycomConfig.xsd'),
            valuespace,
            configuration_values,
        ).parse()

        self.assertTrue(valuespace)
        self.assertTrue(configuration.data)
        self.assertTrue(status.data)
