import json
from typing import Union

import reversion
import sentry_sdk
from django.conf import settings
from django.http import HttpResponse, Http404, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from sentry_sdk import capture_exception

from license import license, get_license
from provider.exceptions import InvalidKey, InvalidData, ResponseError, AuthenticationError, NotFound
from provider.forms import CoSpaceForm
from provider.models.acano import CoSpace

RERAISE_ERRORS = settings.DEBUG or getattr(settings, 'TEST_MODE', False)


def meeting_response(meeting, message_format='rtf'):
    result = {'status': 'OK'}
    result.update(meeting.as_dict(message_format=message_format))
    return result


def cospace_response(cospace_id, customer):
    from ui_message.models import Message
    result = {'status': 'OK'}

    form = CoSpaceForm(cospace=cospace_id)

    meeting = form.get_temp_meeting(customer)
    message = Message.objects.get_by_type(type=Message.TYPES.acano_cospace, customer=customer)

    invite_message = message.format(meeting)

    result.update(form.load(customer, include_members=True))

    obj = CoSpace.objects.get(customer=customer, provider_ref=cospace_id)

    result['message_title'] = message.title
    result['message'] = invite_message
    result['id'] = obj.id_key
    result['rest_url'] = obj.get_api_url()

    return result


class ApiRequest:

    def json_response(self, data, **kwargs):

        if not isinstance(data, str):
            data = json.dumps(data)

        return HttpResponse(data, **{**kwargs, "content_type": "application/json"})

    def dispatch(self, request, *args, **kwargs) -> Union[HttpResponse, dict]:
        self.request = request

        if request.method != 'GET' and not get_license().has_flag('core:enable_core'):
            return JsonResponse(
                {
                    'status': 'error',
                    'error': 'License is missing or has expired',
                },
                status=403,
            )
        if request.method == "POST" and hasattr(self, 'post'):
            return self.post(*args, **kwargs)
        elif request.method == "PUT" and hasattr(self, "put"):
            return self.put(*args, **kwargs)
        elif request.method == "PATCH" and hasattr(self, "patch"):
            return self.patch(*args, **kwargs)
        elif request.method == "DELETE" and hasattr(self, "delete"):
            return self.delete(*args, **kwargs)
        elif hasattr(self, 'get'):
            return self.get(*args, **kwargs)

        raise Http404()

    @classmethod
    def as_view(cls):

        @reversion.create_revision()
        @csrf_exempt
        def handle(request, *args, **kwargs):

            obj = cls()

            try:
                result = obj.dispatch(request, *args, **kwargs)
            except InvalidKey as e:
                return obj.json_response(
                    {
                        "status": "Error",
                        "type": "InvalidKey",
                        "message": str(e),
                    },
                    status=403,
                )
            except InvalidData as e:
                with sentry_sdk.push_scope() as scope:
                    scope.set_extra('fields', e.fields)
                    capture_exception()

                return obj.json_response(
                    {
                        "status": "Error",
                        "type": "InvalidData",
                        "message": str(e),
                        "fields": e.fields,
                    },
                    status=400,
                )
            except (NotFound, Http404) as e:
                if e.args and isinstance(e.args[0], str):
                    return JsonResponse({'status': 'Error', 'message': e.args[0]}, status=404)
                return HttpResponse(str(e), status=404)
            except Exception as e:
                return obj._handle_other_errors(request, e)
            else:
                if isinstance(result, HttpResponse):
                    return result
                return obj.json_response(result)

        return handle

    def _handle_other_errors(self, request, e: Exception):
        if isinstance(e, (ResponseError, AuthenticationError)):
            data = {}
            if len(e.args) > 1:
                data = e.args[1]
                import requests
                if isinstance(data, requests.Response):
                    data = {
                        'request': dict(data.request.headers),
                        'response': dict(data.headers),
                    }

                elif hasattr(data, 'to_dict'):
                    data = data.to_dict()
                elif not isinstance(data, dict):
                    data = str(data)

            with sentry_sdk.push_scope() as scope:
                scope.set_extra('data', data)
                capture_exception()

            if RERAISE_ERRORS and request.path != '/test/':
                raise
            return self.json_response(
                {
                    "status": "Error",
                    "type": "ResponseError",
                    "message": str(e),
                },
                status=400,
            )
        else:
            capture_exception()

            if RERAISE_ERRORS and request.path != '/test/':
                raise
            return self.json_response(
                {
                    "status": "Error",
                    "type": "Unhandled",
                    "message": str(e),
                },
                status=500,
            )
