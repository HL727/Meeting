import logging

from django.db import models, transaction
from provider.models.provider import Provider
from customer.models import Customer
from django.utils.translation import ugettext_lazy as _
import json
from datetime import timedelta
from django.utils.timezone import now
from django.conf import settings

from provider.exceptions import NotFound


logger = logging.getLogger(__name__)

Q = models.Q


class HookManager(models.Manager):

    def get_hooks(self, customer=None, provider=None, provider_ref=None):

        hooks = Hook.objects.all()
        if customer:
            hooks = hooks.filter(customer=customer)

        if provider:
            hooks = hooks.filter(provider=provider)

        if provider_ref:
            hooks = hooks.filter(provider_ref=provider_ref)

        return hooks

    def handle_tag(self, type, call_leg):

        for hook in self.filter(provider_ref=call_leg.call.cospace_id):
            hook.handle_tag(type, call_leg)

        if type == 'callLegEnd':
            for dialout in ScheduledDialout.objects.filter(provider_ref=call_leg.call.cospace_id, is_active=True):
                if dialout.is_active:
                    dialout.check_status()


class Hook(models.Model):
    "Auto dialout on first participant to cospace"

    customer = models.ForeignKey(Customer, verbose_name=_('Kund'), null=True, blank=True, on_delete=models.CASCADE)
    provider = models.ForeignKey(Provider, on_delete=models.CASCADE)

    provider_ref = models.CharField(_('Cospace'), max_length=200)

    is_active = models.BooleanField(_('Aktiv'), default=True)
    recording_key = models.CharField(max_length=200)
    last_session_start = models.DateTimeField(null=True)
    last_session_end = models.DateTimeField(null=True)

    objects = HookManager()

    def get_api(self):
        return self.provider.get_api(self.customer)

    def handle_tag(self, type, call_leg):

        with transaction.atomic():
            active_sessions = self.get_sessions().select_for_update()

            if type == 'callLegUpdate':
                if not active_sessions:
                    self.activate()
                else:
                    for s in active_sessions:
                        s.update_status()

            elif type == 'callLegEnd':
                for s in active_sessions:
                    s.update_status()

    def get_sessions(self):
        return Session.objects.filter(hook=self, backend_active=True)

    def activate(self):

        if not self.is_active:
            return False

        api = self.get_api()

        calls, total = api.get_calls(cospace=self.provider_ref)

        dialouts = Dialout.objects.filter(hook=self)

        if not dialouts and not self.recording_key:
            return

        call = calls[0]['id'] if calls else api.add_call(self.provider_ref)

        session = Session.objects.get_or_create(hook=self, provider_ref=call, backend_active=True)[0]

        if self.recording_key:
            vprovider = self.customer.get_videocenter_provider()

            if vprovider:
                uri = 'sip:record:{}@{}'.format(self.recording_key, vprovider.hostname or vprovider.ip)
                session.recording_ref = api.add_participant(call, uri)

        refs = {}

        for dialout in dialouts:
            refs[dialout.pk] = api.add_participant(call, dialout.dialstring)

        session.refs = refs
        session.backend_active = True
        session.ts_last_active = now()
        session.save()

        self.last_session_start = now()
        self.last_session_end = None
        self.save()

        return True


class Dialout(models.Model):
    "Dialout on hook"

    hook = models.ForeignKey(Hook, on_delete=models.CASCADE)
    dialstring = models.CharField(_('Uppringningsadress'), max_length=100)
    persistant = models.BooleanField(_('Håller samtalet öppet'), default=False)
    ts_created = models.DateTimeField(auto_now_add=True, editable=False)


