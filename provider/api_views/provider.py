from datetime import timedelta

from django.utils.timezone import now
from drf_yasg.utils import swagger_auto_schema, no_body
from rest_framework import permissions, viewsets, generics
from rest_framework.decorators import action
from rest_framework.response import Response

from customer.view_mixins import CustomerAPIMixin
from license import lock_license, license_allow_another
from license.api_helpers import license_validate_add
from provider.exceptions import ResponseError
from provider.models.provider import Cluster, VideoCenterProvider, Provider
from provider.models.vcs import VCSEProvider
from shared.mixins import CreateRevisionViewSetMixin
from shared.models import GlobalLock
from provider import docs
from provider.models.provider_data import ProviderLoad
from provider.serializers import ProviderLoadSerializer, ProviderSerializer, VCSProviderSerializer, \
    RecordingProviderSerializer, ClusterSerializer, ClusterAdminSerializer, ProviderAdminSerializer


class ProviderLoadViewSet(generics.ListAPIView):

    permission_classes = [permissions.IsAdminUser]
    serializer_class = ProviderLoadSerializer

    queryset = ProviderLoad.objects.none()

    def get_queryset(self):
        return ProviderLoad.objects.filter(ts_created__gt=now() - timedelta(days=2)).select_related('provider').order_by('ts_created')


class ProviderViewSet(CreateRevisionViewSetMixin, CustomerAPIMixin, viewsets.ModelViewSet):

    permission_classes = [permissions.IsAdminUser, permissions.DjangoModelPermissions]
    serializer_class = ProviderSerializer
    queryset = Provider.objects.all()

    def get_serializer_class(self):
        if self.request.user.is_superuser:
            return ProviderAdminSerializer
        return super().get_serializer_class()

    @lock_license('core:mcu')
    def create(self, request, *args, **kwargs):
        license_validate_add('core:mcu')
        return super().create(request, *args, **kwargs)

    @action(['POST'], detail=True)
    @swagger_auto_schema(request_body=no_body, responses={200: docs.StatusResponseSerializer()})
    def update_stats(self, request, pk=None):

        if not request.user.is_staff:
            return Response('', status=403)

        from provider import tasks
        if GlobalLock.is_locked('stats.update_provider_stats.{}'.format(self.get_object().pk)):
            return Response({'status': 'error', 'message': 'Already running'})
        tasks.update_provider_statistics.delay(self.get_object().pk)
        return Response({'status': 'OK', 'message': 'Running in background'})

    @action(['POST'], detail=True, permission_classes=[permissions.IsAdminUser])
    @swagger_auto_schema(
        request_body=no_body,
        query_serializer=docs.LdapSyncParamsSerializer,
        responses={200: docs.StatusResponseSerializer()},
    )
    def sync_ldap(self, request, pk=None):

        if not request.user.is_staff:
            return Response('', status=403)

        provider, api, tenant_id = self._get_dynamic_provider_api(self.get_object().pk)

        if self.request.GET.get('all') and self._has_all_customers():
            tenant_id = None

        try:
            api.sync_ldap(tenant_id=tenant_id)
        except ResponseError as e:
            return Response({'status': 'error', 'message': str(e)})

        return Response({'status': 'OK'})

    @action(['POST'], detail=True, permission_classes=[permissions.IsAdminUser])
    @swagger_auto_schema(request_body=no_body, responses={200: docs.StatusResponseSerializer()})
    def sync_profiles(self, request, pk=None):

        if not request.user.is_staff:
            return Response('', status=403)

        provider, api, tenant_id = self._get_dynamic_provider_api(self.get_object().pk)
        if not provider.is_acano:
            return Response({'status': 'error', 'message': 'Only available for CMS servers'})

        apis = [api] if not provider.is_cluster else list(api.iter_clustered_provider_api())
        errors = []
        for api in apis:
            try:
                api.sync_profiles()
            except ResponseError as e:
                errors.append(e)
        if errors:
            return Response({'status': 'error', 'message': '\n'.join(str(e) for e in errors)})
        return Response({'status': 'OK'})

    @action(['POST'], detail=True)
    @swagger_auto_schema(request_body=no_body, responses={200: docs.StatusResponseSerializer()})
    def remove_duplicates(self, request, pk=None):
        if not request.user.is_staff:
            return Response('', status=403)

        provider = self.get_object()

        server = (provider.cluster or provider).get_statistics_server()
        server.clean_duplicates()

        return Response({'status': 'OK', 'message': 'Running in background'})

    @action(['GET'], detail=True, url_path='related_policy_objects')
    @swagger_auto_schema(request_body=no_body, responses={200: None})
    def related_policy_objects(self, request, pk=None):

        return self.related_policy_objects_global(request)

    @action(['GET'], detail=False, url_path='related_policy_objects')
    @swagger_auto_schema(request_body=no_body, responses={200: None})
    def related_policy_objects_global(self, request, pk=None):

        provider, api, tenant_id = self._get_dynamic_provider_api(self.kwargs.get('pk'))
        if not provider.is_pexip:
            return Response({'message': 'Only available for pexip providers'}, status=400)

        return Response(api.get_related_policy_objects())


class ClusterViewSet(CreateRevisionViewSetMixin, viewsets.ModelViewSet):

    permission_classes = [permissions.IsAdminUser, permissions.DjangoModelPermissions]
    serializer_class = ClusterSerializer
    queryset = Cluster.objects.all()

    @lock_license('core:cluster')
    def create(self, request, *args, **kwargs):
        license_validate_add('core:cluster')
        return super().create(request, *args, **kwargs)

    def get_serializer_class(self):
        if self.request.user.is_superuser:
            return ClusterAdminSerializer
        return super().get_serializer_class()


class VCSProviderViewSet(CreateRevisionViewSetMixin, viewsets.ModelViewSet):

    permission_classes = [permissions.IsAdminUser, permissions.DjangoModelPermissions]
    serializer_class = VCSProviderSerializer
    queryset = VCSEProvider.objects.all()

    @action(['POST'], detail=True)
    @swagger_auto_schema(request_body=no_body, responses={200: docs.StatusResponseSerializer()})
    def update_stats(self, request, pk=None):
        from customer.models import Customer
        error = None
        try:
            self.get_object().get_api(Customer.objects.first()).update_stats(incremental=False)
        except Exception as e:
            error = str(e)
        return Response({'status': 'OK' if not error else 'error', 'error': error})


class RecordingProviderViewSet(CreateRevisionViewSetMixin, viewsets.ModelViewSet):

    permission_classes = [permissions.IsAdminUser, permissions.DjangoModelPermissions]
    serializer_class = RecordingProviderSerializer
    queryset = VideoCenterProvider.objects.all()

