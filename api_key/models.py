import base64
import hashlib
import secrets
import time

from django.conf import settings
from django.db import models
from django.urls.base import reverse
from django.utils.functional import cached_property
from django.utils.translation import gettext_lazy as _
from jsonfield import JSONField
from oauthlib.common import generate_token
from oauthlib.oauth2 import BackendApplicationClient, WebApplicationClient, InvalidClientError
from requests_oauthlib import OAuth2Session

from customer.models import Customer
from msgraph.models import MSGraphCredentials
from provider.exceptions import AuthenticationError


def new_key():
    return secrets.token_urlsafe(32).replace('-', '3')


class BookingAPIKeyManager(models.Manager):

    def populate_system_keys(self):
        for key in settings.EXTENDED_API_KEYS:
            self.get_or_create(title='System generated', key=key)


class BookingAPIKey(models.Model):

    enabled = models.BooleanField(_('Aktiverad'), default=True)
    title = models.CharField(_('Namn'), max_length=255, blank=True)
    key = models.CharField(_('Nyckel'), max_length=200, default=new_key, unique=True)
    limit_customers = models.ManyToManyField(
        Customer, verbose_name=_('Begränsa till kunder'), blank=True
    )
    enable_cospace_changes = models.BooleanField(
        _('Aktivera ändra inställningar för fasta mötesrum'), default=False, blank=True
    )

    ts_created = models.DateTimeField(_('Skapades'), auto_now_add=True)
    ts_last_used = models.DateTimeField(_('Senast använd'), null=True)

    objects = BookingAPIKeyManager()

    def __str__(self):
        return self.title or '-'

    class Meta:
        verbose_name = _('bokningsportal API-nyckel')
        verbose_name_plural = _('bokningsportal API-nycklar')


