
from django.http import JsonResponse, HttpResponse
from drf_yasg import openapi
from drf_yasg.utils import swagger_auto_schema
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django.utils.translation import gettext_lazy as _

from endpoint.view_mixins import CustomerRelationMixin
from .docs import ExportUrlResponseSerializer, ExportRoomControlSerializer
from .export import get_export_url
from .models import RoomControl, RoomControlFile, RoomControlTemplate
from .serializers import RoomControlSerializer, RoomControlFileSerializer, RoomControlUpdateSerializer, \
    RoomControlTemplateSerializer, RoomControlTemplateCreateSerializer, RoomControlExportUrlSerializer, \
    RoomControlAddFilesSerializer


class RoomControlFileViewSet(CustomerRelationMixin, viewsets.ModelViewSet):

    serializer_class = RoomControlFileSerializer
    queryset = RoomControlFile.objects.none()

    def get_queryset(self):
        return RoomControlFile.objects.filter(control__customer=self._get_customer())

    def perform_create(self, serializer):
        instance = serializer.save(orig_file_name=serializer.validated_data['file'].name)
        instance.control.export_zip_all()
        return instance

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        control = RoomControlSerializer(instance.control, context={'request': request})
        self.perform_destroy(instance)
        instance.control.export_zip_all()
        return Response(control.data, status=status.HTTP_200_OK)


class RoomControlViewSet(CustomerRelationMixin, viewsets.ModelViewSet):

    serializer_class = RoomControlSerializer
    queryset = RoomControl.objects.all()

    def get_serializer_class(self):
        if self.action in ('create', 'update'):
            return RoomControlUpdateSerializer
        return self.serializer_class

    @swagger_auto_schema(request_body=RoomControlExportUrlSerializer, responses={200: ExportUrlResponseSerializer})
    @action(detail=False, methods=['POST'])
    def get_export_url(self, request):
        serializer = RoomControlExportUrlSerializer(data=request.data, context=self.get_serializer_context())
        serializer.is_valid(raise_exception=True)

        files = RoomControlFile.objects.filter(control__in=serializer.validated_data['controls']).order_by('pk')

        export_url = get_export_url(customer=self._get_customer(), files=files)

        result = {
            'status': 'OK',
            'url': export_url,
        }

        return JsonResponse(result, status=200)

    @swagger_auto_schema(
        query_serializer=ExportRoomControlSerializer,
        responses={200: openapi.Response(_('File attachment'), schema=openapi.Schema(type=openapi.TYPE_FILE))}
    )
    @action(detail=True, methods=['GET'])
    def export(self, request, pk=None):
        instance = self.get_object()

        file_ids = request.GET.get('files', '')

        if file_ids:
            files = instance.files.filter(pk__in=file_ids.split(','))
        else:
            files = instance.files.all()

        filename, filecontent = instance.get_zip_content(files)

        response = HttpResponse(filecontent, content_type="application/x-zip-compressed")
        response['Content-Disposition'] = 'attachment; filename={}'.format(filename)

        return response

    @swagger_auto_schema(
        request_body=RoomControlAddFilesSerializer,
        responses={200: RoomControlSerializer}
    )
    @action(detail=True, methods=['POST'])
    def add_files(self, request, pk=None):
        instance = self.get_object()

        serializer = RoomControlAddFilesSerializer(instance, data=request.data,
                                                   context=self.get_serializer_context())

        serializer.is_valid(raise_exception=True)

        serializer.save()

        return Response(self.get_serializer(instance).data, status=status.HTTP_201_CREATED)

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop('partial', False)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)

        if getattr(instance, '_prefetched_objects_cache', None):
            # If 'prefetch_related' has been applied to a queryset, we need to
            # forcibly invalidate the prefetch cache on the instance.
            instance._prefetched_objects_cache = {}

        response_serializer = RoomControlSerializer(instance, context=serializer.context)

        return Response(response_serializer.data)

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        instance = serializer.save(customer=self._get_customer())

        response_serializer = RoomControlSerializer(instance, context=serializer.context)

        headers = self.get_success_headers(response_serializer.data)
        return Response(response_serializer.data, status=status.HTTP_201_CREATED, headers=headers)


class RoomControlTemplateViewSet(CustomerRelationMixin, viewsets.ModelViewSet):
    serializer_class = RoomControlTemplateSerializer
    queryset = RoomControlTemplate.objects.all()

    def get_serializer_class(self):
        if self.action in ('create', 'update'):
            return RoomControlTemplateCreateSerializer
        return self.serializer_class

    @swagger_auto_schema(
        responses={200: openapi.Response(_('File attachment'),
                    schema=openapi.Schema(type=openapi.TYPE_FILE))}
    )
    @action(detail=True, methods=['GET'])
    def export(self, request, pk=None):
        filename, filecontent = self.get_object().get_zip_content()

        response = HttpResponse(filecontent, content_type="application/x-zip-compressed")
        response['Content-Disposition'] = 'attachment; filename={}'.format(filename)

        return response

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        serializer.save(customer=self._get_customer())

        headers = self.get_success_headers(serializer.data)
        return Response(serializer.data, status=status.HTTP_201_CREATED, headers=headers)
