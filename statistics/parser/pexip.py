import re
from datetime import timedelta, datetime
from typing import Dict, Tuple
from urllib.parse import parse_qsl

from cacheout import fifo_memoize
from django.db import transaction, IntegrityError
from django.db.models import Q
from django.db.models.expressions import RawSQL
from django.utils.timezone import make_aware, utc, now

from django.conf import settings
from customer.models import CustomerMatch, Customer
from datastore.models.pexip import Conference
from debuglog.models import PexipEventLog
from shared.utils import maybe_update
from statistics.parser.utils import get_ou, get_org_unit, is_phone, rewrite_internal_domains, \
    get_internal_domains, clean_target
from ..models import Leg, Call, LegConversation, tenant_obj
from django.utils.dateparse import parse_datetime
from collections import Counter
import logging

LIMIT = 2 * 60

logger = logging.getLogger(__name__)

'''
Pexip Event sink (live events/CDR)

Events are not necessarily delivered in order.

If queue at node has grown too large or has connection errors the sender process is stopped.
If the event sink is later restarted (from ui or updating restart timestamp) all buffered
events from all nodes are sent at the same time (!) which requires multiple restarts a
couple of minutes apart before it is cleared.

Misc notes:
SIP calls are updated from connecting -> ivr -> room. Other may have a new call.

Sometimes SIP calls can go from service_type = ivr to service_type = conference only in participant_disconnect

Pexip wierd id connections:

all:
event.conversation = history.conversation

sip in:
event.uuid = history.id

sip, webrtac, rtmp:
event.call_id = history.call_uuid
event.call_id = history.call_uuid

skype in:
event.call_id = history.call_uuid

skype, teams, gcm: (out)
event.uuid = history.id
event.uuid = history.id

'''


@fifo_memoize(500, ttl=10)
def _conference_id(name, cluster_id):
    conferences = Conference.objects.filter(name=name).order_by('-is_active', '-last_synced')
    if cluster_id:
        conferences = conferences.filter(provider=cluster_id)

    return conferences.values_list('cid', flat=True).first() or ''


