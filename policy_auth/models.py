import hashlib
import json
import re

from django.conf import settings
from django.db import models, transaction
from django.utils.translation import gettext_lazy as _

# Create your models here.
from django.utils.timezone import now
from jsonfield import JSONField

from customer.models import Customer, validate_regexp, CustomerMatch
from statistics.parser.utils import clean_target


class PolicyAuthorizationOverrideManager(models.Manager):
    def match(self, customer, params, cluster=None):

        customer = customer or CustomerMatch.objects.match(params, cluster=cluster)
        if not customer:
            return

        for wl in PolicyAuthorizationOverrideManager.customer_overrides(customer.pk, cluster.pk if cluster else None):
            if wl.match(params):
                return wl
        return None

    @staticmethod
    def customer_overrides(customer_id, cluster_id):
        objects = PolicyAuthorizationOverride.objects.filter(customer=customer_id)
        if cluster_id:
            objects = objects.filter(cluster=cluster_id)
        return list(objects)


class PolicyAuthorizationOverride(models.Model):

    customer = models.ForeignKey(Customer, on_delete=models.CASCADE)
    cluster = models.ForeignKey('provider.Cluster', on_delete=models.CASCADE)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, editable=False, null=True)

    match_location_name = models.CharField(_('Matcha endast samtal i denna location'), max_length=255, blank=True)

    match_incoming_sip = models.BooleanField(_('Matcha inkommande SIP-samtal'), default=True, blank=True)
    match_incoming_h323 = models.BooleanField(_('Matcha inkommande H323'), default=True, blank=True)
    match_incoming_skype = models.BooleanField(_('Matcha inkommande Skype-samtal'), default=True, blank=True)
    match_incoming_webrtc = models.BooleanField(_('Matcha inkommande WebRTC-samtal'), default=False, blank=True,
                                                help_text=_('Notera att denna är enkelt att skriva fake-värden, så använd i kombination med location'))

    local_alias_match = models.CharField(_('Alias regexp-matchning'), max_length=500, blank=True, validators=[validate_regexp],
                                    help_text=_('Matchar från start (implicit ^)'))
    remote_list = models.TextField(_('Lista med godkända adresser'), help_text=_('Ett inlägg per rad. Rader som börjar med { tolkas som JSON där samtliga key/values matchas. '
                                                                          'Ex {"remote_alias": "test@example.org", "registered": "True"}'
                                                                          'Använd / i början av slut för regexp, ex. /123.*example.org/'))
    settings_override = JSONField(_('Override för rumsinställningar'), blank=True, help_text=_('Ändra inställningar för videomöte som matchar denna inloggning, ex. moderator-status'))

    objects = PolicyAuthorizationOverrideManager()

    class Meta:
        verbose_name = _('förutbestämd inloggning')
        verbose_name_plural = _('förutbestämda inloggningar')

    @property
    def match_objects(self):
        for l in self.remote_list.split('\n'):
            if not l.strip():
                continue
            if l.startswith('{'):
                try:
                    yield json.loads(l)
                    continue
                except ValueError:
                    pass
            yield {'remote_alias': l.strip()}

    def _get_valid_protocols(self, params):
        valid_protocols = set()
        if self.match_incoming_sip:
            valid_protocols.add('SIP')
        if self.match_incoming_h323:
            valid_protocols.add('H323')
        if self.match_incoming_skype:
            valid_protocols.add('LYNC')
            valid_protocols.add('MSSIP')
        if self.match_incoming_webrtc:
            valid_protocols.add('WEBRTC')
            valid_protocols.add('API')
            valid_protocols.add('RTMP')
        return valid_protocols

    def match(self, params):
        protocol = (params.get('protocol') or '').upper()
        valid_protocols = self._get_valid_protocols(params)

        if self.match_location_name and self.match_location_name != params.get('location'):
            return

        if self.local_alias_match and not any(
            [
                re.match(self.local_alias_match, params.get('local_alias', '')),
                re.match(self.local_alias_match, clean_target(params.get('local_alias', ''))),
            ]
        ):
            return

        if protocol not in valid_protocols:
            return

        for obj in self.match_objects:
            for k, required_value in obj.items():
                if k == 'md5()':
                    if not isinstance(required_value, dict):
                        break
                    if md5_match(params, required_value['fields'], required_value['hash']):
                        continue
                    break

                if k.endswith('_alias') and params.get(k) != required_value:
                    if required_value == clean_target(params.get(k)):
                        continue

                if params.get(k) != required_value:
                    regexp_match, new_value = match_regexp(required_value, params.get(k))
                    if not regexp_match:
                        break
                    if new_value != params.get(k):
                        params[k] = new_value
            else:
                return self, obj

    def __str__(self):
        return self.local_alias_match


def md5_match(obj, fields, hash):
    """
    match concatenated values in `obj` for keys `fields` against md5 hash, e.g. for sensitive data
    """

    result = []
    for f in fields:
        v = obj.get(f, '')
        if isinstance(v, bool):
            result.append(str(v).lower())
        else:
            result.append(str(v))

    return hashlib.md5(''.join(result).encode('utf-8')).hexdigest() == hash


