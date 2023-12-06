from base64 import b64encode
from typing import Tuple, Dict

from django.http import HttpResponse, Http404, HttpResponseBadRequest, QueryDict
from django.utils.translation import gettext as _

from audit.models import AuditLog
from meeting.api_views_base import meeting_response, cospace_response, ApiRequest
from meeting.book_handler import BookingEndpoint
from provider.exceptions import InvalidData, ResponseError, NotFound, InvalidKey
from provider.ext_api.base import MCUProvider
from provider.models.acano import CoSpace
from meeting.models import Meeting
from provider.models.provider import Provider
from customer.models import Customer
from django.shortcuts import get_object_or_404, render
from django.conf import settings
from django.views.decorators.csrf import csrf_exempt

from recording.models import AcanoRecording
from supporthelpers.forms import CoSpaceForm


class Book(ApiRequest):

    def dispatch(self, request, *args, **kwargs):

        endpoint = BookingEndpoint(request.POST, Customer.objects.from_request(request))
        meeting = endpoint.book()

        result = meeting_response(meeting)
        if request.GET.get('include_moderator'):
            result['moderator_data'] = ModeratorMessage.get_message(meeting, meeting.customer)
        return result


class Webinar(ApiRequest):

    def dispatch(self, request, *args, **kwargs):

        endpoint = BookingEndpoint(request.POST, Customer.objects.from_request(request))
        meeting = endpoint.webinar()

        result = meeting_response(meeting)
        if request.GET.get('include_moderator'):
            result['moderator_data'] = ModeratorMessage.get_message(meeting, meeting.customer)
        return result


class WebinarList(ApiRequest):

    def dispatch(self, request, *args, **kwargs):
        # TODO extra authentication

        customer = Customer.objects.from_request(request)

        result = []

        group_filter = {}
        if request.GET.get('group'):
            group_filter = {
                'webinars__group': request.GET.get('group'),
            }

        for m in Meeting.objects.filter(customer=customer, webinars__isnull=False, **group_filter):
            if m.backend_active:

                cur = {
                    'title': m.title,
                    'password': m.password,
                    'webinar': m.get_webinar_info(),
                    'rest_url': m.get_api_rest_url(),
                    'call_id': m.provider_ref,
                    'join_url': m.join_url,
                    'uri': m.get_preferred_uri(),
                }
                result.append(cur)

        return result


class UpdateCoSpace(ApiRequest):

    def dispatch(self, request, *args, **kwargs):

        endpoint = BookingEndpoint(request.POST, Customer.objects.from_request(request))
        if kwargs.get('cospace_id'):
            pk, secret = kwargs.get('cospace_id', '-').split('-')
            obj = get_object_or_404(CoSpace, customer=endpoint.customer, pk=pk)
            if obj.secret_key != secret:
                AuditLog.objects.store_request(request, 'Invalid key for cospace')
                raise Http404()

            if request.method == "GET":
                return cospace_response(obj.provider_ref, customer=endpoint.customer)

            if request.method == "DELETE":
                return {
                    'status': 'OK' if endpoint.delete_cospace(obj) else 'ERROR',
                }

            else:
                cospace = endpoint.cospace(cospace_id=obj.provider_ref)

        else:
            if request.method != "POST":
                return HttpResponseBadRequest()
            cospace = endpoint.cospace()

        return cospace_response(cospace, endpoint.customer)


class CoSpaceMembers(ApiRequest):

    def dispatch(self, request, *args, **kwargs):

        endpoint = BookingEndpoint(request.POST, Customer.objects.from_request(request))
        assert kwargs.get('cospace_id')

        pk, secret = kwargs.get('cospace_id', '-').split('-')
        obj = get_object_or_404(CoSpace, customer=endpoint.customer, pk=pk)
        if obj.secret_key != secret:
            AuditLog.objects.store_request(request, 'Invalid key for cospace')
            raise Http404()

        cospace = endpoint.cospace_members(obj.provider_ref)

        return cospace_response(cospace, endpoint.customer)


