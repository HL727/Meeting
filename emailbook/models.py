from django.db import models
from meeting.models import Meeting, RecurringMeeting
from customer.models import Customer
from django.urls import reverse
from django.conf import settings


API_DOMAIN = getattr(settings, 'API_DOMAIN', None) or settings.ALLOWED_HOSTS[0]


def new_secret_key(length=16):
    from random import choice

    chars = '1234567890qwertyuiopasdfghjklzxcvbnmQWERTYUIOPASDFGHJKLZXCVBNM'
    return ''.join(choice(chars) for i in list(range(length)))


class SenderLock(models.Model):

    sender = models.CharField(max_length=200, unique=True)


class EmailMeeting(models.Model):

    customer = models.ForeignKey(Customer, on_delete=models.CASCADE)
    sender = models.EmailField()
    meeting = models.ForeignKey(Meeting, on_delete=models.CASCADE)
    uid = models.TextField(blank=True)
    recurrence_id = models.TextField(blank=True)  # TODO remove after v2.10

    dialstring = models.CharField(max_length=500, blank=True)
    mode = models.CharField(max_length=100, blank=True)

    ts_received = models.DateTimeField(auto_now_add=True)
    ts_deleted = models.DateTimeField(null=True)

    secret_key = models.CharField(default=new_secret_key, max_length=16, unique=True, editable=False)
    recurring_meeting = models.ForeignKey(RecurringMeeting, null=True, blank=True, on_delete=models.SET_NULL)

    def get_unbook_url(self):
        return 'https://{}{}'.format(API_DOMAIN, reverse('emailbook_unbook', args=[self.secret_key]))


