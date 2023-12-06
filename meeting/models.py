import json
import logging
from collections import defaultdict, Counter
from copy import deepcopy
from datetime import timedelta, datetime
from time import time
from typing import TYPE_CHECKING, Sequence, NamedTuple, Dict, Union

import reversion
from cacheout import fifo_memoize
from django.conf import settings
from django.db import models, transaction
from django.db.models import Q
from django.urls import reverse
from django.utils.functional import cached_property
from django.utils.timezone import now, utc
from django.utils.translation import ugettext_lazy as _
from oauthlib.common import urlencode
from sentry_sdk import capture_exception
from timezone_field import TimeZoneField

from organization.models import OrganizationUnit
from provider.exceptions import NotFound
from provider.models.consts import ENABLE_CELERY, TASK_DELAY
from provider.models.utils import date_format, _date_format_getter, parse_timestamp, new_secret_key, rrule_set
from provider.models.provider import Provider, VideoCenterProvider
from customer.models import Customer
from shared.utils import partial_update, get_multidict
from statistics.parser.utils import clean_target


logger = logging.getLogger(__name__)


if TYPE_CHECKING:
    from provider.ext_api.base import MCUProvider


class MeetingManager(models.Manager['Meeting']):

    def get_by_id_key(self, input_str) -> 'Meeting':

        input_str = str(input_str)
        parts = input_str.split('-', 1)

        meeting = self.get(pk=parts[0])
        if not meeting.secret_key == parts[1]:
            raise Meeting.DoesNotExist
        return meeting

    def get_by_id_key_or_404(self, request, input_str):
        from django.http import Http404
        try:
            return self.get_by_id_key(input_str)
        except Meeting.DoesNotExist:
            from audit.models import AuditLog

            AuditLog.objects.store_request(request, 'Invalid secret for meeting')
            raise Http404

    def get_active(self):

        return self.get_queryset().filter(backend_active=True, ts_stop__gt=now())

    def unbook_expired(self, api: 'MCUProvider'):
        from provider.models.acano import CoSpace
        from provider.models.pexip import PexipSpace

        def check_active(api, cospace_id):
            if not cospace_id:
                return False

            if api.cluster.is_acano:
                return api.get_calls(cospace=cospace_id)[1]
            elif api.cluster.is_pexip:
                cospace = api.get_cospace(cospace_id)
                return api.get_calls(cospace=cospace['name'])[1]

        def unbook(api, m):
            try:
                if check_active(api, m.provider_ref2):
                    logger.info('Meeting is still active, delay room removal')
                    return
            except NotFound:
                pass
            except Exception:
                if settings.TEST_MODE or settings.DEBUG:
                    raise
                capture_exception()
                logger.warning('Unable to get status for meeting room')

            api.unbook(m)
            external = m.get_external_account()

            if external:
                external.provider.get_api(m.customer).unbook(external)

        providers = [api.cluster] + list(api.cluster.get_clustered())  # TODO remove after all meetings are using Cluster instead of single provider

        @fifo_memoize(100)
        def customer_settings(customer_id):
            return api.get_settings(customer_id)

        default_limit = customer_settings(None).remove_expired_meeting_rooms

        for m in Meeting.objects.filter(provider__in=providers, backend_active=True, ts_stop__lt=now()):
            customer_minutes = customer_settings(m.customer_id).remove_expired_meeting_rooms or default_limit
            customer_limit = now() - timedelta(minutes=customer_minutes)

            try:
                overriden_limit = max(
                    list(
                        CoSpace.objects.filter(
                            provider=m.provider_id,
                            provider_ref=m.provider_ref2,
                            ts_auto_remove__isnull=False,
                        ).values_list('ts_auto_remove', flat=True)
                    )
                    + list(
                        PexipSpace.objects.filter(
                            cluster=m.provider_id,
                            external_id=m.provider_ref2,
                            ts_auto_remove__isnull=False,
                        ).values_list('ts_auto_remove', flat=True)
                    )
                )
            except ValueError:
                limit = customer_limit
            else:
                limit = max(customer_limit, overriden_limit)

            if m.is_recurring:
                ruleset = m.rrule_set
                rrule = ruleset._rrule[0]

                if not rrule._count and not rrule._until:  # no end limit
                    if (now() - m.ts_start) > 365:
                        unbook(api, m)
                    continue

                if list(ruleset)[-1].replace(tzinfo=utc) < limit:
                    try:
                        unbook(api, m)
                    except Exception:
                        capture_exception()
            elif m.ts_stop < limit:
                try:
                    unbook(api, m)
                except Exception:
                    capture_exception()