class CoSpaceList(ApiRequest):

    def dispatch(self, request, *args, **kwargs):
        # TODO extra authentication

        customer = Customer.objects.from_request(request)

        result = []

        group_filter = {}
        if request.GET.get('group'):
            group_filter = {
                'group': request.GET.get('group'),
            }

        for cospace in CoSpace.objects.filter(customer=customer, **group_filter):

            cur = {
                'id': cospace.id_key,
                'title': cospace.title,
                'uri': cospace.uri,
                'call_id': cospace.call_id,
                'rest_url': cospace.get_api_url(),
                'join_url': cospace.join_url,
            }
            result.append(cur)

        return result


class MeetingApiRequest(ApiRequest):

    def dispatch(self, request, *args, **kwargs):

        meeting_id = kwargs['meeting_id']
        meeting = Meeting.objects.get_by_id_key_or_404(request, meeting_id)
        return self.handle_meeting(request, meeting)

    def handle_meeting(self, request, meeting) -> dict:
        raise NotImplementedError()


class MeetingDetailsView(MeetingApiRequest):

    def handle_meeting(self, request, meeting):
        Customer.objects.from_request(request)
        return meeting_response(meeting)


class ConfirmMeetingView(MeetingApiRequest):

    def handle_meeting(self, request, meeting):
        Customer.objects.from_request(request)
        meeting.confirm()
        return meeting_response(meeting)


class UnBook(MeetingApiRequest):

    def handle_meeting(self, request, meeting):
        endpoint = BookingEndpoint(request.POST, Customer.objects.from_request(request))
        meeting = endpoint.unbook(meeting.pk)
        if request.GET.get('all_recurring') in ('1', 'true', True):
            if meeting.recurring_master:
                meeting.recurring_master.unbook()

        return meeting_response(meeting)


class ReBook(MeetingApiRequest):

    def handle_meeting(self, request, meeting):
        endpoint = BookingEndpoint(request.POST, Customer.objects.from_request(request))
        meeting = endpoint.rebook(meeting.pk)
        if request.GET.get('all_recurring') in ('1', 'true', True):
            if meeting.recurring_master:
                meeting.recurring_master.rebook(meeting)

        return meeting_response(meeting)


class UpdateSettings(MeetingApiRequest):

    def handle_meeting(self, request, meeting):
        endpoint = BookingEndpoint(request.POST, Customer.objects.from_request(request))
        meeting = endpoint.update_settings(meeting.pk)

        result = meeting_response(meeting)
        if request.GET.get('include_moderator'):
            result['moderator_data'] = ModeratorMessage.get_message(meeting, meeting.customer)
        return result


class Status(ApiRequest):

    def dispatch(self, request, *args, **kwargs):

        customer = Customer.objects.from_request(request)
        try:
            api = customer.get_api()
        except NotFound:
            api = None

        from endpoint.models import CustomerSettings

        address_book = CustomerSettings.objects.get_for_customer(
            customer
        ).default_portal_address_book_id

        enable_cospace_changes = False

        try:
            extended_key = Customer.objects.get_extended_key_from_request(request)
            if extended_key:
                api_key = Customer.objects.check_extended_key(extended_key)
                enable_cospace_changes = api_key.enable_cospace_changes
        except InvalidKey:
            pass

        result = {
            'status': 'OK',
            'enable_dial_out': False,
            'enable_addressbook': bool(address_book),
            'enable_cospace_changes': enable_cospace_changes,
            'is_pexip': api.provider.is_pexip if api else False,
            'is_cms': api.provider.is_acano if api else False,
            'enable_cma': api.provider.is_acano and (api.provider.software_version or '') < '3.0',
        }

        if request.GET.get('extended'):
            result['seevia_key'] = customer.seevia_key
        return result


class WelcomeMessage(ApiRequest):

    def dispatch(self, request, *args, **kwargs):
        from ui_message.models import Message, String

        customer = Customer.objects.from_request(request)

        message = Message.objects.get_welcome(customer=customer)

        message_content = message.content

        data = {
            'status': 'OK',
            'welcome_title': message.title,
            'welcome_message': message_content,
        }

        for s in String.objects.get_all(customer=customer):
            data[s.type_key] = s.title

        return data


class MeetingMessage(ApiRequest):
    def dispatch(self, request, *args, **kwargs):
        from ui_message.models import Message

        Customer.objects.from_request(request)

        meeting = Meeting.objects.get_by_id_key_or_404(request, kwargs.get('meeting_id'))

        message = Message.objects.get_for_meeting(meeting)

        return {
            'status': 'OK',
            'message_title': message.format_title(meeting),
            'message_content': message.format(meeting),
        }


