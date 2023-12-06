
import json
import logging
from datetime import timedelta
from importlib import import_module
from random import shuffle

import requests
import sentry_sdk
from celery import Task
from django.conf import settings
from django.core.cache import cache
from django.db import transaction, DatabaseError
from django.utils.dateparse import parse_datetime
from django.utils.timezone import now
from django.utils.translation import gettext_lazy as _
from sentry_sdk import capture_exception, capture_message

from conferencecenter.celery import app
from provider.exceptions import NotFound, ResponseConnectionError, AuthenticationError

logger = logging.getLogger(__name__)


@app.task(bind=True)
def schedule_meeting_start(self: Task, meeting_id: int, schedule_id: int = None):
    from meeting.models import Meeting
    try:
        meeting = Meeting.objects.get(pk=meeting_id)
    except Meeting.DoesNotExist:
        logger.warning('Meeting %s could not be found', meeting_id)
        return

    if meeting.schedule_id and meeting.schedule_id != schedule_id:
        logger.debug('Meeting %s started, but has been rescheduled', meeting_id)
        return

    if meeting.backend_active:
        logger.debug('Meeting %s started', meeting_id)
        meeting.schedule_recording()
        meeting.schedule_dialout()
        meeting.sync_endpoint_bookings()
    else:
        logger.info('Meeting %s not started, backend_active=False', meeting_id)


@app.task(bind=True)
def add_cospace_member(
    self: Task, meeting_id: int, member_jid: str, schedule_id: int = None, moderator=True
):

    from meeting.models import Meeting

    try:
        meeting = Meeting.objects.get(pk=meeting_id)
    except Meeting.DoesNotExist:
        raise self.retry(delay=1)

    if not meeting.backend_active:
        logger.info('Meeting %s unscheduled, skipping adding member %s', meeting_id, member_jid)
        return

    if meeting.schedule_id and meeting.schedule_id != schedule_id:
        logger.info(
            'Meeting %s schedule id has changed, skipping adding member %s', meeting_id, member_jid
        )
        return

    existing_members = meeting.api.get_members(meeting.provider_ref2, include_permissions=False)
    if member_jid in (e['user_jid'] for e in existing_members):
        logger.info('%s is already a member for meeting %s', member_jid, meeting_id)
        return

    call_leg_profile = None

    if moderator:
        try:
            call_leg_profile = meeting.api._get_webinar_call_legs()[1]
        except AttributeError:
            pass

    try:
        meeting.api.add_member(
            meeting.provider_ref2,
            member_jid,
            can_add_remove_members=True,
            can_remove_self=True,
            can_destroy=True,
            can_delete_messages=True,
            call_leg_profile=call_leg_profile,
        )
    except NotFound:
        logger.warning('Could not add member %s to meeting %s - 404 error', member_jid, meeting_id)
        return

    remove_cospace_member.apply_async([meeting_id, member_jid], eta=meeting.ts_stop_corrected)


@app.task(bind=True)
def remove_cospace_member(self: Task, meeting_id: int, member_jid: str, schedule_id: int = None):

    from meeting.models import Meeting
    meeting = Meeting.objects.get(pk=meeting_id)
    if not meeting.backend_active:
        return

    if meeting.schedule_id and meeting.schedule_id != schedule_id:
        return

    meeting.api.remove_member(meeting.provider_ref2, member_jid)


@app.task(bind=True)
def dialout(self: Task, meeting_id: int, dialout_id: int, check_active=True, schedule_id: int = None):

    from meeting.models import MeetingDialoutEndpoint
    from meeting.models import Meeting
    meeting = Meeting.objects.get(pk=meeting_id)
    if not meeting.backend_active:
        logger.info('Dialout %s from meeting id %s not performed, backend_active=False',
            dialout_id, meeting_id)
        return

    dialout = MeetingDialoutEndpoint.objects.get(pk=dialout_id)

    if schedule_id and dialout.schedule_id and schedule_id != dialout.schedule_id:
        logger.info('Dialout %s from meeting id %s has been rescheduled, returning.',
            dialout_id, meeting_id)
        return

    if meeting.provider.supports_dialout:
        try:
            with transaction.atomic():
                Meeting.objects.select_for_update().get(pk=meeting_id)
                dialout.call()
        except Exception as e:
            capture_exception()
            self.retry(exc=e, countdown=15)
        else:
            if check_active:
                check_dialout.apply_async([meeting_id, dialout_id, schedule_id], countdown=40)


