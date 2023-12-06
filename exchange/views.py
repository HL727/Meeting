from django.conf import settings
from django.shortcuts import redirect, get_object_or_404
from django.urls import reverse
from django.utils.translation import gettext as _
from django.views import View
from django.views.generic import CreateView, UpdateView, TemplateView
from oauthlib.oauth2 import InvalidClientError
from sentry_sdk import capture_exception

from exchange.models import EWSCredentials
from api_key.models import OAuthCredential
from exchange.forms import EWSOauthSetupForm, EWSSetupForm
from provider.exceptions import AuthenticationError, ResponseError
from shared.utils import partial_update
from supporthelpers.views.mixins import SettingsProductMixin, CustomerMixin


class EWSSetup(SettingsProductMixin, CustomerMixin, CreateView):
    template_name = 'exchange/ews.html'
    form_class = EWSSetupForm

    def get_context_data(self, **kwargs):
        return super().get_context_data(error=getattr(self, 'error', None))

    def form_valid(self, form):
        credentials = form.save(customer=self.customer)
        from exchange import tasks
        try:
            tasks.sync_ews_rooms(credentials.pk)
        except Exception as e:
            form.add_error('user', str(e))
            self.error = e
            return self.form_invalid(form)
        return redirect('cloud_dashboard_epm')


class EWSOauthBase(SettingsProductMixin, CustomerMixin, View):
    form_class = EWSOauthSetupForm
    credentials_class = EWSCredentials

    def get_form_kwargs(self):
        return {**super().get_form_kwargs(), 'customer': self.customer}

    def get_context_data(self, **kwargs):
        if self.credentials_class == EWSCredentials:
            callback_url = OAuthCredential.get_exchange_callback_url()
        else:
            callback_url = OAuthCredential.get_msgraph_callback_url()

        return {
            **super().get_context_data(**kwargs),
            'callback_url': callback_url,
            'oauth': True,
        }

    def form_valid(self, form):
        oauth_credential = form.save(customer=self.customer)
        credentials, created = self.credentials_class.objects.get_or_create(oauth_credential=oauth_credential,
                                                                            defaults=dict(customer=self.customer))
        credentials.username = oauth_credential.username
        credentials.save()

        self.object = oauth_credential
        return redirect(self.get_success_url())

    def get_success_url(self) -> str:
        return reverse('onboard_ews_complete', args=[self.object.pk])


class EWSOauthSetup(EWSOauthBase, CreateView):
    template_name = 'exchange/ews.html'


class EWSOauthComplete(EWSOauthBase, UpdateView):
    template_name = 'base_vue.html'
    form_class = EWSOauthSetupForm
    credentials_class = EWSCredentials
    model = OAuthCredential

    def get(self, request, *args, **kwargs):

        object = self.get_object()
        self.object = object

        if request.GET.get('redirect'):
            request.session['oauth_ews'] = object.pk
            partial_update(object, {'use_app_authorization': False})
            url, request.session['oauth_ews_state'], request.session['oauth_code_verifier'] = object.start_interactive_authorization()
            return redirect(url)

        if request.GET.get('consent'):
            request.session['oauth_ews'] = object.pk
            partial_update(object, {'use_app_authorization': False})
            url, request.session['oauth_ews_state'] = object.start_interactive_consent()
            return redirect(url)

        if request.GET.get('app'):
            try:
                return self.init_app_authorization(object)
            except (ResponseError, AuthenticationError) as e:
                self.error = str(e)

        return super().get(request, *args, **kwargs)

    def init_app_authorization(self, oauth):
        from exchangelib.errors import EWSError

        oauth.authorization = ''
        oauth.access_token = {}
        oauth.use_app_authorization = True
        oauth.save()

        credentials, created = self.credentials_class.objects.get_or_create(oauth_credential=oauth,
                                                                            defaults={
                                                                                'customer': oauth.customer,
                                                                                'username': oauth.username,
                                                                            })

        try:
            credentials.sync_rooms()
        except (EWSError, AuthenticationError, InvalidClientError) as e:
            self.error = str(e)
            return super().get(self.request, *self.args, **self.kwargs)
        return redirect('cloud_dashboard_epm')

    def get_object(self, queryset=None) -> OAuthCredential:
        return get_object_or_404(OAuthCredential, customer=self.customer, pk=self.kwargs['pk'])

    def get_context_data(self, **kwargs):
        context = {
            **super().get_context_data(**kwargs),
            'callback_url': self.object.callback_url,
            'error': getattr(self, 'error', None) or self.request.session.pop('oauth_ews_error', None),
            'complete': True,
        }
        return context

    def get_success_url(self):
        return redirect(self.request.path + '?complete={}'.format(self.object.pk))


class EWSOauthVerify(CustomerMixin, TemplateView):

    credentials_class = EWSCredentials

    def get(self, request, *args, **kwargs):

        oauth = get_object_or_404(OAuthCredential, pk=request.session.get('oauth_ews'))

        if request.GET.get('admin_consent') == 'True':
            if oauth.type == OAuthCredential.MSGRAPH:
                return redirect('onboard_msgraph_complete', oauth.pk)
            return redirect('onboard_ews_complete', oauth.pk)

        token = oauth.validate(settings.BASE_URL.rstrip('/') + request.get_full_path(),
                               state=request.session.pop('oauth_ews_state', None),
                               code_verifier=request.session.pop('oauth_code_verifier', None),
                               )

        oauth.access_token = token
        oauth.save()
        self.oauth = oauth

        credentials, created = self.credentials_class.objects.get_or_create(oauth_credential=oauth,
                                                                 defaults=dict(customer=oauth.customer))

        try:
            credentials.sync_rooms()
        except AuthenticationError:
            request.session['oauth_ews_error'] = _('Behörighetsfel. Kontrollera API-rättigheter samt att behörighet är inlagd in Manifest')
            return redirect(self.get_error_url())
        except Exception as e:
            request.session['oauth_ews_error'] = str(e)
            capture_exception()
            return redirect(self.get_error_url())

        return redirect('cloud_dashboard_epm')

    def get_error_url(self):
        return reverse('onboard_ews_complete', args=[self.oauth.pk])



