import json
from os import path

from defusedxml.cElementTree import parse as safe_xml_parse, fromstring as safe_xml_fromstring
from django.test import TestCase

from ..ext_api.parser import poly_x as parser

root = path.dirname(path.abspath(__file__))


class TestPolyStudioParser(TestCase):
    def _get_file(self, path):
        # return safe_xml_parse(open(root + '/data/' + path)).getroot()
        return safe_xml_fromstring(open(root + '/data/' + path).read())

    def test_parser(self):

        valuespace = parser.PolyXValueSpaceParser(
            self._get_file('x30/videocodec/x30polycomConfig.xsd')
        ).parse()

        status = parser.PolyXStatusParser(json.dumps({'test.sub.key': 'value'})).parse()

        configuration_values = parser.PolyXConfigurationValueParser(
            self._get_file('x30/exportConfiguration.cfg'),
        ).parse()

        configuration = parser.PolyXConfigurationParser(
            self._get_file('x30/videocodec/x30polycomConfig.xsd'), valuespace, configuration_values
        ).parse()

        print(valuespace)
        self.assertTrue(valuespace)
        self.assertTrue(configuration.data)
        self.assertTrue(status.data)
