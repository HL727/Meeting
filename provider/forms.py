from django import forms
from django.core.validators import validate_integer

from license.api_helpers import license_validate_add
from .exceptions import ResponseError, ResponseConnectionError
from random import randint
from django.utils.translation import ugettext_lazy as _
from django.utils.timezone import now
from django.conf import settings
import json

from .ext_api.acano import AcanoAPI
from .models.acano import CoSpace
from meeting.models import Meeting
from provider.models.utils import parse_timestamp
from datetime import timedelta
from urllib.parse import urlencode
from organization.models import OrganizationUnit, CoSpaceUnitRelation


def get_timestamp(field_name):

    def _inner(self):
        try:
            return parse_timestamp(self.cleaned_data.get(field_name, ''))
        except Exception:
            raise forms.ValidationError(_('Date is in wrong format. Should be %Y%M%DT%H%m%sZ. E.g. 20141231T235959Z'))
    return _inner


def default_pin():
    return str(randint(1000, 9999))

def default_moderator_pin():
    return str(randint(1000000, 9999999))


class WebinarForm(forms.Form):

    title = forms.CharField(label=_('Namn'))
    uri = forms.CharField(label=_('URI'))
    password = forms.CharField(label=_('PIN-kod'), initial=default_pin, required=False)
    moderator_password = forms.CharField(label=_('PIN-kod moderator'), initial=default_moderator_pin)
    force_encryption = forms.BooleanField(label=_('Kräv kryptering'), required=False, help_text=_('Ev. deltagare utan stöd kommer inte kunna ansluta'))
    group = forms.CharField(label=_('Koppla till grupp'), required=False)

    enable_chat = forms.BooleanField(label=_('Aktivera chat'), required=False, initial=True)

    def __init__(self, *args, **kwargs):
        from django.conf import settings
        super().__init__(*args, **kwargs)
        if not getattr(settings, 'ENABLE_GROUPS', False):
            self.fields['group'].widget = forms.HiddenInput()

    def save(self, ip='127.0.0.1', creator='', customer=None):
        c = self.cleaned_data

        customer = customer or c.get('customer')
        assert customer
        provider = customer.get_provider()
        assert provider

        webinar_data = {
            'uri': c['uri'],
            'enable_chat': c['enable_chat'],
            'moderator_pin': c['moderator_password'],
            'group': c.get('group') or '',
        }

        settings = {
            'force_encryption': c.get('force_encryption'),
        }

        meeting = Meeting.objects.create(provider=provider, customer=customer,
            title=c['title'], password=c['password'],
            provider_ref='', webinar=json.dumps(webinar_data),
            creator_ip=ip or '127.0.0.1', creator=creator, settings=json.dumps(settings),
            ts_start=now(), ts_stop=now() + timedelta(days=20 * 365),
        )

        meeting.api.book(meeting, uri=c['uri'])
        webinar = meeting.api.webinar(meeting)

        meeting.save()

        return meeting, webinar


class CoSpaceFormInitMixin(forms.Form):
    def __init__(self, *args, cospace=None, **kwargs):
        self.cospace = cospace

        super().__init__(*args, **kwargs)

        if self.cospace is None:
            self.cospace = self.initial.get('cospace')

        from django.conf import settings

        if not getattr(settings, 'ENABLE_GROUPS', False):
            self.fields['group'].widget = forms.HiddenInput()

        customer = kwargs.get('customer')
        if customer and not (customer.enable_streaming or customer.enable_recording):
            self.fields.pop('stream_url', None)

        if not getattr(settings, 'ENABLE_ORGANIZATION', False):
            self.fields.pop('org_unit', None)


