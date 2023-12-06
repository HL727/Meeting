# Cisco VCS Expressway
import json
from typing import Dict
from urllib.parse import urlparse

import pytz
from django.utils.translation import gettext_lazy as _

import requests
from django.conf import settings
from django.utils.timezone import now

from customer.models import CustomerMatch
from ..exceptions import AuthenticationError, ResponseError, ResponseConnectionError, NotFound
from datetime import timedelta
import re
from collections import Counter, defaultdict

from defusedxml import cElementTree as ET
from .base import ProviderAPI, DistributedReadOnlyCallControlProvider
import logging
from sentry_sdk import capture_exception

logger = logging.getLogger(__name__)


class VCSExpresswayAPI(DistributedReadOnlyCallControlProvider, ProviderAPI):

    def update_request_kwargs(self, kwargs):
        kwargs['auth'] = (self.provider.username, self.provider.password)
        kwargs.setdefault('timeout', 10)
        try:
            login, sharpid = self.provider.session_id.split('|')
        except Exception:
            pass
        else:
            kwargs['cookies'] = {
                'SHARPID': sharpid,
                'tandberg_login': login,
            }

    def login(self, force=False, timeout=10):

        if self.provider.has_session and not force:
            return True

        s = requests.Session()
        s.verify = self.verify_certificate

        login_url = 'https://%s/login/' % (self.provider.hostname or self.ip)
        data = {
            'submitbutton': 'Login',
            'formbutton': 'Login',
            'username': self.provider.username,
            'password': self.provider.password,
        }

        try:
            response = s.post(login_url, data, allow_redirects=False, headers={'Referer': login_url},
                              timeout=timeout)
        except requests.exceptions.ConnectionError as e:
            raise ResponseConnectionError('ConnectionError', e)

        if not response.headers.get('location'):
            raise AuthenticationError(_('Authentication error'), response)
        else:

            self.provider.session_id = '{}|{}'.format(response.cookies['tandberg_login'], response.cookies['SHARPID'])

            self.provider.session_expires = now() + timedelta(hours=12)
            self.provider.save()

        return True

    def get_url(self, path=None):
        return '%s/%s' % (self.get_base_url(), path)

    def check_login_status(self, response):
        if '/login/' in response.headers.get('location', ''):
            raise AuthenticationError()

        if response.status_code in (401, 403):
            raise AuthenticationError()

        if '<b>Login expired</b>' in response.text:
            raise AuthenticationError()

        if '<title>Login</title>' in response.text:
            raise AuthenticationError()

    def get_status(self, timeout=10):
        response = self.get('getxml?location=/Status/SystemUnit', timeout=timeout)

        if response.status_code != 200:
            raise self.error('Invalid status {}'.format(response.status_code), response)

        ns = {'ns': 'http://www.tandberg.no/XML/CUIL/1.0'}

        root = ET.fromstring(response.content).find('./ns:SystemUnit', ns)

        try:
            seconds = int(root.findtext('./ns:Uptime', '', ns))
            uptime = str(timedelta(seconds=seconds))
            if ':' in uptime:
                uptime = uptime[:uptime.rindex(':')]
        except ValueError:
            uptime = ''

        software_version = root.findtext('./ns:Software/ns:Version', '', ns) or ''
        if self.provider.software_version != software_version:
            self.provider.software_version = software_version
            if self.provider.pk:
                self.provider.save(update_fields=['software_version'])

        return {
            'uptime': uptime,
            'product': root.findtext('./ns:Product', '', ns),
            'expressway': root.findtext('./ns:Expressway', '', ns).lower() == 'true',
            'hardware': root.findtext('./ns:Hardware/ns:Version', '', ns),
            'software_version': software_version,
            'software_release': root.findtext('./ns:Software/ns:ReleaseDate', '', ns),
        }

    def check_cdr_enabled(self):
        response = self.get('getxml?location=/Status/CDR/Service')

        if response.status_code != 200:
            raise self.error('Invalid status {}'.format(response.status_code), response)

        ns = {'ns': 'http://www.tandberg.no/XML/CUIL/1.0'}
        result = ET.fromstring(response.content).findtext('./ns:CDR/ns:Service', 'off', ns) != 'off'

        if self.provider.cdr_active != result:
            self.provider.cdr_active = result
            self.provider.save()
        return result

    def get_uptime(self):
        return self.get_status()['uptime']

    def get_uptime_by_scrape(self):
        "scrape html"

        response = self.get('overview')

        if response.status_code != 200:
            raise self.error('Invalid status {}'.format(response.status_code), response)

        # invalid xml in page, extract tables
        tables = re.findall(r'(<table class="status_table".*?</table>)', response.text, re.DOTALL)
        for table_html in tables:
            root = ET.fromstring(table_html)

            rows = root.findall('.//tr')

            for row in rows:
                if row[0].text == 'Up time':
                    return re.sub(r' \d+ seconds?', '', row[1].text)
        return ''

    def get_status_by_scrape(self):
        "scrape html"

        response = self.get('statustablexml')

        if response.status_code != 200:
            raise self.error('Invalid status {}'.format(response.status_code), response)

        table = ET.fromstring(response.text)

        result = {}

        if table.tag != "table":
            raise self.error(_('Response is not table'), response)

        result['last_update'] = table.findtext('./thead//th', '')

        cur = {}

        for row in table.findall('./tbody/tr'):

            columns = list(row)

            new_section = columns[0].findtext('./a', '')
            if new_section:
                cur = result.setdefault(new_section, {})

            if not columns[1].text and len(columns[1]) == 0:
                continue  # header
            subsection = columns[1].text or columns[1][0].text
            if subsection:
                cur[subsection] = str(columns[2].text or '').strip() or columns[2].findtext('./b', '')
                if cur[subsection] and cur[subsection].isdigit():
                    cur[subsection] = int(cur[subsection])

        return result

    def get_registrations(self):

        response = self.get('api/management/status/registration/registration')

        if response.status_code != 200:
            raise self.error('Invalid status {}'.format(response.status_code), response)

        data = response.json()

        result = []

        for peer in data:
            records = [r for r in peer['records'] if r.get('active')]

            for record in records:
                result.append({
                    'id': record['uuid'],
                    'ip': urlparse(record['uuid']).hostname,
                    'protocol': record['protocol'],
                    'alias': record.get('alias') or '',
                    'number': record.get('number') or '',
                    'type': record['device_type'],
                })

        return result

    def get_resource_usage(self):
        response = self.get('api/management/status/resourceusage')

        if response.status_code != 200:
            raise self.error('Invalid status {}'.format(response.status_code), response)

        return response.json()

    def get_calls(self, include_legs=False, include_participants=False, filter=None, cospace=None, limit=None,
                  tenant=None, offset=0, timeout=10, only_active=True):

        if only_active:
            url = 'api/management/status/call/call/active/true'
        else:
            url = 'api/management/status/call/call'

        response = self.get(url, timeout=timeout)

        if response.status_code != 200:
            raise self.error('Invalid status {}'.format(response.status_code), response)

        nodes = response.json()

        result = []

        calls = [call for node in nodes for call in node['records']]
        if only_active:
            calls = [call for call in calls if call['active']]

        for call in calls:

            cur = self.format_call(call)
            if tenant is not None and cur['tenant'] != tenant:
                continue

            result.append(self.format_call(call))

        return result, len(calls)

    def format_call(self, call):
        match = CustomerMatch.objects.get_match(call, cluster=self.cluster)

        return {
            **call,
            'tenant': match.tenant_id if match else '',
            'participants': [
                {
                    'local': call['source_alias'],
                    'remote': call['destination_alias'],
                    'call': call['uuid'],
                    'id': call['uuid'] + '1',
                },
                {
                    'remote': call['source_alias'],
                    'local': call['destination_alias'],
                    'call': call['uuid'],
                    'id': call['uuid'] + '2',
                },
            ]
        }

    def get_call(self, call_id, cospace=None, include_legs=False, include_participants=False) -> Dict:

        response = self.get('api/management/status/call/call/uuid/{}'.format(call_id))

        if response.status_code != 200:
            raise self.error('Invalid status {}'.format(response.status_code), response)

        calls = [call for node in response.json() for call in node['records']]
        if not calls or not calls[0]['active']:
            raise NotFound('Call not active', response)

        return self.format_call(calls[0])

    def get_participants(self, call_id=None, cospace=None, filter=None, tenant=None, only_internal=True,
                         limit=None):

        call = self.get_call(call_id)

        return call['participants'], len(call['participants'])

    def get_call_protocol_stats(self):

        response = self.get('api/management/status/call/call', timeout=10)
        if response.status_code != 200:
            raise self.error('Invalid status', response)

        peer_results = defaultdict(Counter)

        for node in response.json():
            for record in node['records']:
                if not record['active']:
                    continue
                peer_results[node['peer']][record['protocol']] += 1

        if len(peer_results) > 1:
            for k in peer_results:
                if k in ('localhost', self.provider.ip, self.provider.hostname):
                    return peer_results[k]

        result = Counter()
        for cur in peer_results.values():
            result += cur  # combine all peers if no match
        return result

    def get_alarms(self, only_raised=True):
        response = self.get('api/management/status/alarm')

        if response.status_code != 200:
            raise self.error('Invalid status {}'.format(response.status_code), response)

        alarms = response.json()

        def _convert_timestamps(record):
            from datetime import datetime
            from django.utils.timezone import make_aware, get_current_timezone

            tz = get_current_timezone()
            if record.get('last_raised'):
                record['last_raised'] = make_aware(datetime.fromtimestamp(float(record['last_raised'])), tz)
            if record.get('first_raised'):
                record['first_raised'] = make_aware(datetime.fromtimestamp(record['first_raised']), tz)
            return record

        result = {
            'peers': [],
            'total_count': 0,
            'acknowledged_count': 0,
        }

        for peer in alarms:
            if only_raised:
                peer['records'] = [r for r in peer['records'] if r.get('total_count')]

            peer['records'] = [_convert_timestamps(r) for r in peer['records']]

            peer['acknowledged_count'] = sum(1 for r in peer['records'] if r.get('status') == 'acknowledged')
            peer['unacknowledged_count'] = sum(1 for r in peer['records'] if r.get('total_count') and r.get('status') != 'acknowledged')
            result['peers'].append(peer)

        result['total_count'] = sum(len(p['records']) for p in result['peers'])
        result['acknowledged_count'] = sum(p['acknowledged_count'] for p in result['peers'])
        result['unacknowledged_count'] = sum(p['unacknowledged_count'] for p in result['peers'])

        return result

    def get_license_usage(self, only_active=True):
        usage_response = self.get('api/management/status/licensemanager/licensepool')
        limits_response = self.get('api/management/status/licensemanager/licensepoollimits')

        if usage_response.status_code != 200:
            raise self.error('Invalid status {}'.format(usage_response.status_code), usage_response)

        if limits_response.status_code != 200:
            raise self.error('Invalid status {}'.format(limits_response.status_code), limits_response)

        usage = usage_response.json()
        limits = limits_response.json()


        limit_map = {}
        for peer in limits:
            cur = limit_map.setdefault(peer['peer'], {})
            for record in peer['records']:
                cur[record['license_type']] = record['token_limit'] or record['resource_limit']  # TODO use resource_limit or token_limit?

        result = {
            'peers': [],
        }

        filter_peer = ('localhost', self.provider.ip, self.provider.hostname)

        for license in usage:
            if only_active:
                license['records'] = [r for r in license['records'] if r.get('total') and r.get('license_type') != 'demoted']

            if len(limit_map) > 1 and any(m for m in limit_map.keys() if m in filter_peer):
                if license['peer'] not in filter_peer:
                    continue

            for record in license['records']:
                peer_limit = limit_map.get(license['peer'], {})
                if peer_limit.get(record['license_type']):  # may be zero
                    record['usage_percent'] = record['inuse'] / float(peer_limit[record['license_type']]) * 100
                    record['max_percent'] = record['max'] / float(peer_limit[record['license_type']]) * 100
            result['peers'].append(license)

        return result

    def get_cdr_for_all_time(self):
        from debuglog.models import VCSCallLog
        response = self.get('api/external/callusage/get_all_records', timeout=(3.07, 60))

        if response.status_code == 503:
            VCSCallLog.objects.store(content=b'[]', error='CDR not active')
            if self.provider.cdr_active:
                self.provider.cdr_active = False
                self.provider.save()
            return []  # TODO. disabled in vcs. return error?

        if response.status_code != 200:
            raise self.error('Invalid status {}'.format(response.status_code), response)

        if not self.provider.cdr_active:
            self.provider.cdr_active = True
            self.provider.save()

        try:
            VCSCallLog.objects.store(content=response.content, ip=self.ip)
        except Exception:
            if settings.DEBUG:
                raise
            capture_exception()

        return response.json()

    def get_cdr_for_interval(self, ts_start, ts_stop):
        "end time between timestamps according to manual testing"
        from debuglog.models import VCSCallLog

        def t(ts):
            return ts.strftime('%Y-%m-%d %H:%M:%S')

        response = self.get('api/external/callusage/get_records_for_interval',
                            params=dict(fromtime=t(ts_start), totime=t(ts_stop)),
                            timeout=(3.07, 60))

        if response.status_code == 503:
            VCSCallLog.objects.store(content=b'[]', ts_start=ts_start, ts_stop=ts_stop, error=_('CDR not active'), ip=self.ip)

            if self.provider.cdr_active:
                self.provider.cdr_active = False
                self.provider.save()

            return []  # TODO. disabled in vcs. return error?

        if response.status_code != 200:
            raise self.error('Invalid status {}'.format(response.status_code), response)

        if not self.provider.cdr_active:
            self.provider.cdr_active = True
            self.provider.save()

        try:
            VCSCallLog.objects.store(content=response.content, ts_start=ts_start, ts_stop=ts_stop, ip=self.ip)
        except Exception:
            if settings.DEBUG:
                raise
            capture_exception()

        return response.json()

    def get_license(self):
        response = self.get('api/management/status/licensemanager/licensepool')

        if response.status_code != 200:
            raise self.error('Invalid status {}'.format(response.status_code), response)

        data = response.json()
        if len(data) > 1:  # clustered, only display self
            for peer in data['peers']:
                if peer.get('peer') in ('localhost', self.provider.ip, self.provider.hostname):
                    return {'peers': [peer]}

        return response.json()

    def get_timezone(self):
        response = self.get('getxml?location=/Status/SystemUnit/TimeZone')
        if response.status_code != 200:
            raise self.error('Invalid status {}'.format(response.status_code), response)

        match = re.search(r'<TimeZone[^>]*>\s*(.*?)</', response.text)
        if match:
            try:
                return pytz.timezone(match.group(1).strip())
            except pytz.UnknownTimeZoneError:
                pass
        return None

    def update_stats(self, incremental=True):
        from statistics.parser.vcse import VCSEParser
        from statistics.models import Server
        from debuglog.models import VCSCallLog

        try:
            timezone = self.get_timezone()
            if not self.provider.cdr_active:
                data = [call for call in self.get_calls(only_active=False)[0] if call.get('end_time')]
                try:
                    VCSCallLog.objects.store(content=json.dumps(data), ip=self.ip)
                except Exception:
                    if settings.DEBUG:
                        raise
                    capture_exception()
            elif incremental:
                data = self.get_cdr_for_interval(now() - timedelta(hours=3), now())
            else:
                data = self.get_cdr_for_all_time()
        except AuthenticationError as e:
            VCSCallLog.objects.store(content=b'[]', error=str(e), ip=self.ip)
        except ResponseError as e:
            VCSCallLog.objects.store(content=b'[]', error=str(e), ip=self.ip)
        except Exception as e:
            VCSCallLog.objects.store(content=b'[]', error=str(e), ip=self.ip)
            if settings.DEBUG:
                raise
            capture_exception()
        else:
            cluster = self.cluster if self.cluster.is_cluster else None

            parser = VCSEParser(
                Server.objects.get_for_customer(self.provider.customer, type=Server.VCS, cluster=cluster,
                                                create={'type': Server.VCS, 'name': self.cluster.title,
                                                        'cluster': cluster}),
                timezone=timezone,
            )
            parser.parse_json(data)

        return True

    @staticmethod
    def update_all_vcs_stats(incremental=True):
        from provider.models.vcs import VCSEProvider
        from customer.models import Customer

        exceptions = []

        for provider in VCSEProvider.objects.all():
            api = VCSExpresswayAPI(provider, provider.customer or Customer.objects.all()[0])
            if not api.cluster.is_cluster or not api.cluster.auto_update_statistics:
                continue

            try:
                api.update_stats(incremental=incremental)
            except Exception as e:
                exceptions.append(e)

        if exceptions:
            raise exceptions[0]

    def get_sip_uri(self, uri=None, cospace=None):
        return ''

    def get_web_url(self, alias=None, passcode=None, cospace=None):
        return ''

