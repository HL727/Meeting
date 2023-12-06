from typing import TYPE_CHECKING, Iterator

import exchangelib
from django.db import models
from django.db.models import Q
from django.utils.functional import cached_property
from django.utils.translation import gettext_lazy as _

from calendar_invite.models import Calendar, Credentials
from provider.exceptions import AuthenticationError

if TYPE_CHECKING:
    from api_key.models import OAuthCredential


RECURSE_SUBCALENDARS = False


class EWSCredentials(Credentials):

    password = models.CharField(_('Lösenord'), max_length=100, blank=True, help_text=_('Används om man kör Basic auth istället för OAuth'))
    server = models.CharField(_('Värdnamn för exchange-server'), max_length=255, blank=True, help_text=_('Lämna tomt för att hitta rätt server via auto-discovery'))

    _ews_account: exchangelib.Account = None

    def __str__(self):
        return self.username

    def save(self, *args, **kwargs):
        self.type = Credentials.EXCHANGE
        super().save(*args, **kwargs)
        if self.username and self.oauth_credential_id and not self.oauth_credential.username:
            self.oauth_credential.username = self.username
            self.oauth_credential.save(update_fields=['username'])

    class Meta:
        verbose_name = _('Exchange Web Services-koppling (EWS)')
        verbose_name_plural = _('Exchange Web Services-kopplingar (EWS)')

    def get_sync_handler(self):
        from exchange.handler import ExchangeHandler

        return ExchangeHandler(self, account=self._ews_account)

    @staticmethod
    def ews_oauth_credentials(oauth_credential: 'OAuthCredential'):

        class MividasOauthCredentials(exchangelib.OAuth2AuthorizationCodeCredentials):
            def on_token_auto_refreshed(self, access_token):
                oauth_credential.update_token(access_token)
                super().on_token_auto_refreshed(access_token)

        kwargs = dict(
            client_id=oauth_credential.client_id,
            client_secret=oauth_credential.secret,
            tenant_id=oauth_credential.tenant_id,
        )
        if oauth_credential.authorization or oauth_credential.access_token:
            credentials = MividasOauthCredentials(authorization_code=oauth_credential.authorization,
                                                  access_token=oauth_credential.access_token,
                                                  **kwargs)
        else:
            credentials = exchangelib.OAuth2Credentials(
                identity=exchangelib.Identity(primary_smtp_address=oauth_credential.username),
                **kwargs)

        return credentials

    @cached_property
    def ews_credentials(self):

        if self.oauth_credential_id:
            return self.oauth_credential.ews_credentials

        return exchangelib.Credentials(self.username, self.password)

    @property
    def ews_account(self):
        if self._ews_account:
            return self._ews_account

        return self.get_ews_account()

    def get_ews_account(self, validate_login=False):

        if validate_login is None:
            validate_login = bool(self._ews_account is None)

        if not self.autodiscover_data or validate_login:
            return self.login()

        account = self.prepare_account(self.username,
                                       autodiscover_data=self.autodiscover_data,
                                       )
        self._ews_account = account
        return account

    def login(self) -> exchangelib.Account:

        try:
            account, autodiscover_data = self.validate_account(self.username,
                                                               autodiscover_data=self.autodiscover_data,
                                                               )
        except AuthenticationError:
            self.is_working = False
            self.autodiscover_data = {}
            self.save()
            self._ews_account = None
            raise

        self._force_root(account)

        if not self.is_working or not self.autodiscover_data:
            self.is_working = True
            self.autodiscover_data = autodiscover_data
            self.save()
            from .tasks import sync_ews_rooms
            sync_ews_rooms.delay(self.pk)
        self._ews_account = account
        return account

    def _force_root(self, account: exchangelib.Account):
        """
        Fake root folder if not already populated to be able to use service account without mailboxes
        """
        if 'root' not in account.__dict__:
            from exchangelib.folders.roots import Root

            account.__dict__['root'] = exchangelib.folders.roots.Root(account=account)

    def prepare_account(self, username: str, autodiscover_data: dict = None):

        config_kwargs = {
            'credentials': self.ews_credentials,
            'server': self.server or None,
        }
        account_kwargs = {}

        if not autodiscover_data:
            autodiscover_data = self.autodiscover_data

        if autodiscover_data:
            autodiscover_keys = {'service_endpoint', 'auth_type', 'version'}
            config_kwargs.update({k: v for k, v in autodiscover_data.items()
                                  if k in autodiscover_keys})

            if config_kwargs.get('service_endpoint'):
                config_kwargs.pop('server', None)

        if self.oauth_credential_id:
            config_kwargs['auth_type'] = exchangelib.OAUTH2
            if not config_kwargs.get('service_endpoint') and not self.server:
                config_kwargs['server'] = 'outlook.office365.com'
            if not self.oauth_credential.access_token:  # Not authorization
                account_kwargs['access_type'] = exchangelib.IMPERSONATION

        account = exchangelib.Account(username,
                                      credentials=self.ews_credentials,
                                      config=exchangelib.Configuration(**config_kwargs),
                                      autodiscover=not (autodiscover_data or config_kwargs['server']),
                                      **account_kwargs,
                                      )
        return account

    def validate_account(self, username: str, autodiscover_data: dict = None):

        if not autodiscover_data:
            autodiscover_data = self.autodiscover_data

        account = self.prepare_account(username, autodiscover_data=autodiscover_data)
        if not autodiscover_data:
            autodiscover_data = {
                'service_endpoint': account.protocol.service_endpoint,
                'auth_type': account.protocol.auth_type,
                'version': account.version,
            }

        from exchangelib.errors import ErrorAccessDenied, ErrorItemNotFound, ErrorNonExistentMailbox
        from exchangelib.items import ID_ONLY
        from exchangelib.properties import FolderId
        from exchangelib.services import GetFolder

        if self.username != username:  # Fake root for service account
            self._force_root(self.ews_account)

        try:
            # Bug exchangelib, ignores impersonate for folder lookups in oauth
            # This will make delegatee permission differ in bulk access to login() if just using account.<folder>
            # Do an extra lookup of calendar folder id to be sure
            check_account = account if self.username == username else self.ews_account
            check = list(GetFolder(account=check_account).call([FolderId(account.calendar.id)], [], ID_ONLY))
            if not check or isinstance(check[0], ErrorItemNotFound):
                raise AuthenticationError(check[0])
        except ErrorNonExistentMailbox as e:
            if self.username != username:
                raise AuthenticationError(e)
        except (ErrorAccessDenied, ErrorItemNotFound) as e:
            raise AuthenticationError(e)

        return account, autodiscover_data

    def get_room_lists(self, do_raise=True):
        from exchangelib.errors import ErrorNameResolutionNoMailbox

        try:
            return list(self.ews_account.protocol.get_roomlists())
        except ErrorNameResolutionNoMailbox:
            if do_raise:
                raise
            return []

    def get_rooms(self, room_list_address: str = None):
        return list(self.ews_account.protocol.get_rooms(room_list_address))

    def sync_rooms(self, delay: bool = False):

        from exchangelib.errors import ErrorNonExistentMailbox

        if delay:
            from .tasks import sync_ews_rooms
            sync_ews_rooms.delay(self.pk)
            return

        done = set()

        for email_address in self._iter_all_room_addresses():
            if email_address in done:
                continue
            done.add(email_address)

            try:
                self.sync_room(email_address)
            except (AuthenticationError, ErrorNonExistentMailbox):
                pass

    def _iter_all_room_addresses(self) -> Iterator[str]:
        if self.username:
            yield self.username

        for room_list in self.get_room_lists(do_raise=False):
            for room in self.get_rooms(room_list.email_address):
                yield room.email_address

        for calendar in Calendar.objects.filter(credentials=self, folder_id=''):
            yield calendar.username

    def sync_room(self, email_address: str, force=False) -> Calendar:
        from exchangelib.errors import ErrorNonExistentMailbox

        calendar, created = Calendar.objects.filter(Q(cached_path='') | Q(cached_path='/')) \
                                            .get_or_create(credentials=self,
                                                           customer=self.customer,
                                                           username=email_address,
                                                           defaults=dict(
                                                               cached_path='/',
                                                           ))

        if not created and calendar.folder_id and not force:
            return calendar

        try:
            calendar.login()
        except (ErrorNonExistentMailbox, AuthenticationError):
            calendar.is_working = False
            calendar.save()
            raise
        else:
            calendar.folder_id = calendar.ews_account.calendar.id
            calendar.cached_name = calendar.ews_account.calendar.name
            calendar.is_working = True
            calendar.save()

        if RECURSE_SUBCALENDARS:
            self._sync_subcalendars(calendar)
        return calendar

    def _sync_subcalendars(self, calendar: Calendar):

        for c in calendar.ews_account.calendar.walk():

            if c.id == calendar.ews_account.calendar.id:
                continue

            Calendar.objects.get_or_create(
                username=calendar.username,
                folder_id=c.id,
                credentials=self,
                cached_name=c.name,
                cached_path='/' + c.name,
            )

        return calendar