class Session(models.Model):
    "Active session for Hook"

    hook = models.ForeignKey(Hook, on_delete=models.CASCADE)
    provider_ref = models.CharField(_('Call'), max_length=200)
    recording_ref = models.CharField(max_length=100)

    refs_json = models.TextField(blank=True)

    ts_start = models.DateTimeField(auto_now_add=True, null=True)
    ts_stop = models.DateTimeField(null=True)

    ts_last_active = models.DateTimeField(null=True)

    backend_active = models.BooleanField(default=False)

    @property
    def refs(self):
        return json.loads(self.refs_json or '{}')

    @refs.setter
    def refs(self, value):
        self.refs_json = json.dumps(value)

    def _check_active(self, participants):
        "Get active participants not dialed by this system (i.e. 'real' users)"
        current = {p['id'] for p in participants}

        dialed = set()
        for dialout_id, ref in list(self.refs.items()):
            try:
                if not Dialout.objects.get(pk=dialout_id).persistant:
                    dialed.add(ref)
            except Dialout.DoesNotExist:
                pass

        diff = current - dialed

        if self.recording_ref:
            diff -= set(self.recording_ref)

        return diff

    def _get_participants(self):
        api = self.hook.get_api()
        try:
            return api.get_participants(self.provider_ref)[0]
        except NotFound:
            return []

    def is_active(self):

        try:
            participants = self._get_participants()
        except Exception:
            return False  # todo?

        diff = self._check_active(participants)

        if diff:
            return True

        return False

    def deactivate(self):
        api = self.hook.get_api()

        if self.recording_ref:
            try:
                api.hangup_participant(self.recording_ref)
            except NotFound:
                pass

        for _dialout_id, ref in list(self.refs.items()):
            try:
                api.hangup_participant(ref)
            except NotFound:
                pass

        self.backend_active = False
        self.save()

        self.hook.last_session_end = now()
        self.hook.save()

    def update_status(self, commit=True):

        if not self.backend_active:
            if commit:
                self.save()
            return

        if not self.is_active():
            if not self.ts_stop:
                self.ts_stop = now()
            try:
                if not self._get_participants():  # no one left. deactivate at once
                    return self.deactivate()
            except Exception:  # TODO
                pass
        else:
            if self.ts_stop:
                self.ts_stop = None
            self.ts_last_active = now()

        if commit:
            self.save()

    @property
    def should_update_status(self):
        if not self.backend_active:
            return False
        return (now() - self.ts_last_active).total_seconds() > 60

    @property
    def should_deactivate(self):
        if not self.backend_active:
            return False
        return (now() - self.ts_last_active).total_seconds() > 10 * 60


class ScheduledDialoutManager(models.Manager):

    def get_active(self, provider, cospace_id):
        result = self.get_queryset().filter(provider=provider, provider_ref=cospace_id)

        result = result.filter(Q(ts_start__gte=now()) | Q(ts_stop__gt=now()))
        return result


class ScheduledDialout(models.Model):
    "Automatic dialout/recording scheduled for existing rooms"

    customer = models.ForeignKey(Customer, on_delete=models.CASCADE)
    provider = models.ForeignKey(Provider, on_delete=models.CASCADE)

    provider_ref = models.CharField(_('Cospace'), max_length=200)
    provider_ref2 = models.CharField(_('Call ID'), max_length=200, blank=True)

    ts_start = models.DateTimeField()
    ts_stop = models.DateTimeField(null=True)

    task_index = models.SmallIntegerField(_('Active celery task id'), default=0)

    is_active = models.BooleanField(default=True)

    objects = ScheduledDialoutManager()

    @property
    def is_ongoing(self):
        if not self.is_active:
            return False

        if not self.ts_stop:
            return False
        return self.ts_start <= now() <= self.ts_stop

    def schedule(self):
        from provider.tasks import schedule_dialout_start
        self.task_index += 1
        self.save()
        schedule_dialout_start.apply_async([self.pk, self.task_index], eta=self.ts_start - timedelta(seconds=10))

    def unschedule(self):
        self.task_index += 1
        self.is_active = False
        self.save()
        if abs((now() - self.ts_start).total_seconds()) < 10:
            self.stop()

    def start(self):
        from provider.tasks import schedule_dialout_stop

        if not self.is_active:
            return

        api = self.provider.get_api(self.customer)

        self.task_index += 1
        self.provider_ref2 = api.add_call(self.provider_ref)
        self.save()

        try:
            for part in ScheduledDialoutPart.objects.filter(dialout=self):
                part.call()
        finally:
            if not settings.CELERY_TASK_ALWAYS_EAGER:
                schedule_dialout_stop.apply_async(
                    [self.pk, self.task_index], eta=self.ts_stop + timedelta(seconds=10)
                )

        logger.info('Scheduled dialout started for cospace %s with call id %s', self.provider_ref, self.provider_ref2)

    def stop(self):

        logger.info('Scheduled dialout stopped for cospace %s with call id %s', self.provider_ref, self.provider_ref2)
        for part in ScheduledDialoutPart.objects.filter(dialout=self):
            part.hangup()

        # TODO remove call?

    def check_status(self):

        if not self.is_active:
            return

        with transaction.atomic():
            for part in ScheduledDialoutPart.objects.select_for_update(of=('self',)).filter(dialout=self):
                part.check_status()

    def add_part(self, dialstring, redial=True):
        return ScheduledDialoutPart.objects.create(dialout=self, dialstring=dialstring, redial=redial)

    def save(self, *args, **kwargs):
        if self.customer_id and not self.provider_id:
            self.provider = self.customer.get_provider()

        super().save(*args, **kwargs)