class PexipParserBase:

    def __init__(self, server, debug=False):
        self.server = server
        self.internal_domains = get_internal_domains()

    def parse_xml(self, content):
        # Not really xml, rename later
        return self.parse_json(content)

    def parse_json(self, content):
        for call_data in content:
            self.parse_call(call_data)

    def _parse_times(self, data):
        start_time = make_aware(parse_datetime(data.get('start_time') or data.get('connect_time')), timezone=utc).replace(microsecond=0)
        if data.get('end_time'):
            end_time = make_aware(parse_datetime(data['end_time']), timezone=utc).replace(microsecond=0)
        else:
            end_time = None

        return start_time, end_time

    def _rewrite_domain(self, target):
        return rewrite_internal_domains(target, default_domain=self.server.default_domain, internal_domains=self.internal_domains)

    def _parse_protocol_text(self, protocol):

        if not protocol:
            return None

        protocol_text = protocol.strip().split(' ', 1)[0]

        if protocol_text == 'SIP':
            return Leg.SIP
        elif protocol_text == 'WebRTC':
            return Leg.WEBRTC
        elif protocol_text == 'H323':
            return Leg.H323
        elif protocol_text == 'TEAMS':
            return Leg.TEAMS
        elif protocol_text == 'RTMP':
            return Leg.STREAM
        elif protocol_text == 'GMS':
            return Leg.GMS
        elif protocol_text == 'MSSIP':
            return Leg.LYNC
        return None

    def parse_target_data(self, target):

        target = self._rewrite_domain(clean_target(target))

        from endpoint.models import Endpoint
        endpoint = Endpoint.objects.get_from_uri(target, only='id')
        if endpoint:
            endpoint_kwargs = {'endpoint': endpoint}
        else:
            endpoint_kwargs = {}

        if is_phone(target):
            target = is_phone(target)

        return target, endpoint_kwargs

    def parse_streams(self, streams):

        if not streams or isinstance(streams, str):
            return Counter()

        stats = Counter()
        for stream in streams:
            stats['packetloss'] += int(stream['rx_packets_lost'])
            stats['total_packets'] += int(stream.get('rx_packets_received') or 0) + int(stream.get('rx_packets_lost') or 0)
            stats['bandwidth'] += int(stream['rx_bitrate']) + int(stream['tx_bitrate'])

            # pexip bug, sometimes rx_resolution is str 'None'
            if stream.get('stream_type') == 'video' and 'x' in str(stream.get('tx_resolution')):
                stats['tx_resolution'] = int(stream['tx_resolution'].split('x')[0])
            if stream.get('stream_type') == 'video' and 'x' in str(stream.get('rx_resolution')):
                stats['rx_resolution'] = int(stream['rx_resolution'].split('x')[0])

        if streams:
            stats.setdefault('tx_resolution', 0)
            stats.setdefault('rx_resolution', 0)

        return stats

    def get_call_for_time(
        self,
        conference_name: str,
        ts_start: datetime = None,
        **kwargs,
    ) -> Tuple[Call, bool]:
        """
        Find call for time using time info and conference name.
        No guid are received for live events and calls can be distributed on multiple nodes
        """

        ts_start_fallback = kwargs.pop('ts_start_fallback', None)
        ts_stop_fallback = kwargs.pop('ts_stop_fallback', None)

        if ts_start:
            ts_start_fallback = ts_start
        ts_stop_fallback = kwargs.get('ts_stop') or ts_stop_fallback or ts_start_fallback + timedelta(minutes=15)

        if not kwargs.get('guid') and not kwargs.get('ts_stop'):
            stop_lte_kwargs = dict(ts_stop__lte=ts_start_fallback + timedelta(hours=48))
        else:
            stop_lte_kwargs = {}

        calls_base_qs = Call.objects.filter(
            server=self.server,
            cospace=conference_name,
        )
        calls = calls_base_qs.filter(
            Q(ts_stop__isnull=True) | Q(ts_stop__gte=ts_start_fallback, **stop_lte_kwargs),
            ts_start__lte=ts_stop_fallback,
        )

        ts_start_limit = ts_start_fallback - timedelta(hours=48)

        created = False

        def _get_existing_call(calls):
            if kwargs.get('guid'):
                call = calls_base_qs.filter(guid=kwargs['guid']).first() or calls.filter(ts_start__gte=ts_start_limit, guid='').first()
            else:
                if not kwargs.get('ts_stop'):
                    calls = calls.filter(ts_start__gte=ts_start_limit)

                if settings.IS_POSTGRES:
                    calls = calls.order_by(RawSQL('ABS(EXTRACT(EPOCH FROM (ts_start - %s)))', (ts_start_fallback,)))
                call = calls.first()

            if call:
                logger.debug('Matched existing call %s, ts_start=%s, ts_stop=%s for space %s',
                             call.pk, ts_start, kwargs.get('ts_stop'), conference_name)
            else:
                logger.debug('Matched no existing call for ts_start=%s, ts_stop=%s for space %s',
                             ts_start, kwargs.get('ts_stop'), conference_name)
            return call

        call = _get_existing_call(calls)

        # pexip may send multiple conference_ended eventsink events for the same call if distributed
        if call and kwargs.get('ts_stop') and not kwargs.get('guid'):
            if Leg.objects.filter(call=call, ts_start__gt=ts_start_limit, ts_stop__isnull=True).exists():
                kwargs.pop('ts_stop', None)

        tenant_fallback = kwargs.pop('tenant_fallback', None)

        if not call:  # no match, lock server and try again before creating call
            with transaction.atomic():
                self.server.acquire_lock('call')
                call = _get_existing_call(calls)
                if not call:
                    kwargs['ts_start'] = ts_start_fallback
                    if tenant_fallback and not kwargs.get('tenant'):
                        kwargs['tenant'] = tenant_fallback
                    call = Call.objects.create(server=self.server, cospace=conference_name, **kwargs)
                    logger.debug('Created call %s for ts_start=%s, ts_stop=%s for space %s',
                             call.pk, ts_start, kwargs.get('ts_stop'), conference_name)
                    created = True

        if tenant_fallback and not call.tenant and not created:
            kwargs['tenant'] = tenant_fallback

        if ts_start:
            kwargs['ts_start'] = ts_start

        if call.ts_stop and not kwargs.get('ts_stop'):
            pass  # old event? ignore changes.
        elif not created:
            from policy.models import CustomerPolicyState

            if not call.ts_finalized or kwargs.get('ts_finalized'):
                if kwargs.get('ts_finalized') and call.ts_finalized:
                    kwargs.pop('ts_finalized')

                changed = maybe_update(call, kwargs)
            else:
                changed = False

            if changed:
                CustomerPolicyState.objects.update_call(cluster=self.server.cluster, name=conference_name,
                                                 pexip_tenant_id=call.tenant)

        return call, created

    def get_or_create_leg(self, call, guid, participant_data):
        """
        get existing leg object
        """
        leg_qs = Leg.objects.filter(ts_start__gt=participant_data['ts_start'] - timedelta(days=3)) \
            .select_for_update(of=('self',))

        try:
            leg = leg_qs.get(server=self.server, guid=guid)
            created = False
        except Leg.DoesNotExist:
            self.server.acquire_lock('leg')
            leg, created = leg_qs.get_or_create(server=self.server, guid=guid, defaults=participant_data)

        return leg, created

    def get_tenant(self, tag=None, target=None, room_alias=None, conference=None):
        _customer, tenant = self.get_customer_tenant(
            tag=tag, target=target, room_alias=room_alias, conference=conference
        )
        return tenant

    def get_customer_tenant(
        self, tag: str = None, target: str = None, room_alias: str = None, conference: str = None
    ):

        if tag:
            tenant = dict(parse_qsl(tag)).get('t')
            if tenant:
                customer = Customer.objects.find_customer(
                    pexip_tenant_id=tenant, cluster=self.server.cluster
                )
                return customer, {
                    'tenant': tenant,
                    'tenant_fk': tenant_obj(tenant),
                }

        customer = CustomerMatch.objects.get_customer_for_pexip(conference, {
            'local_alias': room_alias,
            'remote_alias': target,
        }, cluster=self.server.cluster)

        if not customer and (target or room_alias):
            customer = CustomerMatch.objects.match({
                'local_alias': room_alias,
                'remote_alias': target,
            }, cluster=self.server.cluster)

        if customer:
            return customer, {
                'tenant': customer.get_pexip_tenant_id(),
                'tenant_fk': tenant_obj(customer.pexip_tenant_id),
            }

        return None, {}

    def get_org_unit(self, conference: str, local_alias: str, target: str = None, customer=None):
        conference = Conference.objects.match({'name': conference, 'local_alias': local_alias})
        if conference and conference.organization_unit:
            org_unit = conference.organization_unit
        else:
            org_unit = get_org_unit(target or local_alias)
        if org_unit and customer and org_unit.customer_id != customer.pk:
            return None
        return org_unit

    def parse_float_timestamp(self, ts):
        result = datetime.utcfromtimestamp(ts)
        return result.replace(tzinfo=utc)