class ModeratorMessage(ApiRequest):
    def dispatch(self, request, *args, **kwargs):
        meeting = Meeting.objects.get_by_id_key_or_404(request, kwargs.get('meeting_id'))
        customer = Customer.objects.from_request(request)

        return self.get_message(meeting, customer)

    @classmethod
    def get_message(cls, meeting, customer):
        from ui_message.models import Message

        meeting.is_moderator = True

        if meeting.get_connection_data('password'):
            default_type = 'clearsea_meeting_pin'
        else:
            default_type = 'clearsea_meeting'

        message = Message.objects.get_moderator_message(meeting.meeting_type or default_type, customer=customer)

        return {
            'status': 'OK',
            'message_title': message.format_title(meeting),
            'message_content': message.format(meeting),

            'room_id': meeting.get_connection_data('provider_ref'),
            'web_url': meeting.join_url,
            'sip_uri': meeting.sip_uri,
        }


class SyncUsers(ApiRequest):

    def dispatch(self, request, *args, **kwargs):

        customer = Customer.objects.from_request(request)

        if customer.lifesize_provider_id:
            provider = customer.lifesize_provider
        else:
            provider = Provider.objects.get_active('acano')

        if not provider or not (provider.is_acano or provider.is_pexip):
            raise InvalidData('Customer has no video provider')

        provider.get_api(customer).sync_ldap(
            tenant_id=customer.tenant_id if customer.tenant_id else None
        )

        return {
                'status': 'OK',
        }


class APIDocs(ApiRequest):

    def dispatch(self, request, *args, **kwargs):

        Customer.objects.from_request(request)

        with open('%s/conferencecenter/docs.js' % settings.BASE_DIR) as fd:
            content = fd.read()

        data = {
            'content': content,
        }
        return render(request, 'provider/documentation.html', data)


@csrf_exempt
def meeting_rest(request, *args, **kwargs):

    if request.method == "POST":
        return Book.as_view()(request, *args, **kwargs)

    if not args:
        meeting_id = kwargs.get('meeting_id')
    else:
        meeting_id = args[0]

    Meeting.objects.get_by_id_key_or_404(request, meeting_id)

    if request.method == "GET":
        return MeetingDetailsView.as_view()(request, *args, **kwargs)
    elif request.method == "PUT":
        put = QueryDict(request.body)
        request.POST = put
        return ReBook.as_view()(request, *args, **kwargs)
    elif request.method == "DELETE":
        return UnBook.as_view()(request, *args, **kwargs)
    else:
        raise Http404()


class UserJidMixin:
    def _validate_and_get_user(
        self, request, allow_email_fallback=True
    ) -> Tuple[Dict, MCUProvider]:

        customer = Customer.objects.from_request(request, require_extended_key=True)

        user_jid = ''
        for k in ('user_jid', 'username'):
            user_jid = request.GET.get(k) or request.POST.get(k)
            if user_jid:
                break

        email = request.GET.get('email') or request.POST.get('email') or ''

        api = customer.get_api(allow_cached_values=True)
        if api.cluster.is_pexip:
            tenant_id = customer.get_pexip_tenant_id()
        else:
            tenant_id = customer.acano_tenant_id

        try:
            user = api.find_user(user_jid or '---', tenant=tenant_id or None)
            user.setdefault('jid', user.get('email'))
        except NotFound:
            if api.cluster.is_pexip and allow_email_fallback:
                result = self._get_fallback_pexip_email(api, email)
                if result:
                    return result
            raise Http404()
        return user, api

    def _get_fallback_pexip_email(self, api, email):
        from datastore.models.pexip import Conference

        if Conference.objects.search_active(
            api.cluster, tenant=api.get_tenant_id(api.customer), email__email=email
        ):
            return {'email': email, 'id': email, 'email_fallback': True}, api


