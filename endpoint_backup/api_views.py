from django.http import FileResponse
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.generics import get_object_or_404
from rest_framework.mixins import DestroyModelMixin
from rest_framework.response import Response

from endpoint.view_mixins import CustomerRelationMixin
from endpoint_backup.models import EndpointBackup
from endpoint_backup.serializers import EndpointBackupSerializer
from endpoint_provision.models import EndpointProvision
from provider.exceptions import ResponseError


class EndpointBackupViewSet(CustomerRelationMixin, DestroyModelMixin, viewsets.ReadOnlyModelViewSet):

    serializer_class = EndpointBackupSerializer
    queryset = EndpointBackup.objects.all().select_related('endpoint')

    def get_queryset(self):
        queryset = super().get_queryset()
        if self.request.GET.get('endpoint'):
            from endpoint.models import Endpoint
            endpoint = get_object_or_404(Endpoint,
                                         pk=self.request.GET['endpoint'],
                                         customer=self._get_customer())
            return queryset.filter(endpoint=endpoint)
        return queryset

    @action(detail=True, methods=['POST'])
    def restore(self, request, pk=None):
        backup = self.get_object()
        if not backup.file:
            return Response({'status': 'error', 'message': 'No file available'}, status=400)

        endpoint = backup.endpoint
        try:
            result = backup.restore()
            EndpointProvision.objects.log(endpoint, 'restore_backup', self.request.user)
        except ResponseError as e:
            EndpointProvision.objects.log(endpoint, 'restore_backup', self.request.user, result=str(e), error=True)
            return Response({'status': 'error', 'message': str(e)})

        return Response({'status': 'OK', 'result': result})

    @action(detail=True)
    def download(self, request, pk=None):
        response = FileResponse(self.get_object().file)
        response['Content-Disposition'] = 'attachment; filename="{}"'.format(self.get_object().slug)
        return response
