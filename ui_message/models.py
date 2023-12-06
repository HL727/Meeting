from django.core.validators import FileExtensionValidator
from django.db import models
from django.utils.timezone import localtime, localdate
from django.utils.translation import ugettext_lazy as _
from descriptive_choices import DescriptiveChoices
from django.urls import reverse

import reversion
import uuid
from customer.models import Customer
import re
from django.conf import settings
from xml.sax.saxutils import escape

from . import message_types

ENABLE_LIFESIZE_MESSAGES = getattr(settings, 'ENABLE_LIFESIZE_MESSAGES', False)


class MessageManager(models.Manager):

    def get_active(self, type, customer):
        msg = Message.objects.filter(customer=customer, type=type, active=True).first()
        if msg and not msg.extend_other:
            return msg, type

        if msg and msg.extend_other:
            type = msg.extend_other
        return None, type

    def get_by_type(self, type, customer):
        """
        returns:
        1. active message for customer with type.
        2. if message has extend_other: active message for customer with type <extend_other>.
        3. active default message with type
        4. if default message has extend other: default message with type <default.extend_other>
        """

        cur_type = type
        for _i in range(5):

            msg, new_type = self.get_active(cur_type, customer)
            if msg:
                return msg

            if cur_type == new_type:
                break
            cur_type = new_type

        def _freeze(m: Message):
            if customer and not m.customer:
                m.save = None  # should never be modified
            return m

        return _freeze(self.get_default(type))

    def get_default(self, type):
        cur_type = type
        for _i in range(5):
            default_msg, new_type = self.get_active(cur_type, None)
            if default_msg:
                return default_msg

            if cur_type == new_type:
                break
            cur_type = new_type

        # not existing. create empty default message
        return Message.objects.get_or_create(
            customer=None,
            type=cur_type,
        )[0]

    def get_welcome(self, customer=None):

        return self.get_by_type(Message.TYPES.outlook_welcome, customer)

    def get_moderator_message(self, type_name, customer=None):

        moderator_type_name = '{}_moderator'.format(type_name)
        try:
            type = getattr(Message.TYPES, moderator_type_name)
        except AttributeError:
            try:
                type = getattr(Message.TYPES, type_name)
            except AttributeError:
                if 'clearsea_meeting_pin' not in type_name:
                    return self.get_moderator_message('clearsea_meeting_pin', customer=customer)
                return Message()

        result = self.get_by_type(type, customer)
        if not result.active:
            return self.get_by_type(type, None)
        return result

    def get_for_meeting(self, meeting, message_type=None) -> 'Message':

        types = Message.TYPES
        customer = meeting.customer

        if message_type is None:
            message_type = meeting.meeting_type

        def _get(type, customer):
            if meeting.is_moderator:
                return self.get_moderator_message(Message.TYPES.key_map[type], customer)

            result = self.get_by_type(type, customer)
            if not result.active:
                return self.get_by_type(type, None)
            return result

        if message_type and getattr(Message.TYPES, message_type, None):
            return _get(getattr(Message.TYPES, message_type), customer)

        if meeting.is_internal_meeting and not (meeting.provider and meeting.provider.is_acano) and ENABLE_LIFESIZE_MESSAGES:  # internal meeting
            if meeting.password:
                return _get(types.lifesize_meeting_pin, customer)
            if meeting.internal_clients > 2 or meeting.provider.is_acano:
                return _get(types.lifesize_multipart, customer)
            return _get(types.lifesize_meeting, customer)
        else:  # external participants/allow clearsea
            if meeting.is_webinar:
                return _get(types.webinar, customer)
            else:
                if meeting.get_connection_data('password'):
                    return _get(types.clearsea_meeting_pin, customer)
                return _get(types.clearsea_meeting, customer)

    def get_for_cospace(
        self, customer, cospace_id, message_type='acano_cospace', is_moderator=False
    ):

        from supporthelpers.forms import CoSpaceForm

        meeting = CoSpaceForm(cospace=cospace_id).get_temp_meeting(
            customer, is_moderator=is_moderator
        )

        message = Message.objects.get_by_type(
            type=getattr(Message.TYPES, message_type), customer=customer
        )
        if not message.active:
            message = Message.objects.get_by_type(type=getattr(Message.TYPES, message_type), customer=None)

        return message.to_dict(meeting)

    def get_plain_message(self, html_content):
        from html import unescape

        invite_plain = re.sub(r'<a href="(https://.*?)">https://[^<]+</a>', r'\1', html_content)  # fix for encoded urls. linked urls are probably the same
        invite_plain = re.sub(r'<a href="(.*?)">\1</a>', r'\1', invite_plain)
        invite_plain = re.sub(r'<a href="(.*?)">(.*?)</a>', r'\2 [ \1 ]', invite_plain)
        invite_plain = re.sub(r'</p>', '\n', invite_plain)
        invite_plain = re.sub(r'<br ?/?>', '\n', invite_plain)
        invite_plain = re.sub(r'<.*?>', '', invite_plain)
        invite_plain = re.sub(r'\n\n\n+', '\n\n', invite_plain)

        invite_plain = unescape(invite_plain)

        return invite_plain.strip()

    def get_all(self, customer=None):

        messages = {m.type: m for m in Message.objects.filter(customer=customer).order_by('ts_updated')}
        default = {m.type: m for m in Message.objects.filter(customer=None).order_by('ts_updated')}

        if not customer:
            has_lifesize = ENABLE_LIFESIZE_MESSAGES
        else:
            provider = customer.get_provider()
            has_lifesize = provider and provider.is_lifesize

        result = []
        for id, _desc in Message.ENABLED_TYPES:
            if id not in messages:
                try:
                    default_content = default[id].content
                    default_title = default[id].title
                    default_extend_other = default[id].extend_other
                except KeyError:
                    default_content = ''
                    default_title = ''
                    default_extend_other = None
                messages[id] = Message.objects.get_or_create(
                    type=id,
                    customer=customer,
                    defaults=dict(
                        content=default_content,
                        title=default_title,
                        active=not customer,
                        extend_other=default_extend_other,
                    ),
                )[0]

            if not has_lifesize and ENABLE_LIFESIZE_MESSAGES and id in (
                Message.TYPES.lifesize_meeting,
                Message.TYPES.lifesize_meeting_pin,
                Message.TYPES.lifesize_multipart,
                ):
                    pass  # FIXME, always use multipart?
                    # continue
            result.append(messages[id])
        return result

    def init_default(self):
        from .initial import INITIAL_MESSAGES, MessageTuple

        sandbox_message_content = '<br />\n'.join(
            '{} = {}'.format(p.rstrip('{}'), p) for p in Message.get_placeholder_names()
        )

        def _iter_message_customers():
            customers = [None]
            if Customer.objects.count() == 1:
                customers.append(Customer.objects.first())

            for m in INITIAL_MESSAGES:
                for customer in customers:
                    if m.name == 'sandbox':
                        yield MessageTuple('sandbox', {**m.value, 'content': sandbox_message_content}), customer
                        continue

                    yield m, customer

        result = []
        for initial, customer in _iter_message_customers():
            try:
                message_type = getattr(Message.TYPES, initial.name)
            except AttributeError:  # disabled
                continue

            m, created = Message.objects.get_or_create(type=message_type, customer=customer, defaults=dict(
                title=initial.value['title'],
                content=initial.value['content'],
            ))
            changed = created

            if not m.content:
                m.content = initial.value['content']
                changed = True
            if not m.title:
                m.title = initial.value['title']
                changed = True

            if changed and not created:
                m.save()

            result.append([m, changed])
        return result


