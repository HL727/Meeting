from defusedxml.cElementTree import fromstring as safe_xml_fromstring
from xml.etree import cElementTree as ET


class TMSSearch:

    def __init__(self, xml_body):

        self.xml_body = xml_body
        self.ns = {
            'env': 'http://schemas.xmlsoap.org/soap/envelope/',
            'ns': 'http://www.tandberg.net/2004/06/PhoneBookSearch/',
        }

    def parse_params(self):

        root = safe_xml_fromstring(self.xml_body)

        ns = self.ns

        search = root.find('.//ns:Search', ns)

        if not search:
            raise ValueError('No search tag specified!')

        def _findtext(node, path):

            result = node.find(path, ns)
            return result.text or '' if result is not None else ''

        return {
            'mac': _findtext(search, './ns:Identification/ns:MACAddress'),
            'group_id': _findtext(search, './ns:SearchPath'),
            'value': _findtext(search, './ns:SearchString'),
            'limit': _findtext(search, './ns:MaxResult'),
            'last_id': _findtext(search, './ns:StartFromId'),
        }

    def search(self, address_book, value=None, params=None):

        if params is None:
            params = {k: v for k, v in self.parse_params().items() if v}

        if value is not None:
            params['value'] = value
        else:
            params.setdefault('value', '')

        params.pop('mac', None)

        groups, items = address_book.limit_search(**params)
        last = len(groups) + len(items)

        root = ET.Element('env:Envelope', {
            'xmlns:xsi': "http://www.w3.org/2001/XMLSchema-instance",
            'xmlns:xsd': "http://www.w3.org/2001/XMLSchema",
            'xmlns:env': "http://schemas.xmlsoap.org/soap/envelope/",
        })
        body = ET.SubElement(root, 'env:Body')
        response = ET.SubElement(body, 'SearchResponse', {'xmlns': self.ns['ns']})
        result = ET.SubElement(response, 'SearchResult')

        ET.SubElement(result, 'Name').text = str(address_book)
        ET.SubElement(result, 'Id').text = '0'
        ET.SubElement(result, 'IsFirst').text = 'true' if not params.get('last_id') else 'false'
        ET.SubElement(result, 'IsLast').text = 'true' if last < int(params.get('limit') or 20) else 'false'
        ET.SubElement(result, 'NoOfEntries').text = str(last)

        i = 0
        for group in groups:
            i += 1
            catalog = ET.SubElement(result, 'Catalog')
            ET.SubElement(catalog, 'Name').text = str(group)
            ET.SubElement(catalog, 'Id').text = group.ext_id
            ET.SubElement(catalog, 'IsFirst').text = 'true' if i == 1 else 'false'
            ET.SubElement(catalog, 'IsLast').text = 'true' if i == last else 'false'

        for item in items:
            i += 1
            entry = ET.SubElement(result, 'Entry')
            ET.SubElement(entry, 'Name').text = str(item.title)
            ET.SubElement(entry, 'Id').text = item.ext_id
            ET.SubElement(entry, 'IsFirst').text = 'true' if i == 1 else 'false'
            ET.SubElement(entry, 'IsLast').text = 'true' if i == last else 'false'
            ET.SubElement(entry, 'BaseDN')
            ET.SubElement(entry, 'SystemType')

            for k, protocol in {'sip': 'SIP', 'h323': 'H323'}.items():
                if not getattr(item, k):
                    continue

                route = ET.SubElement(entry, 'Route')
                ET.SubElement(route, 'CallType').text = 'Video'
                ET.SubElement(route, 'Protocol').text = protocol
                ET.SubElement(route, 'DialString').text = getattr(item, k)
                ET.SubElement(route, 'Restrict')
                ET.SubElement(route, 'Description')
                ET.SubElement(route, 'SystemType')

        return ET.tostring(root)




