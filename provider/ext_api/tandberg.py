from urllib.parse import urljoin
from xml.sax.saxutils import escape
from defusedxml import cElementTree as ET
import requests
from urllib.parse import urlparse

from provider.exceptions import ResponseError


MAX_ITEMS = 10000


class TandbergAPI:

    def __init__(self, mac, host=None, default_domain=None, verify_certificate=False,
                 phonebook_url=None):

        if not host and not '://' in phonebook_url:
            raise ValueError('Hostname to TMS must be specified')
        self.mac = mac
        self.host = host or urlparse(phonebook_url).hostname
        self.verify_certificate = verify_certificate
        self.default_domain = '@{}'.format(default_domain) if default_domain else ''
        self.phonebook_url = phonebook_url or '/tms/public/external/phonebook/phonebookservice.asmx?op=%s'

    def get_url(self, url):

        base = 'http://{}/'.format(self.host) if self.host else ''

        if '/' in url:
            return urljoin(base, url)

        return urljoin(base, self.phonebook_url.replace('%s', url))

    def post(self, url, *args, **kwargs):
        # TODO user Provider.post?
        override_function = getattr(self, 'override_post', None)
        if override_function:
            return override_function(url, method='POST', *args, **kwargs)

        return requests.post(self.get_url(url), **kwargs)

    def log_error(self, url, content, **kwargs):
        from debuglog.models import ErrorLog

        ErrorLog.objects.store(
            title='Http request resulted in an error',
            type=self.__class__.__name__,
            url=url,
            content=content,
            **kwargs,
        )


    @staticmethod
    def get_search_xml(mac, query, parent_id=None, start_id=None, limit=None):

        if start_id:
            pagination = '<RangeInclusive>false</RangeInclusive> <StartFromId>{}</StartFromId>'.format(start_id)
        else:
            pagination = ''

        xml = '''
<?xml version="1.0" encoding="UTF-8"?>
  <env:Envelope xmlns:env="http://schemas.xmlsoap.org/soap/envelope/" xmlns="http://www.tandberg.net/2004/06/PhoneBookSearch/">
    <env:Body xmlns="http://www.tandberg.net/2004/06/PhoneBookSearch/">
      <Search><Identification>
    <MACAddress>{mac}</MACAddress>
  </Identification>
        <CaseSensitiveSearch>false</CaseSensitiveSearch>
        <SearchString>{query}</SearchString>
        <SearchType>Free</SearchType>
        <MaxResult>{limit}</MaxResult>
        {path}
        {pagination}
        <Scope>{scope}</Scope>
        <RangeInclusive>false</RangeInclusive>
      </Search>
    </env:Body>
  </env:Envelope>
        '''.format(mac=mac, query=escape(query),
                   path='<SearchPath>{}</SearchPath>'.format(parent_id) if parent_id else '',
                   limit=limit or 100,
                   pagination=pagination,
                   scope='SubTree' if query and not parent_id else 'SingleLevel',
                   ).strip()

        return xml

    def search(self, query, parent_id=None, limit=30):

        if not self.mac:
            raise ValueError('Tandberg authentication not specified')

        if not self.host:
            raise ValueError('Tandberg hostname not specified')

        result_catalogs = []
        result_entries = []

        last_id = None

        for _i in range(limit or 1000):
            catalogs, entries, pagination = self.search_single_page(query, parent_id=parent_id, start_id=last_id, limit=limit)

            if last_id is not None and pagination['last_id'] == last_id:
                break
            last_id = pagination['last_id']

            result_catalogs.extend(catalogs)
            result_entries.extend(entries)

            if pagination['has_last']:
                break

            if limit and len(result_catalogs) + len(result_entries) > limit:
                break

        return result_catalogs, result_entries

    def search_single_page(self, query, parent_id=None, start_id=None, limit=None):
        response = self._post_search(query, parent_id=parent_id, start_id=start_id, limit=limit)
        return self._handle_search_response(response)

    def _post_search(self, query, parent_id=None, start_id=None, limit=None):
        request = self.get_search_xml(self.mac, query, parent_id, start_id=start_id, limit=limit)

        headers = {
            'Content-Type': 'text/xml; charset=utf-8',
            'SOAPAction': 'http://www.tandberg.net/2004/06/PhoneBookSearch/Search',
        }

        url = 'Search'

        response = self.post(
            url, data=request.encode('utf-8'), headers=headers, verify=self.verify_certificate
        )

        if response.status_code != 200:
            self.log_error(self.get_url(url), response, request=request)
            raise ResponseError('Invalid status code {}'.format(response.status_code), response)

        return response

    def _handle_search_response(self, response):

        root = ET.fromstring(response.content)

        catalogs = []
        entries = []

        ns = {'s': 'http://www.tandberg.net/2004/06/PhoneBookSearch/'}

        search_result = root.find('.//s:SearchResult', namespaces=ns)

        last_id = None
        has_last = False
        skipped_entries = 0

        for catalog in search_result.findall('./s:Catalog', ns):

            catalogs.append({
                'name': catalog.findtext('./s:Name', '', ns),
                'id': catalog.findtext('./s:Id', '', ns),
                'count': catalog.findtext('./s:NoOfEntries', '', ns),
            })
            last_id = catalogs[-1]['id']
            has_last = catalog.findtext('./s:IsLast', '', ns) == 'true'

        for item in search_result.findall('./s:Entry', ns):

            cur = {
                'name': item.findtext('./s:Name', '', ns),
                'id': item.findtext('./s:Id', '', ns),
            }
            last_id = cur['id']
            has_last = item.findtext('./s:IsLast', '', ns) == 'true'

            dialstring = None

            routes = item.findall('./s:Route', ns)
            for route in routes:

                protocol = route.findtext('./s:Protocol', '', ns)
                dialstring = route.findtext('./s:DialString', '', ns).strip()

                if dialstring.isdigit() and protocol == 'SIP':
                    dialstring = '{}{}'.format(dialstring, self.default_domain)

                if not dialstring:
                    skipped_entries += 1
                    continue

                cur[protocol.lower()] = dialstring

            cur['dialstring'] = cur.get('sip') or dialstring

            if not cur['dialstring']:
                continue

            entries.append(cur)

        pagination = {
            'last_id': last_id,
            'has_last': has_last,
            'count': search_result.findtext('./s:NoOfEntries', '', ns),
            'skipped_entries': skipped_entries,
        }

        return catalogs, entries, pagination

    def recursive_get(self):
        """
        ({'name': 'Catalog'}, [...], entries})
        """

        catalogs, entries = self.search('', limit=None)

        MAX_ITEMS = 10000
        run = set()

        count = [0]

        def _rec(catalogs):
            count[0] += 1
            if count[0] > MAX_ITEMS:
                raise ValueError('Cant get more than 1000 groups from tms')

            for c in catalogs:
                if c['id'] in run:
                    continue
                run.add(c['id'])
                child_catalogs, entries = self.search('', parent_id=c['id'], limit=None)
                yield (c, list(_rec(child_catalogs)), entries)

        result = ({'id': None, 'name': 'Root'}, list(_rec(catalogs)), entries)

        return result

    def get_phonebooks(self):

        if not self.mac:
            raise ValueError('Tandberg authentication not specified')

        if not self.host:
            raise ValueError('Tandberg hostname not specified')

        request = '''
        <?xml version="1.0" encoding="utf-8"?>
        <soap:Envelope xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xmlns:xsd="http://www.w3.org/2001/XMLSchema" xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/">
        <soap:Body>
        <GetPhonebooks xmlns="http://www.tandberg.net/2004/06/PhoneBookSearch/">
        <SystemIdentifier>
            <MACAddress>{mac}</MACAddress>
        </SystemIdentifier>
        <Routing>None</Routing>
    </GetPhonebooks>

        </soap:Body>
        </soap:Envelope>
        '''.format(mac=self.mac).strip()

        headers = {
            'Content-Type': 'text/xml; charset=utf-8',
            'SOAPAction': 'http://www.tandberg.net/2004/06/PhoneBookSearch/GetPhonebooks',
        }

        url = 'GetPhonebooks'

        response = self.post(url, data=request, headers=headers,
           verify=self.verify_certificate)
        content = response.text

        result = []

        root = ET.fromstring(content)

        ns = {'s': 'http://www.tandberg.net/2004/06/PhoneBookSearch/'}

        result = []

        for catalog in root.findall('.//s:Catalog', ns):

            name = catalog.find('./s:Name', ns).text

            for item in catalog.findall('./s:Entry', ns):

                dialstring = item.find('./s:Route/s:DialString', ns).text.strip()
                if dialstring.isdigit():
                    dialstring = '{}{}'.format(dialstring, self.default_domain)

                result.append({
                    'name': item.find('./s:Name', ns).text,
                    'catalog': name,
                    'dialstring': dialstring,
                    })

        return result

    def get_systems(self):
        # TODO test

        request = '''
        <?xml version="1.0" encoding="utf-8"?>
        <soap:Envelope xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xmlns:xsd="http://www.w3.org/2001/XMLSchema" xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/">
          <soap:Body>
          <GetSystems xmlns="http://tandberg.net/2004/02/tms/external/booking/remotesetup/" />
          </soap:Body>
        </soap:Envelope>
        '''.strip()

        headers = {
            'Content-Type': 'text/xml; charset=utf-8',
            'SOAPAction': 'http://tandberg.net/2004/02/tms/external/booking/remotesetup/GetSystems',
        }

        response = self.post('GetSystems', data=request, headers=headers)

        ns = {'s': 'http://tandberg.net/2004/02/tms/external/booking/remotesetup/'}

        result = []
        root = ET.fromstring(response.text)

        for system in root.findall('.//s:GetSystemsResult/s:TMSSystem', ns):

            cur = {
                'name': system.findtext('./s:SystemName', '', ns),
                'ip': system.findtext('./s:WebInterfaceURL', '', ns),
                'sip': system.findtext('./s:SIPUri', '', ns),
                'h323': system.findtext('./s:H323Id', '', ns),
                'h323_e164': system.findtext('./s:E164Alias', '', ns),
            }
            result.append(cur)

        return result



