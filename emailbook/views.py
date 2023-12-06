from django.shortcuts import render, get_object_or_404
from django.http import HttpResponse
from django.utils.timezone import now
from django.utils.encoding import force_text
from django.utils.translation import gettext_lazy as _
from sentry_sdk import capture_exception

from .handler import EmailHandler
from .models import EmailMeeting
from meeting.book_handler import BookingEndpoint
from django.views.decorators.csrf import csrf_exempt
from datetime import datetime
from django.conf import settings
from os import mkdir
from os.path import exists

"""
Add alias in postfix:

book_script: "|/home/..venv../python /home/...venv../emailbook/script.py https://<host>/email/book/"

Add wildcard domain in virtual:

@book.<domain>.com      book_script


"""


def _load_message_content(request):

    message = ''
    if request.POST.get('message'):
        message = request.POST['message']
    else:
        try:
            message = force_text(request.body)
        except UnicodeDecodeError:
            try:
                message = force_text(request.body, 'latin1')
            except Exception:
                pass
    return message


@csrf_exempt
def handle_http(request):
    valid = error = None
    content = {}

    message = _load_message_content(request)

    if settings.EMAIL_REQUIRE_EXTENDED_KEY:
        if request.META.get('HTTP_X_MIVIDAS_TOKEN') != settings.EXTENDED_API_KEY:
            return _log_invalid_key(request, message)

    try:
        valid, content, error = EmailHandler(message).handle_locked()
    except Exception as e:
        if settings.TEST_MODE or settings.DEBUG:
            raise
        error = str(e)
        capture_exception()
    finally:
        if content and (content.get('no_invite') and content.get('mode', 'external') in ('external', '')):
            message = 'External meeting without calendar attachment. Redacted.'
        elif content and content.get('is_private'):
            message = 'Private meeting. Redacted.'

        subject = ''
        if content:
            subject = '-- Private --' if content.get('is_private') else content.get('subject') or ''

        _log_message(request, subject, message, content, valid, error)

    return HttpResponse('{"status": "%s"}' % ('OK' if valid else 'Error'))


def _log_message(request, subject, message, content, valid, error):
    from debuglog.models import EmailLog

    data = {
        'ts': str(datetime.now()),
        'ip': request.META.get('REMOTE_ADDR', '127.0.0.1'),
        'subject': subject,
        'sender': content and content.get('creator') or '',
        'dialstring': content and content.get('dialstring') or '',
        'rawpost': message,
        'valid': valid,
        'error': error,
        'email_meeting': content and content.get('email_meeting') and content['email_meeting'].pk,
        'meeting': content and content.get('email_meeting') and content['email_meeting'].meeting_id,
        'is_duplicate': content and content.get('is_duplicate'),
        'is_cancelled': content and content.get('cancelled'),
        'rebook': content and content.get('rebook'),
        'customer': content['customer'].pk if content.get('customer') else None,
    }

    try:
        EmailLog.objects.store(**{**data, 'content': message, 'rawpost': None})
    except Exception as e:
        data['log_error'] = str(e)

    root = settings.LOG_DIR
    if not exists(root):
        mkdir(root)


def _log_invalid_key(request, message):
    from debuglog.models import EmailLog

    data = {
        'ip': request.META.get('REMOTE_ADDR', '127.0.0.1'),
        'subject': _('Error: Unauthorized mail server'),
        'sender': '',
        'rawpost': '',
        'valid': '',
        'error': 'Invalid X-Mividas-Token',
    }
    EmailLog.objects.store(**{**data, 'content': message, 'rawpost': None})

    return HttpResponse('Forbidden', status=403)


def unbook(request, secret_key):

    email_meeting = get_object_or_404(EmailMeeting, secret_key=secret_key)

    context = {}
    if request.POST.get('unbook'):
        BookingEndpoint({}, email_meeting.customer).unbook(email_meeting.meeting_id)
        email_meeting.ts_deleted = now()
        email_meeting.save()
        context['done'] = True

    return render(request, 'emailbook/unbook.html', context)
