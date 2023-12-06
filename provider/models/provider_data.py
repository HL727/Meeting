from django.db import models
from django.utils.timezone import now

from provider.models.provider import Provider
from meeting.models import Meeting
import jsonfield


class ClearSeaAccount(models.Model):

    provider = models.ForeignKey(Provider, on_delete=models.CASCADE)
    meeting = models.ForeignKey(Meeting, on_delete=models.CASCADE)
    backend_active = models.BooleanField(default=False)
    username_index = models.IntegerField(default=0)
    saved_username = models.CharField(max_length=100)
    user_active_until = models.DateTimeField(null=True, blank=True)
    extension = models.CharField(max_length=20, blank=True)

    @property
    def username(self):

        if self.saved_username:
            return self.saved_username

        username = '%s_%s' % (self.meeting.customer.username_prefix or 'user', self.meeting.provider_ref)

        if self.username_index > 0:
            return '%s_%s' % (username, self.username_index)

        return username

    @property
    def dialstring(self):
        return '%s##%s' % (self.provider.ip, self.extension)

    def increase_index(self):
        if self.username_index >= 10:
            return False

        self.saved_username = ''
        self.username_index += 1
        self.save()

        return True

    def activate(self):
        self.backend_active = True
        self.save()

    def deactivate(self):
        self.backend_active = False
        self.save()

    class Meta:
        unique_together = ('provider', 'meeting')

    def get_absolute_url(self):
        return 'http://%s/%s' % (self.provider.hostname, self.username)

    def __str__(self):
        return 'Clearsea user %s' % self.username


class ProviderLoad(models.Model):

    provider = models.ForeignKey(Provider, null=False, on_delete=models.CASCADE)
    ts_created = models.DateTimeField(default=now, db_index=True)
    load = models.IntegerField()
    participant_count = models.IntegerField(default=0)
    bandwidth_in = models.IntegerField(default=0)
    bandwidth_out = models.IntegerField(default=0)


class SettingsProfileManager(models.Manager):

    def get_for(self, provider, target_type, target_id, type, parent=None):

        def _new():
            return SettingsProfile(provider=provider, target_type=target_type, target_id=target_id or None, profile_type=type, parent=parent)

        if not target_id:
            return _new()

        try:
            profile = SettingsProfile.objects.get(provider=provider, target_type=target_type, target_id=target_id or None, profile_type=type)
            if profile and profile.parent_id != parent.id if parent else None:
                profile.parent = parent
                profile.save()
            return profile
        except SettingsProfile.DoesNotExist:
            return _new()

    def add_settings(self, target_type, target_id, profile_type, settings, name='', priority=0):

        profile, created = SettingsProfile.objects.get_or_create(
            target_type=target_type, target_id=target_id, profile_type=profile_type)

        profile.add_settings(settings, name, priority=priority)


class SettingsProfile(models.Model):

    provider = models.ForeignKey(Provider, on_delete=models.CASCADE)

    target_type = models.CharField(max_length=100)
    target_id = models.CharField(max_length=100, null=True)

    profile_type = models.CharField(max_length=100)
    profile_id = models.CharField(max_length=100)

    extends_profile_id = models.CharField(max_length=100, null=True, blank=True)

    ts_created = models.DateTimeField(auto_now_add=True)

    parent = models.ForeignKey('self', null=True, blank=True, on_delete=models.CASCADE)

    result = jsonfield.JSONField()

    objects = SettingsProfileManager()

    _save_hook = None
    _remove_hook = None
    _extend_hook = None

    def register_hooks(self, create_fn, remove_fn=None, extend_fn=None):
        self._save_hook = create_fn
        self._remove_hook = remove_fn
        self._extend_hook = extend_fn

    def commit(self):
        if not self.result:
            if self.profile_id and self._remove_hook:
                self._remove_hook(self)
            return self.extends_profile_id
        if self._extend_hook:
            self._extend_hook(self)
        if self._save_hook:
            self._save_hook(self)
        return self.profile_id

    def extend(self, profile_id):
        self.extends_profile_id = profile_id or ''
        if self._extend_hook and self.result:
            self._extend_hook(self)
        self.save()

    def delete(self, *args, **kwargs):
        if self._remove_hook and self.profile_id:
            self._remove_hook(self)
        if self.id:
            super().delete(*args, **kwargs)

    def update_target_id(self, target_id):
        if target_id == self.target_id:
            return self

        existing = SettingsProfile.objects.get_for(self.provider, self.target_type, target_id, self.profile_type, parent=self.parent)
        if existing.pk:
            SettingsNode.objects.filter(profile=self).update(profile=existing)
            self.delete()
            return existing

        self.target_id = target_id
        self.save()
        return self

    def toggle_settings(self, name, enable, settings):
        if enable:
            self.add_settings(name, settings)
        else:
            self.pop_settings(name)

    def add_settings(self, name, settings, priority=0):

        if not self.pk:
            if self.parent and not self.parent.result:
                if not self.parent.pk:
                    self.parent = None
            self.save()

        node, created = SettingsNode.objects.update_or_create(
            profile=self, name=name, defaults={'settings': settings, 'priority': priority})

        self.result = self.get_results()
        self.save()

    def pop_settings(self, name=''):
        if not self.pk:
            return

        SettingsNode.objects.filter(profile=self, name=name).delete()

        self.result = self.get_results()
        self.save()

    def get_results(self):

        result = {}

        other_than_extend = False

        for node in SettingsNode.objects.filter(profile=self).order_by('-priority', 'ts_created'):
            for key, value in node.settings.items():

                if value is None:
                    result.pop(key, None)
                    continue

                if node.name != 'parent_profile':
                    other_than_extend = True

                result[key] = value

        if not other_than_extend and self.extends_profile_id:
            result = {}

        return result

    class Meta:
        unique_together = ('provider', 'target_type', 'target_id', 'profile_type')


class SettingsNode(models.Model):

    profile = models.ForeignKey(SettingsProfile, on_delete=models.CASCADE)

    name = models.CharField(max_length=100)
    settings = jsonfield.JSONField()

    priority = models.SmallIntegerField(default=10)
    ts_created = models.DateTimeField(auto_now_add=True)
