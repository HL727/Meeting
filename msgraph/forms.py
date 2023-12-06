from django.conf import settings
from django import forms
from django.utils.translation import gettext as _
from oauthlib.oauth2 import WebApplicationClient
from requests_oauthlib import OAuth2Session

from .models import MSGraphCredentials
from api_key.models import OAuthCredential


class MSGraphOauthSetupForm(forms.ModelForm):

    def __init__(self, *args, customer=None, **kwargs):
        self.customer = customer
        super().__init__(*args, **kwargs)

    class Meta:
        model = OAuthCredential
        fields = ('client_id', 'tenant_id', 'secret')
        widgets = {
            'password': forms.PasswordInput(),
        }

    def clean_username(self):
        value = self.cleaned_data.get('username')
        if MSGraphCredentials.objects.filter(username=value, customer=self.customer).exclude(pk=self.instance.pk or -1):
            raise forms.ValidationError(_('Det finns redan en anslutning för detta konto'))
        return value

    def clean(self):
        cleaned_data = super().clean()

        scope = OAuthCredential.SCOPES['msgraph']
        client = WebApplicationClient(cleaned_data['client_id'])
        session = OAuth2Session(client=client, scope=scope, redirect_uri=settings.BASE_URL + 'ews/oauth/')

        url = 'https://login.microsoftonline.com/%s/oauth2/v2.0/authorize' % (cleaned_data.get('tenant_id') or 'common')
        try:
            authorization_url, state = session.authorization_url(url)
        except Exception as e:
            raise forms.ValidationError({'client_id': 'Invalid data: {}'.format(e)})

        return cleaned_data

    def save(self, customer):
        instance = super().save(commit=False)
        instance.customer = customer
        instance.type = OAuthCredential.MSGRAPH
        instance.enable_sync = True
        instance.save()
        return instance
