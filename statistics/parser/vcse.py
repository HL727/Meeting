from datetime import tzinfo

from django.utils.timezone import make_aware

from shared.utils import partial_update_or_create
from statistics.parser.utils import get_ou, get_org_unit, is_phone, rewrite_internal_domains
from ..models import Leg, Call
import json
from django.utils.dateparse import parse_datetime
from collections import defaultdict, Counter

LIMIT = 2 * 60


class VCSEParser:

    def __init__(self, server, timezone: tzinfo = None, debug=False):
        self.server = server
        self.timezone = timezone

    def parse_xml(self, content):
        # Not really xml, rename later
        return self.parse_json(content)

    def parse_json(self, content):
        for call_data in content:
            self.parse_call(call_data)

    def parse_call(self, call_data):

        if not call_data['details'] or not call_data.get('start_time'):
            return

        start_time = make_aware(parse_datetime(call_data['start_time']), timezone=self.timezone)
        end_time = make_aware(parse_datetime(call_data['end_time']), timezone=self.timezone)

        try:
            details = json.loads(call_data['details'])
        except json.JSONDecodeError:
            details = {'Call': {}}

        if call_data.get('initial_call') in ('false', False) and call_data.get('licensed') in ('false', False):
            return  # multipart call

        call_data['source_alias'] = call_data['source_alias'].replace('sip:', '')
        call_data['destination_alias'] = call_data['destination_alias'].replace('sip:', '')

        licenses = {k: int(v) for k, v in list(details['Call'].get('License', {}).items()) if v != '0'}

        if details.get('traversal_license_tokens', 0) != 0:
            licenses['traversal'] = details['traversal_license_tokens']

        if details.get('non_traversal_license_tokens', 0) != 0:
            licenses['non_traversal'] = details['non_traversal_license_tokens']

        if (end_time - start_time).total_seconds() < LIMIT:
            return

        call, created = partial_update_or_create(Call, server=self.server, guid=call_data['uuid'], defaults=dict(
            leg_count=2, duration=(end_time - start_time).total_seconds(),
            ts_start=start_time, ts_stop=end_time,
            cospace=rewrite_internal_domains(call_data['destination_alias'], default_domain=self.server.default_domain),
            licenses=licenses,
        ))

        self.parse_legs(call, call_data, details)

    def parse_legs(self, call: Call, call_data: dict, details: dict):

        protocol_text = call_data.get('Protocol', call_data.get('protocol') or '').split(' ', 1)[0]  # TODO check source/destinaton (?)
        if protocol_text == 'SIP':
            protocol = Leg.SIP
        elif protocol_text == 'H323':
            protocol = Leg.H323
        elif protocol_text == 'Lync':  # FIXME possible to check?
            protocol = Leg.LYNC
        else:
            protocol = None

        sessions = details['Call'].get('Sessions') or []
        stats = defaultdict(Counter)

        len(stats[0])  # init empty
        len(stats[1])

        for session in sessions:
            if not session['Session'].get('Media'):
                continue

            for channel_container in session['Session']['Media']['Channels']:
                channel = channel_container['Channel']

                cur = stats[int(channel['Outgoing']['Leg'])]

                analysis = channel['Packets']['Analysis']

                cur['packetloss'] += int(analysis['Lost'])
                cur['total_packages'] += int(channel['Packets']['Forwarded']['Total'])

                cur['rate'] += int(channel['Rate'])
                cur['jitter'] = analysis['Jitter'] or cur['jitter']
                cur['jitter_peak'] = analysis.get('JitterPeak') or cur.get('JitterPeak')

        for leg_index in [0, 1]:

            if leg_index == 0:
                target = call_data['source_alias'].lower()
                leg_guid = call.guid + 'l'
                leg_direction = 'outgoing'
            else:
                target = call_data['destination_alias'].lower()
                leg_guid = call.guid + 'd'
                leg_direction = 'incoming'
            target = rewrite_internal_domains(target, default_domain=self.server.default_domain)

            from endpoint.models import Endpoint
            endpoint = Endpoint.objects.get_from_uri(target, only='id')
            if endpoint:
                endpoint_kwargs = {'endpoint': endpoint}
            else:
                endpoint_kwargs = {}

            if is_phone(target):
                target = is_phone(target)

            partial_update_or_create(Leg, server=self.server, call=call,
                target=target,
                remote=call_data['destination_alias'], local=call_data['source_alias'],
                defaults=dict(
                    direction=leg_direction,
                    ts_start=call.ts_start, ts_stop=call.ts_stop,
                    ou=get_ou(target), org_unit=get_org_unit(target),
                    guid=leg_guid,
                    protocol=protocol,
                    packetloss_percent=stats[leg_index]['packetloss'] / (stats[leg_index]['total_packages'] or 1),
                    bandwidth=stats[leg_index]['rate'],
                    **endpoint_kwargs,
                ),
            )

