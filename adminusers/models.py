from django.db import models
from django.utils.translation import ugettext_lazy as _
from django.contrib.auth.models import User
from django.urls import reverse


class AdminOrganization(models.Model):

    title = models.CharField(_('Namn'), max_length=50)

    admin_url = models.CharField(_('URL till adminbackend'), max_length=200)
    portal_url = models.CharField(_('URL till portal'), max_length=200)
    videocenter_url = models.CharField(_('URL till videocenter'), max_length=200)
    users = models.ManyToManyField(User, blank=True)

    def get_absolute_url(self):
        return reverse('adminusers_organization', args=[self.pk])

    def __str__(self):
        return self.title


class BackendAdministrator(models.Model):

    organization = models.ForeignKey(AdminOrganization, related_name='admin_users', on_delete=models.CASCADE)
    username = models.CharField(max_length=100)
    email = models.EmailField(max_length=100, blank=True)
    password = models.CharField(max_length=100, blank=True)

    handle_calls = models.BooleanField(default=False)
    handle_cospaces = models.BooleanField(default=False)
    handle_stats = models.BooleanField(default=False)
    confirmed = models.BooleanField(default=True)
    delete_requested = models.BooleanField(default=False)


class PortalAdministrator(models.Model):
    organization = models.ForeignKey(AdminOrganization, related_name='portal_users', on_delete=models.CASCADE)
    username = models.CharField(max_length=100)
    email = models.EmailField(max_length=100, blank=True)
    password = models.CharField(max_length=100, blank=True)


    confirmed = models.BooleanField(default=True)
    delete_requested = models.BooleanField(default=False)


class VideoCenterAdministrator(models.Model):
    organization = models.ForeignKey(AdminOrganization, related_name='videocenter_users', on_delete=models.CASCADE)
    username = models.CharField(max_length=100)
    email = models.EmailField(max_length=100, blank=True)
    password = models.CharField(max_length=100, blank=True)

    confirmed = models.BooleanField(default=True)
    delete_requested = models.BooleanField(default=False)