class UserCospacesListView(UserJidMixin, ApiRequest):

    def dispatch(self, request, *args, **kwargs):

        user, api = self._validate_and_get_user(request)

        cospace_data = api.get_user_cospaces(user['id'], include_cospace_data=True)

        cospaces = [
            {
                'name': c['name'],
                'id': c['id'],
                'uri': c.get('uri') or c.get('full_uri'),
                'call_id': c.get('call_id', ''),
                'sip_uri': api.get_sip_uri(cospace=c),
                'web_url': api.get_web_url(cospace=c),
            }
            for c in cospace_data
        ]

        result = {
            'status': 'OK',
            'cospaces': cospaces
        }
        return result


class UserCospaceInviteMessage(UserJidMixin, ApiRequest):

    def dispatch(self, request, *args, **kwargs):

        user, api = self._validate_and_get_user(request)

        cospace_id = kwargs['cospace_id']

        for cospace in api.get_user_cospaces(user['id']):
            if str(cospace['id']) == cospace_id:
                break
        else:
            raise NotFound('Cospace {} not found for user {}'.format(cospace_id, user.get('jid') or user.get('email')))

        return user_cospace_response(api, cospace['id'])


def user_cospace_response(api, cospace_id, include_moderator_message=False):
    from ui_message.models import Message

    cospace = CoSpaceForm(cospace=cospace_id, customer=api.customer).load(customer=api.customer)

    message = Message.objects.get_for_cospace(api.customer, cospace['id']).copy()
    if message.get('attachment'):
        message['attachment'] = {
            'content': b64encode(message['attachment'].read()).decode(),
            'filename': message['attachment'].name,
        }
    else:
        message.pop('attachment', None)

    return {
        'status': 'OK',
        'message': message,
        'sip_uri': api.get_sip_uri(cospace=cospace),
        'web_url': api.get_web_url(cospace=cospace),
        'name': cospace['name'],
        'id': cospace['id'],
        'password': cospace.get('password') or '',
        'moderator_password': cospace.get('moderator_password'),
        'call_id': cospace.get('call_id', ''),
        'uri': cospace.get('uri', ''),
    }


class ChangeUserCoSpaceSettings(UserJidMixin, ApiRequest):
    def dispatch(self, request, *args, **kwargs):
        if request.method in ("POST", "PUT"):
            return self.change(request, *args, partial=False, **kwargs)
        elif request.method == "PATCH":
            return self.change(request, *args, partial=True, **kwargs)
        else:
            return HttpResponseBadRequest()

    def change(self, request, *args, partial=False, **kwargs):

        user, api = self._validate_and_get_user(request)

        enable_cospace_changes = False
        try:
            extended_key = Customer.objects.get_extended_key_from_request(request)
            if extended_key:
                api_key = Customer.objects.check_extended_key(extended_key)
                enable_cospace_changes = api_key.enable_cospace_changes
        except InvalidKey:
            pass

        if not enable_cospace_changes:
            raise InvalidKey(_('Meeting room changes are not activated for this API-key'))

        cospace_id = kwargs["cospace_id"]
        cospace = {}

        for cospace in api.get_user_cospaces(user["id"]):
            if str(cospace["id"]) == cospace_id:
                break
        else:
            raise NotFound(
                "Cospace {} not found for user {}".format(
                    cospace_id, user.get("jid") or user.get("email")
                )
            )

        from provider.api.generic.serializers import GenericCoSpaceUpdateSerializer

        if not request.POST:
            data = QueryDict(request.body)
        else:
            data = request.POST

        serializer = GenericCoSpaceUpdateSerializer(data=data, partial=partial)
        if not serializer.is_valid():
            raise InvalidData("Invalid cospace values", serializer.errors)

        try:
            api.update_cospace(cospace["id"], serializer.transform(api))
        except ResponseError as e:
            raise InvalidData(e.get_message(), e.get_all_errors())

        return user_cospace_response(
            api,
            cospace['id'],
            include_moderator_message=request.GET.get('include_moderator_message'),
        )