@app.task(bind=True)
def check_dialout(self: Task, meeting_id: int, dialout_id: int, schedule_id: int = None):
    "redial if not active"
    from meeting.models import MeetingDialoutEndpoint
    from meeting.models import Meeting
    meeting = Meeting.objects.get(pk=meeting_id)
    if not meeting.backend_active:
        logger.info('Dialout %s from meeting id %s not checked, backend_active=False',
            dialout_id, meeting_id)
        return

    dialout_obj = MeetingDialoutEndpoint.objects.get(pk=dialout_id)

    if dialout_obj.schedule_id and schedule_id != dialout_obj.schedule_id:
        logger.info('Dialout %s from meeting id %s has been rescheduled, returning.',
            dialout_id, meeting_id)
        return

    if meeting.provider.supports_dialout:
        try:
            is_active = dialout_obj.check_active()
        except Exception as e:
            capture_exception()
            self.retry(exc=e, countdown=15)
        else:
            if not is_active:
                dialout.apply_async([meeting_id, dialout_id, False], countdown=5 * 60)


@app.task(bind=True)
def record(self: Task, meeting_id: int, recording_id, schedule_id: int = None):

    from recording.models import MeetingRecording
    from meeting.models import Meeting
    meeting = Meeting.objects.get(pk=meeting_id)
    if not meeting.backend_active:
        logger.info('Dialout %s from meeting id %s not performed, meeting.backend_active=False',
            recording_id, meeting_id)
        return

    recording = MeetingRecording.objects.get(pk=recording_id)
    if recording.ts_activated:
        logger.info('Recording %s from meeting id %s not started, already active',
            recording_id, meeting_id)

        return

    if recording.schedule_id and schedule_id != recording.schedule_id:
        logger.info('Recording %s from meeting id %s has been rescheduled, returning.',
            recording_id, meeting_id)
        return

    try:
        with transaction.atomic():
            Meeting.objects.select_for_update().get(pk=meeting_id)
            recording.start_record()
        logger.debug('Recording started',
                    extra=dict(meeting_id=meeting_id, recording_id=recording_id,
                    provider_ref=recording.recording_id))

    except Exception as e:
        logger.warning('Recording %s for meeting %s not started, exception!',
            recording_id, meeting_id, exc_info=1)

        capture_exception()

        if record.request.retries >= 2:  # fallback recording
            call_id, call_leg_id = meeting.fallback_record()
            if call_leg_id:
                hangup_call_leg.apply_async([meeting_id, call_leg_id], eta=meeting.ts_stop_corrected)
        else:
            self.retry(exc=e, countdown=15)


@app.task(bind=True)
def stop_record(self: Task, meeting_id: int, recording_id, schedule_id: int = None):

    from recording.models import MeetingRecording
    from meeting.models import Meeting
    meeting = Meeting.objects.get(pk=meeting_id)
    if not meeting.backend_active:
        logger.info('Recording %s from meeting id %s not stopped, meeting.backend_active=False',
            recording_id, meeting_id)
        return

    try:
        recording = MeetingRecording.objects.get(pk=recording_id)
    except MeetingRecording.DoesNotExist:
        return
    if not recording.backend_active:

        logger.warning('Recording %s (%s) for meeting %s not stopped, backend_active=False',
            recording_id, recording.recording_id, meeting_id)
        return

    if recording.schedule_id and schedule_id != recording.schedule_id:
        logger.info('Recording %s from meeting id %s has been rescheduled for stop, returning.',
            recording_id, meeting_id)
        return

    try:
        with transaction.atomic():
            Meeting.objects.select_for_update().get(pk=meeting_id)
            recording.stop_record()
        logger.debug('Recording stopped',
            extra=dict(meeting_id=meeting_id, recording_id=recording_id,
            provider_ref=recording.recording_id))

    except Exception as e:
        logger.warning('Recording %s (%s) for meeting %s not stopped, exception!',
            recording_id, recording.recording_id, meeting_id, exc_info=1)
        self.retry(exc=e, countdown=15)


