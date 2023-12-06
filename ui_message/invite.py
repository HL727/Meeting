from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.utils.timezone import now

from premailer import Premailer
import logging

from supporthelpers.forms import CoSpaceForm
from ui_message.models import Message


def format_message_content(subject, body):
    instance = Premailer(base_url=settings.BASE_URL, cssutils_logging_level=logging.ERROR)
    context = {
        'subject': subject,
        'content': body,
        'test_mode': settings.TEST_MODE,
    }
    content = render_to_string('email/message_body.html', context)

    return instance.transform(content)


def send_email_for_message(message, emails, subject=None):
    if not message['content'].strip():
        return ValueError('Message is empty')

    msg = EmailMultiAlternatives(subject or message['title'], message['plain'], settings.SERVER_EMAIL, emails)

    msg.attach_alternative(format_message_content(subject or message['title'], message['content']), "text/html")

    if message['attachment']:
        msg.attach_file(message['attachment'].path)

    try:
        return msg.send()
    except Exception:
        raise


def send_email_for_cospace(api, cospace_id, emails=None, subject=None, meeting=None):

    if meeting is None:
        meeting = CoSpaceForm(cospace=cospace_id).get_temp_meeting(api.customer)

    if emails is None:
        emails = [meeting.creator_email]

    message = Message.objects.get_by_type(Message.TYPES.acano_cospace, api.customer).to_dict(meeting)

    return send_email_for_message(message, emails, subject=subject)


def send_email_for_user_cospace(api, user_id, emails=None, subject=None, meeting=None):

    if meeting is None:
        cospace = api.get_user_private_cospace(user_id)
        if not cospace:
            raise ValueError('User has no private cospace')
        meeting = CoSpaceForm(cospace=cospace['id']).get_temp_meeting(api.customer)

    if emails is None:
        emails = [meeting.creator_email]

    message = Message.objects.get_by_type(Message.TYPES.acano_cospace, api.customer).to_dict(meeting)

    result = send_email_for_message(message, emails, subject=subject)
    if meeting.creator_email in emails:
        if api.cluster.is_acano:
            from datastore.models import acano as ds
            user = ds.User.objects.get_user(api, user_id)
            user.ts_instruction_email_sent = now()
            user.save()

    return result
