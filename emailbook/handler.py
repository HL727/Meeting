import json
from email import policy
from email.parser import HeaderParser
from email.utils import format_datetime
from typing import Any, List, Optional, Tuple

from django.conf import settings
from django.core.mail import EmailMessage
from django.db import transaction
from django.db.models import Q
from django.template.loader import render_to_string
from django.utils.timezone import now
from django.utils.translation import gettext as _
from sentry_sdk import capture_exception

from calendar_invite.handler import InviteHandler
from calendar_invite.types import InviteMessageParseDict
from endpoint.models import Endpoint, CustomerDomain
from meeting.book_handler import BookingEndpoint
from meeting.forms import MeetingForm
from provider.exceptions import InvalidKey
from provider.models.provider import Provider
from customer.models import Customer
from recording.models import MeetingRecording
from provider.models.utils import date_format
from .models import EmailMeeting, SenderLock
from .parser import EmailParser


class EmailResultDict(InviteMessageParseDict, total=False):

    mode: str
    customer: Customer
    no_invite: Optional[bool]
    valid_domains: bool
    provider: Provider
    recording: str


class EmailHandler(InviteHandler):

    def __init__(self, message):
        self.message = message

    def validate(self):
        """
        Validate input message
        """
        data = EmailParser(self.message).parse()

        if data.get('error'):
            return False, data, _('Ett fel uppstod när mötet skulle hanteras ({})').format(data['error'])

        result = EmailResultDict(**data)

        mode, matched_endpoints, has_valid_domains = self.validate_recipients(result.get('participants') or [])

        result['mode'] = mode

        if not (result['ts_start'] and result['ts_stop']):
            result['no_invite'] = True
            return False, result, _('Kunde inte hitta något möte. Vänligen kontrollera att kalenderbokning skickats med som bilaga till meddelandet')

        if not mode:
            return False, result, _('Felaktig mottagare angiven')

        domain = result['creator'].split('@', 1)[-1]
        try:
            customer = Customer.objects.get_by_key(domain)
        except InvalidKey:
            customer = None
        except Customer.MultipleObjectsReturned:
            return False, result, _('Din domän är kopplad till flera kunder. Kontakta support')
        except Exception as e:
            if settings.TEST_MODE:
                raise
            capture_exception()
            return False, result, _('Ett fel uppstod: {}').format(e)

        customer, endpoints = self.get_endpoint_email_customer(domain, matched_endpoints, customer)

        if not customer:
            return False, result, _('Tyvärr är din adress inte betrodd (%s)') % (result['creator'] or 'Okänd')

        result['customer'] = customer

        result['endpoints'] = endpoints
        result['valid_domains'] = has_valid_domains

        if mode == 'external':
            result['provider'] = Provider.objects.get_active('external')

        self.populate_meeting_dial_settings(result, endpoints, dialout=mode != 'external')

        if mode not in ('book',):  # require dial string
            if not result['dialstring']:
                return False, result, _('Kunde inte hitta mötesrum att ringa upp. '
                        'Kontrollera bifogade filer, eller skriv in adressen i '
                        'formatet sip:1234@video.example.org')

        if mode in ('record', 'stream', 'record+stream'):
            result['recording'] = json.dumps({
                'record': (mode != 'stream'),
                'is_live': (mode in ('record+stream', 'stream')),
            })

        if not result['creator']:
            return False, result, _('Hittade ingen avsändare')

        if result['skype_conference'] and mode != 'external':
            return False, result, _('Tyvärr kan videosystemet inte ringa upp skype-konferenser')
        return True, result, ''

    def get_endpoint_email_customer(self, domain, endpoints, customer=None):

        epm_customers = set(CustomerDomain.objects.filter(domain=domain).values_list('customer', flat=True))
        if customer:
            epm_customers.add(customer.pk)

        endpoints = [e for e in endpoints if e.customer_id in epm_customers]
        if not customer and endpoints:
            customer = endpoints[0].customer

        return customer, endpoints

    def validate_recipients(self, participants):
        endpoints = []

        mode = ''
        valid_domains = False
        for p in participants:
            parts = p.split('@')

            full_url_endpoints = Endpoint.objects.filter(sip_aliases__sip=p)
            endpoints.extend(list(full_url_endpoints))

            if len(parts) == 2:
                username, domain = parts
                if domain not in {settings.EPM_HOSTNAME, settings.HOSTNAME, settings.BOOK_EMAIL_HOSTNAME}:
                    if not (settings.TEST_MODE and domain == 'book.example.org'):
                        continue
                else:
                    valid_domains = True
            else:
                username = parts[0]  # TODO remove this?

            if not username:
                continue

            username_endpoints = Endpoint.objects.distinct().filter(Q(email_key=username) | Q(sip_aliases__sip=username))
            endpoints.extend(list(username_endpoints))

            if username in ('record', 'inspelning'):
                mode = 'record'
                break
            elif username in ('record+stream', 'record.stream', 'record+streaming', 'record.streaming',
                              'inspelning+streaming', 'inspelning.streaming'):
                mode = 'record+stream'
                break
            elif username in ('stream', 'streaming'):
                mode = 'stream'
                break
            elif username in ('book', 'boka', 'video'):
                mode = 'book'
                break

        if endpoints and not mode:
            mode = 'external'

        return mode, endpoints, valid_domains

    def get_meeting_form(self, result):

        # prepare for form
        is_private = bool(result.get('is_private'))

        form_data = result.copy()
        form_data['external_clients'] = 1
        form_data['internal_clients'] = 1
        form_data['ts_start'] = date_format(result['ts_start'])
        form_data['ts_stop'] = date_format(result['ts_stop'])
        form_data['title'] = result['subject'] if not is_private else '-- Private --'
        form_data['is_private'] = is_private
        form_data['source'] = 'email'
        form_data['recurrence_id'] = result['recurrence_id']
        form_data['confirm'] = '1'

        form = MeetingForm(form_data)
        return form.is_valid(), form_data, form

    def handle_locked(self) -> Tuple[bool, dict, str]:
        parser = HeaderParser(policy=policy.default)
        headers = parser.parsestr(self.message)
        sender = str((headers['From'] or headers['from']).addresses[0].addr_spec)[:100],
        with transaction.atomic():
            SenderLock.objects.select_for_update().get_or_create(sender=sender)
            return self.handle()

    def _get_existing(self, content) -> Optional[EmailMeeting]:
        existing_queryset = EmailMeeting.objects\
            .filter(uid=content['uid'], customer=content['customer']) \
            .filter(Q(meeting__recurrence_id__in={content['recurrence_id'],
                                                  date_format(content['ts_start']),
                                                  '',
                                                  })
                    | Q(meeting__recurrence_id__isnull=True)
                    )

        if content['creator']:
            existing_queryset = existing_queryset.filter(sender=content['creator'])

        if content['uid'] and existing_queryset:
            return existing_queryset.order_by('-ts_received')[0]

        return None

    def validate_meeting(self, content):

        valid, book_content, form = self.get_meeting_form(content)
        if not valid:
            return False, None, form.errors

        book_endpoint = BookingEndpoint(book_content, book_content['customer'],
                                        provider=book_content.get('provider'))

        return valid, book_endpoint, ''

    def _maybe_send_error(self, content, error):
        if '@' in content['creator'].strip() and content.get('mode') not in {None, '', 'external'}:
            if content.get('valid_domains'):  # check for valid receiver domains. catchall spam otherwise?
                self.send_error(error, content)

    def handle(self):

        valid, content, error = self.validate()
        if valid:
            base_content = content.copy()

            valid, content, error = self.handle_single(content)
            if valid and content['mode'] not in ('external',):
                self.send_confirmation(content['email_meeting'], content)

            for extra in content.get('extra_events') or []:  # TODO extra error/email handling?
                _valid, _content, _error = self.handle_single({**base_content, **extra, 'recurring': ''})

            return valid, content, error

        self._maybe_send_error(content, error)
        return False, content, error

    def handle_single(self, content):

        valid, book_endpoint, error = self.validate_meeting(content)
        if not valid:
            return False, content, error

        existing = self._get_existing(content)

        is_duplicate = False

        if content['cancelled']:
            return self.handle_cancelled(existing, content, book_endpoint)
        elif existing:
            email_meeting, meeting = self.handle_existing(existing, content, book_endpoint)
            is_duplicate = content.get('is_duplicate', is_duplicate)
        else:
            email_meeting = None
            meeting = book_endpoint.book()

        if not is_duplicate:
            email_meeting = EmailMeeting.objects.create(
                meeting=meeting,
                recurring_meeting=meeting.recurring_master,
                customer=content['customer'], uid=content['uid'], recurrence_id=content['recurrence_id'],
                sender=content['creator'], dialstring=content['dialstring'],
                mode=content['mode'],
            )

        content['email_meeting'] = email_meeting
        content['meeting'] = meeting

        return True, content, ''

    def handle_existing(self, email_meeting, content, book_endpoint):

        meeting = email_meeting.meeting
        can_rebook, rebook_error = self._check_can_rebook(email_meeting)

        existing_data = (meeting.ts_start, meeting.ts_stop, email_meeting.dialstring, email_meeting.mode)
        new_data = (content['ts_start'], content['ts_stop'], content['dialstring'], content['mode'])

        is_duplicate = (existing_data == new_data)  # identical time and info
        rooms_changed = (meeting.room_info != content['room_info'])  # changed endpoints

        if is_duplicate:
            if rooms_changed:
                meeting.room_info = self.merge_room_infos([
                    meeting.room_info,
                    [{'endpoint': e.email_key} for e in content['endpoints']]
                ])
                meeting.save()
                meeting.connect_endpoints()
            else:
                content['is_duplicate'] = True
        elif can_rebook:
            content['rebook'] = True
            content['rebook_old_info'] = {
                'title': meeting.title,
                'ts_start': meeting.ts_start,
                'ts_stop': meeting.ts_stop
            }
            meeting = book_endpoint.rebook(meeting.id)
        else:
            content['message'] = rebook_error
            meeting = book_endpoint.book()

        return email_meeting, meeting

    def handle_cancelled(self, email_meeting, content, book_endpoint):
        if not email_meeting:
            return True, content, ''

        meeting = email_meeting.meeting
        try:
            endpoints_left = meeting.remove_endpoints(content['endpoints'], commit_empty=False)
            if not endpoints_left:
                email_meeting.meeting = book_endpoint.unbook(email_meeting.meeting_id)
            content['email_meeting'] = email_meeting
            content['meeting'] = email_meeting.meeting
            return True, content, ''
        except Exception as e:
            return False, content, e

    def _check_can_rebook(self, email_meeting: EmailMeeting):
        """recordings, dialouts, streams are not 100% sure it can be rescheduled"""
        can_rebook = True
        rebook_error = ''

        if not email_meeting.meeting.backend_active:
            rebook_error = _('Du har fått nya uppgifter då det tidigare mötesrummets giltighetstid löpt ut')
            can_rebook = False
        elif email_meeting.meeting.ts_start > now():
            can_rebook = True
        else:
            for r in MeetingRecording.objects.filter(meeting=email_meeting.meeting):
                if not r.get_api().can_reschedule:
                    can_rebook = False
                    rebook_error = _(
                        'Du har fått nya uppgifter då det var bokat en inspelning hos en leverantör där ombokning inte stöds')

        return can_rebook, rebook_error

    def send_error(self, error, content):

        context = content.copy()
        context['error'] = error

        sender_email = settings.SERVER_EMAIL
        body = render_to_string('emailbook/email/error.txt', context)
        msg = EmailMessage('Fel vid bokning - {}'.format(context['subject']),
                           body, sender_email, [context['creator']])
        if content.get('envelope'):
            msg.extra_headers['In-Reply-To'] = content['envelope']
            msg.extra_headers['References'] = content['envelope']
        return msg.send()

    def get_confirmation_message(self, email_meeting, content):

        context = content.copy()

        playback_urls = []
        for recording in MeetingRecording.objects.filter(meeting=email_meeting.meeting):
            try:
                url = json.loads(recording.video_sources or '{}')['playback_url']
            except Exception:
                pass
            else:
                playback_urls.append(url)

        context['playback_urls'] = playback_urls

        mode = context.pop('mode', 'book')
        if mode == 'book':

            from ui_message.models import Message
            try:
                message = Message.objects.get_for_meeting(email_meeting.meeting)
                context['instructions'] = message.format(email_meeting.meeting)
            except Message.DoesNotExist:
                pass

            body = render_to_string('emailbook/email/book.html', context)
        elif mode in ('record', 'record+stream', 'stream'):
            context['action'] = {
                    'record': _('spelas in'),
                    'record+stream': _('spelas in och streamas'),
                    'stream': _('streamas'),
            }.get(mode)
            body = render_to_string('emailbook/email/record.html', context)
        else:
            raise ValueError('mode can not be {}'.format(mode))

        return body

    def send_confirmation(self, email_meeting, content):

        body = self.get_confirmation_message(email_meeting, content)

        sender_email = settings.SERVER_EMAIL
        msg = EmailMessage(_('Bokningsbekräftelse') + ' - {}'.format(content['subject'].replace('\n', '')),
                           body, sender_email, [content['creator']])

        msg.content_subtype = 'html'

        if content.get('envelope'):
            msg.extra_headers['In-Reply-To'] = content['envelope']
            msg.extra_headers['References'] = content['envelope']

        return msg.send()
