import logging
from collections import Counter
from typing import NamedTuple, List, Dict

from dateutil.rrule import rrulestr
from django import forms
from django.conf import settings
from django.core.cache import cache
from django.core.validators import validate_integer
from django.db.models import Q
from django.utils.dateparse import parse_datetime
from django.utils.timezone import now
from django.utils.translation import ugettext_lazy as _
from datetime import timedelta

from sentry_sdk import capture_exception

from numberseries.models import NumberSeries, NumberRange
from policy.models import ClusterPolicy
from provider import forms as provider_forms
from provider.exceptions import ResponseError, AuthenticationError, NotFound
from provider.models.pexip import PexipEndUser
from provider.models.provider import Provider, Cluster, ClusterSettings
from provider.models.vcs import VCSEProvider
from meeting.models import Meeting
from customer.models import Customer
from provider.models.utils import date_format
from organization.models import OrganizationUnit, UserUnitRelation
import json

from shared.utils import partial_update

logger = logging.getLogger(__name__)


class WebinarForm(provider_forms.WebinarForm):

    customer = forms.ModelChoiceField(queryset=Customer.objects.all(), widget=forms.HiddenInput())


class MeetingForm(forms.Form):

    title = forms.CharField(label=_('Rubrik'), required=True)
    password = forms.CharField(label=_('PIN-kod'), required=False)

    lobby = forms.BooleanField(label=_('Använd lobby för gästanvändare'), required=False)
    lobby_pin = forms.CharField(
        label=_('Separat PIN-kod för moderator'), required=False, validators=[validate_integer]
    )

    ts_start = forms.DateTimeField(label=_('Starttid'), initial=now)
    ts_stop = forms.DateTimeField(label=_('Sluttid'), initial=lambda: now() + timedelta(hours=1))

    owner_jid = forms.CharField(label=_('Ägare'), required=False)
    dialout = forms.CharField(label=_('Auto-uppringning'), required=False, help_text=_('Komma-separerad lista'))
    recurring = forms.CharField(label=_('Återkommande möte'), required=False, help_text=_('Ex. RRULE:FREQ=WEEKLY;COUNT=2 (iCalendar RFC 5545)'))

    record = forms.BooleanField(label=_('Spela in'), required=False)
    webinar = forms.BooleanField(label=_('Webinar'), required=False)

    def clean_webinar(self):
        if self.cleaned_data.get('webinar'):
            return json.dumps({'is_webinar': True})
        return ''

    def clean_record(self):
        if self.cleaned_data.get('record'):
            return json.dumps({'record': True, 'is_live': True})
        return ''

    def clean_recurring(self):
        value = self.cleaned_data.get('recurring', '').strip()
        if value:
            try:
                rrulestr(value)
            except Exception as e:
                raise forms.ValidationError(
                    'Invalid RFC 5545 value. Make sure that no spaces are included in each rule. %s'
                    % e.args
                )

        return value

    def serialize(self, creator='admin'):

        c = self.cleaned_data

        rooms = None

        if self.cleaned_data.get('webinar'):
            c['type'] = 'webinar'

        settings = {}
        if c.get('lobby'):
            settings['lobby'] = True
            settings['lobby_pin'] = c.get('lobby_pin') or ''

        if c.get('dialout'):

            rooms = [{'dialstring': dial.strip()} for dial in c.get('dialout').split(',') if dial.strip()]

        return {
            'title': c['title'],
            'password': c['password'],
            'ts_start': date_format(c['ts_start']),
            'ts_stop': date_format(c['ts_stop']),
            'room_info': json.dumps(rooms or []),
            'webinar': c.get('webinar') or '',
            'recording': c.get('record') or '',
            'recurring': c.get('recurring') or '',
            'settings': json.dumps(settings or {}),
            'creator': c.get('owner_jid') or creator,
            'source': 'mvms',
            'confirm': True,
            'internal_clients': 0,
            'external_clients': 3,
            'type': c.get('type') or '',
        }

    def clean(self):

        from meeting.forms import MeetingForm as APIMeetingForm

        form = APIMeetingForm(self.serialize())
        if not form.is_valid():
            for k, v in form.errors.items():
                self.errors[k] = v

            raise forms.ValidationError(_('Errors: {}').format(json.dumps(form.errors)))
        return self.cleaned_data

    def save(self, customer, creator_ip):

        from meeting.book_handler import BookingEndpoint

        endpoint = BookingEndpoint(self.serialize(), customer)

        try:
            meeting = endpoint.book()
        except ResponseError as e:
            error = 'Error: {}'.format(e)
            self.add_error('__all__', error)
            raise forms.ValidationError(error)

        return meeting