@reversion.register
class Meeting(models.Model):

    ACANO_LAYOUT_CHOICES = (
        ('automatic', _('Automatisk')),
        ('allEqual', _('Dela utrymme mellan deltagare')),
        ('speakerOnly', _('Endast talare')),
        ('telepresence', _('Talare med övriga deltagare flytande')),
        ('stacked', _('Talare med övriga deltagare under')),
    )

    provider = models.ForeignKey(Provider, on_delete=models.CASCADE)
    customer = models.ForeignKey(Customer, verbose_name=_('Kund'), on_delete=models.CASCADE)

    secret_key = models.CharField(default=new_secret_key, max_length=48)

    title = models.CharField(max_length=100, blank=True)

    creator = models.CharField(max_length=80)
    creator_ip = models.GenericIPAddressField(null=True, unpack_ipv4=True)
    creator_name = ''  # TODO? Ad hoc invites for now
    creator_email = ''  # TODO? Ad hoc invites for now
    uri = ''  # TODO? Ad hoc invites for now
    is_moderator = False  # Used for messages

    meeting_type = models.CharField(max_length=100, blank=True)

    ts_created = models.DateTimeField(auto_now_add=True)
    ts_provisioned = models.DateTimeField(null=True, editable=False)
    ts_deprovisioned = models.DateTimeField(null=True, editable=False)
    ts_unbooked = models.DateTimeField(null=True, editable=False)

    internal_clients = models.IntegerField(blank=True, default=0)
    external_clients = models.IntegerField(blank=True, null=True)
    is_internal_meeting = models.BooleanField(default=False)

    layout = models.CharField(_('Skärmlayout'), max_length=20, choices=ACANO_LAYOUT_CHOICES, default='allEqual')
    moderator_layout = models.CharField(_('Skärmlayout moderator'), max_length=20, blank=True, choices=ACANO_LAYOUT_CHOICES, default='')

    source = models.CharField(_('Källa'), max_length=100, default='outlook', blank=True)

    password = models.CharField(_('PIN-kod'), max_length=36)
    moderator_password = models.CharField(
        _('PIN-kod moderator'),
        max_length=36,
        blank=True,
        default='',
    )

    ts_start = models.DateTimeField()
    ts_stop = models.DateTimeField()
    timezone = TimeZoneField(null=True, blank=True)

    # TODO: remove Meeting.recurring and Meeting.recurring_exceptions
    recurring_master = models.ForeignKey('meeting.RecurringMeeting', null=True, on_delete=models.CASCADE,
                                         db_index=False, related_name='occurences')

    is_recurring = models.BooleanField(default=False)
    recurring = models.CharField(blank=True, max_length=100)
    recurring_exceptions = models.CharField(blank=True, max_length=200)
    recurrence_id = models.CharField(blank=True, null=True, max_length=256)
    ical_uid = models.CharField(max_length=256, blank=True, default='')

    is_private = models.BooleanField(default=False, blank=True)

    room_info = models.TextField(blank=True)
    settings = models.TextField(blank=True)
    recording = models.TextField(blank=True)
    webinar = models.TextField(blank=True)

    backend_active = models.BooleanField(default=False)
    ts_activated = models.DateTimeField(null=True, editable=False)

    is_superseded = models.BooleanField(default=False)
    parent = models.ForeignKey('self', null=True, blank=True, related_name='prev_bookings', on_delete=models.SET_NULL)

    customer_confirmed = models.DateTimeField(blank=True, null=True)

    organization_unit = models.ForeignKey('organization.OrganizationUnit', null=True, db_index=False, on_delete=models.SET_NULL)

    provider_ref = models.CharField(max_length=128, blank=True)
    provider_ref2 = models.CharField(max_length=128, blank=True)
    provider_secret = models.CharField(max_length=128, blank=True)

    existing_ref = models.BooleanField(default=False, blank=True)

    schedule_id = models.CharField(max_length=20, editable=False)

    objects: 'models.Manager[Meeting]' = MeetingManager()

    class Meta:
        db_table = 'meeting_meeting'
        indexes = [
            models.Index(name='meeting_recurring_master', fields=['recurring_master'], condition=Q(recurring_master__isnull=False)),
            models.Index(name='meeting_org_unit', fields=('organization_unit',), condition=models.Q(organization_unit__isnull=False)),
        ]

    @property
    def id_key(self):
        return '%s-%s' % (self.pk, self.secret_key)

    @property
    def is_active(self):
        return self.backend_active

    @property
    def ts_start_corrected(self):
        return self.ts_start - timedelta(seconds=self.customer.meeting_add_seconds_before)

    @property
    def ts_stop_corrected(self):
        return self.ts_stop + timedelta(seconds=self.customer.meeting_add_seconds_after)

    @cached_property
    def api(self):
        return self.provider.get_api(self.customer)

    def copy(self, **new_data):
        copy = Meeting.objects.get(pk=self.pk) if self.pk else deepcopy(self)

        copy.ts_provisioned = None
        copy.ts_deprovisioned = None

        for k, v in new_data.items():
            setattr(copy, k, v)

        copy.pk = copy.id = copy.parent = None
        copy.save()
        return copy

    ts_start_lifesize = _date_format_getter('ts_start')
    ts_stop_lifesize = _date_format_getter('ts_stop')
    ts_start_lifesize_corrected = _date_format_getter('ts_start_corrected')
    ts_stop_lifesize_corrected = _date_format_getter('ts_stop_corrected')

    @property
    def recurring_exceptions_corrected(self):

        parts = self.recurring_exceptions.split(',')
        result = []

        add_before = timedelta(seconds=self.customer.meeting_add_seconds_before)

        for p in parts:
            if not p:
                continue
            ts = parse_timestamp(p)
            result.append(date_format(ts - add_before))

        return ','.join(result)

    @property
    def should_book_external_client(self):
        """
        External provider are mostly deprecated. It's main use was providers
        that required separate MCU for multipart calls but could call directly
        to each other. Kept in place to maybe later enable extra interface for
        external clients, e.g. proxy/jump host or such
        """
        if self.provider.is_acano or self.provider.is_pexip:
            return False
        if self.password or self.external_clients:
            return True

        if self.is_internal_meeting:
            if self.internal_clients == 2 and not self.external_clients:
                return False

        if self.customer.always_enable_external:
            return True

        return False

    @property
    def has_started(self):
        if self.ts_start_corrected <= now():
            return True
        return False

    @property
    def has_ended(self):
        if self.ts_stop_corrected <= now():
            return True
        return False

    @property
    def is_ongoing(self):
        return self.backend_active and self.has_started and not self.has_ended

    def confirm(self):
        self.customer_confirmed = now()
        self.save()

    def activate(self):

        if self.parent_id:
            Meeting.objects.filter(pk=self.parent_id).update(backend_active=False, is_superseded=True)

        if not self.organization_unit_id:
            from datastore.models.pexip import EndUser
            from datastore.models.acano import User as AcUser

            try:
                if self.provider.is_pexip:
                    self.organization_unit = EndUser.objects.filter(email__email=self.creator)[0].organization_unit
                elif self.provider.is_acano:
                    self.organization_unit = AcUser.objects.filter(username=self.creator)[0].organization_unit
            except IndexError:
                pass

            if not self.organization_unit_id:
                try:
                    self.organization_unit = OrganizationUnit.objects.only('id').filter(pk=Counter(self.endpoints.all().values_list('org_unit', flat=True)).most_common()[0][0])[0]
                except IndexError:
                    pass

        self.backend_active = True
        self.ts_activated = self.ts_activated or now()
        self.save()

        if not settings.TEST_MODE:
            transaction.on_commit(self.schedule)
        else:
            self.schedule()

    def schedule(self, time_changed=False):
        # book stream key for recording

        only_changed = not time_changed

        self.book_streams(only_changed=only_changed)
        self.connect_endpoints()

        if ENABLE_CELERY:
            from provider import tasks

            self.schedule_id = str(time())
            Meeting.objects.filter(pk=self.pk).update(schedule_id=self.schedule_id)

            if self.ts_stop_corrected > now() or getattr(settings, 'DEBUG', False):
                tasks.schedule_meeting_start.apply_async([self.pk, self.schedule_id], eta=max(now() + timedelta(seconds=2), self.ts_start_corrected - timedelta(seconds=TASK_DELAY)))

                tasks.sync_seevia_customer.apply_async([self.customer_id], expires=5 * 60)
            self.schedule_add_creator_member()
        else:
            self.schedule_add_creator_member()

    def book_streams(self, only_changed=False):

        result = True

        try:
            recording_api = self.customer.get_recording_api()
        except AttributeError:
            recording_api = None

        if recording_api and recording_api.can_schedule_stream:
            recording = self.real_sync_recording(only_changed=only_changed, is_separate_streaming=False)
            if recording:
                try:
                    recording_api.schedule_stream(self, recording)
                except Exception:
                    capture_exception()
                    result = False

        # book stream key for separate stream
        if self.customer.streaming_provider_id:
            streaming_api = self.customer.get_streaming_api()
            if streaming_api.can_schedule_stream:
                stream = self.real_sync_recording(only_changed=only_changed, is_separate_streaming=True, provider=self.customer.streaming_provider)
                if stream:
                    try:
                        streaming_api.schedule_stream(self, stream)
                    except Exception:
                        capture_exception()
                        result = False

        return result

    def deactivate(self, is_unbook=False):
        if is_unbook and not self.has_ended:
            self.ts_unbooked = self.ts_unbooked or now()
        self.backend_active = False
        self.save()

        self.sync_endpoint_bookings()
        if self.recurring_master:
            if is_unbook:
                self.recurring_master.unbook_single(self)  # must be updated on client as well
            self.recurring_master.sync_active()

    def book_external(self, provider):
        from provider.models.provider_data import ClearSeaAccount

        csea = ClearSeaAccount.objects.get_or_create(meeting=self, provider=provider)[0]
        provider.get_api(self.customer).book(csea)

    def schedule_add_creator_member(self):

        from provider import tasks

        if not self.provider.is_acano:
            return

        cospace = self.api.get_cospace(self.provider_ref2)
        if cospace.get('ownerJid') and not self.existing_ref:
            logger.debug('Schedule adding member to meeting %s', self.id)
            if not ENABLE_CELERY:
                return tasks.add_cospace_member(self.pk, cospace['ownerJid'], self.schedule_id)
            else:
                return tasks.add_cospace_member.apply_async([self.pk, cospace['ownerJid'], self.schedule_id], eta=self.ts_start - timedelta(minutes=10))
        else:
            logger.debug('No owner set for meeting %s, skip scheduling adding member', self.pk)

    def schedule_recording(self):
        from recording.models import MeetingRecording

        result = self.sync_recording()

        if not ENABLE_CELERY:
            return result

        for rec in MeetingRecording.objects.filter(meeting=self, ts_activated__isnull=True):
            rec.schedule()

        if result:
            result.refresh_from_db()
        return result

    def add_endpoints(self, endpoints):
        room_info = json.loads(self.room_info)
        existing = {r['endpoint'] for r in room_info if r.get('endpoint')}
        missing_endpoints = {e.email_key for e in endpoints} - existing
        room_info.extend({'endpoint': e} for e in missing_endpoints)

        self.room_info = json.dumps(room_info)
        self.save()
        self.connect_endpoints()

        return existing | missing_endpoints

    def remove_endpoints(self, endpoints, commit_empty=True):
        room_info = json.loads(self.room_info or '[]')

        existing = {r['endpoint'] for r in room_info if r.get('endpoint')}
        remove = {e.email_key for e in endpoints}

        room_info = [r for r in room_info if r.get('endpoint') not in remove]

        if existing - remove or commit_empty:
            self.room_info = json.dumps(room_info)
            self.save()
            self.connect_endpoints()

        return existing - remove

    def connect_endpoints(self):

        from endpoint.models import Endpoint, EndpointMeetingParticipant

        rooms = json.loads(self.room_info or '[]')

        endpoints = Endpoint.objects.distinct().filter(customer=self.customer).filter(
            Q(email_key__in=[r.get('endpoint').split('@')[0] for r in rooms if r.get('endpoint')])
            | Q(sip__in=[clean_target(r.get('dialstring')) for r in rooms if r.get('dialstring')])
            | Q(sip_aliases__sip__in=[clean_target(r.get('dialstring')) for r in rooms if r.get('dialstring')])
        ).filter(connection_type__gte=0)

        for endpoint in endpoints:
            EndpointMeetingParticipant.objects.get_or_create(meeting=self, endpoint=endpoint)

        removed = EndpointMeetingParticipant.objects.filter(meeting=self).exclude(endpoint__in=endpoints).select_related('endpoint')
        previous_endpoints = [r.endpoint for r in removed]
        removed.delete()

        if previous_endpoints or self.ts_start < now() + timedelta(days=2):
            self.sync_endpoint_bookings(extra_endpoints=previous_endpoints)

    def sync_endpoint_bookings(self, extra_endpoints=None):
        from endpoint import tasks

        endpoints = list(self.endpoints.all())
        if extra_endpoints:
            endpoints.extend(extra_endpoints)

        for endpoint in endpoints:
            if ENABLE_CELERY:
                tasks.sync_endpoint_bookings_locked_delay(endpoint.pk)
                tasks.update_active_meeting.apply_async([endpoint.pk], eta=self.ts_start)
                tasks.update_active_meeting.apply_async([endpoint.pk], eta=self.ts_stop)
            else:
                endpoint.sync_bookings()
                endpoint.update_active_meeting()

    def schedule_dialout(self):

        self.sync_dialouts()

        if not ENABLE_CELERY:
            return

        for dialout in MeetingDialoutEndpoint.objects.filter(meeting=self, ts_activated__isnull=True):
            dialout.schedule()

    def sync_dialouts(self, only_changed=False):

        valid_ids = []
        result = []
        for room in json.loads(self.room_info or '[]'):
            if room.get('dialout'):
                existing = MeetingDialoutEndpoint.objects.filter(meeting=self, uri=room.get('dialstring'))
                existing = existing.exclude(backend_active=False, ts_activated__isnull=False)

                if existing:
                    cur = existing.first()
                    created = False
                else:
                    cur = MeetingDialoutEndpoint.objects.create(meeting=self, uri=room.get('dialstring'))
                    created = True

                valid_ids.append(cur.pk)
                if created or not only_changed:
                    result.append(cur)

        for m in MeetingDialoutEndpoint.objects.filter(meeting=self).exclude(pk__in=valid_ids):
            logger.info('Hangup dialout {}, meeting {}'.format(m.pk, self.pk))
            try:
                m.hangup()
            except NotFound:
                pass
            if not m.ts_activated:
                m.delete()

        return result

    def sync_recording(self, only_changed=False):

        result = self.real_sync_recording(only_changed=only_changed, is_separate_streaming=False,
            provider=self.customer.get_videocenter_provider() if self.customer.streaming_provider_id else None)

        if self.customer.streaming_provider_id and self.customer.videocenter_provider_id:
            data = json.loads(self.recording or '{}') or {}
            if data.get('is_live'):
                self.real_sync_recording(only_changed=only_changed, is_separate_streaming=True, provider=self.customer.streaming_provider)

        return result

    def real_sync_recording(self, only_changed=False, is_separate_streaming=False, provider=None):
        "do the sync according to is_separate_streaming"

        from recording.models import MeetingRecording
        data = json.loads(self.recording or '{}') or {}

        existing = MeetingRecording.objects.filter(meeting=self, is_separate_streaming=is_separate_streaming)
        existing = existing.exclude(backend_active=False, ts_activated__isnull=False)  #  already completed

        if is_separate_streaming:
            is_active = data.get('is_live')
        else:
            is_active = data.get('record') or data.get('is_live')

        if not is_active:  # not enabled. stop active, delete future
            for r in existing:
                if r.backend_active:
                    from provider import tasks
                    tasks.stop_record.delay(self.pk, r.pk, r.schedule_id)
                    logger.info('Schedule stop of recording {}, meeting {} due too changes settings'.format(r.pk, self.pk))

                elif not r.ts_activated:
                    r.delete()
            return

        # record
        if not existing:

            if not provider and is_separate_streaming and self.customer.streaming_provider_id:
                provider = self.customer.streaming_provider
            else:
                provider = provider or self.customer.videocenter_provider or VideoCenterProvider.objects.get_active()

            recording = MeetingRecording.objects.create(meeting=self,
                provider=provider,
                is_separate_streaming=is_separate_streaming,
                is_public=data.get('is_public') or False,
                is_live=data.get('is_live') or False,
                name=data.get('name') or '',
                )

            return recording
        else:
            existing = existing[0]

            prev_state = (existing.is_public, existing.is_live, existing.name)

            existing.is_public = data.get('is_public') or False
            existing.is_live = data.get('is_live') or False
            existing.name = data.get('name') or ''

            new_state = (existing.is_public, existing.is_live, existing.name)
            if only_changed and prev_state == new_state:
                return None
            return existing

    def get_external_account(self):
        from provider.models.provider_data import ClearSeaAccount
        try:
            return ClearSeaAccount.objects.get(meeting=self)
        except ClearSeaAccount.DoesNotExist:
            return None

    def get_unprotected_uri(self):
        import hashlib

        if self.provider.is_acano:
            return hashlib.md5(self.provider_ref2.encode('utf-8')).hexdigest()
        else:
            return self.provider_ref

    @property
    def is_webinar(self):
        return bool(self.get_webinar_info())

    @property
    def type_str(self):
        if self.provider.is_external:
            return str(_('Externt möte'))
        if self.provider.is_offline:
            return str(_('Offline-möte'))
        if self.is_webinar:
            return str(_('Webinar'))
        if self.is_private:
            return 'Privat möte'
        if self.meeting_type in ('meeting', ''):
            return str(_('Möte'))
        return str(_('Annat (%s)')) % self.meeting_type

    def get_webinar_info(self):
        if not self.webinar or not json.loads(self.webinar):
            return {}

        data = {
            'uri': '',
            'moderator_pin': '',
            'group': '',
            'user_jids': [],
            'disable_chat': False,
        }
        data.update(json.loads(self.webinar))

        if not data['user_jids']:
            data['user_jids'] = []
        elif isinstance(data['user_jids'], str):
            data['user_jids'] = list(data['user_jids'].split())

        return data

    def get_settings(self):

        recording = {
            'is_live': False,
            'record': False,
        }
        if self.recording:
            try:
                recording.update(json.loads(self.recording or '{}'))
            except ValueError:
                pass

        dialout = []

        if self.room_info:
            try:
                dialout.extend([
                    {
                        'dialout': True,
                        'dialstring': r.get('dialstring'),
                    } for r in json.loads(self.room_info or '[]')
                    if r.get('dialout')
                ])
            except ValueError:
                pass

        settings = {
            'force_encryption': None,
            'disable_chat': False,
            'lobby_pin': '',
            'recording': recording,
            'dialout': dialout,
        }
        settings.update(json.loads(self.settings or '{}'))

        return settings

    def get_preferred_uri(self):
        return self.get_connection_data('preferred_uri')

    @property
    def rrule_set(self):
        return rrule_set(self.ts_start, self.recurring, self.recurring_exceptions, self.timezone)

    def get_ical_file_contents(self):

        recurring = recurring_exceptions = ''
        if self.recurring:
            recurring = '\n{}{}'.format('RRULE:' if ':' not in self.recurring else '', self.recurring)
        if self.recurring_exceptions:
            recurring_exceptions = '\nEXDATE:%s' % self.recurring_exceptions_corrected

        ts_start = self.ts_start_lifesize_corrected
        ts_stop = self.ts_stop_lifesize_corrected

        if not self.external_clients:
            participant_count = self.internal_clients
        else:
            participant_count = 10

        if self.existing_ref:
            uid = '{}-{}'.format(self.provider_ref2, self.pk)  # TODO handle rebooked meetings
        else:
            uid = self.provider_ref2

        data = {
            'uid': uid,
            'title': str(_('Möte för %s')) % self.customer,
            'description': str(_('Bokad %(date)s av %(creator)s')) % dict(date=self.ts_created, creator=self.creator),
            'ts_start': ts_start,
            'ts_stop': ts_stop,
            'ts_created': date_format(self.ts_created),
            'internal_clients': self.internal_clients,
            'external_clients': self.external_clients,
            'only_internal': self.is_internal_meeting,
            'recurring': recurring,
            'recurring_exceptions': recurring_exceptions,
            'conference_id': self.provider_ref,
            'password': self.password,
            'password_arg': 'password=%s' % self.password,
            'participant_count': participant_count,
        }

        from django.template.loader import render_to_string
        return render_to_string('provider/lifesize_ical_meeting.txt', data).replace("\n", "\r\n")

    def get_connection_data(self, key=None):

        provider = self.provider

        try:
            main_domain = self.provider.get_cluster_settings(self.customer).get_main_domain()
        except AttributeError:
            main_domain = provider.internal_domain

        # sip uri
        if self.provider_ref:
            uri_numeric = '%s@%s' % (self.provider_ref, main_domain)
        else:
            uri_numeric = ''

        if self.uri and '@' in self.uri:
            uri = self.uri
        elif self.uri:
            uri = '%s@%s' % (self.uri, main_domain)
        elif json.loads(self.settings or '{}').get('external_uri'):
            uri = json.loads(self.settings or '{}').get('external_uri')
            if not self.provider_ref:
                uri_numeric = uri
        else:
            uri = uri_numeric

        if uri.startswith('@'):
            uri = uri_numeric = self.uri or ''

        data = {
            'password': self.password or '',
            'uri': uri,
            'uri_numeric': uri_numeric or uri,
            'provider_ref': self.provider_ref,
            'secret': self.provider_secret,
            'preferred_uri': self.get_webinar_info().get('uri') or self.provider_ref or '',
        }
        # override
        if self.is_webinar:
            data['preferred_uri'] = self.get_webinar_info().get('uri') or data['preferred_uri']
            try:
                webinar = self.webinars.get()
            except models.ObjectDoesNotExist:
                pass
            else:
                if self.is_moderator:
                    data.update(webinar.override_moderator_connection_data(data))
                else:
                    data.update(webinar.override_connection_data(data))

        elif self.is_moderator:
            if self.moderator_password or self.get_settings().get('lobby_pin'):
                data['password'] = self.moderator_password or self.get_settings().get('lobby_pin')
                if self.api.provider.is_acano:
                    moderator_data = self.api.get_cospace_moderator_settings(self.provider_ref2)
                    if moderator_data:
                        data['secret'] = moderator_data['secret']
                        if moderator_data.get('call_id'):
                            data['provider_ref'] = moderator_data['call_id']

        # override dependant data

        if not data.get('dialstring'):

            if provider.is_acano:
                data['dialstring'] = data['uri']
            elif provider.is_pexip:
                data['dialstring'] = data['uri']
            else:
                data['dialstring'] = '%s##%s' % (provider.ip, data['provider_ref'])

        if not data.get('web_url'):

            def _web_url():
                if self.provider.is_acano:
                    return self.api.get_web_url(data['provider_ref'], data['secret'])

                if self.provider.is_pexip:
                    return self.api.get_web_url(data['uri'], data['password'])

                external = self.get_external_account()
                if external:
                    return external.get_absolute_url()
                return ''

            data['web_url'] = _web_url()

        if key:
            return data[key]
        return data

    @property
    def dialstring(self):
        return self.get_connection_data('dialstring')

    @property
    def pin_dialstring(self):
        provider = self.provider

        if provider.is_acano or provider.is_pexip:
            return self.pin_sip_uri

        password = '*%s' % self.password if self.password else ''
        return '%s##%s%s' % (provider.ip, self.provider_ref, password)

    @property
    def sip_uri(self):
        return self.get_connection_data('uri')

    @property
    def sip_uri_numeric(self):
        return self.get_connection_data('uri_numeric')

    @property
    def h323_uri(self):
        return ''  # TODO add to cluster settings?

    @property
    def pin_sip_uri(self):
        if not self.password:
            return self.sip_uri
        if self.provider.is_pexip:
            return '{}**{}'.format(self.provider_ref, self.password)
        return self.api.get_sip_uri(self.get_unprotected_uri())  # requires api.book_unprotected_access()

    @property
    def join_url(self):

        return self.get_connection_data('web_url')

    def check_possible_rebook(self):
        from recording.models import MeetingRecording
        for r in MeetingRecording.objects.filter(meeting=self):
            if not r.get_api().can_reschedule:
                raise ValueError(_('Du har bokat en inspelning som förhindrar ombokning'))

        if not self.backend_active:
            if not (self.provider.is_acano or self.provider.is_pexip):
                raise ValueError(_('Det här mötet kan inte bokas om'))

        return True

    def save(self, *args, **kwargs):

        if self.is_internal_meeting:
            self.external_clients = None

        self.is_recurring = bool(self.recurring)

        self.source = self.source or 'outlook'

        super().save(*args, **kwargs)

    def as_dict(self, message_format='rtf'):

        message_content = message_title = ''

        if message_format in ('rtf', 'html'):
            message_format = message_format
        else:
            message_format = 'rtf'

        try:
            from ui_message.models import Message
        except ImportError:
            pass
        else:
            try:
                message = Message.objects.get_for_meeting(self)
                message_content = message.format(self)
                message_title = message.format_title(self)
            except Message.DoesNotExist:
                pass

        if not self.creator_email and self.creator:
            try:
                user = self.api.find_user(self.creator) or {}
            except Exception:
                if self.api.cluster.is_pexip:
                    self.creator_email = self.creator
            else:
                self.creator_email = user.get('email') or user.get('primary_email_address') or ''
                self.creator_name = user.get('name') or ''

        return {
            'id': self.id,
            'title': self.title,
            'meeting_id': self.id_key,
            'ts_start': self.ts_start_lifesize,
            'ts_stop': self.ts_stop_lifesize,
            'is_recurring': bool(self.is_recurring),
            'is_private': bool(self.is_private),
            'recurring': self.recurring_master.recurring_rule if self.recurring_master_id else '',
            'recurring_exceptions': self.recurring_master.recurring_exceptions if self.recurring_master_id else '',
            'only_internal': self.is_internal_meeting,
            'internal_clients': self.internal_clients,
            'external_clients': self.external_clients,
            'has_password': bool(self.password),
            'password': self.password,
            'moderator_password': self.moderator_password,
            'rest_url': self.get_api_rest_url(),
            'backend_active': str(self.backend_active),
            'message_title': message_title,
            'message': message_content,
            'room_id': self.get_connection_data('provider_ref'),
            'web_url': self.join_url,
            'sip_uri': self.sip_uri,
        }

    def __str__(self):
        return str(_('Möte #%(id)s för %(customer)s (%(provider)s) den %(date)s')) % dict(id=self.pk, customer=self.customer, provider=self.provider, date=self.ts_start)

    def get_api_rest_url(self):
        return reverse('api_meeting_rest', args=[self.id_key])

    def get_api_client_url(self):
        url = ''

        if not self.provider_ref2 or not self.backend_active:
            url = ''
        elif self.provider.is_pexip:
            url = 'configuration/v1/conference/{}/'.format(self.provider_ref2)
        elif self.provider.is_acano:
            url = 'coSpaces/{}'.format(self.provider_ref2)

        return reverse('rest_client') + '?' + urlencode({'url': url, 'provider': self.provider_id}.items())

    def get_absolute_url(self):
        if self.provider_id and (self.provider.is_external or self.provider.is_offline):
            return reverse('meeting_debug_details_epm', args=[self.pk])
        return reverse('meeting_debug_details', args=[self.pk])

    def get_debug_details_url(self):
        return self.get_absolute_url()

    def get_invite_url(self):
        return reverse('meeting_invite', args=[self.pk])

    def recording_embed_callback(self):
        if self.recording:
            recording = json.loads(self.recording)

            if recording.get('callback'):
                from provider.ext_api.base import RecordingProviderAPI
                RecordingProviderAPI.embed_callback(self, recording['callback'])

    def fallback_record(self):
        videocenter = self.customer.get_videocenter_provider()
        api = self.customer.get_api()

        if videocenter and videocenter.recording_key and api and api.cluster.is_acano:
            uri = 'sip:record:{}@{}'.format(videocenter.recording_key, videocenter.hostname or videocenter.ip)
            call_id = api.add_call(self.provider_ref2)
            return call_id, api.add_call_leg(call_id, uri)
        return None, None