class OAuthCredential(models.Model):

    EXCHANGE = 0
    MSGRAPH = 10

    TYPES = (
        (EXCHANGE, 'EWS'),
        (MSGRAPH, 'Microsoft Graph'),
    )
    TYPES_KEYS = {
        EXCHANGE: 'exchange',
        MSGRAPH: 'msgraph',
    }

    customer = models.ForeignKey(Customer, on_delete=models.CASCADE)
    type = models.SmallIntegerField(choices=TYPES, default=EXCHANGE)

    username = models.CharField(_('Service account användarnamn'), max_length=255,
                                help_text=_('All åtkomst kommer ske från detta konto'),
                                blank=True)

    client_id = models.CharField(_('Application (Client) ID'), max_length=255, help_text=_('Finns i Overview'))
    tenant_id = models.CharField(_('Directory (Tenant) ID'), max_length=255, help_text=_('Finns i Overview'), blank=True)
    secret = models.CharField(_('Client secret'), max_length=255, blank=True, help_text=_('Finns i Certificates and secrets'))
    authorization = models.CharField(max_length=255, editable=False)
    access_token = JSONField(editable=False)

    use_app_authorization = models.BooleanField(default=False)

    def __str__(self):
        if self.username:
            return self.username

        client_id = self.client_id if len(self.client_id) < 14 else '{}...'.format(self.client_id[:11])
        return 'Graph {}'.format(client_id)

    class Meta:
        verbose_name = _('Open Auth-tjänst (OAuth)')
        verbose_name_plural = _('Open Auth-tjänster (OAuth)')

    @cached_property
    def ews_credentials(self):

        from exchange.models import EWSCredentials
        return EWSCredentials.ews_oauth_credentials(self)

    @property
    def callback_url(self):
        if self.type == self.EXCHANGE:
            return self.get_exchange_callback_url()
        elif self.type == self.MSGRAPH:
            return self.get_msgraph_callback_url()

    @staticmethod
    def get_exchange_callback_url():
        return '{}{}'.format(settings.BASE_URL.rstrip('/'), reverse('ews_oauth_verify'))

    @staticmethod
    def get_msgraph_callback_url():
        return '{}{}'.format(settings.BASE_URL.rstrip('/'), reverse('msgraph_oauth_verify'))

    SCOPES = {
        'exchange': ['offline_access https://outlook.office365.com/.default'],
        'msgraph': ['offline_access https://graph.microsoft.com/.default'],
        'msgraph_authorize': [
            'offline_access {}'.format(
                ' '.join('https://graph.microsoft.com/' + s for s in ('User.ReadBasic.All', 'Calendars.Read.Shared', 'Place.Read.All'))
            ),
        ],
    }

    _oauth_state = None

    def get_absolute_url(self):
        if self.type == self.EXCHANGE:
            return reverse('onboard_ews_complete', args=[self.pk]) + '?customer={}'.format(self.customer_id)
        elif self.type == self.MSGRAPH:
            return reverse('onboard_msgraph_complete', args=[self.pk]) + '?customer={}'.format(self.customer_id)

    @property
    def oauth_state(self):
        if not self._oauth_state:
            self._oauth_state = generate_token()
        return self._oauth_state

    @oauth_state.setter
    def oauth_state(self, value):
        self._oauth_state = value
        self.session._state = value

    @property
    def active_scope(self):
        type_key = self.TYPES_KEYS[self.type]
        if not self.use_app_authorization and '{}_authorize'.format(type_key) in self.SCOPES:
            return self.SCOPES['{}_authorize'.format(type_key)]
        return self.SCOPES[type_key]

    @cached_property
    def session(self):

        if self.use_app_authorization:
            client = BackendApplicationClient(self.client_id)
        else:
            client = WebApplicationClient(self.client_id)

        def _get_state():
            return self.oauth_state

        has_refresh_token = self.access_token and self.access_token.get('refresh_token')

        session = OAuth2Session(
            client=client,
            # scope=self.active_scope,
            redirect_uri=self.callback_url,
            auto_refresh_url=self.token_url if has_refresh_token or not self.use_app_authorization else None,
            auto_refresh_kwargs={
                'client_id': self.client_id,
                'client_secret': self.secret or None,
            },
            token=self.access_token,
            token_updater=self.update_token,
            state=_get_state,
        )
        return session

    def update_token(self, access_token):
        self.access_token = access_token
        self.save()

    def check_session(self):
        try:
            expires_at = self.access_token and self.access_token.get('expires_at')
            SKEW = 5 * 60
            if (not self.access_token or expires_at and expires_at < time.time() + SKEW) and self.secret:
                self.fetch_token()
            return self.session
        except InvalidClientError as e:
            raise AuthenticationError(str(e), e)

    def fetch_token(self):
        if self.access_token.get('refresh_token'):
            token = self.session.refresh_token(self.token_url, timeout=(4.1, 20))
        else:
            token = self.session.fetch_token(
                include_client_id=True,
                client_secret=self.secret or None,
                token_url=self.token_url,
                scope=self.active_scope,
                timeout=(4.1, 20),
            )
        self.update_token(token)

    @property
    def consent_url(self):
        return 'https://login.microsoftonline.com/%s/v2.0/adminconsent' % (self.tenant_id or 'common')

    def start_interactive_consent(self):
        self.session.scope = self.active_scope
        consent_url, state = self.session.authorization_url(self.consent_url)
        self.session.scope = None

        return consent_url, state

    @property
    def authorization_url(self):
        return 'https://login.microsoftonline.com/%s/oauth2/v2.0/authorize' % (self.tenant_id or 'common')

    def start_interactive_authorization(self):

        self.session.scope = self.active_scope

        code_verifier = secrets.token_urlsafe(64)
        kwargs = {
            'code_challenge': base64.urlsafe_b64encode(hashlib.sha256(code_verifier.encode('ascii')).digest())[:-1],
            'code_challenge_method': 'S256',
        }

        authorization_url, state = self.session.authorization_url(self.authorization_url, **kwargs)

        self.session.scope = None

        return authorization_url, state, code_verifier

    @property
    def token_url(self):
        return 'https://login.microsoftonline.com/%s/oauth2/v2.0/token' % (self.tenant_id or 'common')

    def validate(self, response, state=None, code_verifier=None):
        if state:
            self.oauth_state = state

        self.session.scope = None
        kwargs = {}
        if code_verifier:
            kwargs['code_verifier'] = code_verifier
        token = self.session.fetch_token(include_client_id=True, client_secret=self.secret or None,
                                         token_url=self.token_url, authorization_response=response, **kwargs)
        return token

    def save(self, *args, **kwargs):
        old = None
        if self.pk:
            old = OAuthCredential.objects.filter(pk=self.pk).first()

        if old and old.use_app_authorization != self.use_app_authorization:
            self.access_token = ''

        super().save(*args, **kwargs)

    def connect_related(self):
        if self.type == self.EXCHANGE:
            from exchange.models import EWSCredentials
            EWSCredentials.objects.update_or_create(
                customer=self.customer,
                oauth_credential=self,
                defaults={
                    'username': self.username,
                },
            )
        elif self.type == self.MSGRAPH:
            MSGraphCredentials.objects.update_or_create(
                customer=self.customer,
                oauth_credential=self,
                defaults={
                    'username': self.username,
                },
            )