class CoSpaceFormMixin(forms.Form):

    customer = forms.ModelChoiceField(queryset=Customer.objects.all(), widget=forms.HiddenInput(), required=False)
    org_unit = forms.CharField(label=_('Organisationsenhet'), required=False)
    owner_jid = forms.CharField(required=False, label=_('Ägare'))
    owner_email = forms.EmailField(required=False, label=_('Ägarens e-postadress'), help_text=_('Hämtas automatiskt om användare är kopplad'))
    stream_url = forms.CharField(label=_('Streamkey'), required=False)
    ts_auto_remove = forms.DateTimeField(label=_('Radera efter tidpunkt'), required=False)

    def serialize(self):
        data = super().serialize()
        data['ownerJid'] = self.cleaned_data.get('owner_jid') or ''
        if 'stream_url' in self.fields:
            data['streamUrl'] = self.cleaned_data.get('stream_url') or ''

        if not getattr(settings, 'ENABLE_ORGANIZATION', False):
            self.fields.pop('org_unit', None)

        return data

    def __init__(self, *args, **kwargs):

        customer = kwargs.pop('customer', None)
        super().__init__(*args, **kwargs)

        if customer:
            org_unit = OrganizationUnit.objects.filter(cospaces__provider_ref=self.cospace).first()
            if org_unit:
                self.initial.setdefault('org_unit', org_unit.full_name)

        if customer and not (customer.enable_streaming or customer.enable_recording):
            self.fields.pop('stream_url', None)

        self.customer = customer

    def save(self, ip='127.0.0.1', creator='', customer=None):
        is_add = not self.cospace
        customer = customer or self.customer
        cospace_id, errors = super().save(ip=ip, creator=creator, customer=customer)
        if cospace_id and is_add and self.cleaned_data.get('owner_jid'):
            member = self.cleaned_data['owner_jid']
            try:
                customer.get_api().add_member(cospace_id, member, is_moderator=True)
            except NotFound:
                logger.warning(
                    'Could not add member %s to cospace %s - NotFound error',
                    member,
                    cospace_id,
                    exc_info=True,
                )
            except Exception:
                logger.warning(
                    'Could not add member %s to cospace %s', member, cospace_id, exc_info=True
                )
                if settings.TEST_MODE or settings.DEBUG:
                    raise
                capture_exception()
        return cospace_id, errors

    def clean_stream_url(self):
        value = self.cleaned_data.get('stream_url')
        if value and not value.startswith('rtmp://'):
            raise forms.ValidationError(_('Stream url stödjer bara rtmp://'))

        value = value.replace('mp4:', '')  # quickchannel compatitilbity missmatch with cms
        return value


class CoSpaceBasicForm(
    CoSpaceFormMixin,
    provider_forms.CoSpaceBasicForm,
):
    field_order = list(provider_forms.CoSpaceBasicForm.declared_fields.keys())


class CoSpaceAutoForm(
    CoSpaceFormMixin,
    provider_forms.CoSpaceAutoForm,
):
    owner_jid = None
    owner_email = None

    field_order = list(provider_forms.CoSpaceAutoForm.declared_fields.keys())


class CoSpaceForm(
    CoSpaceFormMixin,
    provider_forms.CoSpaceForm,
):
    field_order = [
        f
        for f in provider_forms.CoSpaceForm.declared_fields
        if f not in ('enable_chat', 'force_encryption')
    ]