class PexipParser(PexipParserBase):

    def parse_call(self, call_data, history_log=None):

        if not call_data.get('id'):
            return

        if call_data.get('participant_count') == 0 or call_data.get('duration', 60) < 60:
            return

        start_time, end_time = self._parse_times(call_data)
        conference_room_id = _conference_id(call_data['name'], self.server.cluster_id)

        kwargs = self.get_tenant(tag=call_data.get('tag') or call_data.get('service_tag'), conference=call_data['name'])

        if call_data.get('participant_count'):
            kwargs['leg_count'] = call_data['participant_count']

        kwargs['ts_finalized'] = now()

        call, created = self.get_call_for_time(call_data['name'], guid=call_data['id'], ts_start=start_time, ts_stop=end_time,
                              cospace_id=conference_room_id, **kwargs)

        call = call.merge_calls('cospace')[0]

        if call_data.get('participants'):
            participant_ids = [p.strip('/').split('/')[-1] for p in call_data['participants']]
            from statistics import tasks

            tasks.move_call_legs_to_call.apply_async(
                [self.server.id, call.pk, participant_ids], countdown=30
            )

        if history_log:
            call.pexip_history_logs.add(history_log)

        return call

    def parse_participant(self, participant, history_log=None):

        if not participant['start_time']:
            return

        if participant['service_type'] in ('ivr', 'two_stage_dialing'):
            return

        start_time, end_time = self._parse_times(participant)

        participant['local_alias'] = participant['local_alias'].replace('sip:', '')
        participant['remote_alias'] = participant['remote_alias'].replace('sip:', '')

        if start_time and end_time:
            participant['duration'] = int((end_time - start_time).total_seconds())

        target = participant['remote_alias'] or participant['local_alias']
        target, endpoint_kwargs = self.parse_target_data(target)

        kwargs = {}

        protocol = self._parse_protocol_text(participant['protocol'])
        if protocol == Leg.WEBRTC:
            target = 'webrtc'
        kwargs['is_guest'] = True  # TODO can a user be logged in?

        room_alias = self._rewrite_domain(participant['local_alias'] or participant['remote_alias'])

        stats = self.parse_streams(participant.get('streams') or ())

        customer, tenant_kwargs = self.get_customer_tenant(
            participant.get('service_tag') or participant.get('tag'),
            target,
            room_alias,
            participant.get('conference_name'),
        )
        kwargs.update(tenant_kwargs if tenant_kwargs else {'tenant': ''})

        if participant.get('license_count'):
            kwargs['license_count'] = participant['license_count']
            kwargs['license_type'] = participant['license_type']

        should_count_stats = True
        if end_time:
            should_count_stats = (end_time - start_time).total_seconds() > 60

        if protocol in (Leg.LYNC, Leg.LYNC_SUB, Leg.TEAMS, Leg.GMS) and participant['call_direction'] == 'out':
            if not self.server.keep_external_participants:
                should_count_stats = False

        if stats.get('rx_resolution') is not None:
            kwargs['rx_pixels'] = stats['rx_resolution']
            kwargs['tx_pixels'] = stats['tx_resolution']

        if protocol in {Leg.LYNC, Leg.TEAMS, Leg.GMS}:
            guid = participant['id']
        else:
            guid = participant['call_uuid'] or participant['id']

        guid2 = participant['id']

        call_guid = None
        if participant.get('conference'):
            call_guid = participant['conference'].strip('/').split('/')[-1]

        call, _created = self.get_call_for_time(participant['conference_name'],
                                      guid=call_guid,
                                      ts_start_fallback=start_time,
                                      ts_stop_fallback=end_time,
                                      tenant_fallback=self.get_tenant(room_alias=room_alias).get('tenant'),
                                      )

        conversation_id = participant['conversation_id']
        conversation = None

        if conversation_id and conversation_id != guid:
            # make sure conversation exists so it can be locked later
            conversation = LegConversation.objects.get_or_create(server=self.server, guid=conversation_id,
                                                                 defaults=dict(first_leg_guid='')
                                                                 )[0]

        org_unit = self.get_org_unit(
            participant['conference_name'], participant['local_alias'], target
        )
        if customer and org_unit and customer.pk != org_unit.pk:
            org_unit = None

        with transaction.atomic():

            defaults = dict(
                call=call,
                guid2=guid2,
                target=target[:300],
                remote=participant['remote_alias'][:300],
                local=participant['local_alias'],
                direction=participant['call_direction'],
                ts_start=start_time,
                ts_stop=end_time,
                ou=get_ou(target),
                org_unit=org_unit,
                protocol=protocol,
                service_type=participant['service_type'],
                role=participant['role'],
                should_count_stats=should_count_stats,
                packetloss_percent=stats['packetloss'] / (stats['total_packets'] or 1),
                bandwidth=stats['bandwidth'],
                name=re.sub(r'\s\s+', ' ', (participant.get('display_name') or '').split('|')[0], re.DOTALL).strip()[:300],
                **kwargs,
                **endpoint_kwargs,
            )

            if conversation:
                conversation, should_count_stats = self.update_conversation(conversation, guid, defaults)
                kwargs['conversation'] = conversation
                kwargs['should_cont_stats'] = should_count_stats

            leg, created = self.get_or_create_leg(call, guid, defaults)

            changed = False
            if not created:
                changed = maybe_update(leg, defaults)

        is_gateway = participant.get('service_type') == 'gateway'

        if (changed or created) and leg.ts_stop and leg.should_count_stats and leg.ts_stop > now() - timedelta(hours=1):  # why doesnt all eventsink events arrive?
            from policy.models import CustomerPolicyState
            CustomerPolicyState.objects.change_participants(-1, gateway=is_gateway, cluster=self.server.cluster, pexip_tenant_id=kwargs.get('tenant'),
                                                            guid=conversation_id, name=participant.get('display_name', '')[:300], fallback=True, source='history')

        if history_log:
            leg.pexip_history_logs.add(history_log)

        if created and call.ts_stop and kwargs.get('ts_stop'):
            call.merge_calls('cospace')

    def _update_and_lock_conversation(self, conversation: LegConversation, new_first_leg_guid=''):
        new_object = LegConversation.objects.select_for_update(of=('self',)).get(pk=conversation.pk)
        conversation.first_leg_guid = new_object.first_leg_guid = new_first_leg_guid
        new_object.save()
        return new_object

    def update_conversation(self, conversation: LegConversation, guid: str, data: Dict):
        should_count_stats = data['should_count_stats']

        if conversation.first_leg_guid == '' and should_count_stats:  # first leg werent countable. overwrite
            return self._update_and_lock_conversation(conversation, guid), should_count_stats
        elif conversation.first_leg_guid != guid and should_count_stats:
            # check if main leg is shorter
            duration = (data['ts_stop'] - data['ts_start']).total_seconds()
            shorter_existing_main_leg = Leg.objects.filter(server=self.server, guid=conversation.first_leg_guid, ts_stop__isnull=False, duration__lt=duration).first()
            if shorter_existing_main_leg:
                logger.info('Changed main leg for conversation %s (%s) from %s to %s', conversation.guid, conversation.id, conversation.first_leg_guid, guid)

                if shorter_existing_main_leg.should_count_stats:
                    shorter_existing_main_leg.should_count_stats = False
                    shorter_existing_main_leg.save(update_fields=['should_count_stats'])

                return self._update_and_lock_conversation(conversation, guid), should_count_stats
            else:
                should_count_stats = False

        return conversation, should_count_stats


