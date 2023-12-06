import json

from dateutil.rrule import rrulestr
from django import forms
from django.utils.timezone import now
from django.utils.translation import ugettext_lazy as _

from provider.forms import get_timestamp
from meeting.models import Meeting, RecurringMeeting
from provider.models.utils import parse_timestamp, date_format
from shared.utils import partial_update


class MeetingSettingsForm(forms.Form):

    room_info = forms.CharField(required=False)
    recording = forms.CharField(required=False)
    layout = forms.ChoiceField(choices=Meeting.ACANO_LAYOUT_CHOICES, required=False)
    moderator_layout = forms.ChoiceField(choices=Meeting.ACANO_LAYOUT_CHOICES, required=False)

    def clean_room_info(self):
        value = self.cleaned_data.get('room_info') or ''

        if value:
            try:
                data = json.loads(value)
            except ValueError as e:
                raise forms.ValidationError(_('room_info is not valid JSON %s' % e))
            else:
                if not isinstance(data, (list, tuple)):
                    raise forms.ValidationError(_('room_info not JSON-encoded list'))
                for obj in data:
                    if not isinstance(obj, dict):
                        raise forms.ValidationError(_('room_info not JSON-encoded list of objects'))
                    if {obj.get('title'), obj.get('dialstring'), obj.get('endpoint')} == {None}:
                        raise forms.ValidationError('Object in room_info lacks title and dialstring value')

        return value

    def clean_recording(self):
        value = self.cleaned_data.get('recording') or ''

        if value:
            try:
                obj = json.loads(value)
            except ValueError as e:
                raise forms.ValidationError(_('recording is not valid JSON %s' % e))
            else:
                if not isinstance(obj, dict):
                    raise forms.ValidationError(_('recording not JSON-encoded list of objects'))

        return value


class MeetingUpdateSettingsForm(MeetingSettingsForm):

    title = forms.CharField(required=False)
    ts_start = forms.CharField(required=False)
    ts_stop = forms.CharField(required=False)
    recurring_exceptions = forms.CharField(required=False)

    password = forms.CharField(required=False)
    moderator_password = forms.CharField(required=False)

    def __init__(self, *args, meeting, **kwargs):
        self.meeting = meeting
        super().__init__(*args, **kwargs)

    def clean_ts_start(self):

        if not self.cleaned_data.get('ts_start'):
            return None

        try:
            value = parse_timestamp(self.cleaned_data.get('ts_start', ''))
        except Exception:
            raise forms.ValidationError(_('Date is in wrong format. Should be %Y%M%DT%H%m%sZ. E.g. 20141231T235959Z'))

        if value < now() and value < self.meeting.ts_start:
            raise forms.ValidationError(_('Mötet kan inte flyttas bakåt i tiden'))

        return value

    def clean_ts_stop(self):

        if not self.cleaned_data.get('ts_stop'):
            return None

        try:
            value = parse_timestamp(self.cleaned_data.get('ts_stop', ''))
        except Exception:
            raise forms.ValidationError(_('Date is in wrong format. Should be %Y%M%DT%H%m%sZ. E.g. 20141231T235959Z'))

        return value

    def clean_recurring_exceptions(self):
        return MeetingForm.clean_recurring_exceptions(self)

    def clean(self):
        c = super().clean()

        if 'ts_start' in c or 'ts_stop' in c:
            if (c.get('ts_stop') or self.meeting.ts_stop) < (c.get('ts_start') or self.meeting.ts_start):
                self.add_error('ts_stop', 'Stop time must be later than start time')

        if c.get('title') and c.get('title') == self.meeting.title:
            c.pop('title')

        return c