class TenantSyncForm(forms.Form):

    name_conflict = forms.ChoiceField(label=_('Hantera namnkonflikt med befintliga kunder'),
                                       choices=(
                                           ('add_suffix', _('Lägg till suffix')),
                                           ('merge', _('Koppla tenant-id till befintlig kund utan att ändra inställningar')),
                                           ('skip', _('Hoppa över import')),
                                           ('ignore', _('Skapa dublett')),
                                       ), initial='skip')


class TenantForm(forms.Form):

    name = forms.CharField()
    callbranding_url = forms.CharField(required=False)
    invite_text_url = forms.CharField(required=False)

    ivrbranding_url = forms.CharField(required=False)

    create_customer = forms.BooleanField(label=_('Create Core customer'), initial=True, required=False)
    customer_ous = forms.CharField(label=_('Customer API keys'), required=False)

    create_ldap = forms.BooleanField(label=_('Create LDAP Source'), initial=False, required=False)
    ldap_server = forms.ChoiceField(required=False, choices=[])
    ldap_mapping = forms.ChoiceField(required=False, choices=[])
    ldap_base_dn = forms.CharField(required=False)
    ldap_filter = forms.CharField(required=False)

    enable_streaming = forms.BooleanField(required=False)
    enable_recording = forms.BooleanField(required=False)

    def __init__(self, api, *args, **kwargs):
        self.api = api
        initial = kwargs.pop('initial', None) or {}

        sources, servers, mappings = self.get_ldap_sources()

        initial['ldap_base_dn'] = self.get_most_common_base_dn([s['base_dn'] for s in sources])
        initial['ldap_filter'] = self.get_most_common_filter([s['filter'] for s in sources])
        if not initial['ldap_filter']:
            initial['ldap_filter'] = '(objectClass=person)'

        try:
            initial['ldap_server'] = Counter([s['server'] for s in sources]).most_common(1)[0][0]
            initial['ldap_mapping'] = Counter([s['mapping'] for s in sources]).most_common(1)[0][0]
        except IndexError:
            pass
        kwargs['initial'] = initial

        super().__init__(*args, **kwargs)
        self.fields['ldap_server'].choices = [(l['id'], l['address']) for l in servers]
        self.fields['ldap_mapping'].choices = [(l['id'], l['jid_mapping']) for l in mappings]

    class LdapTuple(NamedTuple):
        sources: List[Dict]
        servers: List[Dict]
        mappings: List[Dict]

    def get_ldap_sources(self):

        cache_key = 'acano.ldapdata.{}'.format(self.api.cluster.pk)

        cached = cache.get(cache_key)
        if cached is not None:
            return self.LdapTuple(*cached)

        result = self.LdapTuple(self.api.get_ldapsources(), self.api.get_ldapservers(), self.api.get_ldapmappings())

        cache.set(cache_key, tuple(result), 120)
        return result

    def get_most_common_base_dn(self, choices, separator=',', skip=1):

        counter = Counter()
        for c in choices:
            parts = c.split(separator)
            counter.update([separator.join(parts[-i - skip - 1:]) for i in range(len(parts) - skip - 1)])

        if counter:
            return sorted(counter.most_common(10), key=lambda x: (x[1], len(x[0])), reverse=True)[0][0]
        return ''

    def get_most_common_filter(self, choices, separator=')', skip=1):

        counter = Counter()
        for c in choices:
            parts = c.rstrip(separator).split(separator)
            counter.update([separator.join(parts[:i + skip + 1:]) for i in range(len(parts) - skip - 1)])

        if counter:
            try:
                most_common = sorted(counter.most_common(10), key=lambda x: (x[1], len(x[0])), reverse=True)[0][0]
            except IndexError:
                return ''
            return most_common + (')' * (most_common.count('(') - most_common.count(')')))
        return ''

    def clean(self):
        c = self.cleaned_data
        error = False

        if c.get('create_ldap'):
            for k in ('ldap_server', 'ldap_base_dn', 'ldap_filter', 'ldap_mapping'):
                if not c.get(k):
                    self.add_error(k, 'This field must be filled in')
                    error = True
        if error:
            raise forms.ValidationError(_('Ldap errors'))

        return c

    def save(self):

        callbranding_id = ''
        ivrbranding_id = ''
        tenant_id = customer = ldapsource = None

        data = self.cleaned_data
        api = self.api

        if data.get('callbranding_url'):
            invite_text_url = data.get('invite_text_url')
            callbranding_id = api.add_callbranding(location=data['callbranding_url'], invite_text=invite_text_url)

        if data.get('ivrbranding_url'):
            ivrbranding_id = api.save_ivrbranding(location=data['ivrbranding_url'])

        tenant_id = api.save_tenant(data['name'], callbranding=callbranding_id,
            ivrbranding=ivrbranding_id, enable_streaming=data.get('enable_streaming'), enable_recording=data.get('enable_recording'))

        if data.get('create_customer'):

            keys = data['customer_ous'].replace(' ', '').split(',')

            keys = [_f for _f in keys if _f]

            customer = Customer.objects.get(pk=api.customer.pk)
            customer.pk = None
            customer.title = data['name']
            customer.acano_tenant_id = tenant_id
            customer.save()

            for key in keys:
                from customer.models import CustomerKey
                CustomerKey.objects.create(customer=customer, shared_key=key)

        if data.get('create_ldap'):
            ldapsource = api.save_ldapsource(filter=data['ldap_filter'],
                                             base_dn=data['ldap_base_dn'],
                                             server_id=data['ldap_server'],
                                             mapping_id=data['ldap_mapping'],
                                             tenant_id=tenant_id,
                                             )

        return tenant_id, customer, ldapsource