class PexipEventParser(PexipParserBase):
    def parse_eventsink_event(self, event, cdr_log=None):

        if not event or not event.get('data'):
            return

        event_scope = event['event'].split('_')[0]
        if event_scope not in ('participant', 'conference'):
            return

        data = event['data']

        if event['event'] in ('conference_started', 'conference_updated', 'conference_ended'):
            return self.handle_eventsink_call(event, data, cdr_log=cdr_log)

        if event['event'] in ("participant_connected", "participant_updated", "participant_disconnected"):

            return self.handle_eventsink_participant(event, data, cdr_log=cdr_log)

    def handle_eventsink_call(self, event, data, cdr_log=None):
        try:
            ts_start = self.parse_float_timestamp(int(data['start_time']))
        except ValueError:
            ts_start = self._parse_times(data)[0]

        kwargs = {
            'cospace_id': _conference_id(data['name'], self.server.cluster_id),
        }
        kwargs.update(self.get_tenant(data.get('tag'), conference=data['name']))

        if data.get('end_time'):
            kwargs['ts_stop'] = self.parse_float_timestamp(int(data['end_time']))

        call, created = self.get_call_for_time(data['name'], ts_start, **kwargs)

        from policy.models import CustomerPolicyState

        if self.parse_float_timestamp(event['time']) < now() - timedelta(hours=10):
            pass  # old event that's been resent
        else:
            if event['event'] == 'conference_ended':
                if self.server.remove_active_call_node(data['name'], event['node']):
                    CustomerPolicyState.objects.change_calls(
                        -1,
                        cluster=self.server.cluster,
                        pexip_tenant_id=kwargs.get('tenant'),
                        name=data['name'],
                        source='eventsink',
                    )
            else:
                if self.server.set_call_active(data['name'], event['node']):
                    CustomerPolicyState.objects.change_calls(
                        1,
                        cluster=self.server.cluster,
                        pexip_tenant_id=kwargs.get('tenant'),
                        name=data['name'],
                        source='eventsink',
                    )
            call.cdr_state_info = data if not call.ts_stop else None

        if cdr_log:
            call.pexip_cdr_event_logs.add(cdr_log)

        return call

    def parse_eventsink_participant(self, event, data):

        if not data.get('connect_time'):
            return  # e.g. connecting. some situation when this still apply?

        protocol = self._parse_protocol_text(data['protocol'])
        if protocol in {Leg.LYNC, Leg.TEAMS, Leg.GMS}:
            guid = data['uuid'] or data['call_id']
            guid2 = data['call_id'] if data['uuid'] else ''
        else:
            guid = data['call_id'] or data['conversation_id']
            guid2 = data['uuid']

        try:
            ts_start = self.parse_float_timestamp(int(data['connect_time'] or event['time']))
        except ValueError:
            ts_start = self._parse_times(data)[0]
        ts_stop = None

        data['source_alias'] = (data.get('source_alias') or '').replace('sip:', '')
        data['remote_alias'] = (data.get('remote_alias') or '').replace('sip:', '')

        kwargs = {}

        if event['event'] == 'participant_disconnected':
            ts_stop = self.parse_float_timestamp(int(event['time']))

            stats = self.parse_streams(data.get('media_streams') or ())
            kwargs['packetloss_percent'] = stats['packetloss'] / (stats['total_packets'] or 1)
            kwargs['bandwidth'] = stats['bandwidth']
            if stats.get('rx_resolution') is not None:
                kwargs['rx_pixels'] = stats['rx_resolution']
                kwargs['tx_pixels'] = stats['tx_resolution']

        local = data['destination_alias'] if data['call_direction'] == 'in' else data['source_alias']
        remote = data['source_alias'] if data['call_direction'] == 'in' else data['destination_alias']

        target, endpoint_kwargs = self.parse_target_data(remote or local)
        room_alias = self._rewrite_domain(local)

        if protocol == Leg.WEBRTC:
            target = 'webrtc'
        kwargs['is_guest'] = True  # TODO can a user be logged in?

        should_count_stats = True
        is_external = False

        if protocol in (Leg.LYNC, Leg.LYNC_SUB, Leg.TEAMS, Leg.GMS) and data['call_direction'] == 'out':
            if not self.server.keep_external_participants:
                should_count_stats = False
            is_external = True

        if should_count_stats:
            if data.get('service_type') in ('ivr', 'two_stage_dialing'):
                should_count_stats = False
            if should_count_stats and ts_stop:
                should_count_stats = (ts_stop - ts_start).total_seconds() > 60

        customer, tenant_kwargs = self.get_customer_tenant(
            data.get('tag'), target, room_alias, data['conference']
        )
        kwargs.update(tenant_kwargs if tenant_kwargs else {'tenant': ''})

        org_unit = self.get_org_unit(data['conference'], local, target, customer=customer)

        logger.info('Tenant for leg %s matched as %s for event %s', guid, kwargs.get('tenant'), event['event'])

        display_name = (data.get('display_name') or '').split('|')[0]

        return dict(
            guid=guid,
            guid2=guid2,
            room_alias=room_alias,  # pop before save
            remote=remote,
            local=local,
            direction=data['call_direction'],
            name=display_name,
            target=target,
            role=data.get('role'),
            service_type=data.get('service_type'),
            should_count_stats=should_count_stats,
            is_external=is_external,
            ts_start=ts_start,
            ts_stop=ts_stop,
            ou=get_ou(target),
            org_unit=org_unit,
            protocol=protocol,
            **kwargs,
            **endpoint_kwargs,
        )

    def handle_eventsink_participant(self, event, data, cdr_log=None):

        participant = self.parse_eventsink_participant(event, data)
        if not participant:
            return

        if data.get('service_type') in ('ivr', 'two_stage_dialing'):
            return

        guid = participant.pop('guid')
        room_alias = participant.pop('room_alias')
        conversation_id = data.get('conversation_id') or guid
        should_count_stats = participant.pop('should_count_stats', False)
        is_external = participant.pop('is_external')

        call_kwargs = {}
        if participant.get('ts_stop'):
            call_kwargs['ts_stop_fallback'] = participant['ts_stop']
            participant['duration'] = int((participant['ts_stop'] - participant['ts_start']).total_seconds())

        call, created = self.get_call_for_time(data['conference'], ts_start_fallback=participant['ts_start'],
                                      tenant_fallback=self.get_tenant(room_alias=room_alias).get('tenant'), **call_kwargs)

        if conversation_id and conversation_id != guid:
            conversation = LegConversation.objects.get_or_create(server=self.server, guid=conversation_id,
                                                                 defaults=dict(first_leg_guid=guid if should_count_stats else ''))[0]
            participant['conversation'] = conversation
            if should_count_stats and conversation.first_leg_guid == '':
                conversation.first_leg_guid = guid
                conversation.save()
            elif conversation.first_leg_guid != guid:
                should_count_stats = False

        from policy.models import CustomerPolicyState
        is_gateway = data.get('service_type') == 'gateway'

        ignore_change = bool(is_external)

        with transaction.atomic():
            leg_data = {
                **participant,
                'should_count_stats': should_count_stats,
                'call': call,
            }

            leg, created = self.get_or_create_leg(call, guid, leg_data)

            should_increase_state = should_count_stats and (created or not leg.should_count_stats) and not participant.get('ts_stop')
            should_decrease_state = not created and (
                (should_count_stats and participant.get('ts_stop')) or
                (leg.should_count_stats and not should_count_stats)
            )

            was_stopped = bool(leg.ts_stop)

            changed = False
            if not created:
                if leg.ts_stop:  # don't overwrite already finished calls. e.g. out of order or old events
                    should_increase_state = False
                    should_decrease_state = False
                else:
                    changed = maybe_update(leg, leg_data)

        leg.cdr_state_info = event['data'] if not leg.ts_stop else None

        if created:  # add existing events
            existing_events = PexipEventLog.objects.filter(ts_created__gt=participant['ts_start'] - timedelta(minutes=5),
                                                           uuid_start__startswith=guid[:36]).only('id')
            try:
                leg.pexip_cdr_event_logs.add(*existing_events)
            except IntegrityError:
                pass

        if not created and changed:
            # participant may change call and customer, e.g. ivr -> conference
            CustomerPolicyState.objects.update_participant(gateway=is_gateway, cluster=self.server.cluster, pexip_tenant_id=participant.get('tenant'),
                                                           guid=conversation_id, name=participant['name'][:300])

        if cdr_log:
            try:
                leg.pexip_cdr_event_logs.add(cdr_log)
            except IntegrityError:  # should always work but has race condition. django bug?
                pass

        if should_decrease_state:  # sometimes a participant can be ivr, and become conference just for disconnect
            logger.info('Decrease participant for conversation %s (leg %s) with tenant %s. gateway=%s', conversation_id, guid, participant.get('tenant'), is_gateway)
            CustomerPolicyState.objects.change_participants(-1, gateway=is_gateway, cluster=self.server.cluster, pexip_tenant_id=participant.get('tenant'),
                                                            guid=conversation_id, name=participant['name'][:300], ignore_change=ignore_change, fallback=was_stopped, source='eventsink')

        if should_increase_state and not participant.get('ts_stop'):

            if self.server.set_call_active(data['conference'], event['node']):
                from policy.models import CustomerPolicyState

                CustomerPolicyState.objects.change_calls(
                    1,
                    cluster=self.server.cluster,
                    pexip_tenant_id=data.get('tenant'),
                    fallback=True,
                    name=data['conference'],
                    source='eventsink',
                )

            CustomerPolicyState.objects.change_participants(1, gateway=is_gateway,
                                                            cluster=self.server.cluster,
                                                            pexip_tenant_id=participant.get('tenant'),
                                                            guid=conversation_id,
                                                            name=participant['name'][:300],
                                                            ignore_change=ignore_change,
                                                            source='eventsink')

        return leg