class CoSpaceBasicForm(CoSpaceFormInitMixin, forms.Form):

    title = forms.CharField(label=_('Namn'))
    layout = forms.ChoiceField(
        label=_('Layout'), choices=Meeting.ACANO_LAYOUT_CHOICES, required=False
    )
    group = forms.CharField(label=_('Koppla till grupp'), required=False)
    stream_url = forms.CharField(label=_('Stream URL'), required=False)

    def serialize(self, customer=None):
        """serialize to CMS request"""

        c = self.cleaned_data

        if c.get('org_unit'):
            org_unit, _created = OrganizationUnit.objects.get_or_create_by_full_name(
                c['org_unit'],
                customer=customer,
            )
        else:
            org_unit = None

        result = {
            'defaultLayout': c.get('layout') or 'telepresence',
            'organization_unit': org_unit,
        }
        if 'title' in self.fields:
            result['name'] = c.get('title') or ''
        if 'stream_url' in self.fields:
            result['streamUrl'] = c.get('stream_url') or ''
        if 'password' in self.fields:
            result['passcode'] = c.get('password') or ''

        return result

    def save(self, ip='127.0.0.1', creator='', customer=None):
        c = self.cleaned_data

        customer = customer or c.get('customer')

        api = customer.get_api()

        data = self.serialize()

        try:
            api.update_cospace(self.cospace, data)
        except ResponseConnectionError:
            raise
        except ResponseError as e:
            if 'duplicateCoSpaceUri' in e.args[1].text:
                return None, {'uri': str(_('Den angivna URIn används redan'))}
            if 'duplicateCoSpaceId' in e.args[1].text:
                return None, {'call_id': str(_('Det angivna callID används redan'))}
            raise
        else:
            return self.cospace, None


class CoSpaceAutoForm(CoSpaceBasicForm):

    title = None
    password = forms.CharField(label=_('PIN-kod'), required=False, validators=[validate_integer])