@app.task(bind=True)
def book_streams_retry(self: Task, meeting_id: int, schedule_id: int = None):

    from meeting.models import Meeting
    meeting = Meeting.objects.get(pk=meeting_id)
    if not meeting.backend_active:
        logger.info('Meeting not active, skip schedule streams',
            extra=dict(meeting_id=meeting_id))
        return

    try:
        meeting.book_streams()
    except Exception:
        capture_exception()
        raise self.retry(delay=60 + 60 * book_streams_retry.request.retries)


@app.task(bind=True)
def stop_record_notification(self: Task, meeting_id: int, recording_id: int):

    from recording.models import MeetingRecording
    from meeting.models import Meeting
    meeting = Meeting.objects.get(pk=meeting_id)
    if not meeting.backend_active:
        logger.info('Recording %s from meeting id %s not notified, meeting.backend_active=False',
            recording_id, meeting_id)
        return

    recording = MeetingRecording.objects.get(pk=recording_id)

    if recording.backend_active:
        recording.notify()
        logger.debug('Recording notified',
            extra=dict(meeting_id=meeting_id, recording_id=recording_id,
            provider_ref=recording.recording_id))
    else:
        logger.info('Recording not notified, backend_active=False',
            extra=dict(meeting_id=meeting_id, recording_id=recording_id,
            provider_ref=recording.recording_id))


@app.task(bind=True)
def get_recording_embed(self: Task, meeting_id: int, recording_id: int):

    from recording.models import MeetingRecording
    from meeting.models import Meeting
    meeting = Meeting.objects.get(pk=meeting_id)

    recording = MeetingRecording.objects.get(pk=recording_id)
    if not recording.recording_id:
        logger.info('No recording embed fetched. Empty recording id',
            extra=dict(meeting_id=meeting_id, recording_id=recording_id,
            provider_ref=recording.recording_id))

        return

    try:
        recording.get_embed()
        logger.debug('Recording embed fetched',
            extra=dict(meeting_id=meeting_id, recording_id=recording_id,
            provider_ref=recording.recording_id))

    except Exception as e:
        logger.warning('Embed %s (%s) for recording %s not fetched, exception!',
                       recording_id, recording.recording_id, meeting_id, exc_info=1)

        if get_recording_embed.request.retries >= 2:
            meeting.recording_embed_callback()
        self.retry(exc=e, countdown=15)


@app.task(bind=True)
def hangup_call_leg(self: Task, meeting_id: int, call_leg_id: int):

    from meeting.models import Meeting
    meeting = Meeting.objects.get(pk=meeting_id)
    api = meeting.customer.get_api()
    try:
        api.hangup_call_leg(call_leg_id)
    except Exception:
        capture_exception()


@app.task(bind=True)
def sync_cospace_callids(self: Task):

    callbacks = getattr(settings, 'COSPACE_CALLID_SYNC_CALLBACKS', None) or []

    if not settings.SET_CALLID_TO_URIS:
        return

    callbacks = [callbacks] if isinstance(callbacks, str) else callbacks

    from provider.models.provider import Provider
    from datastore.utils.acano import update_extra_cospace_uris

    done = set()
    for provider in Provider.objects.filter(type=0, subtype=1):

        if provider.id in done or not provider.enabled:
            continue

        if not provider.cluster.acano.set_call_id_as_uri:
            continue

        result = update_extra_cospace_uris(provider)

        for p in provider.clustered.all():
            done.add(p.pk)

        for callback in callbacks:
            if not result:
                break
            requests.post(callback, data=json.dumps(result))

    return done


