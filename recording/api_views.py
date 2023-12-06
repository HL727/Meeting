from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from django.utils.timezone import now

from provider.exceptions import InvalidKey
from .models import AcanoRecording
from rest_framework.decorators import api_view, permission_classes
from rest_framework.views import APIView
from rest_framework.response import Response
from django.conf import settings
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import AllowAny

from customer.models import Customer
from meeting.api_views import UserJidMixin


@api_view(['GET'])
@permission_classes((AllowAny, ))
def get_recording(request, secret_key):

    recording = get_object_or_404(AcanoRecording, secret_key=secret_key)

    shared_key = request.META.get('HTTP_X_MIVIDAS_TOKEN') or request.GET.get('shared_key')
    try:
        Customer.objects.check_extended_key(shared_key)
    except InvalidKey:
        if not request.user.is_staff:
            raise PermissionDenied()

    return Response({
        "title": recording.title,
        "cospace_id": recording.cospace_id,
        "call_id": recording.call_id,
        "call_leg_id": recording.call_leg_id,
        "tenant_id": recording.tenant_id,
        "path": recording.path,
        "targets": recording.targets,
    })


class RecordingInfoView(APIView):

    permission_classes = (AllowAny,)

    def get(self, request, secret_key, *args, **kwargs):

        from recording.models import AcanoRecording

        customer = Customer.objects.from_request(request)

        recording = get_object_or_404(AcanoRecording, secret_key=secret_key)

        video_url = recording.get_video_url(customer)

        result = {
            'status': 'OK',
            'recording': {
                'title': recording.title,
                'ts_start': recording.ts_start,
                'ts_stop': recording.ts_stop,
                'video_url': video_url,
            }
        }
        return Response(result)


class UserRecordingsListView(UserJidMixin, APIView):

    permission_classes = (AllowAny,)

    def get(self, request, *args, **kwargs):

        from recording.models import AcanoRecording
        user, api = self._validate_and_get_user(request)

        recordings = AcanoRecording.objects.get_for_users([user['jid']], request.GET.get('cospace_id'))

        result = {
            'status': 'OK',
            'recordings': [{
                'title': r.title,
                'ts_start': r.ts_start,
                'ts_stop': r.ts_stop,
                'secret_key': r.secret_key,
                'video_url': r.get_video_url(),
                'embed_code': r.get_embed_code(),
            } for r in recordings]
        }
        return Response(result)


def quickchannel_callback(request):
    data = {
        'ts': str(now()),
        'ip': request.META.get('REMOTE_ADDR', '127.0.0.1'),
        'get': request.GET.dict(),
        'rawpost': request.body.decode('utf-8'),
    }

    from compressed_store.utils import log_compressed
    log_compressed('quickchannel', data)

    return HttpResponse('OK')
