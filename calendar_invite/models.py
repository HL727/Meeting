from abc import abstractmethod
from datetime import timedelta

import exchangelib
from django.db import models
from django.utils.timezone import now

from django.utils.translation import gettext_lazy as _

from customer.models import Customer
from endpoint.models import Endpoint
from exchange.fields import AutoDiscoverJSONField
from meeting.models import Meeting, RecurringMeeting
from provider.exceptions import AuthenticationError


class Credentials(models.Model):
    """
    Credentials are used to provide Core access to an exchange server.
    They can be used to gain access to multiple calendars on the same instance.
    """

    EXCHANGE = 0
    MSGRAPH = 10

    TYPES = (
        (EXCHANGE, _('EWS / Exchange')),
        (MSGRAPH, _('Microsoft Graph')),
    )

    customer = models.ForeignKey(Customer, on_delete=models.CASCADE)
    username = models.CharField(_('Användarnamn'), max_length=100, help_text='UserPrincipalName/SMTP-adress (user@example.com)')

    enable_sync = models.BooleanField(_('Aktivera synk'), default=True)

    type = models.SmallIntegerField(choices=TYPES, default=0)

    last_modified_time = models.DateTimeField(null=True, editable=False)
    last_sync = models.DateTimeField(null=True, editable=False)
    last_incremental_sync = models.DateTimeField(null=True, editable=False)

    last_sync_error = models.CharField(max_length=200, blank=True)

    is_working = models.BooleanField(default=False, help_text='If True then this was last working on last_modified_time', editable=False)

    video_meetings_only = models.BooleanField(default=True, help_text=_('Hoppa över alla möten som inte kan matchas till uppringningsadress'))

    oauth_credential = models.OneToOneField('api_key.OAuthCredential', related_name='credentials', null=True, blank=True, on_delete=models.SET_NULL)

    autodiscover_data = AutoDiscoverJSONField(editable=False)

    def get_room_lists(self):
        raise NotImplementedError()

    def get_rooms(self, room_list_address):
        raise NotImplementedError()

    def sync_room(self, email_address):
        raise NotImplementedError()

    def sync_rooms(self, delay):
        raise NotImplementedError()

    def __str__(self):
        return self.username

    @property
    def should_sync_full(self):
        limit_minutes = 60
        if self.last_sync is None:
            return True
        return self.last_sync < now() - timedelta(minutes=limit_minutes)

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        if not kwargs.get('update_fields') or 'customer' in kwargs['update_fields']:
            Calendar.objects.filter(credentials=self).exclude(customer=self.customer_id).update(customer=self.customer)

    class Meta:
        verbose_name = _('Kalender bas-koppling')
        verbose_name_plural = _('Kalender bas-koppling')


class Calendar(models.Model):
    """
    A calendar folder belonging to an EWS manager account and linked to a certian Endpoint
    """
    customer = models.ForeignKey(Customer, null=True, on_delete=models.CASCADE, editable=False)

    credentials = models.ForeignKey(Credentials, on_delete=models.CASCADE)
    username = models.CharField(max_length=256)
    endpoint = models.ForeignKey(Endpoint, blank=True, null=True, on_delete=models.CASCADE)
    folder_id = models.CharField(blank=True, max_length=256, editable=False)
    # "Room 1234"
    cached_name = models.CharField(blank=True, max_length=100, editable=False)
    # from account.calendar: "/Room 1234"
    cached_path = models.CharField(blank=True, max_length=100, default='', editable=False)

    autodiscover_data = AutoDiscoverJSONField(editable=False)

    is_working = models.BooleanField(default=False, help_text='Could this calendar be accessed the last try', editable=False)
    ts_last_sync = models.DateTimeField(null=True, editable=False)

    _ews_account: exchangelib.Account = None

    def save(self, **kwargs):

        if not self.customer_id:
            self.customer = self.credentials.customer
        super().save(**kwargs)

        if not self.folder_id and self.endpoint_id and self.username:
            try:
                self.credentials.sync_room(self.username)
            except Exception:
                pass

    @property
    def ews_account(self):
        if self._ews_account:
            return self._ews_account

        return self.get_ews_account()

    def get_ews_account(self, validate_login=False):

        if not self.autodiscover_data or not self.folder_id or validate_login:
            return self.login()

        ews_credentials = self.credentials.ewscredentials

        account = ews_credentials.prepare_account(self.username,
                                                   autodiscover_data=self.autodiscover_data,
                                                   )
        self._ews_account = account
        return account

    def login(self):

        ews_credentials = self.credentials.ewscredentials
        try:
            account, autodiscover_data = ews_credentials.validate_account(self.username,
                                                                           autodiscover_data=self.autodiscover_data,
                                                                           )
        except AuthenticationError:
            self.is_working = False
            self.autodiscover_data = {}
            self._ews_account = None
            raise

        self.is_working = True
        self.autodiscover_data = autodiscover_data
        self.save()
        self._ews_account = account
        return account

    def __str__(self):
        if self.cached_name or self.cached_path:
            return str(_('{username} kalender {name}')).format(username=self.username, name=self.cached_name or self.cached_path)
        return str(_('{username} kalender'))

    class Meta:
        unique_together = ('endpoint', 'folder_id', 'username')
        verbose_name = _('kalenderkoppling')
        verbose_name_plural = _('kalenderkopplingar')


class CalendarItem(models.Model):
    """
    Keep track of calendar objects
    """

    credentials = models.ForeignKey(Credentials, on_delete=models.CASCADE)

    item_id = models.CharField(max_length=256)
    changekey = models.CharField(blank=True, max_length=256)

    ical_uid = models.CharField(max_length=256)
    calendar = models.ForeignKey(Calendar, null=True, on_delete=models.CASCADE)

    meeting = models.ForeignKey(Meeting, null=True, blank=True, on_delete=models.CASCADE)
    recurring_meeting = models.ForeignKey(RecurringMeeting, null=True, blank=True, on_delete=models.SET_NULL)

    def delete(self, using=None, keep_parents=False):
        if self.meeting and self.meeting.backend_active:
            self.meeting.deactivate()

        if self.meeting and not self.meeting.has_started:
            self.meeting.delete()

        return super().delete(using=using, keep_parents=keep_parents)

    def __str__(self):
        return '{} {} {}'.format(self.meeting.title if self.meeting_id else '', self.credentials, self.item_id[:20])

    class Meta:
        unique_together = ('credentials', 'item_id')

