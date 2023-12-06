import logging
import re
from datetime import date
import uuid
from typing import Tuple

from django.utils.translation import gettext_lazy as _

import sentry_sdk
from django.db import models
from django.utils.timezone import now

from customer.models import Customer
from provider.exceptions import NotFound
from policy_rule.consts import PEXIP_HELP_TEXTS, PEXIP_VERBOSE_NAMES
from policy_rule.fields import NullableRemoteObjectRelationField
from provider.models.provider import Cluster
from shared.utils import partial_update_or_create
from statistics.parser.utils import clean_target
from sentry_sdk import capture_message


logger = logging.getLogger(__name__)


class PolicyRuleManager(models.Manager):

    def sync_down(self, cluster):

        api = cluster.get_api(Customer.objects.first())
        api.get_related_policy_objects(force=True)
        rules = api.get_gateway_rules()

        exclude = {'creation_time', 'resource_uri'}
        valid_fields = {f.name for f in PolicyRule._meta.fields}

        new_objects = []
        valid_ids = set()

        for rule in rules:

            cur = {}
            for k, v in rule.items():
                if k not in valid_fields or k in exclude:
                    continue
                if isinstance(v, dict):
                    if v.get('id'):
                        v = v.get('id')

                if isinstance(v, str) and '/admin/' in v:
                    v = int(v.strip('/').split('/')[-1])  # load id
                cur[k] = v

            obj, created = self.sync_down_single(cluster, cur)

            if created:
                new_objects.append(obj)
            valid_ids.add(cur.get('id'))

        PolicyRule.objects\
            .filter(cluster=cluster, external_id__isnull=False)\
            .exclude(external_id__in=valid_ids)\
            .update(sync_back=False, external_id=None)

        return new_objects

    def sync_down_single(self, cluster, data):
        external_id = data.pop('id')

        obj = PolicyRule.objects.filter(cluster=cluster, external_id=external_id).first()
        if obj and not obj.sync_back:
            return None, False

        data['external_id'] = external_id
        data['last_external_sync'] = now()
        data['in_sync'] = True
        PolicyRule._global_sync = True
        try:
            obj, created = partial_update_or_create(PolicyRule, defaults=data,
                                                    cluster=cluster, external_id=external_id)
        finally:
            PolicyRule._global_sync = False

        return obj, created