class MeetingDialoutEndpoint(models.Model):

    meeting = models.ForeignKey(Meeting, on_delete=models.CASCADE, related_name='dialouts')
    uri = models.CharField(max_length=200)
    provider_ref = models.CharField(max_length=100)
    backend_active = models.BooleanField(default=False)
    ts_activated = models.DateTimeField(null=True)
    ts_deactivated = models.DateTimeField(null=True)

    schedule_id = models.CharField(max_length=20)

    class Meta:
        db_table = 'meeting_meetingdialoutendpoint'


    def call(self):
        self.meeting.api.dialout(self.meeting, self)

    def hangup(self):
        self.meeting.api.close_call(self.meeting, self)

    def activate(self, commit=True):
        self.backend_active = True
        self.ts_activated = now()
        if commit:
            self.save()

    def check_active(self, commit=True):
        try:
            self.meeting.api.get_call_leg(self.provider_ref)
        except NotFound:
            if commit:
                self.backend_active = False
            return False
        else:
            return True

    def deactivate(self, commit=True):
        self.backend_active = False
        self.ts_deactivated = now()
        if commit:
            self.save()

    def schedule(self):

        self.schedule_id = str(time())
        self.save()

        if not ENABLE_CELERY:
            return

        if self.meeting.ts_stop_corrected < now():
            return

        from provider import tasks
        tasks.dialout.apply_async([self.meeting_id, self.pk, True, self.schedule_id],
                                  eta=self.meeting.ts_start_corrected - timedelta(seconds=TASK_DELAY))


