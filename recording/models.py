import json
import logging
from datetime import timedelta
from time import time

from django.conf import settings
from django.db import models
from django.urls import reverse
from django.utils.timezone import now

from provider.exceptions import NotFound
from provider.models.consts import ENABLE_CELERY, TASK_DELAY
from provider.models.provider import Provider, VideoCenterProvider
from customer.models import Customer
from django.db.models import Q
import uuid
from django.utils.translation import gettext_lazy as _


logger = logging.getLogger(__name__)

# TODO move other recording models here


def get_secret():
    return str(uuid.uuid4())


class CoSpaceAutoStreamUrl(models.Model):

    provider = models.ForeignKey(Provider, on_delete=models.CASCADE)
    cospace_id = models.CharField(max_length=128, blank=True)
    tenant_id = models.CharField(max_length=128, blank=True)
    stream_url = models.CharField(max_length=200)


class AcanoRecordingManager(models.Manager):

    def get_for_users(self, usernames, cospace_id=None):

        from datastore.models.acano import CoSpace
        from meeting.models import Meeting

        usernames = list(usernames[:])
        usernames.extend(RecordingUserAlias.objects.filter(admin__user_jid__in=usernames).values_list('owner_jid',
                                                                                       flat=True))
        cospace_ids = CoSpace.objects.filter(
            Q(users__username__in=usernames) | Q(owner__username__in=usernames)).values_list('cid', flat=True)
        cospace_ids2 = Meeting.objects.filter(creator__in=usernames, existing_ref=False).values_list(
            'provider_ref2', flat=True)
        recordings = AcanoRecording.objects.filter(cospace_id__in=set(cospace_ids) | set(cospace_ids2))
        if cospace_id:
            recordings = recordings.filter(cospace_id=cospace_id)
        return recordings


class AcanoRecording(models.Model):

    # provider = models.ForeignKey(Provider, on_delete=models.CASCADE)
    title = models.CharField(max_length=200, blank=True)
    recording_id = models.CharField(max_length=128, blank=True)
    cospace_id = models.CharField(max_length=128, blank=True)
    call_id = models.CharField(max_length=128, blank=True)
    call_leg_id = models.CharField(max_length=128, blank=True)
    tenant_id = models.CharField(max_length=128, blank=True)
    path = models.CharField(max_length=128, blank=True)

    secret_key = models.CharField(max_length=64, db_index=True, default=get_secret)

    targets = models.TextField()

    ts_start = models.DateTimeField(null=True)
    ts_stop = models.DateTimeField(null=True)

    objects = AcanoRecordingManager()

    def get_api(self, customer=None):
        # TODO: check <recorderUrl> and connect to provider
        for v in VideoCenterProvider.objects.filter(type=30):

            return v.get_api(customer or Customer.objects.all().first())

    def get_video_url(self, customer=None):
        api = self.get_api(customer)

        return api.get_video_url(self.secret_key)

    def get_embed_code(self, customer=None):
        api = self.get_api(customer)

        return api.get_embed_code(secret_key=self.secret_key)

    def get_absolute_url(self):
        return reverse('recording', args=[self.secret_key])


class AcanoStream(models.Model):

    # provider = models.ForeignKey(Provider, on_delete=models.CASCADE)
    title = models.CharField(max_length=200, blank=True)
    stream_id = models.CharField(max_length=128, blank=True)
    cospace_id = models.CharField(max_length=128, blank=True)
    call_id = models.CharField(max_length=128, blank=True)
    call_leg_id = models.CharField(max_length=128, blank=True)
    tenant_id = models.CharField(max_length=128, blank=True)

    stream_url = models.CharField(max_length=200)

    targets = models.TextField()

    ts_start = models.DateTimeField(null=True)
    ts_stop = models.DateTimeField(null=True)


class RecordingUserAdmin(models.Model):

    user_jid = models.CharField(_('Användarnamn administratör'), max_length=200)

    def __str__(self):
        return self.user_jid


class RecordingUserAlias(models.Model):

    admin = models.ForeignKey(RecordingUserAdmin, on_delete=models.CASCADE)
    owner_jid = models.CharField(_('Ägare för inspelning'), max_length=200)


