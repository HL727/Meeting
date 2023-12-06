import base64
import hashlib
import json

from django.conf import settings
from django.http import JsonResponse, HttpResponse
from django.shortcuts import redirect, get_object_or_404
from django.views.generic import TemplateView

from endpoint.models import Endpoint
from roomcontrol.docs import PackageSerializer
from roomcontrol.models import RoomControlFile, RoomControlTemplate, RoomControl, RoomControlDownloadLink, \
    RoomControlZipExport
from customer.view_mixins import LoginRequiredMixin, CustomerMixin
from .export import generate_roomcontrol_zip


class VueSPAView(LoginRequiredMixin, CustomerMixin, TemplateView):

    template_name = 'base_vue.html'

    def get(self, request, *args, **kwargs):
        if not settings.ENABLE_EPM or (self.customer and not self.customer.enable_epm):
            return redirect('/')
        return super().get(request, *args, **kwargs)


def zipfile(request, secret_key):
    dl = get_object_or_404(RoomControlZipExport, secret_key=secret_key)

    response = HttpResponse(dl.content, content_type="application/x-zip-compressed")
    response['Content-Disposition'] = 'attachment; filename={}.zip'.format(secret_key)
    return response


def package(request):

    if request.GET.get('dl'):
        dl = get_object_or_404(RoomControlDownloadLink, secret_key=request.GET['dl'])
        serializer = PackageSerializer(data=dl.serialize_url_params())
    else:
        serializer = PackageSerializer(data=request.GET)
    serializer.is_valid(raise_exception=True)

    url_files = serializer.validated_data.get('f')
    url_controls = serializer.validated_data.get('c')
    url_templates = serializer.validated_data.get('t')
    url_endpoint = serializer.validated_data.get('e')

    hash = serializer.validated_data.get('k')

    if hash != hashlib.sha224(
        ''.join([settings.SECRET_KEY, url_files or '', url_controls or '', url_templates or '', url_endpoint or '']).encode()
    ).hexdigest():
        return JsonResponse({
            'status': 'error',
            'error': 'Forbidden, no matching hash'
        }, status=401)

    files = []
    controls = []
    templates = []
    endpoint = None

    if url_files:
        files = RoomControlFile.objects.filter(id__in=json.loads(base64.b64decode(url_files)))
    if url_controls:
        controls = RoomControl.objects.filter(id__in=json.loads(base64.b64decode(url_controls)))
    if url_templates:
        templates = RoomControlTemplate.objects.filter(id__in=json.loads(base64.b64decode(url_templates)))
    if url_endpoint:
        endpoint = Endpoint.objects.filter(id=json.loads(base64.b64decode(url_endpoint))).first()

    filename, filecontent = generate_roomcontrol_zip('roomcontrols', files=files, controls=controls, templates=templates)

    response = HttpResponse(filecontent, content_type="application/x-zip-compressed")
    response['Content-Disposition'] = 'attachment; filename={}'.format(filename)

    if endpoint:
        if templates:
            endpoint.room_control_templates.add(*list(templates))
            endpoint.room_controls.add(*list(RoomControl.objects.distinct().filter(templates=templates)))
        if controls:
            endpoint.room_controls.add(*list(controls))

    return response