class ScheduledDialoutPart(models.Model):
    "Participant in scheduled dialout"

    dialout = models.ForeignKey(ScheduledDialout, related_name='parts', on_delete=models.CASCADE)
    dialstring = models.CharField(max_length=100)
    redial = models.BooleanField(default=True)

    backend_active = models.BooleanField(default=False)
    ts_last_check = models.DateTimeField(null=True, default=None)
    dial_count = models.SmallIntegerField(default=0)

    provider_ref = models.CharField(_('Participant id'), max_length=200, editable=False)

    @property
    def is_record(self):
        if self.dialstring == 'record':
            return True
        return False

    def call(self):
        dialout = self.dialout

        if self.dial_count > 5:
            logger.info('Scheduled dialout canceled to %s from cospace %s, call id %s. Reason: too many redials', self.dialstring, dialout.provider_ref, dialout.provider_ref2)
            return

        participant_id = None

        logger.debug('Scheduled dialout, dialout to %s from cospace %s, call id %s', self.dialstring, dialout.provider_ref, dialout.provider_ref2)

        mcu_api = dialout.provider.get_api(dialout.customer)

        if self.is_record:
            api = dialout.customer.get_recording_api()
            if api:
                participant_id = api.adhoc_record(
                    mcu_api, mcu_api.get_sip_uri(dialout.provider_ref)
                )  # TODO pin code
        else:
            participant_id = mcu_api.add_participant(dialout.provider_ref2, self.dialstring)

        self.dial_count += 1
        self.ts_last_check = now()
        self.provider_ref = participant_id
        self.backend_active = True
        self.save()

    def hangup(self):

        dialout = self.dialout

        logger.debug('Scheduled dialout, hangup %s from cospace %s, call id %s', self.dialstring, dialout.provider_ref, dialout.provider_ref2)

        try:
            dialout.provider.get_api(dialout.customer).hangup_participant(self.provider_ref)
        except NotFound:
            pass

        self.backend_active = False
        self.save()

    def check_status(self):

        dialout = self.dialout
        api = dialout.provider.get_api(dialout.customer)

        logger.debug('Scheduled dialout, check status of call to %s from cospace %s, call id %s', self.dialstring, dialout.provider_ref, dialout.provider_ref2)

        try:
            participants = api.get_participants(dialout.provider_ref2)[0]
        except NotFound:
            is_active = False
        else:
            is_active = any(p for p in participants if p['id'] == self.provider_ref)

        if not is_active:
            if self.redial and self.dialout.is_ongoing:
                logger.info('Scheduled dialout, redial %s from cospace %s, call id %s', self.dialstring, dialout.provider_ref, dialout.provider_ref2)

                self.call()
        else:
            self.ts_last_check = now()
            self.save()