@reversion.register
class Message(models.Model):

    # type definitions:
    ENABLED_TYPES = message_types.ENABLED_TYPES
    TYPES = message_types.TYPES
    PLAIN_TEXT_TYPES = message_types.PLAIN_TEXT_TYPES
    PUBLIC_URL_TYPES = message_types.PUBLIC_URL_TYPES
    ATTACHMENT_TYPES = message_types.ATTACHMENT_TYPES

    # fields:
    title = models.CharField(max_length=250, blank=True)
    type = models.IntegerField(choices=TYPES)
    content = models.TextField()
    customer = models.ForeignKey(Customer, blank=True, null=True, on_delete=models.CASCADE)
    active = models.BooleanField(default=True)

    extend_other = models.IntegerField(choices=TYPES, null=True, blank=True)

    attachment = models.FileField(
        verbose_name=_('Bifoga användarmanual/andra instruktioner'),
        upload_to='attachments',
        blank=True,
        null=True,
        validators=[
            FileExtensionValidator(
                allowed_extensions=['pdf', 'doc', 'docx', 'html', 'odt', 'odp', 'ppt']
            )
        ],
        help_text=str(_('Max 5 MB, filformat %s')).format(
            ', '.join(['pdf', 'doc', 'docx', 'html', 'odt', 'odp', 'ppt'])
        ),
    )

    type_title = TYPES.title_for('type')
    type_key = TYPES.key_for('type')
    type_description = TYPES.info_for('type')

    secret_key = models.CharField(max_length=255, default=uuid.uuid4)

    ts_created = models.DateTimeField(auto_now_add=True)
    ts_updated = models.DateTimeField(auto_now=True)

    objects: MessageManager['Message'] = MessageManager()

    class Meta:
        unique_together = ('customer', 'type')

    @staticmethod
    def get_placeholder_names():
        placeholders = [
            'room_number',
            'pin',
            'dialstring',
            'sip',
            'sip_numeric',
            'phone_ivr',
            'is_moderator',
            'owner',
            'owner_name',
            'owner_email',
            'deskop_url',
            'deskop_link',
            'web_url',
            'web_link',
            'title',
            'logo',
            'internal_number',
            'date_start',
            'date_stop',
            'time_start',
            'time_stop',
            'customer',
            ]

        if ENABLE_LIFESIZE_MESSAGES:
            placeholders += [
                'lifesize_dialstring',
                'lifesize_ip',
                'clearsea_username',
                'clearsea_url',
                'clearsea_link',
                'clearsea_dialstring',
                'clearsea_sip',
                'clearsea_ip',
                'clearsea_extension',
            ]
        return ['{%s}' % s for s in placeholders]

    def get_placeholders(self, meeting):

        join_url = meeting.join_url

        logo_url = meeting.customer.logo_url or settings.DEFAULT_MESSAGE_LOGO

        data = {
            'room_number': meeting.get_connection_data('provider_ref'),
            'password': meeting.get_connection_data('password'),
            'pin': meeting.get_connection_data('password'),
            'lifesize_dialstring': meeting.dialstring,
            'lifesize_ip': meeting.provider.ip,
            'dialstring': meeting.dialstring,
            'sip': meeting.sip_uri,
            'sip_numeric': meeting.sip_uri_numeric,
            'phone_ivr': meeting.provider.get_cluster_settings().get_phone_ivr() or meeting.provider.phone_ivr,
            'is_moderator': str(_('moderator')) if meeting.is_moderator else '',
            'owner': meeting.creator,
            'owner_name': meeting.creator_name,
            'owner_email': meeting.creator_email,
            'customer': str(meeting.customer),
            'acano_url': '',
            'acano_link': '',
            'cma_desktop_url': '',
            'cma_desktop_link': '',
            'desktop_url': '',
            'desktop_link': '',
            'title': meeting.title,
            'date_start': localdate(meeting.ts_start),
            'date_stop': localdate(meeting.ts_stop),
            'time_start': localtime(meeting.ts_start).strftime('%H:%M'),
            'time_stop': localtime(meeting.ts_stop).strftime('%H:%M'),
            'internal_number': '',
            'clearsea_username': '',
            'clearsea_url': '',
            'clearsea_link': '',
            'clearsea_dialstring': '',
            'clearsea_sip': '',
            'clearsea_ip': '',
            'clearsea_extension': '',
            'web_url': join_url,
            'web_link': '',
            'logo': '',
            'logo_url': logo_url,
        }
        if join_url:
            data['web_link'] = '<a href="{}">{}</a>'.format(escape(join_url), join_url)
        if logo_url:
            data['logo'] = '<img src="{}" alt="{}" />'.format(
                escape(logo_url), escape(str(meeting.customer) if meeting.customer.logo_url else '')
            )

        if Customer.objects.all().count() > 1:
            data['customer_logo_url'] = meeting.customer.logo_url

        for start, stop in settings.INTERNAL_NUMBER_SERIES:
            if int(meeting.provider_ref) >= start and int(meeting.provider_ref) <= stop:
                data['internal_number'] = meeting.provider_ref
                break

        external = meeting.get_external_account()

        if external:
            external_link = '<a href="%s">%s</a>' % (escape(external.get_absolute_url()), external.get_absolute_url())
            external_sip = '%s@%s' % (external.username, external.provider.internal_domain)

            data.update({
                'clearsea_username': external.username,
                'clearsea_url': external.get_absolute_url(),
                'clearsea_link': external_link,
                'clearsea_dialstring': external.dialstring,
                'clearsea_sip': external_sip,
                'clearsea_ip': external.provider.ip,
                'clearsea_extension': external.extension,
            })

            if meeting.provider.is_acano:  # FIXME remove when acano has support
                data['dialstring'] = external.dialstring

        if meeting.provider.is_acano:

            desktop_url = meeting.join_url.replace('https://', 'ciscomeeting://')

            data.update(
                {
                    'acano_url': join_url,
                    'acano_link': '<a href="%s">%s</a>' % (escape(join_url), join_url),
                    'cma_desktop_link': '<a href="%s">%s</a>' % (escape(desktop_url), desktop_url),
                    'cma_desktop_url': desktop_url,
                    'desktop_link': '<a href="%s">%s</a>' % (escape(desktop_url), desktop_url),
                    'desktop_url': desktop_url,
                }
            )
        elif meeting.provider.is_pexip:
            desktop_url = 'pexip://{}?pin={}'.format(meeting.dialstring, meeting.password)
            data.update(
                {
                    'desktop_url': desktop_url,
                    'desktop_link': '<a href="%s">%s</a>' % (escape(desktop_url), desktop_url),
                }
            )

        return data

    def format(self, meeting, content=None):
        if content is None:
            content = self.content

        data = self.get_placeholders(meeting)

        content = self.expand_conditionals(content, data)

        for k, v in list(data.items()):
            content = content.replace('{%s}' % k, str(v))

        return content

    def to_dict(self, meeting):

        content = self.format(meeting)

        return {
            'title': self.format_title(meeting),
            'content': content,
            'attachment': self.attachment if self.attachment else None,
            'plain': Message.objects.get_plain_message(content),
        }

    def expand_conditionals(self, content, data):
        pattern = r"\{if (not )?(\w+)\}(.*?)\{endif\}"

        def replace(match):
            is_negative = bool(match.group(1))
            key_name = match.group(2)
            is_key_truthy = bool(data.get(key_name))

            if (is_negative ^ is_key_truthy):
                return match.group(3)
            else:
                return ''

        return re.sub(pattern, replace, content, flags=re.DOTALL)

    def format_title(self, meeting):
        return self.format(meeting, self.title)

    def __str__(self):
        return self.title

    def save(self, *args, **kwargs):
        if not self.customer_id:
            self.active = True
        return super().save(*args, **kwargs)

    @property
    def is_plain_text(self):
        return self.type in self.PLAIN_TEXT_TYPES

    def get_default_alternatives(self):
        return DefaultMessage.objects.filter(type=self.type, is_active=True)

    @property
    def has_url(self):
        return self.type in self.PUBLIC_URL_TYPES

    @property
    def has_attachment(self):
        return self.type in self.ATTACHMENT_TYPES

    @property
    def generated_secret_key(self):

        import hashlib
        return hashlib.md5('{}{}'.format(self.pk, self.ts_created).encode('utf-8') * 5).hexdigest()

    def get_absolute_url(self):
        return reverse('get_message', args=[self.pk, self.secret_key])