class ISODateTimeField(forms.DateTimeField):

    def strptime(self, value, format):
        return parse_datetime(value)


class MeetingFilterForm(forms.Form):

     title = forms.CharField(label=_('Fritextfilter, rubrik'), required=False)
     creator = forms.CharField(label=_('Fritextfilter, användare'), required=False)

     ts_start = ISODateTimeField(label=_('Tidpunkt, fr.o.m.'), required=True)
     ts_stop = ISODateTimeField(label=_('Tidpunkt, t.o.m.'), required=False)
     organization = forms.ModelChoiceField(queryset=OrganizationUnit.objects.none(), required=False)

     all_customers = forms.BooleanField(label=_('Visa alla kunder'), initial=False, required=False)
     only_endpoints = forms.BooleanField(label=_('Endast med endpoints'), initial=False, required=False, widget=forms.HiddenInput())
     only_active = forms.BooleanField(label=_('Endast aktiva'), initial=False, required=False)
     include_external = forms.BooleanField(label=_('Inkludera externa möten'), initial=True, required=False)
     endpoint = forms.ModelChoiceField(queryset=None, required=False)

     def __init__(self, *args, **kwargs):

        self.user = kwargs.pop('user', None)
        self.customer = kwargs.pop('customer', None)
        initial = kwargs.get('initial') or {}

        initial['ts_start'] = initial.get('ts_start') or now()

        kwargs['initial'] = initial

        super().__init__(*args, **kwargs)

        self.fields['organization'].queryset = OrganizationUnit.objects.filter(customer=self.customer)
        from endpoint.models import Endpoint
        self.fields['endpoint'].queryset = Endpoint.objects.filter(customer=self.customer)

        if not self.user or not self.user.is_staff:
            self.fields.pop('all_customers')

     def get_meetings(self):

        meetings = Meeting.objects.filter(is_superseded=False).order_by('ts_start').select_related('provider')

        if not self.is_valid() or not self.cleaned_data.get('all_customers'):
            meetings = meetings.filter(customer=self.customer)

        if not self.is_bound:
            # 2 year ahead as default. static webinars and rooms are booked with far ahead future ts_stop
            return meetings.filter(ts_stop__gte=now(), ts_stop__lte=now() + timedelta(days=2 * 365))

        if not self.is_valid():
            return Meeting.objects.none()

        c = self.cleaned_data

        if c.get('title'):
            meetings = meetings.filter(Q(title__icontains=c['title']) | Q(provider_ref__startswith=c['title']))

        if c.get('creator'):
            meetings = meetings.filter(creator__icontains=c['creator'])

        if c.get('ts_start'):
            meetings = meetings.filter(ts_stop__gte=c['ts_start'])

        if c.get('ts_stop'):
            meetings = meetings.filter(ts_stop__lte=c['ts_stop'])
        else:
            meetings = meetings.filter(ts_stop__lte=now() + timedelta(days=2 * 365))

        if not c.get('include_external'):
            meetings = meetings.exclude(provider__type__in=Provider.VIRTUAL_TYPES)

        if c.get('organization'):
            from datastore.models.pexip import EndUser
            from datastore.models.acano import User as AcUser
            org_units = c['organization'].get_descendants(include_self=True)
            meetings = meetings.distinct().filter(
                Q(organization_unit__in=org_units)
                | Q(endpoints__org_unit__in=org_units)
                | Q(creator__in=AcUser.objects.filter(organization_unit__in=org_units).values_list('username', flat=True))
                | Q(creator__in=EndUser.objects.filter(organization_unit__in=org_units).values_list('email__email', flat=True))
            )

        if c.get('only_endpoints'):
            meetings = meetings.filter(endpoints__isnull=False)

        if c.get('endpoint'):
            meetings = meetings.filter(endpoints=c['endpoint'])

        if c.get('only_active'):
            meetings = meetings.filter(backend_active=True)

        if c.get('only_endpoints') or c.get('endpoint'):
            meetings = meetings.distinct().prefetch_related('endpoints')

        return meetings