@app.task(bind=True, time_limit=3 * 60, soft_time_limit=3 * 60 - 10)
def store_provider_load(self: Task):

    from provider.models.provider import Provider
    from provider.models.provider_data import ProviderLoad
    from customer.models import Customer
    from provider.exceptions import AuthenticationError, ResponseError

    customer = Customer.objects.first()

    for provider in Provider.objects.all():
        if not provider.is_acano or not provider.enabled:
            continue
        try:
            load = provider.get_api(customer).get_load()
            participant_count = provider.get_api(customer).get_participants(limit=1)[1]
            status = provider.get_api(customer).get_status()
        except (ResponseError, AuthenticationError):
            continue

        bandwidth_in = bandwidth_out = 0
        try:
            bandwidth_out = int(status.get('audioBitRateOutgoing') or 0) + int(status.get('videoBitRateOutgoing') or 0)
            bandwidth_in = int(status.get('audioBitRateIncoming') or 0) + int(status.get('videoBitRateIncoming') or 0)
        except ValueError:
            pass

        ProviderLoad.objects.create(provider=provider, load=load, participant_count=participant_count,
                                    bandwidth_in=bandwidth_in, bandwidth_out=bandwidth_out)


@app.task(bind=True)
def clean_stale_data(self: Task):
    from statistics.models import PossibleSpamLeg
    PossibleSpamLeg.objects.filter(ts_start__lt=now() - timedelta(days=2)).delete()

    engine = import_module(settings.SESSION_ENGINE)
    try:
        engine.SessionStore.clear_expired()
    except NotImplementedError:
        pass


@app.task(bind=True)
def clean_ghost_calls(self: Task):

    providers = {}

    from customer.models import Customer
    from .exceptions import NotFound
    for customer in Customer.objects.all():
        provider = customer.get_provider()
        if not provider or provider.pk in providers:
            continue

        if not provider.is_acano:
            continue

        for p in provider.get_clustered(include_self=True):
            providers[p.pk] = (p, customer)

    for provider, customer in providers.values():

        api = provider.get_api(customer)

        try:
            calls, total = api.get_calls()
        except (ResponseConnectionError, AuthenticationError):
            continue

        for call in calls:
            try:
                data = api.get_call(call['id'])
            except NotFound:
                continue
            if data['duration'] > 60 * 60 and data['call_legs'] == 0:
                api.hangup_call(call['id'])
                logger.info('Ghost call hung up', extra=dict(call=data, calls=calls, provider_id=provider.id))
            else:
                logger.debug('Call not hung up, not ghost call', extra=dict(call=data, provider_id=provider.id))

    return set(providers.keys())


def get_acano_customers(include_tenant=False):

    processed = set()

    result = []

    from customer.models import Customer
    for customer in Customer.objects.all():
        provider = customer.get_provider()
        if not provider or not provider.is_acano:
            continue

        cur = (provider.pk,)
        if include_tenant:
            cur += (customer.acano_tenant_id,)

        if cur in processed:
            continue
        processed.add(cur)

        if include_tenant:
            result.append((customer, provider, customer.acano_tenant_id))

    return result


@app.task(bind=True)
def clear_old_call_chat_messages(self: Task):

    for customer, provider, tenant_id in get_acano_customers(include_tenant=True):

        api = provider.get_api(customer)

        if provider.software_version[:1] != '2' or api.provider.software_version[:1] != '2':
            continue  # v2.x only

        clear_chat_interval = api.cluster.acano.clear_chat_interval or settings.CLEAR_CHAT_INTERVAL
        if clear_chat_interval is None:
            continue

        api.clear_old_call_chat_messages(since=now() - timedelta(minutes=clear_chat_interval), tenant_id=tenant_id)


@app.task(bind=True)
def sync_seevia(self: Task):

    return  # Seevia service is shut down


@app.task(bind=True)
def sync_seevia_customer(self: Task, customer_id: int):

    return  # Seevia service is shut down


@app.task(bind=True)
def check_hook_sessions(self: Task):
    from cdrhooks.models import Session
    for s in Session.objects.filter(backend_active=True):
        check_hook_session.apply_async([s.pk])


