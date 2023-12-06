from os import path

from defusedxml.cElementTree import parse as safe_xml_parse
from django.conf import settings
from django.test import TestCase

from ..ext_api.parser import cisco_ce as parser

root = path.dirname(path.abspath(__file__))


class TestCiscoParser(TestCase):

    def _get_file(self, path):
        return safe_xml_parse(open(root + '/data/' + path)).getroot()

    def test_parser(self):

        from pprint import pprint

        status = parser.StatusParser(self._get_file('status.xml')).parse()

        self.assertEqual('OK', status.findtext('./HttpFeedback/Status'))
        self.assertEqual('OK', status.findtext('./HttpFeedback[2]/Status'))
        self.assertEqual('Failed', status.findtext('./HttpFeedback[4]/Status'))
        self.assertEqual(list(status.textdict('./Diagnostics/Message').keys()), ['Description', 'Level', 'References', 'Type'])
        self.assertEqual(len(status.textdictall('./Diagnostics/Message')), 3)
        self.assertEqual(len(status.textdictall('./Diagnostics/Message/Invalid')), 0)

        self.assertEqual(status.findtext('./UserInterface/ContactInfo/ContactMethod/Number'), '1234@example.org')
        valuespace = parser.ValueSpaceParser(self._get_file('valuespace.xml')).parse()
        commands = parser.CommandParser(self._get_file('command.xml'), valuespace).parse()
        configuration = parser.ConfigurationParser(self._get_file('configuration.xml'), valuespace).parse()

        if getattr(settings, 'VERBOSE', False):
            pprint(status)
            pprint(valuespace)
            pprint(commands)
            pprint(configuration)