class DataStoreChangeForm(forms.Form):

    def __init__(self, *args, **kwargs):
        self.tenant_id = kwargs.pop('tenant_id', None)
        super().__init__(*args, **kwargs)

    date_start = forms.DateField(label=_('Datum fr.o.m.'))
    date_stop = forms.DateField(label=_('Datum t.o.m.'))

    def get_additions(self):

        if not self.is_valid():
            return []

        c = self.cleaned_data

        return self.get_queryset().filter(
           ts_created__date__gte=c['date_start'], ts_created__date__lte=c['date_stop']
        ).order_by('-ts_created')

    def get_removals(self):

        if not self.is_valid():
            return []

        c = self.cleaned_data

        today_limit = now() - timedelta(hours=3)

        return self.get_queryset().filter(
            last_synced__date__gte=c['date_start'], last_synced__date__lte=c['date_stop'], last_synced__lte=today_limit
        ).order_by('-last_synced')

    def excel_export(self):

        import xlwt

        wb = xlwt.Workbook()

        def _add_sheet(name):
            ws = wb.add_sheet(name)

            x = 0
            for header, _field in self.get_excel_fields():

                ws.write(0, x, str(header))
                x += 1

            return ws

        ws = _add_sheet(str(_('Nya objekt')))

        y = 1
        for obj in self.get_additions():
            x = 0
            for _header, field in self.get_excel_fields():

                ws.write(y, x, str(getattr(obj, field)))
                x += 1

            y += 1

        ws = _add_sheet(str(_('Borttagna objekt')))

        y = 1
        for obj in self.get_removals():
            x = 0
            for _header, field in self.get_excel_fields():

                ws.write(y, x, str(getattr(obj, field)))
                x += 1

            y += 1

        return wb


class UserChangeListForm(DataStoreChangeForm):

    def get_excel_fields(self):
        return [
            (_('Användarnamn'), 'username'),
            (_('LDAP-användarnamn'), 'ldap_username'),
            (_('Skapades'), 'ts_created'),
            (_('Senaste synk'), 'last_synced'),
        ]

    def get_queryset(self):
        from datastore.models import acano as ds
        return ds.User.objects.filter(tenant__tid=self.tenant_id or None)