@app.task(bind=True)
def check_hook_session(self: Task, session_id: int):

    from cdrhooks.models import Session

    with transaction.atomic():
        try:
            session = Session.objects.select_for_update().get(pk=session_id)
        except Session.DoesNotExist:
            logger.info('Session does not exist!', extra=dict(session_id=session_id))
            return

        if session.should_update_status:
            session.update_status()
            logger.debug('Session status updated', extra=dict(session_id=session_id, hook=session.hook_id))
            if session.should_deactivate:
                session.deactivate()
                logger.info('Session deactivated', extra=dict(session_id=session_id, hook=session.hook_id))
            else:
                logger.debug('Session wasnt deactivated', extra=dict(session_id=session_id, hook=session.hook_id))


@app.task(bind=True)
def schedule_dialout_start(self: Task, dialout_id: int, task_index):

    from cdrhooks.models import ScheduledDialout
    try:
        dialout = ScheduledDialout.objects.get(pk=dialout_id, task_index=task_index)
    except ScheduledDialout.DoesNotExist:
        pass
    else:
        dialout.start()


@app.task(bind=True)
def schedule_dialout_stop(self: Task, dialout_id: int, task_index):

    from cdrhooks.models import ScheduledDialout
    try:
        dialout = ScheduledDialout.objects.get(pk=dialout_id, task_index=task_index)
    except ScheduledDialout.DoesNotExist:
        pass
    else:
        dialout.stop()


@app.task(bind=True)
def check_recordings(self: Task):

    from recording.models import MeetingRecording

    for mr in MeetingRecording.objects.filter(backend_active=True):
        if mr.recording_id:
            check_recording.apply_async([mr.pk])


@app.task(bind=True)
def check_recording(self: Task, recording_id: int, is_first_check=False):

    from recording.models import MeetingRecording

    with transaction.atomic():
        try:
            recording = MeetingRecording.objects.select_for_update().get(pk=recording_id)
        except MeetingRecording.DoesNotExist:
            logger.info('Recording does not exist!', extra=dict(recording_id=recording_id))
            return

        if recording.backend_active and recording.recording_id:

            try:
                active = recording.check_active()
            except Exception as e:
                if not recording.meeting.has_ended:
                    return self.retry(exc=e, countdown=5)
            else:
                if active:
                    return True

        # Not active

        if recording.backend_active and recording.recording_id and recording.meeting.has_ended:
            logger.info('Recording was disconnected, but meeting has ended', extra=dict(recording_id=recording_id))
            recording.stop_record()
            return True

        # Recording should be active but isn't

        if is_first_check:
            recording.add_error(_('Inspelningen kopplades aldrig upp.'), commit=False)
        else:
            recording.add_error(_('Inspelningen avslutades i förväg.'), commit=False)
        logger.info('Recording was not connected on check{}'.format(' (first check)' if is_first_check else ''),
             extra=dict(recording_id=recording_id))

        with sentry_sdk.push_scope() as scope:
            scope.set_context('recording', dict(recording_id=recording_id, meeting_id=recording.meeting_id, provider_ref=recording.recording_id))  # TODO remove after making sure everything is correct
            capture_message('Recording not active when it should')

        if recording.meeting.has_ended:
            recording.deactivate()
            return

        try:
            recording.retry()
        except MeetingRecording.MaxRetries:
            recording.add_error(_('För många misslyckade försök att spela in, försöker med fallback. Kontakta support.'), commit=False)
            recording.meeting.fallback_record()
        else:
            recording.add_error(_('Försöker starta en ny inspelning.'), commit=False)

        recording.deactivate()

        return False


@app.task(bind=True)
def send_email_for_cospace(self: Task, customer_id, cospace_id: str, subject=None, emails=None):
    from customer.models import Customer
    try:
        customer = Customer.objects.get(pk=customer_id)
    except Customer.DoesNotExist:
        return

    from ui_message import invite
    invite.send_email_for_cospace(customer.get_api(), cospace_id, subject=None, emails=emails)