def match_regexp(maybe_regex, target):
    """
    match against regexp
    variants:
    /.*@example.org/  # match
    /(.*)@example.org/\1@other.com/  # sub
    /(.*)@example.org/\1@other.com/.*@other.com/  # sub + final match of new value
    /(.*)@example.org/\1@other.com/\d+@other.com/  # sub + final match of new value
    """  # noqa
    if not (isinstance(target, str) and maybe_regex != '/' and maybe_regex.startswith('/') and maybe_regex.endswith('/')):
        return False, target

    sub = final_match = None
    parts = re.split(r'(?<!\\)/', maybe_regex[1:-1])

    if len(parts) >= 2 and parts[1]:
        sub = parts[1]
    if len(parts) >= 3 and parts[2]:
        final_match = parts[2]

    try:
        r = re.compile(parts[0], re.IGNORECASE)
        final_match = final_match and re.compile(final_match)

        if not sub:
            if final_match:
                return bool(r.match(target) and final_match.match(target)), target
            return bool(r.match(target)), target

        new_target = r.sub(sub, target)  # sub
        if not final_match:
            return True, new_target

        if final_match.match(new_target):
            return True, new_target
        return False, target

    except ValueError:
        if settings.TEST_MODE or settings.DEBUG:
            raise
        return False, target


class PolicyAuthorizationManager(models.Manager):

    def match(self, customer, params, cluster=None, ts=None):
        alias = params.get('local_alias')
        customer = customer or CustomerMatch.objects.get_customer(params, cluster=cluster)
        if not customer:
            return

        ts = ts or now()
        for pa in PolicyAuthorization.objects.filter(customer=customer, local_alias=alias, valid_from__lte=ts, valid_to__gte=ts):
            if pa.match(params):
                if pa.usage_limit and pa.usage_count and pa.usage_count >= pa.usage_limit:
                    continue
                return pa
        return None


class PolicyAuthorization(models.Model):

    customer = models.ForeignKey(Customer, on_delete=models.CASCADE)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, editable=False)
    cluster = models.ForeignKey('provider.Cluster', on_delete=models.CASCADE)

    created = models.DateTimeField(default=now, editable=False)

    source = models.CharField(
        _('System'),
        max_length=500,
        blank=True,
        help_text=_('Valfritt fält för att kunna spåra vilket system som skapade en post'),
    )
    external_id = models.CharField(
        _('External ID'),
        max_length=500,
        blank=True,
        null=True,
        help_text=_('Valfritt fält för att kunna spåra externt id'),
    )

    local_alias = models.CharField(max_length=500, db_index=True, help_text=_('Fullständigt alias, måste vara identiskt med vad som policy-server rapporterar'))

    valid_from = models.DateTimeField(default=now, blank=True, null=True)
    valid_to = models.DateTimeField()

    require_fields = JSONField(blank=True, help_text='Matchar fält från policy-server mot dessa. Ex: {"remote_display_name": "Test"}')
    settings_override = JSONField(blank=True, help_text=_('Ändra inställningar för videomöte som matchar denna inloggning, ex. moderator-status'))

    usage_limit = models.SmallIntegerField(null=True, blank=True)
    usage_count = models.SmallIntegerField(null=True, blank=True)
    first_use = models.DateTimeField(null=True, editable=False, help_text=_('Tid när den här inloggningen användes skarpt av systemet av policy-server'))

    objects = PolicyAuthorizationManager()

    def __str__(self):
        return self.local_alias

    class Meta:
        index_together = (
            ('valid_from', 'valid_to'),
        )
        verbose_name = _('tidsbegränsad inloggning')
        verbose_name_plural = _('tidsbegränsade inloggningar')

    def use(self):
        with transaction.atomic():
            p = PolicyAuthorization.objects.get(pk=self.pk)
            p.usage_count = (p.usage_count or 0) + 1
            if not p.usage_count:
                p.usage_count = 1
                p.first_use = now()
                p.save(update_fields=['usage_count', 'first_use'])
            else:
                p.usage_count += 1
                p.save(update_fields=['usage_count'])
        self.usage_count, self.first_use = p.usage_count, p.first_use

    def check_active(self, ts=None):
        return self.valid_from <= (ts or now()) <= self.valid_to

    @property
    def is_active(self):
        return bool(self.check_active())

    def match(self, params):
        for k, require_value in (self.require_fields or {}).items():
            if k == 'md5()':
                if not isinstance(require_value, dict):
                    break
                if md5_match(params, require_value['fields'], require_value['hash']):
                    continue
                break
            if params.get(k) != require_value:

                if k.endswith('_alias') and require_value == clean_target(params.get(k)):
                    continue

                matched, new_value = match_regexp(require_value, params.get(k))
                if not matched:
                    matched, new_value = match_regexp(require_value, clean_target(params.get(k)))
                    if not matched:
                        break

                if params.get(k) != new_value:
                    params[k] = new_value
        else:
            return self
