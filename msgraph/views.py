from django.urls import reverse

from exchange.views import EWSOauthSetup, EWSOauthComplete, EWSOauthVerify
from msgraph.forms import MSGraphOauthSetupForm
from msgraph.models import MSGraphCredentials


class MSGraphOauthSetup(EWSOauthSetup):
    template_name = 'msgraph/msgraph.html'
    form_class = MSGraphOauthSetupForm
    credentials_class = MSGraphCredentials

    def get_success_url(self) -> str:
        return reverse('onboard_msgraph_complete', args=[self.object.pk])


class MSGraphOauthComplete(EWSOauthComplete):
    template_name = 'base_vue.html'
    form_class = MSGraphOauthSetupForm
    credentials_class = MSGraphCredentials


class MSGraphOauthVerify(EWSOauthVerify):

    credentials_class = MSGraphCredentials

    def get_error_url(self):
        return reverse('onboard_msgraph_complete', args=[self.oauth.pk])

