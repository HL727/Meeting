import datetime
import re
from datetime import timedelta

from django.conf import settings
from django.db import transaction
from django.utils.timezone import localtime
from sentry_sdk import capture_message

from endpoint.models import Endpoint
from statistics.parser.utils import get_ou, get_org_unit, is_phone, rewrite_internal_domains
from ..models import Call, Leg
from django.utils.dateparse import parse_datetime
from defusedxml.cElementTree import fromstring as safe_xml_fromstring

LIMIT = 2 * 60
STORE_REMOTE = False


class PolyStatisticsBase:

    def __init__(self, server, endpoint, debug=False):
        self.server = server
        self.endpoint = endpoint

    def get_protocol(self, protocol_text):
        protocol_text = protocol_text.upper()
        if protocol_text == 'SIP':
            protocol = Leg.SIP
        elif protocol_text == 'H323':
            protocol = Leg.H323
        elif protocol_text == 'Lync':
            protocol = Leg.LYNC
        elif protocol_text == 'Spark':
            protocol = Leg.SPARK
        else:
            protocol = None
        return protocol

    def get_guid(self, call_id, start_time):
        return '{}-{}-{}'.format(self.endpoint.id, start_time.date(), call_id)

    @transaction.atomic()
    def get_call(self, guid, local_uri, data, fallback_guid=None):
        ts_start = data.pop('ts_start')

        call = Call.objects.filter(server=self.server, guid__in={g for g in (guid, fallback_guid) if g},
                                   ts_start__gte=ts_start - timedelta(days=3),
                                   ).order_by('-ts_start').first()
        if not call:
            Endpoint.objects.filter(pk=self.endpoint.pk).select_for_update(of=('self',)).get()

        call, created = Call.objects.update_or_create(
            server=self.server, guid=call.guid if call else guid,
            ts_start__gte=ts_start - timedelta(days=3),
            defaults=dict(
                leg_count=2, ts_start=ts_start,
                cospace=rewrite_internal_domains(local_uri, default_domain=self.server.default_domain),
                **data
            ))
        return call, created

    def _migrate_deprecated(self, call, target, guid):

        deprecated = Leg.objects.filter(server=self.server, call=call, target=target)
        if deprecated.update(guid=guid) > 1:
            for d in deprecated[1:]:
                d.delete()

    @transaction.atomic
    def get_leg(self, call, target, guid, data, endpoint):
        target = rewrite_internal_domains(target, default_domain=self.server.default_domain)

        endpoint_kwargs = {'endpoint': endpoint} if endpoint else {}

        if is_phone(target):
            target = is_phone(target)

        Call.objects.filter(pk=call.pk).select_for_update(of=('self',))
        self._migrate_deprecated(call, target, guid)

        return Leg.objects.update_or_create(
            server=self.server, call=call, guid=guid,
            defaults=dict(
                target=target,
                ts_start=call.ts_start, ts_stop=call.ts_stop,
                ou=get_ou(target), org_unit=get_org_unit(target),
                **data, **endpoint_kwargs,
            ),
        )


class StudioXStatisticsParser(PolyStatisticsBase):

    def parse_xml(self, content):

        # Not really xml, rename later
        root = safe_xml_fromstring(content)
        if root.tag != 'Entry':
            root = root.find('.//Entry')
        return self.parse_call(root)

    def parse_call(self, call_data):
        from endpoint.models import Endpoint

        local_uri = self.endpoint.sip or self.endpoint.h323 or self.endpoint.h323_e164

        start_time = datetime.datetime.fromtimestamp(call_data.get('startTime') / 1e3)
        end_time = datetime.datetime.fromtimestamp(call_data.get('endTime') / 1e3)
        remote_uri = call_data.get('', '')

        should_count_stats = True
        if (end_time - start_time).total_seconds() < LIMIT or not remote_uri:
            should_count_stats = False

        call_id = call_data.get('callerId')

        guid = self.get_guid(call_id, start_time)
        fallback_guid = self.get_guid(call_id, start_time - timedelta(minutes=10))
        call, created = self.get_call(guid,
                                      local_uri,
                                      {
                                          'ts_start': start_time,
                                          'ts_stop': end_time,
                                          'correlator_guid': call_data.get('rowId') or '',
                                      },
                                      fallback_guid=fallback_guid
                                      )

        cur = {
            'bandwidth': int(call_data.get('rate', '') or 0),
            'protocol': self.get_protocol(call_data.get('transportType', '')),
            'direction': 'outgoing' if call_data.get('outgoingCall', True) else 'incoming',
            'should_count_stats': should_count_stats,
            'local': local_uri,
            'remote': remote_uri,
        }

        # remote
        if STORE_REMOTE:
            remote_endpoint = Endpoint.objects.get_from_uri(remote_uri, only='id')
            self.get_leg(call, remote_uri, '{}-remote'.format(guid), cur, remote_endpoint)


        self.get_leg(call, local_uri, '{}-local'.format(guid), cur, self.endpoint)

        return call