class PolicyRule(models.Model):
    # Many help texts are in consts.py

    cluster = models.ForeignKey(Cluster, on_delete=models.CASCADE)

    enable = models.BooleanField(blank=True, default=True)
    is_fallback = models.BooleanField(blank=True, default=False,
                                      help_text='This is a fallback rule. These will always be placed last')

    name = models.CharField(max_length=250)
    tag = models.CharField(max_length=250, blank=True)
    description = models.CharField(max_length=250, blank=True)
    priority = models.IntegerField(default=10)

    match_incoming_calls = models.BooleanField(blank=True, default=False)
    match_outgoing_calls = models.BooleanField(blank=True, default=False)

    match_source_location = NullableRemoteObjectRelationField(_('system_location'))
    match_source_location_name = models.CharField(max_length=250, blank=True, editable=False)

    match_source_alias = models.CharField(max_length=250, blank=True)  # custom
    match_source_mode = models.CharField(max_length=250, default='AND', choices=[
        ('AND', 'AND'),
        ('OR', 'OR'),
    ])  # custom

    match_incoming_only_if_registered = models.BooleanField(blank=True, default=False)
    match_incoming_webrtc = models.BooleanField(blank=True, default=False)
    match_incoming_sip = models.BooleanField(blank=True, default=False)
    match_incoming_mssip = models.BooleanField(blank=True, default=False)
    match_incoming_h323 = models.BooleanField(blank=True, default=False)

    match_string_full = models.BooleanField(blank=True, default=False)
    match_string = models.CharField(max_length=250)
    replace_string = models.CharField(max_length=250, blank=True)

    call_type = models.CharField(max_length=250, default='auto', choices=[
        ("audio", 'Audio only'),
        ("video", _("Main video + presentation")),
        ("video-only", "Main video only"),
        ("auto", _("Same as incoming call")),
    ])

    max_callrate_in = models.PositiveIntegerField(null=True)
    max_callrate_out = models.PositiveIntegerField(null=True)

    max_pixels_per_second = models.CharField(max_length=250, null=True, choices=[(x, x) for x in [
        "sd",
        "hd",
        "fullhd"
      ]]
    )
    crypto_mode = models.CharField(max_length=250, blank=True, choices=[(x, x) for x in [
        "besteffort",
        "on",
        "off"
    ]])

    ivr_theme = NullableRemoteObjectRelationField(_('ivr_theme'))

    called_device_type = models.CharField(max_length=250, default='external', choices=[
        ('external', _('Registered device or external system')),
        ('registration', 'Registered devices only'),
        ('mssip_conference_id', _('Lync / Skype for Business meeting direct (Conference ID in dialed alias)')),
        ('mssip_server', _('Lync / Skype for Business clients, or meetings via a Virtual Reception')),
        ('gms_conference', _('Google Meet meeting')),
        ('teams_conference', _('Microsoft Teams meeting')),
        # ('teams_user', 'Microsoft Teams user'),  # removed from pexip?
    ]


    )
    outgoing_location = NullableRemoteObjectRelationField(_('system_location'))
    outgoing_protocol = models.CharField(max_length=250, default='sip', choices=[(x, x) for x in [
        "h323",
        "mssip",
        "sip",
        "rtmp",
        "gms",
        "teams"
    ]])

    sip_proxy = NullableRemoteObjectRelationField(_('sip_proxy'))
    teams_proxy = NullableRemoteObjectRelationField(_('teams_proxy'))
    gms_access_token = NullableRemoteObjectRelationField(_('gms_access_token'))
    h323_gatekeeper = NullableRemoteObjectRelationField(_('h323_gatekeeper'))
    mssip_proxy = NullableRemoteObjectRelationField(_('mssip_proxy'))
    stun_server = NullableRemoteObjectRelationField(_('stun_server'))
    turn_server = NullableRemoteObjectRelationField(_('turn_server'))

    external_participant_avatar_lookup = models.CharField(max_length=250, default='default',
                                                          choices=[(x, x) for x in [
                                                              "default",
                                                              "yes",
                                                              "no"
                                                          ]])

    treat_as_trusted = models.BooleanField(default=False)

    external_id = models.IntegerField(null=True, editable=False)
    sync_back = models.BooleanField(_('Sync back to Pexip'), help_text=_('This rule will be synced back to pexip.'), default=True, blank=True)
    in_sync = models.BooleanField(_('In sync'), default=False, editable=False)
    last_external_sync = models.DateTimeField(null=True, editable=False)

    objects = PolicyRuleManager()

    # new: enable_overlay_text: true|false = false
    # new: view: one_main_zero_pips|one_main_seven_pips|one_main_twentyone_pips|two_mains_twentyone_pips|four_mains_zero_pips = one_main_zero_pips

    _global_sync = False
    _sync = False

    class Meta:
        unique_together = ('cluster', 'external_id')
        ordering = ('priority',)

    def log_hit(self):
        if not PolicyRuleHitCount.objects.filter(date=date.today(), rule=self).update(count=models.F('count') + 1):
            PolicyRuleHitCount.objects.get_or_create(date=date.today(), rule=self, count=1)

    def serialize(self):
        sync_fields = {
            'enable',
            'name',
            'tag',
            'description',
            'priority',
            'match_incoming_calls',
            'match_outgoing_calls',
            'match_source_location',
            'match_incoming_only_if_registered',
            'match_incoming_webrtc',
            'match_incoming_sip',
            'match_incoming_mssip',
            'match_incoming_h323',
            'match_string_full',
            'match_string',
            'replace_string',
            'call_type',
            'max_callrate_in',
            'max_callrate_out',
            'max_pixels_per_second',
            'crypto_mode',
            'ivr_theme',
            'called_device_type',
            'outgoing_location',
            'outgoing_protocol',
            'sip_proxy',
            'teams_proxy',
            'gms_access_token',
            'h323_gatekeeper',
            'mssip_proxy',
            'stun_server',
            'turn_server',
            'external_participant_avatar_lookup',
            'treat_as_trusted',
        }
        data = {k: getattr(self, k) for k in sync_fields}

        for f in PolicyRule._meta.fields:
            if isinstance(f, NullableRemoteObjectRelationField) and data[f.name]:
                assert f.related_system_type
                data[f.name] = '/api/admin/configuration/v1/{}/{}/'.format(f.related_system_type, data[f.name])

        return data

    def sync_up(self, api=None):
        if not self.sync_back:
            raise ValueError('Rule should not be synced back')

        api = self.cluster.get_api(Customer.objects.first())
        data = self.serialize()

        try:
            if self.external_id:
                api.update_gateway_rule(self.external_id, data)
            else:
                new_id = api.create_gateway_rule(data)
                self.external_id = new_id
            self.in_sync = True
        except Exception:
            self.in_sync = False
            self.save(update_fields=['in_sync'])
            raise

        self.last_external_sync = now()
        self.save()

    def __str__(self):
        return self.name

    def delete(self, *args, **kwargs):
        if self.external_id and self.sync_back:
            api = self.cluster.get_api(Customer.objects.first())
            try:
                api.delete_gateway_rule(self.external_id)
            except NotFound:
                pass

        return super().delete(*args, **kwargs)

    def save(self, *args, **kwargs):
        result = super().save(*args, **kwargs)

        if not self.match_source_location:
            self.match_source_location_name = ''
        elif self.cluster.pexip.system_objects_data:
            locations = {loc['id']: loc.get('name')
                         for loc in self.cluster.pexip.system_objects_data.get('system_location', [])
                         if loc.get('id')}
            new_location_name = locations.get(self.match_source_location)
            if new_location_name:
                self.match_source_location_name = new_location_name

        if self.sync_back and not (self._sync or PolicyRule._global_sync):
            self._sync = True
            try:
                self.sync_up()
            finally:
                self._sync = False

        return result

    @property
    def remote_names(self):
        result = {}

        cluster_data = self.cluster.pexip.system_objects_data

        remote_key_overrides = {
            'match_source_location': 'system_location',
            'outgoing_location': 'system_location',
        }

        for local in (
            'ivr_theme',
            'outgoing_location',
            'sip_proxy',
            'teams_proxy',
            'match_source_location',
            'gms_access_token',
            'h323_gatekeeper',
            'mssip_proxy',
            'stun_server',
            'turn_server',
        ):
            remote_key = remote_key_overrides.get(local) or local

            local_id = getattr(self, local)
            if local_id:
                for item in cluster_data.get(remote_key, []):
                    if item['id'] == local_id:
                        result[local] = item['name']
                        break

            if not result.get(local):
                logger.warning(
                    'Missing remote name for %s %s in cluster %s (%s)',
                    local,
                    local_id,
                    self.cluster.pk,
                    self.cluster,
                )
        return result

    def get_response(self, params=None):
        return PolicyRuleResponse(self, params=params).response()