@app.task(bind=True, time_limit=3 * 60, soft_time_limit=3 * 60 - 10)
def unbook_expired(self: Task):
    from provider.ext_api import base, clearsea

    if settings.DEBUG and not getattr(settings, 'FORCE_CLEAN_OLD_MEETINGS', False):
        print('Meetings should be unbooked, but is skipped in DEBUG mode. Please sett FORCE_CLEAN_OLD_MEETIGS = True')
        return
    base.BookMeetingProviderAPI.unbook_expired()
    result = clearsea.ClearSeaAPI.unbook_expired()
    logger.info('Clearsea expired calls unbooked', extra=dict(clearsea_ids=result))


@app.task(bind=True, time_limit=10 * 60, soft_time_limit=10 * 60 - 10)
def update_vcse_statistics(self: Task):
    from provider.ext_api import vcse
    vcse.VCSExpresswayAPI.update_all_vcs_stats(incremental=True)


@app.task(bind=True, time_limit=12 * 60, soft_time_limit=9.5 * 60)
def update_pexip_statistics(self: Task):
    from provider.ext_api import pexip
    pexip.PexipAPI.update_all_pexip_stats(incremental=True)


@app.task(bind=True)
def update_provider_statistics(self: Task, provider_id: int):

    from provider.models.provider import Provider
    from customer.models import Customer

    try:
        from shared.models import GlobalLock
        with GlobalLock.locked('stats.update_provider_stats.{}'.format(provider_id), wait=False):
            Provider.objects.get(pk=provider_id).get_api(Customer.objects.first()).update_stats(
                incremental=False
            )
    except DatabaseError:
        pass


@app.task(bind=True)
def recount_stats(self: Task, recluster=False, verbose=False, ts_start=None, ts_stop=None, force_rematch=False, extra_filters=None):

    from statistics.cleanup import rewrite_history_chunks

    if ts_start and isinstance(ts_start, str):
        ts_start = parse_datetime(ts_start)
    if ts_stop and isinstance(ts_stop, str):
        ts_stop = parse_datetime(ts_stop)

    try:
        from shared.models import GlobalLock
        with GlobalLock.locked('stats.recount_stats', wait=False):
            rewrite_history_chunks(recluster=recluster, verbose=verbose, ts_start=ts_start, ts_stop=ts_stop, force_rematch=force_rematch, extra_filters=extra_filters)
    except DatabaseError:
        pass


@app.task(bind=True)
def sync_ldap(self: Task):
    from ext_sync.models import LdapSyncState
    for s in LdapSyncState.objects.all().select_related('ldap'):
        result = s.sync()
        logger.debug('Ldap synced', extra=dict(customer_id=s.ldap.customer_id, count=len(result)))


@app.task(bind=True)
def remove_schedule_cospace(self: Task, cospace_id: str, ts_auto_remove: str):

    from provider.models.acano import CoSpace
    from meeting.models import Meeting

    try:
        cospace = CoSpace.objects.get(pk=cospace_id)
    except CoSpace.DoesNotExist:
        return

    if cospace.ts_auto_remove and cospace.ts_auto_remove.isoformat() == ts_auto_remove:
        if Meeting.objects.filter(
            provider=cospace.provider, provider_ref2=cospace.provider_ref, backend_active=True
        ):
            logger.info(
                'Skip removing cospace %s, its connected to a scheduled meeting',
                str(cospace.provider_ref),
            )
            return  # use regular function for scheduled meetings
        logger.info('Removing cospace %s according to scheduled', cospace.provider_ref)
        cospace.provider.get_api(cospace.customer).delete_cospace(cospace.provider_ref)
        cospace.delete()
    else:
        logger.info(
            'Not removing cospace %s, removal date has changed from %s to %s',
            cospace.provider_ref,
            ts_auto_remove,
            cospace.ts_auto_remove.isoformat(),
        )


