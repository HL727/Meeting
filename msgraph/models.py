import os
from typing import Iterator, Optional

from django.conf import settings

from django.utils.functional import cached_property
from django.utils.translation import gettext_lazy as _

from customer.models import Customer
from calendar_invite.models import Calendar, Credentials
from msgraph.ext_api.msgraph_api import MSGraphAPI
from provider.exceptions import NotFound, ResponseError
from provider.types import ProviderAPICompatible


class MSGraphCredentials(Credentials, ProviderAPICompatible):

    api_host = 'graph.microsoft.com'
    ip = None  # # type: ignore[override]
    hostname = ''
    session_id = ''
    session_expires = ''

    class Meta:
        verbose_name = _('MS Graph API-koppling')
        verbose_name_plural = _('MS Graph API-kopplingar')

    def __str__(self):
        if self.username:
            return self.username
        if self.oauth_credential_id:
            return str(self.oauth_credential)
        return str(self.customer)

    def save(self, *args, **kwargs):
        self.type = Credentials.MSGRAPH
        super().save(*args, **kwargs)

        if self.username and self.oauth_credential_id and not self.oauth_credential.username:
            self.oauth_credential.username = self.username
            self.oauth_credential.save(update_fields=['username'])

    def get_api(self, customer: 'Customer' = None, allow_cached_values=False):
        return MSGraphAPI(self, customer=customer)

    def get_sync_handler(self):
        from msgraph.handler import MSGraphHandler
        return MSGraphHandler(self)

    @cached_property
    def api(self):
        return self.get_api(self.customer)

    def get_room_lists(self):
        return self.get_api().get_room_lists()

    def get_rooms(self, room_list_address=None):
        return self.get_api().get_rooms(room_list_address)

    def sync_room(self, email_address: str) -> Calendar:
        calendar, created = Calendar.objects.get_or_create(credentials=self,
                                                           customer=self.customer,
                                                           username=email_address,
                                                           cached_path='/',
                                                           )

        return calendar

    def sync_rooms(self, delay=False):

        if delay:
            from .tasks import sync_msgraph_rooms
            sync_msgraph_rooms.delay(self.pk)
            return

        if not self.username:
            try:
                self.username = self.get_api().get_me() or ''
            except ResponseError:  # Only allowed for delegated authentication
                pass
            if self.username:
                self.save(update_fields=['username'])
                if not self.oauth_credential.username:
                    self.oauth_credential.username = self.username
                    self.oauth_credential.save()

        for room in self._iter_all_room_addresses():
            try:
                self.sync_room(room)
            except NotFound:
                continue

    def _iter_all_room_addresses(self) -> Iterator[Optional[str]]:
        if self.username:
            yield self.username

        room_lists = self.get_room_lists() or [{'emailAddress': None}]

        for room_list in room_lists:
            try:
                for room in self.get_rooms(room_list['emailAddress']):
                    yield room['emailAddress']
            except NotFound:
                continue

        for calendar in Calendar.objects.filter(credentials=self, folder_id=''):
            yield calendar.username