class CoSpaceChangeListForm(DataStoreChangeForm):

    def get_excel_fields(self):
        return [
            (_('Namn'), 'name'),
            (_('URI'), 'uri'),
            (_('Call ID'), 'call_id'),
            (_('Ägare'), 'owner'),
            (_('Skapades'), 'ts_created'),
            (_('Senaste synk'), 'last_synced'),
        ]

    def get_queryset(self):
        from datastore.models import acano as ds
        return ds.CoSpace.objects.filter(tenant__tid=self.tenant_id or None).select_related('owner')


class BasicSetupForm(forms.Form):

    customer_name = forms.CharField(label=_('Namn på installation'))

    def save(self, commit=True):

        Customer.objects.filter(pk=1, title='').update(title=self.cleaned_data['customer_name'])


class NewClusterSetupForm(forms.ModelForm):

    type = forms.TypedChoiceField(
        label=_('Typ'),
        coerce=int,
        choices=[(t, Cluster.TYPES.get_title(t)) for t in Cluster.MCU_TYPES],
        widget=forms.RadioSelect(),
    )

    main_sip_domain = forms.CharField(label=_('Primär SIP-domän'), required=False)

    static_vmr_number_start = forms.IntegerField(
        label=_('Statiska rum, fr.o.m.'), initial=settings.ACANO_TEMP_COSPACE_RANGE[0]
    )
    static_vmr_number_stop = forms.IntegerField(
        label=_('Statiska rum, t.o.m.'), initial=settings.ACANO_TEMP_COSPACE_RANGE[1]
    )

    scheduled_vmr_number_start = forms.IntegerField(
        label=_('Bokade rum, fr.o.m.'), initial=settings.ACANO_TEMP_COSPACE_RANGE[0]
    )
    scheduled_vmr_number_stop = forms.IntegerField(
        label=_('Bokade rum, t.o.m.'), initial=settings.ACANO_TEMP_COSPACE_RANGE[1]
    )

    class Meta:
        fields = ('title', 'type', 'web_host', 'phone_ivr')
        model = Cluster

    def save(self, commit=True):
        assert commit
        instance = super().save(commit=True)

        c = self.cleaned_data

        static_room_number_range = NumberRange.objects.create(
            title='Default static number serie for {}'.format(instance.title),
            start=c['static_vmr_number_start'],
            stop=c['static_vmr_number_stop'],
        )

        scheduled_room_number_range = NumberRange.objects.create(
            title='Default scheduled number serie for {}'.format(instance.title),
            start=c['scheduled_vmr_number_start'],
            stop=c['scheduled_vmr_number_stop'],
        )

        ClusterSettings.objects.update_or_create(
            cluster=instance,
            main_domain=c['main_sip_domain'] or '',
            web_domain=c['web_host'] or '',
            phone_ivr=c['phone_ivr'],
            static_room_number_range=static_room_number_range,
            scheduled_room_number_range=scheduled_room_number_range,
        )

        customers = Customer.objects.all()
        customer = customers.first()
        if len(customers) == 1 and customer.id == 1 and customer.lifesize_provider_id is None:
            customer.lifesize_provider = self.instance
            customer.save()
        else:
            customer = Customer.objects.create(
                title='{} default'.format(self.instance.title), lifesize_provider=instance
            )

        if self.instance.is_pexip:
            self.instance.pexip.default_customer = customer
            self.instance.pexip.save()

            ClusterPolicy.objects.create(cluster=self.instance)

        return instance


class NewCallControlClusterSetupForm(forms.ModelForm):

    type = forms.TypedChoiceField(
        label=_('Typ'),
        coerce=int,
        choices=[(t, Cluster.TYPES.get_title(t)) for t in Cluster.CALL_CONTROL_TYPES],
        widget=forms.RadioSelect(),
    )

    main_sip_domain = forms.CharField(label=_('Primär SIP-domän'), required=False)

    class Meta:
        fields = ('title', 'type')
        model = Cluster

    def save(self, commit=True):
        assert commit
        instance = super().save(commit=True)

        c = self.cleaned_data
        ClusterSettings.objects.update_or_create(
            cluster=instance,
            main_domain=c['main_sip_domain'] or '',
        )
        return instance