class UserInviteMessage(UserJidMixin, ApiRequest):

    def dispatch(self, request, *args, **kwargs):

        from ui_message.models import Message

        user, api = self._validate_and_get_user(request)

        cospace = api.get_user_private_cospace(user['id'])
        if not cospace:
            raise NotFound('Private vmr was not found for user')

        message = Message.objects.get_for_cospace(api.customer, cospace['id'], 'acano_user')
        if not message['content']:
            message = Message.objects.get_for_cospace(api.customer, cospace['id'])

        if message.get('attachment'):
            message['attachment'] = {
                'content': b64encode(message['attachment'].read()).decode(),
                'filename': message['attachment'].name,
            }
        else:
            message.pop('attachment', None)

        return {
            'status': 'OK',
            'message': message,
            'sip_uri': api.get_sip_uri(cospace=cospace),
            'web_url': api.get_web_url(cospace=cospace),
            'name': cospace['name'],
            'id': cospace['id'],
            'call_id': cospace.get('call_id', ''),
        }


class UserStatus(UserJidMixin, ApiRequest):

    def dispatch(self, request, *args, **kwargs):

        try:
            user, api = self._validate_and_get_user(request, allow_email_fallback=False)
            customer = api.customer
        except Http404:
            user = api = None
            customer = Customer.objects.from_request(request, require_extended_key=True)

        recording_provider = streaming_provider = None
        try:
            recording_provider = customer.get_recording_api()
            streaming_provider = customer.get_streaming_api()
        except AttributeError:
            pass

        private_cospace = api and api.cluster.is_acano
        if user and api.cluster.is_pexip:
            try:
                private_cospace = bool(api.get_user_private_cospace(user['id']))
            except NotFound:
                pass

        from endpoint.models import Endpoint
        if user and user.get("email"):

            private_endpoints = list(
                Endpoint.objects.filter(
                    customer=customer, owner_email_address=user["email"]
                ).values("title", "sip", "h323", "h323_e164")
            )
        else:
            private_endpoints = []

        return {
            "status": "OK",
            "user_exists": bool(user and not user.get("email_fallback")),
            "user_invite_exists": bool(private_cospace),
            "user_endpoints": list(private_endpoints),
            "enable_streaming": bool(streaming_provider and streaming_provider.provides_streaming),
            "enable_recording": bool(recording_provider and recording_provider.provides_recording),
            "enable_recording_playback": bool(
                recording_provider and recording_provider.provides_playback,
            ),
            "has_meeting_rooms": bool(
                user and api.get_user_cospaces(user["id"], include_cospace_data=False)
            ),
            "has_recordings": bool(
                user
                and AcanoRecording.objects.get_for_users([user.get("jid") or user.get("email")])
            ),
        }


class AddressBookSearch(UserJidMixin, ApiRequest):
    def dispatch(self, request, *args, **kwargs):

        try:
            user, api = self._validate_and_get_user(request, allow_email_fallback=False)
            customer = api.customer
        except Http404:
            customer = Customer.objects.from_request(request, require_extended_key=True)

        if not settings.ENABLE_EPM:
            return {}

        from endpoint.models import CustomerSettings

        address_book = CustomerSettings.objects.get_for_customer(
            customer
        ).default_portal_address_book

        if not address_book:
            return {}

        return addressbook_json_search(request, address_book)


def addressbook_json_search(request, address_book):

        offset = 0
        group = None
        limit = 20

        if request.GET.get("group"):
            try:
                group = int(request.GET["group"])
            except ValueError:
                pass

        groups, items = address_book.search(request.GET.get("q"), group_id=group)

        group_count = groups.only("id").count()
        item_count = items.only("id").count()

        if request.GET.get("offset"):
            try:
                offset = int(request.GET["offset"])
            except ValueError:
                pass
        if request.GET.get("limit"):
            try:
                limit = int(request.GET["limit"])
            except ValueError:
                pass

        items = items[offset : offset + limit]
        groups = groups[offset : offset + limit]

        return {
            "groups": list(groups.values("id", "title", "parent")),
            "items": list(items.values("id", "title", "sip", "h323", "h323_e164")),
            "group_count": group_count,
            "item_count": item_count,
        }


# just for unit tests
class ExceptionTestView(ApiRequest):

    def dispatch(self, request, *args, **kwargs):
        raise Exception('test')


class ResponseErrorTestView(ApiRequest):

    def dispatch(self, request, *args, **kwargs):
        raise ResponseError('Invalid response for test')


def celery_status(request):

    from provider.tasks import check_celery

    if check_celery():
        return HttpResponse('OK')
    return HttpResponse('ERROR', status=500)


def book_start(request):

    return HttpResponse('System up and running.')