class CoSpaceForm(CoSpaceFormInitMixin):

    title = forms.CharField(label=_('Namn'))
    uri = forms.CharField(label=_('URI'), required=False)
    call_id = forms.CharField(label=_('Call ID'), initial=settings.INITIAL_FORM_CALL_ID or '')
    layout = forms.ChoiceField(label=_('Layout'), choices=Meeting.ACANO_LAYOUT_CHOICES, required=False)
    group = forms.CharField(label=_('Koppla till grupp'), required=False)
    password = forms.CharField(label=_('PIN-kod'), required=False, validators=[validate_integer])
    lobby = forms.BooleanField(
        label=_('Använd lobby för gästanvändare'),
        required=False,
        help_text=_('Mötet startar inte förrän en moderator/medlem loggat in'),
    )
    lobby_pin = forms.CharField(
        label=_('Separat PIN-kod för moderator'),
        required=False,
        initial=default_moderator_pin,
        validators=[validate_integer],
    )

    stream_url = forms.CharField(label=_('Stream URL'), required=False)

    custom_call_profile = forms.BooleanField(initial=False, required=False, widget=forms.HiddenInput())
    custom_call_leg_profile = forms.BooleanField(initial=False, required=False, widget=forms.HiddenInput())
    call_profile = forms.CharField(initial=False, required=False, widget=forms.HiddenInput())
    call_leg_profile = forms.CharField(initial=False, required=False, widget=forms.HiddenInput())

    force_encryption = forms.BooleanField(label=_('Kräv kryptering'), required=False, help_text=_('Ev. deltagare utan stöd kommer inte kunna ansluta'))
    enable_chat = forms.BooleanField(label=_('Aktivera chat'), required=False, initial=True)
    moderator_pin = forms.IntegerField(label=_('Alias för lobby_pin'), required=False, widget=forms.HiddenInput())

    def clean(self):
        if self.cleaned_data.get('moderator_password') and 'lobby_pin' not in self.data:
            self.cleaned_data['lobby_pin'] = self.cleaned_data.pop('moderator_password')

        try:
            license_validate_add('core:enable_core')
        except Exception:
            raise forms.ValidationError('License error')

        return self.cleaned_data

    def load(self, customer=None, include_members=False):

        customer = customer or getattr(self, 'cleaned_data', {}).get('customer')
        assert customer
        provider = customer.get_provider()

        api = provider.get_api(customer, allow_cached_values=True)

        try:
            data = api.get_cospace(self.cospace)
        except ResponseError:
            return {}

        if api.cluster.is_pexip:
            return self._load_pexip(api, data)
        return self._load_acano(api, data, include_members=include_members)

    def _load_pexip(self, api, data):
        "fake pexip conference as cospace"  # should this be used like this?
        result = data.copy()

        from datastore.models.pexip import EndUser

        owner_name = ''
        if data.get('primary_owner_email_address'):
            try:
                owner_name = EndUser.objects.search_active(
                    api.cluster, {'primary_email_address': data.get('primary_owner_email_address')}
                )[0].name
            except IndexError:
                pass

        allow_guests = data.get('allow_guests')

        result.update(
            {
                'cospace': data['id'],
                'title': data.get('name', ''),
                'uri': data.get('uri', ''),
                'password': data.get('guest_pin', '') if allow_guests else data.get('pin', ''),
                'moderator_password': data.get('pin', '') if allow_guests else '',
                'owner_name': owner_name or '',
                'owner_email': data.get('primary_owner_email_address', ''),
                'stream_url': data.get('stream_url', ''),  # TODO
                'auto_generated': data.get('autoGenerated', '') == 'true',
                'moderator': {
                    'call_id': data.get('call_id') or '',
                    'uri': data.get('uri') or '',
                    'password': data.get('pin') if data.get('guest_pin') else '',
                }
                if allow_guests
                else {},
            }
        )
        return result

    def _load_acano(self, api: AcanoAPI, data, include_members=False):

        customer = api.customer

        editable = data.get('numAccessMethods') in (None, '', '0', 0)

        default = {
            'lobby_pin': '',
            'group': '',
            'lobby': False,
            'force_encryption': False,
            'enable_chat': True,
            'ts_auto_remove': None,
            'owner_email': '',
            'moderator_access_method': '',
            'moderator': {},
        }

        try:
            obj = CoSpace.objects.get(provider_ref=self.cospace, provider=api.cluster)

            moderator_access_method = {}
            if obj.moderator_ref or obj.activation_ref:
                try:
                    moderator_access_method = api.get_cospace_accessmethod(
                        self.cospace, obj.moderator_ref or obj.activation_ref
                    )
                except ResponseError:
                    pass

            result = {
                'lobby_pin': moderator_access_method.get('passcode') or obj.moderator_password,
                'moderator_password': moderator_access_method.get('passcode')
                or obj.moderator_password,
                'group': obj.group,
                'lobby': bool(obj.lobby),
                'force_encryption': obj.force_encryption,
                'enable_chat': not obj.disable_chat,
                'ts_auto_remove': obj.ts_auto_remove,
                'owner_email': obj.owner_email,
                'moderator_access_method': obj.moderator_ref or obj.activation_ref,
                'moderator': {
                    'call_id': moderator_access_method.get('callId') or data.get('call_id') or '',
                    'uri': moderator_access_method.get('uri') or data.get('uri') or '',
                    'secret': moderator_access_method.get('secret') or data.get('secret'),
                    'password': moderator_access_method.get('passcode') or '',
                },
            }
            if obj.moderator_ref or obj.activation_ref:
                editable = True

        except CoSpace.DoesNotExist:
            result = default

        result.update(
            {
                'id': self.cospace,
                'tenant': data.get('tenant'),
                'cospace': self.cospace,
                'title': data.get('name', ''),
                'name': data.get('name', ''),
                'uri': data.get('uri', ''),
                'call_id': data.get('callId', ''),
                'password': data.get('passcode', ''),
                'layout': data.get('defaultLayout', '') or 'telepresence',
                'secret': data.get('secret', ''),
                'owner_jid': data.get('ownerJid', ''),
                'owner_id': data.get('ownerId', ''),
                'stream_url': data.get('streamUrl', ''),
                'auto_generated': data.get('autoGenerated', '') in ('true', True),
                'editable_accessmethods': editable,
                'organization_unit': CoSpaceUnitRelation.objects.filter(
                    provider_ref=self.cospace, unit__customer=customer
                )
                .values_list('unit', flat=True)
                .first(),
            }
        )

        if result['owner_id']:
            owner = api.get_user(result['owner_id'])
            result.update({
                'owner_email': owner['email'],
                'owner_name': owner['name'],
            })

        if include_members:
            result['members'] = [u['user_jid'] for u in api.get_members(self.cospace)]

        return result

    def serialize(self, customer=None):
        "serialize to CMS request"

        c = self.cleaned_data
        customer = customer or getattr(self, 'cleaned_data', {}).get('customer')

        if c.get('org_unit'):
            org_unit, _created = OrganizationUnit.objects.get_or_create_by_full_name(
                c['org_unit'],
                customer=customer,
            )
        else:
            org_unit = None

        result = {
            'name': c.get('title') or '',
            'uri': c.get('uri') or '',
            'callId': c.get('call_id') or '',
            'passcode': c.get('password') or '',
            'defaultLayout': c.get('layout') or 'telepresence',
            'organization_unit': org_unit,
        }
        if 'stream_url' in self.fields:
            result['streamUrl'] = c.get('stream_url') or ''
        return result

    def serialize_model(self, cleaned_data, **kwargs):
        "serialize to model data"

        c = cleaned_data

        update = {
            'title': c['title'],
            'call_id': c['call_id'],
            'uri': c['uri'],
            'password': c['password'],
            'group': c.get('group') or '',
            'creator': kwargs.get('creator', ''),
            'owner_email': c.get('owner_email', ''),
            'lobby': c.get('lobby'),
            'call_leg_profile': c.get('call_leg_profile', ''),
            'call_profile': c.get('call_profile', ''),
            'disable_chat': not c.get('enable_chat'),
            'force_encryption': kwargs.get('force_encryption', False),
            'ts_auto_remove': c.get('ts_auto_remove'),
        }
        return update

    def save(self, ip='127.0.0.1', creator='', customer=None):
        c = self.cleaned_data

        customer = customer or c.get('customer')

        api = customer.get_api()
        provider = api.cluster

        data = self.serialize()
        force_encryption = c.get('force_encryption')

        call_leg_profile = api._call_leg_profile('cospace', self.cospace)

        if c.get('custom_call_leg_profile'):
            call_leg_profile.extend(c['call_leg_profile'])
        else:
            call_leg_profile.extend('')
            if c.get('lobby'):
                call_leg_profile.add_settings('need_activation', {'needsActivation': 'true'})
            if force_encryption:

                if force_encryption is not None:
                    call_leg_profile.add_settings('force_encryption', {
                        'sipMediaEncryption': 'required' if force_encryption else 'optional'
                    })
                else:
                    call_leg_profile.pop_settings('force_encryption')

        call_profile = api._call_profile('cospace', self.cospace)

        if c.get('custom_call_profile'):
            call_profile.extend(c.get('call_profile'))
        else:
            call_profile.extend('')
            if not c.get('enable_chat'):
                call_profile.add_settings('no_chat', api._get_no_chat_call_profile(only_data=True))

        cdr_tag = [
            ('creator', creator),
            ('customer', customer.id),
            ('provider', provider.id),
            ('ou', c.get('group')),
        ]

        data['cdrTag'] = urlencode([x for x in cdr_tag if x[1]])

        try:
            if self.cospace:
                data['callLegProfile'] = call_leg_profile.commit()
                data['callProfile'] = call_profile.commit()
                cospace = api.update_cospace(self.cospace, data)
            else:
                cospace = api.add_cospace(data, creator=creator)

                call_leg_profile = call_leg_profile.update_target_id(cospace)
                call_profile = call_profile.update_target_id(cospace)
                data['callLegProfile'] = call_leg_profile.commit()
                data['callProfile'] = call_profile.commit()
                cospace = api.update_cospace(cospace, data)

        except ResponseConnectionError:
            raise
        except ResponseError as e:
            if 'duplicateCoSpaceUri' in e.args[1].text:
                return None, {'uri': str(_('Den angivna URIn används redan'))}
            if 'duplicateCoSpaceId' in e.args[1].text:
                return None, {'call_id': str(_('Det angivna callID används redan'))}
            raise
        else:
            try:
                existing = CoSpace.objects.get(provider=provider, provider_ref=cospace)
            except CoSpace.DoesNotExist:
                existing = CoSpace(customer=customer, provider=provider, provider_ref=cospace)

            if existing.moderator_ref and not c.get('lobby'):
                try:
                    api.remove_cospace_accessmethod(cospace, existing.moderator_ref)
                except ResponseError:
                    pass

            update = self.serialize_model(self.cleaned_data, creator=creator, force_encryption=force_encryption)

            if c.get('group'):
                from statistics import models as stats
                if stats.Call.objects.filter(ou=c['group']):
                    stats.Call.objects.filter(ou='', cospace_id=cospace).update(ou=c['group'])
                    stats.Leg.objects.filter(ou='', call__cospace_id=cospace).update(ou=c['group'])

            for k, v in list(update.items()):
                setattr(existing, k, v)

            if c.get('lobby'):
                if c.get('lobby_pin'):
                    existing.moderator_ref = api.lobby_pin(
                        cospace,
                        c.get('lobby_pin'),
                    )
                else:
                    guest_call_leg, moderator_call_leg = api._get_webinar_call_legs()
                    # set all members as moderators
                    for m in api.get_members(cospace):
                        api.update_member(cospace, m['id'], callLegProfile=moderator_call_leg)

                    existing.moderator_ref = api.add_cospace_accessmethod(cospace, data)
            else:
                existing.moderator_ref = ''

            existing.moderator_password = c.get('lobby_pin') or ''

            if not existing.pk:
                try:
                    existing.pk = CoSpace.objects.get(provider=api.cluster, provider_ref=cospace).pk
                except Exception:
                    pass
            existing.save()

        return cospace, None

    def get_temp_meeting(self, customer=None, is_moderator=False):

        cospace = self.load(customer=customer)
        customer = customer or getattr(self, 'cleaned_data', {}).get('customer')

        if is_moderator:
            cospace.update(cospace.get('moderator') or {})

        m = Meeting(provider=customer.get_provider(), customer=customer,
                title=cospace.get('title', ''),
                password=cospace.get('password', ''),
                creator=cospace.get('owner_jid', ''),
                provider_ref=cospace.get('call_id'), provider_ref2=cospace['id'], provider_secret=cospace.get('secret', ''), id=-1,
                ts_start=now(), ts_stop=now())

        m.creator_email = cospace.get('owner_email', '')
        m.creator_name = cospace.get('owner_name', '')
        m.uri = cospace.get('full_uri') or cospace['uri']

        return m


