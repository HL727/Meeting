import sentry_sdk
from django.utils.timezone import now
from django.utils.translation import gettext_lazy as _

from provider.forms import WebinarForm, CoSpaceForm, CoSpaceMemberForm
from meeting.forms import MeetingUpdateSettingsForm, MeetingForm
from provider.exceptions import InvalidData, ResponseError
from meeting.models import Meeting, MeetingDialoutEndpoint, MeetingWebinar
from recording.models import MeetingRecording
from provider.models.provider_data import ClearSeaAccount
from provider.models.provider import Provider
from sentry_sdk import capture_message


class BookingEndpoint:

    def __init__(self, input_data, customer, creator=None, creator_ip='0.0.0.0', provider=None):

        self.customer = customer
        self.input_data = input_data
        self.is_valid = None
        self.creator = creator or ''
        self.creator_ip = creator_ip or '127.0.0.1'
        self.provider = provider

    def _get_provider(self, data):

        if self.provider:
            return self.provider

        internal = data.get('only_internal') and not data.get('password') and data.get('internal_clients') <= 2 and not self.customer.get_provider().is_acano
        if internal:
            provider = Provider.objects.get_active('internal')
        else:
            provider = self.customer.get_provider()

        if not provider:
            raise InvalidData(_('Kunde inte hitta någon konfigurerad mötesbrygga för tenant'), {})
        return provider

    def _get_external_provider(self):
        if self.customer.clearsea_provider_id:
            return self.customer.clearsea_provider

        provider = Provider.objects.get_active('clearsea')
        if not provider:
            raise InvalidData(_('Kunde inte hitta en provider för externa klienter'), {})
        return provider

    def book(self, parent=None):  # parent should only be used when provider is changed (e.g. first unbooked)

        form = MeetingForm(self.input_data)
        if not form.is_valid():
            raise InvalidData(_('Fel i formulär'), dict(form.errors))

        data = form.cleaned_data

        provider = self._get_provider(data)

        if parent:
            assert parent.provider_id != provider.pk

        meeting = form.save(provider=provider, customer=self.customer, parent=parent, creator_ip=self.creator_ip)

        if meeting.api.book(meeting):

            if meeting.should_book_external_client:
                external_provider = self._get_external_provider()
                if external_provider:
                    meeting.book_external(external_provider)

        if form.cleaned_data.get('confirm'):
            meeting.confirm()

        if meeting.is_webinar:
            meeting.api.webinar(meeting)

        if meeting.recurring_master:
            meeting.recurring_master.sync()

        return meeting

    def webinar(self):
        "static webinar"

        form = WebinarForm(self.input_data)
        if not form.is_valid():
            raise InvalidData(_('Fel i formulär'), dict(form.errors))

        meeting, webinar = form.save(customer=self.customer)

        return meeting

    def cospace(self, cospace_id=None):
        "static cospace"

        form = CoSpaceForm(self.input_data, cospace=cospace_id)
        if not form.is_valid():
            raise InvalidData(_('Fel i formulär'), dict(form.errors))

        cospace, errors = form.save(customer=self.customer)
        if errors:
            raise InvalidData(_('Fel i formulär'), errors)

        return cospace

    def cospace_members(self, cospace_id):
        "cospace members"

        form = CoSpaceMemberForm(self.input_data, cospace=cospace_id)
        if not form.is_valid():
            raise InvalidData(_('Fel i formulär'), dict(form.errors))

        cospace, errors = form.save(customer=self.customer)
        if errors:
            raise InvalidData(_('Fel vid uppdatering'), errors)

        return cospace

    def delete_cospace(self, cospace):

        api = cospace.provider.get_api(cospace.customer)
        result = api.delete_cospace(cospace.provider_ref)
        cospace.delete()
        return result

    def update_settings(self, meeting_id):

        meeting = Meeting.objects.get(pk=meeting_id)

        form = MeetingUpdateSettingsForm(self.input_data, meeting=meeting)
        if not form.is_valid():
            raise InvalidData(_('Fel i formulär'), dict(form.errors))

        data = form.cleaned_data

        if not meeting.backend_active:
            if meeting.provider.is_acano and not meeting.is_superseded:
                with sentry_sdk.push_scope() as scope:
                    scope.set_extra('meeting_id', meeting_id)
                    capture_message('Update settings for inactive acano meeting')
            else:
                raise InvalidData(_('Mötet är avbokat eller ersatt av ett nytt möte'), {'meeting_id': 'Meeting is not active'})

        was_started = meeting.has_started
        recurring_changed = False

        prev_time = (meeting.ts_start, meeting.ts_stop)

        if data.get('recurring_exceptions') and meeting.recurring_master_id:
            recurring_changed = True

        try:
            meeting.api.rebook(meeting, data)
        except ResponseError:
            raise
        else:
            meeting.save()

        if was_started and not meeting.has_started:
            if (meeting.ts_start - now()).total_seconds() / 60 > 10:
                from provider import tasks
                for recording in MeetingRecording.objects.filter(backend_active=True, meeting=meeting):
                    tasks.stop_record.delay(meeting.pk, recording.pk, recording.schedule_id)

        time_changed = prev_time != (meeting.ts_start, meeting.ts_stop)

        meeting.schedule(time_changed=time_changed)

        if recurring_changed:
            meeting.recurring_master.sync()  # TODO sync to api

        return meeting

    def rebook(self, meeting_id, move_provider=None):

        meeting = Meeting.objects.get(pk=meeting_id)

        try:
            meeting.check_possible_rebook()
        except ValueError as e:
            raise InvalidData(e.args[0], {'meeting_id': e.args[0]})

        form = MeetingForm(self.input_data)
        if not form.is_valid():
            raise InvalidData(_('Fel i formulär'), dict(form.errors))

        data = form.cleaned_data

        provider = self._get_provider(data)

        prev_time = (meeting.ts_start, meeting.ts_stop)

        if provider.pk != meeting.provider_id and move_provider is not False:
            if move_provider:
                self.unbook(meeting_id)
                return self.book(meeting)
            else:
                try:
                    return self.rebook(meeting_id, move_provider=False)
                except Exception:
                    return self.rebook(meeting_id, move_provider=True)

        extra_args = form.get_meeting_kwargs()

        extra_args.update({
            'provider_ref': meeting.provider_ref,
            'provider_ref2': meeting.provider_ref2,
        })

        new_meeting = form.save(provider=provider, customer=self.customer,
                                parent=meeting, creator_ip=self.creator_ip, **extra_args)

        if new_meeting.api.book(new_meeting):

            existing_external_client = meeting.get_external_account()
            if new_meeting.should_book_external_client:

                external_provider = self._get_external_provider()
                if external_provider:
                    if existing_external_client and existing_external_client.backend_active:
                        existing_external_client.meeting = new_meeting
                        existing_external_client.save()
                    else:
                        new_meeting.book_external(external_provider)
            elif existing_external_client:
                existing_external_client.provider.get_api(self.customer).unbook(existing_external_client)

            MeetingRecording.objects.filter(meeting=meeting).update(meeting=new_meeting)
            MeetingDialoutEndpoint.objects.filter(meeting=meeting).update(meeting=new_meeting)
            MeetingWebinar.objects.filter(meeting=meeting).update(meeting=new_meeting)

            time_changed = prev_time != (meeting.ts_start, meeting.ts_stop)
            meeting.schedule(time_changed=time_changed)

        if form.cleaned_data.get('confirm'):
            new_meeting.confirm()

        if meeting.is_webinar:
            meeting.api.webinar(meeting)

        return new_meeting

    def unbook(self, meeting_id):

        meeting = Meeting.objects.get(pk=meeting_id)

        meeting.ts_unbooked = meeting.ts_unbooked or now()
        meeting.save()

        if not meeting.backend_active:
            if meeting.ts_unbooked:
                raise InvalidData('Mötet är avbokat', {'meeting_id': 'Meeting is not active'})
            if not meeting.is_superseded:
                return meeting
            raise InvalidData(_('Mötet är automatiskt avbokat eller ersatt av ett nytt möte'), {'meeting_id': 'Meeting is not active'})

        meeting.api.unbook(meeting)

        try:
            csea = ClearSeaAccount.objects.get(meeting=meeting, backend_active=True)
        except ClearSeaAccount.DoesNotExist:
            pass
        else:
            csea.provider.get_api(self.customer).unbook(csea)

        for dialout in MeetingDialoutEndpoint.objects.filter(meeting=meeting):
            if dialout.backend_active:
                dialout.meeting.api.close_call(meeting, dialout)

        for recording in MeetingRecording.objects.filter(meeting=meeting):
            if recording.backend_active:
                recording.stop_record()

        # TODO remove meeting from bridge?

        return meeting
