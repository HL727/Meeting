
from django import forms
from django.conf import settings
from django.utils.timezone import now

from endpointproxy.models import EndpointProxy, EndpointProxyStatusChange
from shared.utils import partial_update


class EndpointProxyRegistrationForm(forms.Form):

    ssh_key = forms.CharField(required=False)
    secret_key = forms.CharField(required=False)
    password = forms.CharField(required=False)
    name = forms.CharField(required=False)
    version = forms.CharField()

    time = forms.CharField(required=False)
    hash = forms.CharField(required=False)

    def clean_ssh_key(self):

        value = self.cleaned_data.get('ssh_key', '').strip().replace('\n', '')

        if not value:
            return ''

        parts = value.split(' ')

        key = ''

        if value.startswith('ssh-') and len(parts) > 1:
            key = parts[1]
        else:
            if len(parts[0]) < 200:
                raise forms.ValidationError('Invalid ssh key')

        return key

    def clean_secret_key(self):
        if self.cleaned_data.get('secret_key'):
            try:
                self.get_proxy()
            except EndpointProxy.DoesNotExist:
                raise forms.ValidationError('Invalid key')

        return self.cleaned_data.get('secret_key')

    def clean_password(self):
        value = self.cleaned_data.get('password')
        if not value:
            if settings.EPM_REQUIRE_PROXY_PASSWORD:
                raise forms.ValidationError('Invalid password. Upgrade your proxy')
            return None

        if not EndpointProxy.objects.get_customers_for_password(value).exists():
            raise forms.ValidationError('Invalid password')

        return value

    def verify_hash(self, proxy: EndpointProxy):
        hash = self.cleaned_data.get('hash', '')
        time = self.cleaned_data.get('time', '')

        if (not time or not hash) and not settings.EPM_REQUIRE_PROXY_HASH:
            return

        if not time or not proxy.validate_hash_timestamp(time):
            raise forms.ValidationError(
                {
                    'time': 'Invalid time',
                }
            )

        if not hash:
            raise forms.ValidationError(
                {
                    'hash': 'hash must be provided',
                }
            )

        if not proxy.validate_hash(hash, time):
            raise forms.ValidationError(
                {
                    'hash': 'Invalid hash or timestamp',
                }
            )

    def clean(self):
        if not self.cleaned_data.get('ssh_key') and not self.cleaned_data.get('secret_key'):
            raise forms.ValidationError({'ssh_key': 'ssh_key or secret_key must be set'})

        try:
            self.verify_hash(self.get_proxy())
        except EndpointProxy.DoesNotExist:
            pass

        return super().clean()

    def get_proxy(self):
        if self.cleaned_data.get('secret_key'):
            return EndpointProxy.objects.exclude(ssh_key='').get(
                secret_key=self.cleaned_data.get('secret_key')
            )
        elif self.cleaned_data.get('ssh_key'):
            return EndpointProxy.objects.get(ssh_key=self.cleaned_data.get('ssh_key'))
        raise EndpointProxy.DoesNotExist()

    def save(self, ip=None, customer=None):

        customer = None

        if self.cleaned_data.get('password'):
            customers = EndpointProxy.objects.get_customers_for_password(
                self.cleaned_data.get('password')
            )
            if len(customers) == 1:
                customer = customers[0]

        defaults = {
            'last_connect_ip': ip,
            'last_connect': now(),
            'proxy_version': self.cleaned_data.get('version'),
        }

        existing = None

        if self.cleaned_data.get('ssh_key'):
            try:
                existing = proxy = self.get_proxy()
            except EndpointProxy.DoesNotExist:
                proxy, created = EndpointProxy.objects.get_or_create(
                    ssh_key=self.cleaned_data.get('ssh_key'),
                    defaults={
                        **defaults,
                        'secret_key': EndpointProxy.new_key(),
                        'first_ip': ip,
                        'name': self.cleaned_data.get('name', '').strip()
                        or 'New proxy {}'.format(now()),
                        'customer': customer,
                    },
                )
                if not created:
                    existing = proxy

        elif self.cleaned_data.get('secret_key'):
            existing = proxy = self.get_proxy()
        else:
            raise forms.ValidationError({'ssh_key': 'SSH key or secret_key must be provided'})

        if existing:
            partial_update(proxy, defaults)

        EndpointProxyStatusChange.objects.create(proxy=proxy, is_connect=True, is_online=proxy.is_online if proxy.ts_activated else None)

        if proxy.ts_activated and not proxy.reserved_port:
            proxy.reserve_port(commit=True)

        return proxy, not bool(existing)


class EndpointProxyForm(EndpointProxyRegistrationForm):
    def clean(self):
        cleaned_data = self.cleaned_data
        try:
            self.get_proxy()
        except EndpointProxy.DoesNotExist:
            raise forms.ValidationError({'ssh_key': 'SSH key or secret key must be provided'})
        return cleaned_data