def set_pexip_help_texts():
    for f in PolicyRule._meta.fields:
        if f.name in PEXIP_HELP_TEXTS:
            f.help_text = PEXIP_HELP_TEXTS[f.name]
        if f.name in PEXIP_VERBOSE_NAMES:
            f.verbose_name = PEXIP_VERBOSE_NAMES[f.name]


set_pexip_help_texts()


def get_active_rule(cluster, **kwargs) -> PolicyRule:
    kwargs.pop('only_one', None)
    kwargs.pop('only_enabled', None)
    matches = get_matching_rules(cluster, only_enabled=True, only_one=True, **kwargs)
    return matches[0] if matches else None


def get_matching_rules(cluster, local_alias='', remote_alias='', call_direction='dial_in', protocol='sip',
                       is_registered='false', location='', only_enabled=True, only_one=False, **kwargs):

    if call_direction == 'non_dial':
        return []

    if call_direction not in ('dial_in', 'dial_out'):
        with sentry_sdk.push_scope() as scope:
            scope.set_context('params', locals())
            capture_message('Invalid call_direction')

    cluster_rules = PolicyRule.objects.filter(cluster=cluster)  # TODO cache

    result = []
    for rule in cluster_rules.order_by('priority', 'id'):

        is_match, reason = match_rule(rule, local_alias=local_alias, remote_alias=remote_alias,
                                      call_direction=call_direction, protocol=protocol,
                                      is_registered=is_registered, location=location)
        if is_match:
            result.append(rule)
            if only_one:
                return result

    return result


def match_rule(self: PolicyRule, local_alias='', remote_alias='', call_direction='dial_in', protocol='sip',
               is_registered='false', location='') -> Tuple[bool, str]:

    def _bool(s):
        if s in (True, 'true', 1, '1'):
            return True
        return False

    def _fail(reason: str):
        logger.debug(
            'Policy rule %s (%s) did not match call, reason: %s', self.pk, self.name, reason
        )
        return False, reason

    if not self.enable:
        return _fail('disabled')
    if call_direction == 'dial_in' and not self.match_incoming_calls:
        return _fail('incoming')
    if call_direction == 'dial_out' and not self.match_outgoing_calls:
        return _fail('outgoing')
    if self.match_incoming_only_if_registered and _bool(is_registered) != True:
        return _fail('registered')

    if protocol in ('api', 'webrtc', 'rtmp') and not self.match_incoming_webrtc:
        return _fail('protocol')
    if protocol == 'sip' and not self.match_incoming_sip:
        return _fail('protocol')
    if protocol == 'mssip' and not self.match_incoming_mssip:
        return _fail('protocol')
    if protocol == 'h323' and not self.match_incoming_h323:
        return _fail('protocol')

    # determinate alias directions
    destination = local_alias if call_direction == 'dial_in' else remote_alias
    source = local_alias if call_direction != 'dial_in' else remote_alias

    # strip prefix/suffix
    if not self.match_string_full:
        destination = clean_target(destination)
    source = clean_target(source)

    # source match
    pass_match_source_alias = pass_match_source_location = True
    if self.match_source_location and location != self.match_source_location_name:
        pass_match_source_location = False
    if self.match_source_alias and not re.match(self.match_source_alias, source, re.IGNORECASE):
        pass_match_source_alias = False

    if not (pass_match_source_location and pass_match_source_alias):
        if self.match_source_mode == 'AND':
            return _fail('source')

    # destination match
    if not re.match(self.match_string, destination, re.IGNORECASE):
        return _fail('destination')

    logger.info('Policy rule %s (%s) matched call', self.pk, self.name)
    return True, ''