@app.task(bind=True)
def remove_schedule_pexip_cospace(self: Task, cospace_id: str, ts_auto_remove: str):

    from provider.models.pexip import PexipSpace
    from meeting.models import Meeting

    try:
        cospace = PexipSpace.objects.get(pk=cospace_id)
    except PexipSpace.DoesNotExist:
        return

    if cospace.ts_auto_remove and cospace.ts_auto_remove.isoformat() == ts_auto_remove:
        if Meeting.objects.filter(
            provider=cospace.cluster, provider_ref2=cospace.external_id, backend_active=True
        ):
            logger.info(
                'Skip removing conference %s, its connected to a scheduled meeting',
                cospace.external_id,
            )
            return  # use regular function for scheduled meetings
        logger.info('Removing conference %s according to scheduled', cospace.external_id)
        cospace.cluster.get_api(cospace.customer).delete_cospace(cospace.external_id)
        cospace.delete()
    else:
        logger.info(
            'Not removing conference %s, removal date has changed from %s to %s',
            cospace.external_id,
            ts_auto_remove,
            cospace.ts_auto_remove.isoformat(),
        )


@app.task(bind=True)
def sync_acano_users(self: Task):
    from provider.models.provider import Provider
    from customer.models import Customer
    if not settings.ENABLE_AUTO_LDAP_SYNC:
        return

    done = set()
    for p in Provider.objects.filter(subtype=Provider.SUBTYPES.acano):
        if p.is_acano and p.pk not in done and p.enabled:
            for p2 in p.clustered.all():
                done.add(p2.pk)
            p.get_api(Customer.objects.all()[0]).sync_ldap()


@app.task(bind=True, time_limit=15 * 60, soft_time_limit=15 * 60 - 10)
def set_cospace_stream_urls(self: Task):
    from customer.models import Customer

    for customer in Customer.objects.all():
        try:
            recording_api = customer.get_streaming_api()
        except AttributeError:
            continue

        if not recording_api or not getattr(recording_api, 'can_update_acano_stream_url', False):
            continue

        api = customer.get_api()
        if not api.provider or not api.cluster.is_acano:
            continue

        if not customer.acano_tenant_id:
            if Customer.objects.filter(lifesize_provider=customer.get_provider(), acano_tenant_id='').count() > 1:
                logger.info('Many default tenants exists. Stream urls wont be updated!', extra=dict(customer=customer.pk))
                continue

        def _callback(*args):
            return recording_api.get_stream_url(*args)
        api.set_cospace_stream_urls(_callback, tenant_id=customer.acano_tenant_id)


@app.task(bind=True)
def send_call_stats(self: Task):
    from statistics.utils.report import send_stats
    from statistics.models import Leg

    if not getattr(settings, 'SEND_USER_STATS_URLS', None):
        return

    send_stats(set(Leg.objects.filter(ts_start__gte=now() - timedelta(hours=12),
                                      ts_stop__gte=now() - timedelta(minutes=10),
                                      target__contains='@'
                                      ).distinct().values_list('target', flat=True)))


@app.task(bind=True)
def cache_acano_data(self: Task):
    print('Call to cache_acano_data. This function has been replaced by cache_cluster_data')


@app.task(bind=True)
def cache_pexip_data(self: Task):
    print('Call to cache_pexip_data. This function has been replaced by cache_cluster_data')


@app.task
def cache_cluster_data(incremental=None):
    """
    Cache all clusters
    """

    from provider.models.provider import Provider

    clusters = set()

    for p in Provider.objects.all().order_by('id'):

        if not p.enabled:
            continue

        cluster = p.cluster if p.cluster_id else p

        if not (p.is_acano or p.is_pexip) or cluster.pk in clusters:
            continue

        if not any([p.api_host, p.ip, p.hostname]):
            continue

        clusters.add(cluster.pk)

    shuffled = list(clusters)
    shuffle(shuffled)  # random order in case of failure

    if incremental:  # force incremental
        for cluster_id in shuffled:
            cache_single_cluster_data_incremental.apply_async([cluster_id], expires=8 * 60)
    else:
        for cluster_id in shuffled:
            cache_single_cluster_data.apply_async([cluster_id], {'incremental': incremental}, expires=20 * 60)


