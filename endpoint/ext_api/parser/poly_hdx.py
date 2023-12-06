import json
import xml.etree.ElementTree as ET

from typing import Dict, OrderedDict, Union
from xml.dom.minidom import Element

from django.utils.encoding import force_text

from .cisco_ce import NestedConfigurationXMLResult
from .poly_x import PolyBaseParser

class PolyHdxProfileConfigurationValueParser(PolyBaseParser):
    """Parse exported configurationProfile"""

    def parse(self) -> Dict[str, str]:
        self.result = self._iter(force_text(self.root))
        return self.result

    def _iter(self, parent: str):
        result = OrderedDict[str, str]()
        configItems = parent.split('\n')
        for item in configItems:
            if ',' in item:
                key, value = item.split(',', 1)
                result[key] = value
        return result

# class PolyHdxCommandConfigurationValueParser(PolyBaseParser):
#     """Parse configuration data taken by commands"""

#     def parse(self) -> Dict[str, str]:
#         self.result = self._iter(json.loads(force_text(self.root)))
#         return self.result

#     def _iter(self, parent: Dict[str, str]):
#         result = OrderedDict[str, str]()
        
#         return result

class PolyHdxStatusValueParser(PolyBaseParser):
    """Parse exported configurationProfile"""

    def parse(self) -> Dict[str, str]:
        self.result = self._iter(self.root)
        return self.result

    def _iter(self, parent: Element):
        result = OrderedDict[str, str]()
        trues = ['on', 'up']

        for child in parent:
            label = child.find('LABEL').find('TRANSLATE').text
            for helpLine in child.findall('HELPLINE'):
                # TODO use iter, and node.text + node.tail. Replace '\\n' with '\n'
                xmlstr = force_text(ET.tostring(helpLine, encoding='utf8', method='xml')).replace(
                    r'\n', '\n'
                )
                for translate in helpLine.findall('TRANSLATE'):
                    result['{}.{}'.format(label, translate.text)] = (
                        xmlstr.split('<TRANSLATE>{}</TRANSLATE>'.format(translate.text))[1]
                        .split('<')[0]
                        .strip()
                    )
            
            states = child.findall('STATE')

            if len(states) == 1:
                result['{}.enabled'.format(label)] = True if states[0].text in trues else False
            else:
                for index in range(0, len(states)):
                    result['{}.{}.enabled'.format(label, index)] = True if states[index].text in trues else False

        return result

class PolyHdxCallHistoryParser(PolyBaseParser):

    month_number_mapping = {
        'Jan': '01',
        'Feb': '02',
        'Mar': '03',
        'Apr': '04',
        'May': '05',
        'Jun': '06',
        'Jul': '07',
        'Aug': '08',
        'Sep': '09',
        'Oct': '10',
        'Nov': '11',
        'Dec': '12'
    }

    def parse(self) -> Dict[str, str]:
        self.result = self._iter(self.root)
        return self.result

    def _iter(self, parent: Element):
        result = []
        for callElement in parent.findall('call'):
            data = callElement.findall('data')

            start_date, start_month, start_year = data[1].text.split('/')
            end_date, end_month, end_year = data[3].text.split('/')

            start_month_number = self.month_number_mapping.get(start_month)
            end_month_number = self.month_number_mapping.get(end_month)

            ts_start = '{}-{}-{}T{}'.format(start_year, start_month_number, start_date, data[2].text)
            ts_end = '{}-{}-{}T{}'.format(end_year, end_month_number, end_date, data[4].text)

            rate = str(data[11].text).split('Kbps')[0]

            callData = {
                'number': data[7].text,
                'name': data[8].text,
                'ts_start': ts_start,
                'ts_end': ts_end,
                'type': data[13].text,
                'protocol': data[10].text,
                'count': data[0].text,
                'history_id': data[0].text,
                'id': data[0].text,
                'rate': rate
            }
            result.append(callData)
        return result