class CoSpaceAccessMethodForm(forms.Form):

    name = forms.CharField(label=_('Namn'), required=False)
    uri = forms.CharField(label=_('URI'), required=False)
    call_id = forms.CharField(label=_('Call ID'), initial=settings.INITIAL_FORM_CALL_ID or '')
    password = forms.CharField(label=_('PIN-kod'), required=False, validators=[validate_integer])

    def __init__(self, *args, cospace_id: str, access_method_id: str, **kwargs):
        self.cospace_id = cospace_id
        self.accessmethod_id = access_method_id
        super().__init__(*args, **kwargs)

    @classmethod
    def load(cls, dct):
        return {
            **dct,
            'call_id': dct.get('callId'),
            'password': dct.get('passcode'),
        }

    def serialize(self):

        c = self.cleaned_data

        return {
            'name': c.get('title') or '',
            'uri': c.get('uri') or '',
            'callId': c.get('call_id') or '',
            'passcode': c.get('password') or '',
        }

    def save(self, customer=None):
        c = self.cleaned_data

        customer = customer or c.get('customer')

        api: AcanoAPI = customer.get_api()

        return api.update_cospace_accessmethod(
            self.cospace_id, self.accessmethod_id, {**self.serialize(), 'regenerateSecret': 'false'}
        )