@app.task
def cache_cluster_data_incremental(*args, **kwargs):
    kwargs['incremental'] = True
    cache_cluster_data(*args, **kwargs)


@app.task(bind=True, time_limit=90 * 60, soft_time_limit=90 * 60 - 30)
def cache_single_cluster_data(self: Task, cluster_id: int, customer_id: int = None, incremental: bool = None):
    """
    Cache single cluster. If incremental is None it is determined depending on last sync
    """
    from provider.models.provider import Cluster
    from customer.models import Customer
    from datastore.utils import acano, pexip
    from datastore.models.base import ProviderSync

    try:
        cluster = Cluster.objects.get(pk=cluster_id)

        if customer_id:
            customer = Customer.objects.get(pk=customer_id)
        else:
            customer = Customer.objects.first()
    except (Cluster.DoesNotExist, Customer.DoesNotExist):
        return

    start = now()

    lock_cache_key = 'sync_cluster.{}'.format(cluster_id)
    if cache.get(lock_cache_key):
        logger.info('Sync already in progress for cluster %s (%s). Skip', cluster.pk, str(cluster))
        return

    cache.set(lock_cache_key, 1, 30 * 60)

    if incremental is None:  # check if incremental check should be used
        has_recent_full_sync = ProviderSync.objects.filter(
            provider=cluster,
            last_full_sync__gt=now() - timedelta(minutes=90),
        )
        incremental = bool(has_recent_full_sync)

    try:
        if cluster.is_acano:
            it = acano.sync_all_acano_iter(cluster, customer=customer, incremental=incremental)
        elif cluster.is_pexip:
            it = pexip.sync_all_pexip_iter(cluster, customer=customer, incremental=incremental)
        else:
            return
        for step, _r in it:
            logger.info('Synced %s for cluster %s (%s)', step, cluster.pk, cluster)
            cache.set(lock_cache_key, 1, 30 * 60)  # refresh lock after each task
    except (ResponseConnectionError, AuthenticationError) as e:
        logger.warning('Could not sync cluster %s (id %s) %s: %s',
                       str(cluster), cluster.id, (now() - start).total_seconds(), str(e))
        return False
    except Exception as e:
        logger.warning('Could not sync cluster %s (id %s) after %s: %s',
                       str(cluster), cluster.id, (now() - start).total_seconds(), str(e))
        if settings.DEBUG or settings.TEST_MODE:
            raise
        capture_exception()
    else:
        logger.info('Synced cluster data for cluster %s (id %s) in %s seconds',
                    cluster,
                    cluster_id,
                    (now() - start).total_seconds(),
                    extra=dict(incremental=incremental),
                    )
    finally:
        cache.delete(lock_cache_key)

    return True


@app.task(bind=True, time_limit=20 * 60, soft_time_limit=20 * 60 - 10)
def cache_single_cluster_data_incremental(self: Task, *args, **kwargs):
    kwargs['incremental'] = True
    return cache_single_cluster_data(*args, **kwargs)


@app.task(bind=True, time_limit=15 * 60, soft_time_limit=15 * 60 - 10)
def cache_ldap_data(self: Task):
    from datastore.utils.ldap import sync_ldap_ous_from_ldap

    sync_ldap_ous_from_ldap()


@app.task(bind=True)
def update_status_file(self: Task):

    from shared.models import CeleryStatus
    CeleryStatus.objects.update_or_create(id=1, defaults=dict(ts_last_check=now()))


def check_celery():
    from shared.models import CeleryStatus

    # celery status
    celery_status = False
    last_check = CeleryStatus.objects.values_list('ts_last_check', flat=True).first()
    if last_check and last_check > now() - timedelta(minutes=3):
        celery_status = True

    if not celery_status:
        try:
            with sentry_sdk.push_scope() as scope:
                scope.set_context('heartbeat', {
                    'now': now().isoformat(),
                    'last_heartbeat': last_check.isoformat(),
                })
                capture_message('Celery is down!')
        except Exception:
            pass

    return celery_status