class MeetingWebinar(models.Model):
    "settings for participant connection settings (except for moderator password)"

    meeting = models.ForeignKey(Meeting, related_name='webinars', on_delete=models.CASCADE)
    group = models.CharField(max_length=100, blank=True)
    access_method_id = models.CharField(max_length=128, blank=True)
    provider_ref = models.CharField(max_length=128, blank=True)
    provider_secret = models.CharField(max_length=128, blank=True)
    password = models.CharField(_('Moderator-lösenord'), max_length=50, blank=True)

    class Meta:
        db_table = 'meeting_meetingwebinar'

    def get_moderator_meeting(self):
        meeting = Meeting.objects.get(pk=self.meeting_id)
        meeting.is_moderator = True
        meeting.save = None  # type: ignore  # noqa
        return meeting

    def get_override_connection_data(self):

        return {}

    def override_connection_data(self, data):
        return self.get_override_connection_data()

    @property
    def join_url(self):
        return self.meeting.api.get_web_url(
            self.provider_ref, self.provider_secret or self.password
        )

    def override_moderator_connection_data(self, data):
        # TODO remove get_webinar_info. bug for a while where participant password was saved in both places

        return {
            'provider_ref': self.provider_ref,
            'password': self.meeting.get_webinar_info().get('moderator_pin', '') or self.password,
            'uri': self.meeting.api.get_sip_uri(self.provider_ref),
            'uri_numeric': self.meeting.api.get_sip_uri(self.provider_ref),
            'web_url': self.join_url,
        }


