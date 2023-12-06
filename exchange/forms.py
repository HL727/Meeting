from urllib.parse import urlparse

import exchangelib
from django.utils.translation import gettext_lazy as _
import requests
from django import forms
from django.conf import settings
from django.core.exceptions import ValidationError
from oauthlib.oauth2 import WebApplicationClient
from requests_oauthlib import OAuth2Session

from exchange.models import EWSCredentials
from api_key.models import OAuthCredential


class EWSSetupForm(forms.ModelForm):
    class Meta:
        model = EWSCredentials
        fields = ('username', 'password', 'server')
        widgets = {
            'password': forms.PasswordInput(),
        }

    def clean_server(self):
        value = self.cleaned_data.get('server', '')
        if '/' in value:
            try:
                return urlparse(value).netloc
            except Exception:
                raise forms.ValidationError('Only the domain name should be included')
        return value

    def clean(self):
        cleaned_data = super().clean()

        try:
            # Give the credentials a spin
            cred = exchangelib.Credentials(cleaned_data['username'], cleaned_data['password'])
            if cleaned_data.get('server'):
                config_kwargs = {'server': cleaned_data['server']}
            else:
                config_kwargs = {'autodiscover': True}
            exchangelib.Account(cleaned_data['username'], credentials=cred, **config_kwargs)
        except Exception as e:
            raise ValidationError(e)

        return cleaned_data

    def save(self, customer, commit=False):
        instance = super().save(commit=False)
        instance.customer = customer
        instance.save()
        return instance


class EWSOauthSetupForm(forms.ModelForm):

    def __init__(self, *args, customer=None, **kwargs):
        self.customer = customer
        super().__init__(*args, **kwargs)

    class Meta:
        model = OAuthCredential
        fields = ('username', 'client_id', 'tenant_id', 'secret')
        widgets = {
            'password': forms.PasswordInput(),
        }

    def clean_username(self):
        value = self.cleaned_data.get('username')
        if EWSCredentials.objects.filter(username=value, customer=self.customer).exclude(pk=self.instance.pk or -1):
            raise forms.ValidationError(_('Det finns redan en anslutning för detta konto'))
        return value

    def clean(self):
        cleaned_data = super().clean()

        scope = ['https://outlook.office365.com/.default']
        client = WebApplicationClient(cleaned_data['client_id'])
        session = OAuth2Session(client=client, scope=scope, redirect_uri=settings.BASE_URL + 'ews/oauth/')

        url = 'https://login.microsoftonline.com/%s/oauth2/v2.0/authorize' % cleaned_data['tenant_id']
        try:
            authorization_url, state = session.authorization_url(url)
        except Exception as e:
            raise forms.ValidationError({'client_id': 'Invalid data: {}'.format(e)})

        return cleaned_data

    def save(self, customer):
        instance = super().save(commit=False)
        instance.customer = customer
        instance.save()
        return instance