class CoSpaceMemberForm(forms.Form):

    add = forms.CharField(required=False)
    remove = forms.CharField(required=False)

    def __init__(self, *args, **kwargs):
        self.cospace = kwargs.pop('cospace', None)
        super().__init__(*args, **kwargs)

    def clean_add(self):

        data = self.cleaned_data.get('add') or ''

        values = [_f for _f in [e.strip() for e in data.split(',')] if _f]

        return values

    def clean_remove(self):

        data = self.cleaned_data.get('remove') or ''

        values = [_f for _f in [e.strip() for e in data.split(',')] if _f]

        return values

    def save(self, ip='127.0.0.1', creator='', customer=None):
        c = self.cleaned_data

        customer = customer or c.get('customer')
        assert customer
        provider = customer.get_provider()
        assert provider

        api = provider.get_api(customer)
        member_map = {u['user_jid']: u['id'] for u in api.get_members(self.cospace)}

        errors = {}

        for jid in self.cleaned_data.get('add'):
            if jid in member_map:
                errors.setdefault('add', []).append(str(_('{} är redan inlagd'.format(jid))))
            else:
                try:
                    api.add_member(self.cospace, jid)
                except ResponseError:
                    errors.setdefault('add', []).append(
                        str(_('{} kunde inte läggas till. Kontrollera användarnamnet'.format(jid)))
                    )

        for jid in self.cleaned_data.get('remove'):
            if jid not in member_map:
                errors.setdefault('remove', []).append(str(_('{} är inte medlem'.format(jid))))
            else:
                api.remove_member(self.cospace, member_map[jid])

        for k in list(errors.keys()):
            errors[k] = ', '.join(errors[k])
        return self.cospace, errors