class RecurringMeeting(models.Model):
    provider = models.ForeignKey(Provider, on_delete=models.CASCADE)
    customer = models.ForeignKey(Customer, verbose_name=_('Kund'), on_delete=models.CASCADE)

    recurring_rule = models.CharField(blank=True, max_length=100)
    recurring_exceptions = models.CharField(blank=True, max_length=200)
    recurring_overrides = models.CharField(blank=True, max_length=200)

    duration = models.IntegerField(null=True)

    uid = models.TextField()

    external_occasion_handling = models.BooleanField(default=False)

    first_meeting = models.ForeignKey(Meeting, null=True, on_delete=models.SET_NULL)

    def delete(self, using=None, keep_parents=False):
        for meet in self.occurences.all():
            meet.deactivate()
            meet.delete()

        super().delete(using=using, keep_parents=keep_parents)

    @property
    def rrule_set(self):
        return rrule_set(
            self.first_meeting.ts_start,
            self.recurring_rule,
            self.recurring_exceptions,
            self.first_meeting.timezone
        )

    class SyncResult(NamedTuple):
        created: Sequence[Meeting]
        deleted: Sequence[Meeting]
        changed: Sequence[Meeting]

    @property
    def active_meetings(self):
        return Meeting.objects.filter(recurring_master=self, ts_unbooked__isnull=True)

    @property
    def should_sync(self):
        if self.external_occasion_handling or not self.first_meeting_id:
            return False
        return True

    def sync(self, update_fields: Union[bool, Sequence[str]] = False):

        assert self.first_meeting

        if partial_update(self.first_meeting, {'recurrence_id': date_format(self.first_meeting.ts_start)}):
            if settings.TEST_MODE:
                raise ValueError('Invalid first meeting recurrence_id')

        if self.external_occasion_handling:
            raise ValueError('Occasions are handled in another system')

        missing_times, existing, extra = self.get_state()

        duration = self.first_meeting.ts_stop - self.first_meeting.ts_start

        created = []
        deleted = []
        changed = []

        for recurrence_id, ts in missing_times.items():
            cur = self.first_meeting.copy(
                recurrence_id=recurrence_id, ts_start=ts, ts_stop=ts + duration, backend_active=True
            )
            created.append(cur)

        for meetings in extra.values():
            for meeting in meetings:
                if meeting.has_ended:
                    meeting.deactivate(is_unbook=True)
                else:
                    meeting.api.unbook(meeting)

                deleted.append(meeting)

        if update_fields:
            if update_fields is True:
                update_fields = ['title', 'creator', 'room_info', 'settings', 'webinar']

            data = {k: getattr(self.first_meeting, k) for k in update_fields}
            for meeting in existing.values():
                if partial_update(meeting, data):
                    changed.append(meeting)

        if self.first_meeting.provider_ref:
            if not self.duration:
                self.duration = int(
                    (self.first_meeting.ts_stop - self.first_meeting.ts_start).total_seconds()
                )
            self.sync_active()

        return self.SyncResult(created, deleted, changed)

    def sync_active(self):
        all_upcoming = self.occurences.filter(
            backend_active=True,
            ts_unbooked__isnull=True,
            ts_stop__gte=now(),
        ).order_by('ts_start')

        soon = all_upcoming.filter(
            ts_start__lte=now() + timedelta(days=60),
        )

        if soon:
            upcoming = soon
        else:
            upcoming = all_upcoming[:1]

        for meeting in upcoming:
            meeting.provider_ref = self.first_meeting.provider_ref
            meeting.provider_ref2 = self.first_meeting.provider_ref2
            meeting.ts_provisioned = self.first_meeting.ts_provisioned
            meeting.ts_deprovisioned = self.first_meeting.ts_deprovisioned

            meeting.activate()

    def unbook(self):
        api = self.first_meeting.api
        for meeting in self.occurences.filter(
            backend_active=True,
            ts_unbooked__isnull=True,
            ts_stop__gte=now(),
        ):
            api.unbook(meeting)

    def unbook_single(self, meeting):
        """
        Unbook meeting and add to exceptions. Exception must be saved on client as well for updates
        """
        self.recurring_exceptions = '{},{}'.format(
            self.recurring_exceptions.rstrip(','), meeting.recurrence_id
        ).strip(',')
        self.save(update_fields=['recurring_exceptions'])
        if meeting.backend_active:
            meeting.api.unbook(meeting)

    def rebook(self, meeting):
        """Reschedule all future events"""
        duration = (meeting.ts_stop - meeting.ts_start).total_seconds()

        if date_format(meeting.ts_start) == meeting.recurrence_id:
            if not self.duration or duration == self.duration:
                return self.sync_active()  # time is not changed

        if self.occurences.filter(ts_stop__lt=meeting.ts_stop, backend_active=True):
            pass  # TODO move this and future meetings to separate recurring series

        self.duration = duration
        self.save(update_fields=['duration'])

    class RecurringState(NamedTuple):
        missing_times: Dict[str, datetime]
        existing: Dict[str, Meeting]
        extra: Dict[str, Sequence[Meeting]]

    def get_state(self) -> RecurringState:

        if not self.first_meeting:
            raise ValueError('No first meeting available')

        ruleset = self.rrule_set

        local_meetings = get_multidict(Meeting.objects.filter(recurring_master=self, backend_active=True)
                                                      .exclude(pk=self.first_meeting_id),
                                       key=lambda m: m.recurrence_id)

        first_recurrence_id = date_format(self.first_meeting.ts_start)
        local_meetings.setdefault(first_recurrence_id, []).insert(0, self.first_meeting)

        time_limit = self.first_meeting.ts_start + timedelta(days=365)

        count_limit = 365

        rrule = ruleset._rrule[0]

        if rrule._until:
            time_limit = min(rrule._until, time_limit)
        elif rrule._count < count_limit:
            time_limit = min(list(ruleset)[-1], time_limit)

        missing_times = {}
        existing = {}

        overrides = set(self.recurring_overrides.split(','))

        extra = defaultdict(list)

        for i, ts in enumerate(ruleset):
            if i > count_limit or ts > time_limit:
                break

            recurrence_id = date_format(ts)

            if recurrence_id in overrides:
                pass
            if recurrence_id in local_meetings:
                existing[recurrence_id] = local_meetings[recurrence_id][0]
                if len(local_meetings[recurrence_id]) > 1:
                    extra[recurrence_id].extend(local_meetings[recurrence_id])
            else:
                missing_times[recurrence_id] = ts

        extra_ids = set(local_meetings) - set(existing) - overrides
        for recurrence_id in extra_ids:
            extra[recurrence_id].extend(local_meetings[recurrence_id])

        return self.RecurringState(missing_times, existing, dict(extra))