class StringManager(models.Manager):

    def get_by_type(self, type, customer):

        try:
            return String.objects.get(customer=customer, type=type, active=True)
        except String.DoesNotExist:
            if customer:
                if type in String.ALLOW_DEFAULT:
                    default_title = self.get_by_type(type, None).title
                else:
                    default_title = ''

                return String.objects.get_or_create(customer=customer, type=type,
                    defaults=dict(title=default_title, active=False))[0]
            return String.objects.get_or_create(customer=None, type=type, defaults=dict(active=True))[0]

    def get_all(self, customer=None):

        strings = {s.type: s for s in String.objects.filter(customer=customer)}
        default = {s.type: s for s in String.objects.filter(customer=None)}

        result = []
        for id, _desc in String.ENABLED_TYPES:
            if id not in strings:
                default_title = ''
                try:
                    if id in String.ALLOW_DEFAULT:
                        default_title = default[id].title
                except KeyError:
                    pass
                strings[id] = String.objects.get_or_create(type=id, customer=customer,
                    defaults=dict(active=not customer, title=default_title))[0]
            result.append(strings[id])
        return result


@reversion.register
class String(models.Model):
    "only used by outlook 2013 plugin"

    TYPE_CHOICES = [
        (0, 'rooms_dist_group', _('Namn på grupp för lokaler i AD'), '''Den distributionsgrupp i exchange som innehåller lediga rum'''),
        (1, 'pin_code_help', _('Hjälptext för PIN-kod'), '''Förklaring vad det innebär att skriva in PIN-kod och hur det fungerar'''),
        (2, 'allow_external_clients', _('Aktivera externa deltagare'), '''Visa knappen för att aktivera externa deltagare (värde "yes" isåfall)'''),
    ]

    if getattr(settings, 'ONLY_MAKESPACE_MESSAGES', False):
        ENABLED_TYPES = DescriptiveChoices([])
    else:
        ENABLED_TYPES = DescriptiveChoices(TYPE_CHOICES)

    TYPES = DescriptiveChoices(TYPE_CHOICES)

    ALLOW_DEFAULT = [
        TYPES.rooms_dist_group,
    ]

    title = models.CharField(max_length=100, blank=True)
    active = models.BooleanField(default=True)

    type = models.IntegerField(choices=TYPES)

    type_title = TYPES.title_for('type')
    type_key = TYPES.key_for('type')
    type_description = TYPES.info_for('type')

    customer = models.ForeignKey(Customer, blank=True, null=True, on_delete=models.CASCADE)

    objects: StringManager['String'] = StringManager()

    def save(self, *args, **kwargs):
        if not self.customer:
            self.active = True
        super().save(*args, **kwargs)

    def __str__(self):
        return self.title


class DefaultMessage(models.Model):

    title = models.CharField(max_length=30, blank=True)
    type = models.IntegerField(choices=Message.TYPES)
    is_active = models.BooleanField(_('Visa i lista'), default=True)
    content = models.TextField(help_text=_('Formaterad med HTML beroende på meddelande'))

    def get_absolute_url(self):
        return reverse('get_default_message', args=[self.pk])

    def __str__(self):
        return self.title