class AcanoSetupForm(forms.ModelForm):

    sync_tenants = forms.BooleanField(label=_('Synkronisera tenants från CMS'), required=False)
    is_service_node = forms.BooleanField(label=_('Denna server saknar aktiv call bridge. Innehåller enbart andra kringtjänster'), required=False)
    set_cdr = forms.BooleanField(label=_('Set CDR Receiver for statistics'), required=False)

    def __init__(self, *args, override_cluster, **kwargs):
        self.override_cluster = override_cluster

        super().__init__(*args, **kwargs)
        if Provider.objects.filter(subtype=Provider.SUBTYPES.acano, cluster=self.override_cluster).exists():
            self.fields.pop('sync_tenants', None)
        else:  # first:
            self.fields.pop('is_service_node', None)

    def get_api(self):
        return self.instance.get_api(Customer.objects.all().first())

    class Meta:
        model = Provider
        fields = (
            'title',
            'ip',
            'api_host',
            'hostname',
            'verify_certificate',
            'username',
            'password',
        )
        widgets = {
            'password': forms.PasswordInput(),
        }

    def clean(self):

        c = self.cleaned_data
        if not any([c.get('ip'), c.get('api_host'), c.get('hostname')]):
            self.add_error('ip', 'IP, hostname or API host must be set')
        if self.cleaned_data.get('is_service_node'):
            self.instance.subtype = Provider.SUBTYPES.acano_node
        else:
            self.instance.subtype = Provider.SUBTYPES.acano

        if self.override_cluster and not self.cleaned_data.get('username') and not self.cleaned_data.get('password'):
            providers = self.override_cluster.get_clustered()
            if providers:
                self.instance.username = providers[0].username
                self.instance.password = providers[0].password
        return super().clean()

    def validate_login(self):
        try:
            self.get_api().get('system/status/')
        except AuthenticationError as e:
            self.add_error('api_host', str(_('Kunde inte ansluta: {}')).format(e))
        except (ResponseError, AuthenticationError) as e:
            self.add_error('api_host', str(_('Kunde inte ansluta: {}')).format(e))
        else:
            return
        raise forms.ValidationError(str(_('Kunde inte ansluta till servern')))

    def save(self, commit=True):

        assert commit
        instance = super().save(commit=False)

        if self.override_cluster:
            instance.cluster = self.override_cluster

        api = self.get_api()

        instance.internal_domains = self.instance.hostname or ''
        try:
            instance.internal_domains = ','.join(api.get_internal_domains())
        except (AuthenticationError, ResponseError):
            pass

        new_cluster = not (self.override_cluster or self.instance.cluster).get_clustered()

        instance.save()

        if new_cluster:
            from provider.tasks import cache_single_cluster_data

            try:
                cache_single_cluster_data.delay(instance.cluster.pk)
            except Exception:
                pass

        if self.cleaned_data.get('sync_tenants'):
            api = instance.get_api(Customer.objects.all().first())
            api.sync_tenant_customers()

        if self.cleaned_data.get('set_cdr'):
            api = instance.get_api(Customer.objects.all().first())
            api.set_cdr_settings()

        return instance


class ExtendAcanoClusterForm(AcanoSetupForm):

    class Meta(AcanoSetupForm.Meta):
        fields = ('title', 'ip', 'api_host', 'verify_certificate', 'hostname')


class VCSSetupForm(forms.ModelForm):

    def __init__(self, *args, override_cluster, **kwargs):
        self.override_cluster = override_cluster
        super().__init__(*args, **kwargs)

    def get_api(self):
        return self.instance.get_api(Customer.objects.all().first())

    def clean(self):
        c = self.cleaned_data
        if not c.get('ip') and not c.get('hostname'):
            raise forms.ValidationError(_('IP eller hostname måste anges'))
        return c

    class Meta:
        model = VCSEProvider
        fields = (
            'title',
            'ip',
            'hostname',
            'api_host',
            'verify_certificate',
            'username',
            'password',
        )
        widgets = {
            'password': forms.PasswordInput(),
        }

    def validate_login(self):
        try:
            self.get_api().get_status()
        except (AuthenticationError, ResponseError) as e:
            self.add_error('password', str(_('Kunde inte ansluta: {}')).format(e))
            raise forms.ValidationError(str(_('Kunde inte ansluta till servern')))

    def save(self, commit=True):

        instance = super().save(commit=False)

        if self.override_cluster:
            instance.cluster = self.override_cluster
            instance.default_domain = self.override_cluster.get_cluster_settings(
                None
            ).get_main_domain()

        if commit:
            instance.save()

        return instance


