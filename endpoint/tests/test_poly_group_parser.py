import json
from os import path

from defusedxml.cElementTree import parse as safe_xml_parse, fromstring as safe_xml_fromstring
from django.test import TestCase

from ..ext_api.parser import poly_group as parser
from ..ext_api.parser import poly_x as polyx_parser

root = path.dirname(path.abspath(__file__))


class TestGroupParser(TestCase):
    def _get_file(self, path):
        # return safe_xml_parse(open(root + '/data/' + path)).getroot()
        return safe_xml_fromstring(open(root + '/data/' + path).read())

    def _get_plain_file(self, path):
        return open(root + '/data/' + path).read()

    def test_parser(self):

        valuespace = polyx_parser.PolyXValueSpaceParser(
            self._get_file('group500/Config/group500polycomConfig.xsd')
        ).parse()

        status = polyx_parser.PolyXStatusParser(json.dumps({'test.sub.key': 'value'})).parse()

        configuration_values = parser.PolyGroupConfigurationValueParser(
            self._get_plain_file('group500/exportConfiguration.profile'),
        ).parse()

        configuration = polyx_parser.PolyXConfigurationParser(
            self._get_file('group500/Config/group500polycomConfig.xsd'),
            valuespace,
            configuration_values,
        ).parse()

        # self.assertTrue(valuespace) # TODO ignore for now
        self.assertTrue(configuration.data)
        self.assertTrue(status.data)
