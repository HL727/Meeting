import logging
import re
from os import environ
from traceback import format_exception

logger = logging.getLogger('error')


class RemoveContextVar:
    def __call__(self, event, hint):
        try:
            event = self.handle(event, hint)
        except Exception:
            pass
        from django.conf import settings

        if not settings.ALLOW_SENTRY:
            return None
        return event

    def handle(self, event, hint):

        try:
            self._log(event, hint)
            self._dblog(event, hint)
        except Exception:
            pass

        if 'exception' in event and 'values' in event['exception']:
            self.process_exception(event)

        for k in ('request', 'extra', 'body', 'headers'):
            if event.get(k):
                try:
                    event[k] = redact_values(event[k])
                except Exception as e:
                    print(e)

        return event

    def _get_log_info(self, event, hint):

        body = ''
        error_type = 'Unknown'
        if event.get('exception'):
            error_type = event['exception'][0]['type']

            title = '{}: {}'.format(
                event['exception'][0]['type'], event['exception'][0].get('value')
            )
            if hint.get('exc_info'):
                body = format_exception(*hint['exc_info'])
        else:
            title = event.get('message') or 'Error'

        if event.get('request'):
            body += '\n\nURL: {}'.format(event['request']['url'])

        return title, error_type, body.strip()

    def _log(self, event, hint):
        title, error_type, body = self._get_log_info(event, hint)

        if body:
            logger.warning('{}: %s'.format(title), body.strip().replace('\n', ' \\n '))
        else:
            logger.warning(title)

    def _dblog(self, event, hint):
        title, error_type, body = self._get_log_info(event, hint)

        from debuglog.models import ErrorLog

        if hint.get('exc_info'):
            ErrorLog.objects.store(body, title=title[:255], type=error_type)

    def process_exception(self, event):
        for value in event['exception'].get('values', []):
            for frame in value.get('stacktrace', {}).get('frames', []):
                if 'vars' not in frame:
                    continue
                frame['vars'] = {k: redact_values(v) for k, v in frame['vars'].items()}


ALLOW_KEYS = {
    'cospace_id',
    'provider',
    'cluster',
    'provider_id',
    'command',
    'configuration',
    'settings',
    'meeting_type',
    'call_profile',
    'call_leg_profile',
    'ts_start',
    'ts_stop',
}


def redact_values(val, depth=0):
    try:
        class_name = val.__class__.__name__
    except Exception:
        class_name = '??'

    try:
        return _real_redact_value(val, class_name, depth=depth)
    except Exception:
        return class_name


def _real_redact_value(val, class_name, depth=0):
    length = ''
    if hasattr(val, '__len__'):
        length = '[{}]'.format(len(val))

    if isinstance(val, str) and not val.startswith('\'') and not val.startswith('"'):
        prefix = ''
    else:
        prefix = '{}{}'.format(class_name, length)

    if not val or depth >= 3:
        return prefix

    if isinstance(val, dict) and val:
        redacted = {}
        for k, v in val.items():
            if k in ALLOW_KEYS:
                redacted[k] = v
            else:
                redacted[k] = redact_values(v, depth + 1)

        return '{}<{}>'.format(
            prefix,
            ', '.join('{}: {}'.format(k, v) for k, v in redacted.items()),
        )
    elif isinstance(val, (list, tuple)):
        return '{}<{}>'.format(class_name, ', '.join(redact_values(v, depth + 1) for v in val[:5]))
    elif isinstance(val, str) and val.replace('.', '').isdigit():
        return 'int<{}>'.format(val)
    elif isinstance(val, str) and val in ('None', 'True', 'False'):
        return val
    elif isinstance(val, str) and val == 'None':
        return 'None'
    elif isinstance(val, str) and (val.startswith('datetime') or val.startswith('timedelta')):
        return val
    elif isinstance(val, str) and val.startswith('['):
        return 'list<{}>'.format(redact_values(val[1:].rstrip(']'), depth + 1))
    elif isinstance(val, str) and val.startswith('('):
        return 'tuple<{}>'.format(redact_values(val[1:].rstrip(')'), depth + 1))
    elif isinstance(val, str) and val.startswith('<'):  # repr()
        m = re.match(r'<(bound method|function) ([^: >]+) of <?([^: >]+)', val)
        if m:
            return 'function {}.{}'.format(m.group(2), m.group(1))
        m = re.match(r'<(class [^: >]+)', val)
        if m:
            return m.group(1)

        m = re.match(r'<([^: >]+)', val)
        if m:
            return m.group(1)

    return prefix


def get_verbose_logging(apps, level='INFO', facility=None, syslog_server=None):
    obj = {
        'handlers': ['console_local'],
        'level': level,
        'propagate': False,
    }

    if syslog_server:
        syslog_kwargs = {
            'syslog': {
                'level': level,
                'class': 'logging.handlers.SysLogHandler',
                'formatter': 'verbose',
                'facility': facility,
                'address': syslog_server,
            },
        }
        syslog_handler = ['syslog']
    else:
        syslog_kwargs = {}
        syslog_handler = []

    return {
        'version': 1,
        'disable_existing_loggers': False,
        'handlers': {
            'console_local': {
                'class': 'logging.StreamHandler',
            },
            **syslog_kwargs,
        },
        'root': {
            'handlers': ['console_local', *syslog_handler],
        },
        'loggers': {app: obj for app in apps},
    }


def sentry_init(config: dict, env=None):
    import sentry_sdk
    from sentry_sdk.integrations.django import DjangoIntegration
    from sentry_sdk.integrations.celery import CeleryIntegration
    from sentry_sdk.integrations.threading import ThreadingIntegration

    trace = None
    if (env or environ.get)('SENTRY_PERFORMANCE'):
        trace = min(100, float(env('SENTRY_PERFORMANCE') or 1))

    def sampler(context):
        if not context.get('transaction_context'):
            return trace or 0

        if context.get('parent_sampled') is not None:
            return context['parent_sampled']

        wsgi_environ = context.get('wsgi_environ', {})
        name = context['transaction_context'].get('name')

        if name == 'generic WSGI request' and wsgi_environ:
            name = wsgi_environ.get('PATH_INFO') or ''

        if '/accounts/login/' in name or '/status/up/' in name:
            if wsgi_environ.get('REQUEST_METHOD', 'GET') == 'GET':
                return 0
        return (trace or 0) / 100

    sentry_sdk.init(
        integrations=[DjangoIntegration(), CeleryIntegration(), ThreadingIntegration()],
        traces_sampler=sampler,
        send_default_pii=False,
        before_send=RemoveContextVar(),
        **config,
    )
