import re
from email import policy
from email.parser import BytesHeaderParser, HeaderParser

from django.db import models
from django.db.models import Q
from django.utils.encoding import force_bytes, force_text
from django.utils.translation import gettext_lazy as _

from compressed_store.models import CompressedStoreManager, CompressStoreModel


class AcanoCDRLogManager(CompressedStoreManager):

    ID_SEARCH = re.compile(rb'(?:id="|call>)(.*?)["<]')
    TYPE_SEARCH = re.compile(rb'<record type="([^"]+)"')

    def _get_create_kwargs(self, content, **kwargs):

        ids = self.ID_SEARCH.findall(force_bytes(content))
        types = self.TYPE_SEARCH.findall(force_bytes(content))

        return {
            'id_prefixes': ' {}'.format(force_text(b' '.join(sorted({id[:5] for id in ids}))))[:300],
            'count': len(types),
            'types': ','.join(sorted(force_text(t) for t in set(types)))[:100],
            **kwargs,
        }

    def search_ids(self, find_ids, ts_start=None, ts_stop=None):

        if not find_ids:
            return []

        if isinstance(find_ids, (str, bytes)):
            find_ids = [find_ids]

        cond = Q()
        for find_id in find_ids:
            cond |= Q(id_prefixes__contains=' {}'.format(force_text(find_id[:5])))

        qs = self.filter(cond)

        if ts_start:
            qs = qs.filter(ts_created__gte=ts_start)
        if ts_stop:
            qs = qs.filter(ts_created__lte=ts_stop)

        result = []

        for log in qs:
            for find_id in find_ids:
                if force_bytes(find_id) in log.content:
                    result.append(log)
                    break
        return result


class AcanoCDRLog(CompressStoreModel):
    log_type = 'acano_cdr'
    log_basename = 'acano_cdr'

    ip = models.GenericIPAddressField(null=True)
    id_prefixes = models.CharField(_('Store first digits of leg/call ids for searching'), max_length=300)
    count = models.SmallIntegerField(null=True)
    types = models.CharField(max_length=100, null=True, blank=True)

    objects = AcanoCDRLogManager()


class AcanoCDRSpamLog(CompressStoreModel):
    log_type = 'acano_cdr_spam'
    log_basename = 'acano_cdr_spam'

    ip = models.GenericIPAddressField(null=True)


class ErrorLogManager(CompressedStoreManager['ErrorLog']):
    def store(self, *args, **kwargs):
        if kwargs.get('title'):
            kwargs['title'] = str(kwargs['title'])[:255]
        return super().store(*args, **kwargs)


class ErrorLog(CompressStoreModel):
    log_type = 'error'
    log_basename = 'error'

    title = models.CharField(max_length=255)
    type = models.CharField(max_length=255)
    customer = models.ForeignKey(
        'provider.Customer',
        null=True,
        blank=True,
        on_delete=models.DO_NOTHING,
        db_constraint=False,
    )
    endpoint = models.ForeignKey(
        'endpoint.Endpoint',
        null=True,
        blank=True,
        on_delete=models.DO_NOTHING,
        db_constraint=False,
    )

    objects = ErrorLogManager()


class PexipEventLogManager(CompressedStoreManager):

    def search_ids(self, find_ids, ts_start=None, ts_stop=None):

        if not find_ids:
            return []

        if isinstance(find_ids, (str, bytes)):
            find_ids = [find_ids]

        qs = self.get_queryset().filter(
            uuid_start__in=[force_text(id[:36]) for id in find_ids if id]
        )

        if ts_start:
            qs = qs.filter(ts_created__gte=ts_start)
        if ts_stop:
            qs = qs.filter(ts_created__lte=ts_stop)

        result = []

        for log in qs:
            for find_id in find_ids:
                if force_bytes(find_id) in log.content:
                    result.append(log)
                    break
        return result


class PexipEventLog(CompressStoreModel):
    log_type = 'pexip_eventsink'
    log_basename = 'pexip_eventsink'

    cluster_id = models.IntegerField(null=True)
    ip = models.GenericIPAddressField(null=True)
    type = models.CharField(max_length=100, blank=True)
    uuid_start = models.CharField(max_length=36)

    objects = PexipEventLogManager()