class MeetingRecording(models.Model):

    class MaxRetries(Exception):
        pass

    meeting = models.ForeignKey('meeting.Meeting', on_delete=models.CASCADE)
    provider = models.ForeignKey(VideoCenterProvider, null=True, on_delete=models.CASCADE)

    backend_active = models.BooleanField(default=False)
    is_separate_streaming = models.BooleanField(default=False, editable=False)

    name = models.CharField(max_length=200, blank=True)

    recording_id = models.CharField(max_length=100, blank=True)
    recording_id2 = models.CharField(max_length=100, blank=True)

    stream_url = models.CharField(max_length=200, blank=True)

    is_public = models.BooleanField(default=True)
    is_live = models.BooleanField(default=True)

    ts_activated = models.DateTimeField(null=True)
    ts_deactivated = models.DateTimeField(null=True)

    embed_code = models.TextField()
    video_sources = models.TextField()

    error = models.TextField(blank=True)

    ts_callback_sent = models.DateTimeField(null=True)

    retry_count = models.SmallIntegerField(default=0)

    schedule_id = models.CharField(max_length=20)

    class Meta:
        db_table = 'meeting_meetingrecording'

    def get_api(self):
        return self.provider.get_api(self.meeting.customer)

    def get_embed(self):
        return self.get_api().get_embed(self.meeting, self)

    def start_record(self):
        self.get_api().dialout(self.meeting, self)

        if not ENABLE_CELERY:
            return
        from provider import tasks

        tasks.check_recording.apply_async([self.pk, True], countdown=30)

    def stop_record(self):
        try:
            response = self.get_api().close_call(self.meeting, self)
        except NotFound as e:
            logger.info(
                'Recording already hung up. Record {}, meeting {}'.format(self.pk, self.meeting_id)
            )
            return e.response
        else:
            logger.info('Hangup record {}, meeting {}'.format(self.pk, self.meeting_id))
            return response

    def schedule(self):

        self.schedule_id = str(time())
        self.save()

        if not ENABLE_CELERY:
            return

        if self.meeting.ts_stop_corrected < now():
            return

        from provider import tasks
        eta = self.meeting.ts_start_corrected - timedelta(seconds=TASK_DELAY)
        if self.is_separate_streaming:
            eta += timedelta(seconds=10)  # quick fix for race condition in profile update
        tasks.record.apply_async([self.meeting.pk, self.pk, self.schedule_id], eta=eta)

        if not getattr(settings, 'CELERY_TASK_ALWAYS_EAGER', False):  # TODO better handling for tests?
            tasks.stop_record_notification.apply_async([self.meeting_id, self.pk], eta=self.meeting.ts_stop_corrected + timedelta(seconds=60))
            eta = self.meeting.ts_stop_corrected + timedelta(seconds=30)
            if self.is_separate_streaming:
                eta -= timedelta(seconds=10)   # quick fix for race condition in profile update
            tasks.stop_record.apply_async([self.meeting_id, self.pk, self.schedule_id], eta=eta)

    def retry(self, max_retries=3):
        if self.retry_count > max_retries:
            raise self.MaxRetries('Max retry count met')

        result = MeetingRecording.objects.create(
            meeting=self.meeting,
            provider=self.provider,
            name=self.name,
            is_public=self.is_public,
            is_live=self.is_live,
            is_separate_streaming=self.is_separate_streaming,
            retry_count=self.retry_count + 1,
        )
        result.start_record()
        return result

    def add_error(self, message, commit=True):
        self.error = '{} {}.'.format(self.error, message.rstrip('.')).strip()
        if commit:
            self.save()

    def check_active(self):

        try:
            self.get_api().get_call(self.recording_id)
        except NotFound:
            return False
        else:
            return True

    def notify(self):
        meeting = self.meeting
        msg = _('Om ca %d minuter kommer inspelningen att stängas') % ((meeting.ts_stop_corrected - now()).total_seconds() / 60)
        self.meeting.api.notify(meeting, msg)

    # methods

    def activate(self, commit=True):

        if self.backend_active:
            if commit:
                self.save()
            return

        self.backend_active = True
        self.ts_activated = now()
        if commit:
            self.save()

        if not ENABLE_CELERY:
            return
        from provider import tasks

        if self.is_live:
            tasks.get_recording_embed.apply_async([self.meeting_id, self.pk], countdown=20)

    def deactivate(self, commit=True):

        self.backend_active = False
        self.ts_deactivated = now()
        if commit:
            self.save()

        if not ENABLE_CELERY:
            return
        from provider import tasks

        if not self.embed_code:
            tasks.get_recording_embed.apply_async([self.meeting_id, self.pk], countdown=30)

    def callback(self):
        self.meeting.recording_embed_callback()

    def get_playback_url(self):
        try:
            return json.loads(self.video_sources).get('playback_url')
        except Exception:
            pass