class PolicyRuleResponse:
    def __init__(self, rule, params=None):
        self.rule = rule
        self.params = params or {}

    def response(self):
        result = {
            'name': '{}:{}'.format(self.rule.name, uuid.uuid4()),
            'service_tag': self.rule.tag or '',
            'description': self.rule.description,
            'service_type': 'gateway',
            **self.alias_overrides(),
            **self.response_overrides(),
            **self.outgoing_overrides(),
            **self.protocol_specific_overrides(),
        }
        return result

    def alias_overrides(self):
        if not self.params:
            return {}

        params = self.params
        call_direction = self.params.get('call_direction')

        def _replace(url):
            if not self.rule.replace_string:
                return url

            if not self.rule.match_string_full:
                url = clean_target(url)

            try:
                return re.sub(r'^' + self.rule.match_string, self.rule.replace_string, url)
            except ValueError as e:
                logger.warning('Invalid regexp %s', e)  # TODO debug log

        if call_direction == 'dial_in':
            return {
                'local_alias': params.get('remote_alias', ''),
                'local_display_name': params.get('remote_display_name', ''),
                'remote_alias': _replace(params.get('local_alias')),
            }
        elif call_direction == 'dial_out':
            return {
                'local_alias': params.get('local_alias', ''),
                'remote_alias': _replace(params.get('remote_alias')),
            }
        return {}

    def response_overrides(self):
        rule = self.rule

        result = {}
        if rule.call_type:
            result['call_type'] = rule.call_type
        if rule.max_callrate_in:
            result['max_callrate_in'] = rule.max_callrate_in
        if rule.max_callrate_out:
            result['max_callrate_out'] = rule.max_callrate_out
        if rule.max_pixels_per_second:
            result['max_pixels_per_second'] = rule.max_pixels_per_second
        if rule.crypto_mode:
            result['crypto_mode'] = rule.crypto_mode
        if rule.ivr_theme:
            result['ivr_theme'] = '/admin/configuration/v1/ivr_theme/{}/'.format(rule.ivr_theme)

        return result

    def outgoing_overrides(self):

        rule = self.rule
        result = {}

        if rule.outgoing_protocol:
            result['outgoing_protocol'] = rule.outgoing_protocol

        if rule.outgoing_protocol == 'rtmp':
            result['called_device_type'] = 'external'
        elif rule.called_device_type:
            result['called_device_type'] = rule.called_device_type

        if rule.ivr_theme:
            result['ivr_theme_name'] = rule.remote_names['ivr_theme']

        if rule.outgoing_location:
            result['outgoing_location_name'] = rule.remote_names['outgoing_location']

        if rule.treat_as_trusted:
            result['treat_as_trusted'] = True

        return result

    def protocol_specific_overrides(self):

        rule = self.rule
        result = {}

        if rule.outgoing_protocol in ('sip',):
            if rule.sip_proxy:
                result['sip_proxy_name'] = rule.remote_names['sip_proxy']

        if rule.outgoing_protocol in ('msteams',):
            if rule.teams_proxy:
                result['teams_proxy_name'] = rule.remote_names['teams_proxy']
            if rule.external_participant_avatar_lookup:
                result['external_participant_avatar_lookup'] = rule.remote_names['external_participant_avatar_lookup']

        if rule.outgoing_protocol in ('gms', 'mssip'):
            if rule.turn_server:
                result['turn_server_name'] = rule.remote_names['turn_server']
            if rule.stun_server:
                result['stun_server_name'] = rule.remote_names['stun_server']

        if rule.outgoing_protocol in ('gms',):
            if rule.gms_access_token:
                result['gms_access_token_name'] = rule.remote_names['gms_access_token']

        if rule.outgoing_protocol in ('mssip',):
            if rule.mssip_proxy:
                result['mssip_proxy_name'] = rule.remote_names['mssip_proxy']

        if rule.outgoing_protocol in ('h323',):
            if rule.h323_gatekeeper:
                result['h323_gatekeeper_name'] = rule.remote_names['h323_gatekeeper']

        return result


class PolicyRuleHitCount(models.Model):

    rule = models.ForeignKey(PolicyRule, on_delete=models.CASCADE)
    date = models.DateField(default=date.today)
    count = models.IntegerField(default=1)