class PexipHistoryLog(CompressStoreModel):
    log_type = 'pexip_history'
    log_basename = 'pexip_history'

    cluster_id = models.IntegerField(null=True)
    type = models.CharField(max_length=100, blank=True)
    count = models.IntegerField(default=0)

    first_start = models.DateTimeField(null=True)
    last_start = models.DateTimeField(null=True)

    def find_objects(self, guid=None, name=None):
        data = self.content_json
        if not data or not data.get('objects'):
            return []
        result = []
        for obj in data['objects']:
            if guid and guid in {obj.get('call_uuid'), obj.get('id'), obj.get('conversation_id')}:
                result.append(obj)
                continue
            if name and obj.get('name') == name:
                result.append(obj)
                continue
        return result


class PexipPolicyLog(CompressStoreModel):
    log_type = 'pexip_policy'
    log_basename = 'pexip_policy'

    cluster_id = models.IntegerField(null=True)
    ip = models.GenericIPAddressField(null=True)
    type = models.CharField(max_length=100, blank=True)
    service_type = models.CharField(max_length=255, blank=True)
    service_tag = models.CharField(max_length=255, blank=True)
    action = models.CharField(max_length=255)

    objects: 'CompressedStoreManager[PexipPolicyLog]' = CompressedStoreManager()

    class Meta:
        index_together = (('service_tag', 'ts_created'),)


class EmailLogManager(CompressedStoreManager):

    def _get_create_kwargs(self, content, **kwargs):
        if content and len(content) > 50:
            return self._get_sender_and_subject(content, **kwargs)
        return kwargs

    def _get_sender_and_subject(self, content, **kwargs):

        try:
            if isinstance(content, str):
                parser = HeaderParser(policy=policy.default)
                headers = parser.parsestr(content)
            else:
                parser = BytesHeaderParser(policy=policy.default)
                headers = parser.parsebytes(content)

            from_ = headers['from'] or headers['From']

            email_kwargs = {
                'sender': str(from_.addresses[0].addr_spec if from_ else ''),
                'subject': str(headers['subject']),
            }

        except Exception as e:
            if kwargs.get('error'):
                email_kwargs = {
                    'parse_error': str(e)[:200]
                }
            else:
                email_kwargs = {
                    'error': kwargs.get('error') or 'parse error: {}'.format(str(e)[:200]),
                }

        result = kwargs.copy()
        result.update({k: v for k, v in email_kwargs.items() if v})

        result['sender'] = str(result.get('sender') or '')[:100]
        result['subject'] = str(result.get('subject') or '')[:200]

        return result


class EmailLog(CompressStoreModel):
    log_type = 'email'
    log_basename = 'email'

    sender = models.CharField(max_length=100)
    subject = models.CharField(max_length=200)

    objects = EmailLogManager()

    @property
    def parts(self):
        try:
            return self._get_parts()
        except Exception as e:
            return [{'type': _('Parse Error'), 'content': str(e)}]

    def _get_parts(self):
        from email.parser import BytesParser
        if not self.content:
            return []

        message = BytesParser().parsebytes(self.content)

        result = []

        for part in message.walk():
            content_type = part.get_content_type()
            if content_type.split('/')[0] == 'text':
                content = part.get_payload(decode=True)
                try:
                    content = force_text(content)
                except UnicodeDecodeError:
                    try:
                        content = force_text(content, 'latin1')
                    except Exception:
                        content = '[parser error]'
                result.append({
                    'type': content_type,
                    'content': content,
                })

        return result

class VCSCallLog(CompressStoreModel):
    log_type = 'vcs'
    log_basename = 'vcs'

    ts_start = models.DateTimeField(null=True)
    ts_stop = models.DateTimeField(null=True)


class EndpointCiscoEvent(CompressStoreModel):
    log_type = 'cisco_event'
    log_basename = 'cisco_event'

    ip = models.GenericIPAddressField(null=True)
    endpoint = models.ForeignKey('endpoint.Endpoint', null=True, on_delete=models.SET_NULL, db_constraint=False)
    event = models.CharField(max_length=100)


class EndpointCiscoProvision(CompressStoreModel):
    log_type = 'cisco_provision'
    log_basename = 'cisco_provision'

    ip = models.GenericIPAddressField(null=True)
    endpoint = models.ForeignKey(
        'endpoint.Endpoint', null=True, on_delete=models.DO_NOTHING, db_constraint=False
    )
    event = models.CharField(max_length=100)


class EndpointPolyProvision(CompressStoreModel):
    log_type = 'poly_provision'
    log_basename = 'poly_provision'

    ip = models.GenericIPAddressField(null=True)
    endpoint = models.ForeignKey(
        'endpoint.Endpoint', null=True, on_delete=models.DO_NOTHING, db_constraint=False
    )
    event = models.CharField(max_length=100)
