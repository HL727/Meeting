from datetime import datetime
from datetime import tzinfo

from django.utils.timezone import utc


def date_format(d):
    return '%sZ' % d.astimezone(utc).strftime('%Y%m%dT%H%M%S')


def rrule_set(dtstart: datetime, recurring, exceptions, timezone: tzinfo = None):
    if recurring.startswith('RRULE:') or recurring.startswith('RDATE:'):
        rule = recurring
    else:
        rule = 'RRULE:{}'.format(recurring) if recurring else ''

    if exceptions.startswith('EXDATE:'):
        exdate = exceptions
    else:
        exdate = 'EXDATE:{}'.format(exceptions) if exceptions else ''

    full_str = '{}\n{}'.format(rule, exdate).strip()

    if timezone:
        dtstart = dtstart.astimezone(timezone)

    from dateutil.rrule import rrulestr
    return rrulestr(full_str, dtstart=dtstart, forceset=True)


def _date_format_getter(field):
    def _inner(self):
        return date_format(getattr(self, field))
    return property(_inner)


def parse_timestamp(value):
    return datetime.strptime(value.rstrip('Z'), '%Y%m%dT%H%M%S').replace(tzinfo=utc)


def new_secret_key(length=6):
    from random import choice

    chars = '1234567890qwertyuiopasdfghjklzxcvbnmQWERTYUIOPASDFGHJKLZXCVBNM'
    return ''.join(choice(chars) for i in list(range(length)))