class PexipSetupForm(forms.ModelForm):

    ip = forms.GenericIPAddressField(label=_('IP-nummer'), required=False)
    dial_out_location = forms.CharField(
        label=_('Dial out-location för nya deltagare'), required=False
    )
    create_event_policy = forms.BooleanField(
        label=_('Förbered event sink och external policy'),
        help_text=_('Dessa måste manuellt aktiveras för respektive Location'),
        required=False,
    )

    def __init__(self, *args, override_cluster, **kwargs):
        self.override_cluster = override_cluster
        initial = {**(kwargs.get('initial') or {})}.copy()
        if override_cluster:
            initial.setdefault('title', override_cluster.title)
        kwargs['initial'] = initial
        super().__init__(*args, **kwargs)

    def get_api(self):
        return self.instance.get_api(Customer.objects.all().first())

    class Meta:
        model = Provider
        fields = (
            'title',
            'ip',
            'hostname',
            'api_host',
            'verify_certificate',
            'username',
            'password',
        )
        widgets = {
            'password': forms.PasswordInput(),
        }

    def clean(self):

        c = self.cleaned_data
        if not any([c.get('ip'), c.get('api_host'), c.get('hostname')]):
            self.add_error('ip', 'IP, hostname or API host must be set')

        self.instance.subtype = Provider.SUBTYPES.pexip
        return super().clean()

    def validate_login(self):
        try:
            self.get_api().get('status/v1/worker_vm/')
        except AuthenticationError as e:
            self.add_error('password', str(_('Kunde inte ansluta: {}').format(e)))
            raise forms.ValidationError(str(_('Inloggningsfel')))
        except Exception as e:
            raise forms.ValidationError({'api_host': str(_('Kunde inte ansluta: {}').format(e))})
        else:
            return

    def save(self, commit=True):

        assert commit
        instance = super().save(commit=False)

        if self.override_cluster:
            instance.cluster = self.override_cluster

        api = self.get_api()

        instance.internal_domains = self.instance.hostname or ''
        try:
            instance.internal_domains = ','.join(api.get_internal_domains())
        except (AuthenticationError, ResponseError):
            pass

        new_cluster = not (self.override_cluster or self.instance.cluster).get_clustered()

        instance.save()

        if new_cluster:
            from provider.tasks import cache_single_cluster_data

            cache_single_cluster_data.delay(instance.cluster.pk)

            c_settings = instance.cluster.get_cluster_settings()
            if self.cleaned_data.get('dial_out_location'):
                partial_update(
                    c_settings, {'dial_out_location': self.cleaned_data['dial_out_location']}
                )

            try:
                if not c_settings.dial_out_location:
                    self.populate_default_location(api)
                if self.cleaned_data.get('create_event_policy'):
                    api.create_event_sink()
                    api.create_external_policy_server()
            except Exception:
                logger.warn('Could not save cluster', exc_info=True)
                if settings.TEST_MODE or settings.DEBUG:
                    raise

        return instance

    @staticmethod
    def populate_default_location(api):
        self = api  # TODO move to PexipAPI

        locations = {
            loc['name'].lower(): loc['name']
            for loc in self.get('configuration/v1/system_location/').json().get('objects', [])
        }
        if 'edge' in locations:
            location = locations['edge']
        else:
            location = list(locations.values())[0] if locations else ''

        if location:

            c_settings = self.get_settings()
            if not c_settings.dial_out_location:
                c_settings.dial_out_location = location
                c_settings.save()