class GroupStatisticsParser(PolyStatisticsBase):

    def parse_xml(self, content):

        # Not really xml, rename later
        root = safe_xml_fromstring(content)
        if root.tag != 'Entry':
            root = root.find('.//Entry')
        return self.parse_call(root)

    def parse_call(self, call_data):
        from endpoint.models import Endpoint

        local_uri = self.endpoint.sip or self.endpoint.h323 or self.endpoint.h323_e164

        start_time = datetime.datetime.fromtimestamp(call_data.get('startTime') / 1e3)
        end_time = datetime.datetime.fromtimestamp(call_data.get('endTime') / 1e3)
        remote_uri = call_data.get('', '')

        should_count_stats = True
        if (end_time - start_time).total_seconds() < LIMIT or not remote_uri:
            should_count_stats = False

        call_id = call_data.get('callerId')

        guid = self.get_guid(call_id, start_time)
        fallback_guid = self.get_guid(call_id, start_time - timedelta(minutes=10))
        call, created = self.get_call(guid,
                                      local_uri,
                                      {
                                          'ts_start': start_time,
                                          'ts_stop': end_time,
                                          'correlator_guid': call_data.get('rowId') or '',
                                      },
                                      fallback_guid=fallback_guid
                                      )

        cur = {
            'bandwidth': int(call_data.get('rate', '') or 0),
            'protocol': self.get_protocol(call_data.get('callType', '')),
            'direction': 'outgoing' if call_data.get('outgoingCall', True) else 'incoming',
            'should_count_stats': should_count_stats,
            'local': local_uri,
            'remote': remote_uri,
        }

        # remote
        if STORE_REMOTE:
            remote_endpoint = Endpoint.objects.get_from_uri(remote_uri, only='id')
            self.get_leg(call, remote_uri, '{}-remote'.format(guid), cur, remote_endpoint)


        self.get_leg(call, local_uri, '{}-local'.format(guid), cur, self.endpoint)

        return call

class TrioStatisticsParser(PolyStatisticsBase):

    def parse_xml(self, content):

        # Not really xml, rename later
        root = safe_xml_fromstring(content)
        if root.tag != 'Entry':
            root = root.find('.//Entry')
        return self.parse_call(root)

    def parse_call(self, call_type, call_data):
        from endpoint.models import Endpoint

        local_uri = self.endpoint.sip or self.endpoint.h323 or self.endpoint.h323_e164

        start_time = parse_datetime(call_data.get('StartTime'))

        def get_secs(timestr): # timestr format: 1 hour 2 mins 3 secs
            if timestr == '':
                return 0

            timestr = re.sub('\\s+(hour|hr|min)s?\\s+', ':', timestr)
            timestr = re.sub('\\s+(sec)s?', '', timestr)
            
            seconds= 0
            for part in timestr.split(':'):
                seconds= seconds*60 + int(part, 10)
            return seconds

        duration_secs = get_secs(call_data.get('Duration')) 
        end_time = start_time + datetime.timedelta(seconds=duration_secs)
        remote_uri = call_data.get('RemotePartyNumber', '')

        should_count_stats = True
        if duration_secs < LIMIT or not remote_uri:
            should_count_stats = False

        call_id = call_data.get('LineNumber')

        guid = self.get_guid(call_id, start_time)
        fallback_guid = self.get_guid(call_id, start_time - timedelta(minutes=10))
        call, created = self.get_call(guid,
                                      local_uri,
                                      {
                                          'ts_start': start_time,
                                          'ts_stop': end_time,
                                          'correlator_guid': call_data.get('rowId') or '',
                                      },
                                      fallback_guid=fallback_guid
                                      )

        cur = {
            'bandwidth': int(call_data.get('rate', '') or 0),
            'protocol': self.get_protocol(call_data.get('callType', '')),
            'direction': 'outgoing' if call_type == 'PLACED' else 'incoming',
            'should_count_stats': should_count_stats,
            'local': local_uri,
            'remote': remote_uri,
        }

        # remote
        if STORE_REMOTE:
            remote_endpoint = Endpoint.objects.get_from_uri(remote_uri, only='id')
            self.get_leg(call, remote_uri, '{}-remote'.format(guid), cur, remote_endpoint)


        self.get_leg(call, local_uri, '{}-local'.format(guid), cur, self.endpoint)

        return call

class HdxStatisticsParser(PolyStatisticsBase):

    def parse_xml(self, content):

        # Not really xml, rename later
        root = safe_xml_fromstring(content)
        if root.tag != 'Entry':
            root = root.find('.//Entry')
        return self.parse_call(root)

    def parse_call(self, call_data):
        from endpoint.models import Endpoint

        local_uri = self.endpoint.sip or self.endpoint.h323 or self.endpoint.h323_e164

        start_time = parse_datetime(call_data.get('ts_start'))
        end_time = parse_datetime(call_data.get('ts_end'))
        remote_uri = call_data.get('RemotePartyNumber', '')

        should_count_stats = True
        if (end_time - start_time).total_seconds() < LIMIT or not remote_uri:
            should_count_stats = False

        call_id = call_data.get('id')

        guid = self.get_guid(call_id, start_time)
        fallback_guid = self.get_guid(call_id, start_time - timedelta(minutes=10))
        call, created = self.get_call(guid,
                                      local_uri,
                                      {
                                          'ts_start': start_time,
                                          'ts_stop': end_time,
                                          'correlator_guid': call_data.get('history_id') or '',
                                      },
                                      fallback_guid=fallback_guid
                                      )

        cur = {
            'bandwidth': int(call_data.get('rate', '') or 0),
            'protocol': self.get_protocol(call_data.get('protocol', '')),
            'direction': 'outgoing' if call_data.get('type', 'Out') == 'Out' else 'incoming',
            'should_count_stats': should_count_stats,
            'local': local_uri,
            'remote': remote_uri,
        }

        # remote
        if STORE_REMOTE:
            remote_endpoint = Endpoint.objects.get_from_uri(remote_uri, only='id')
            self.get_leg(call, remote_uri, '{}-remote'.format(guid), cur, remote_endpoint)


        self.get_leg(call, local_uri, '{}-local'.format(guid), cur, self.endpoint)

        return call