class MeetingForm(MeetingSettingsForm, forms.Form):

    title = forms.CharField(required=False)

    only_internal = forms.BooleanField(required=False)
    internal_clients = forms.IntegerField(required=False)
    external_clients = forms.IntegerField(required=False)
    password = forms.CharField(required=False)

    ts_start = forms.CharField()
    ts_stop = forms.CharField()
    is_private = forms.BooleanField(required=False)

    recurring = forms.CharField(required=False)
    recurring_exceptions = forms.CharField(required=False)
    recurrence_id = forms.CharField(required=False)

    meeting_type = forms.CharField(required=False)

    creator = forms.CharField()
    source = forms.CharField(required=False)
    confirm = forms.BooleanField(required=False)

    settings = forms.CharField(required=False)
    webinar = forms.CharField(required=False)

    def clean(self):

        data = self.cleaned_data

        if not any([data.get('only_internal'), data.get('internal_clients'), data.get('external_clients')]):
            raise forms.ValidationError(_('internal_clients or external_clients must be set'))

        if data['external_clients'] and data['only_internal']:
            raise forms.ValidationError(_('external_clients and only_internal can\'t be set at the same time'))

        if data['external_clients'] == 0:  # TODO fix for outlook-plugin. Remove?
            data['only_internal'] = True

        return data

    def clean_password(self):
        value = self.cleaned_data.get('password')
        if value and len(value) < 4:
            raise forms.ValidationError(_('PIN code must be at least 4 characters'))
        return value

    def clean_recurring(self):
        value = self.cleaned_data.get('recurring', '').strip()
        if value:
            try:
                rrulestr(value)
            except Exception as e:
                raise forms.ValidationError(*e.args)

        return value

    def clean_recurring_exceptions(self):
        value = self.cleaned_data.get('recurring_exceptions', '').strip().replace(' ', '')

        if value:
            try:
                for p in value.split(','):
                    assert parse_timestamp(p)
            except Exception as e:
                raise forms.ValidationError(*e.args)
        return value

    clean_ts_start = get_timestamp('ts_start')
    clean_ts_stop = get_timestamp('ts_stop')

    def clean_webinar(self):

        value = self.cleaned_data.get('webinar') or ''

        if not value or value == '{}':
            return ''

        try:
            data = json.loads(value)
        except ValueError as e:
            raise forms.ValidationError(_('webinar is not valid JSON %s' % e))

        else:
            for k, v in list(data.items()):
                if k in ('is_webinar', 'enable_chat'):
                    if v and not isinstance(v, bool):
                        raise forms.ValidationError(_('webinar[%s] must be boolean' % k))
                elif not isinstance(v, str):
                    raise forms.ValidationError(_('only strings are allowed for webinar values %s' % k))

        return value

    def clean_settings(self):

        value = self.cleaned_data.get('settings') or ''

        if not value or value == '{}':
            return ''

        try:
            data = json.loads(value)
        except ValueError as e:
            raise forms.ValidationError(_('settings is not valid JSON %s' % e))

        else:
            for k, v in list(data.items()):
                if k == 'lobby_pin':
                    if v and not (isinstance(v, int) or str(v).isdigit()):
                        raise forms.ValidationError(_('only numbers are allowed for settings values %s' % k))
                elif k == 'external_uri':
                    pass
                elif not isinstance(v, bool):
                    raise forms.ValidationError(_('only booleans are allowed for settings values %s' % k))

        return value

    def get_meeting_kwargs(self):

        c = self.cleaned_data

        optional = {}
        if c.get('recurrence_id'):
            optional['recurrence_id'] = c['recurrence_id']

        return {
            'title': c.get('title') or '',
            'creator': c['creator'],
            'password': c['password'] or '',
            'ts_start': c['ts_start'],
            'ts_stop': c['ts_stop'],
            'timezone': c.get('timezone'),
            'is_recurring': bool(c['recurring']),
            'recurring': c['recurring'],
            'recurring_exceptions': c['recurring_exceptions'],
            'is_internal_meeting': c['only_internal'],
            'internal_clients': c['internal_clients'],
            'external_clients': c['external_clients'],
            'room_info': c['room_info'],
            'recording': c['recording'],
            'layout': c['layout'],
            'moderator_layout': c.get('moderator_layout') or c['layout'],
            'webinar': c['webinar'],
            'settings': c['settings'],
            'meeting_type': c['meeting_type'],
            'source': c.get('source') or '',
            'is_private': bool(c.get('is_private')),
            **optional,
        }

    def save(self, customer, provider, **kwargs) -> 'Meeting':
        data = self.get_meeting_kwargs()
        data.update(kwargs)

        recurring_kwargs = {}
        if data.get('recurring'):
            recurring_kwargs['recurring_rule'] = data['recurring']
            recurring_kwargs['recurring_exceptions'] = data['recurring_exceptions']
            data['recurrence_id'] = data.get('recurrence_id') or date_format(data['ts_start'])

        if data.get('recurring_master'):
            partial_update(data['recurring_master'], recurring_kwargs)
        elif data.get('recurring'):
            if data.get('parent') and data['parent'].recurring_master_id:
                data['recurring_master'] = data['parent'].recurring_master
                partial_update(data['recurring_master'], {})
            else:
                data['recurring_master'] = RecurringMeeting.objects.create(
                    customer=customer,
                    provider=provider,
                    **recurring_kwargs
                )
            data.pop('recurring', None)
            data.pop('recurring_exceptions', None)

        meeting = Meeting.objects.create(customer=customer, provider=provider, **data)

        # TODO can first_meeting_id be None while this should not overwrite it?
        if meeting.recurring_master and not meeting.recurring_master.first_meeting_id:
            meeting.recurrence_id = date_format(meeting.ts_start)
            meeting.recurring_master.first_meeting = meeting
            meeting.recurring_master.save()
            meeting.recurring_master.sync()

        return meeting


