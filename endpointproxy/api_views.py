from ipaddress import IPv4Interface

from django.db.models import Max, Q
from rest_framework import permissions, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from endpoint.view_mixins import CustomerRelationMixin
from endpointproxy.models import EndpointProxy, EndpointProxyIPNet, EndpointProxyStatusChange
from endpointproxy.serializers import (
    EndpointProxyEditSerializer,
    EndpointProxySerializer,
    EndpointProxyStatusChangeSerializer,
    EndpointProxyStatusSerializer,
)


class EndpointProxyViewSet(CustomerRelationMixin, viewsets.ModelViewSet):

    queryset = EndpointProxy.objects.all()
    permission_classes = [permissions.IsAuthenticated & permissions.DjangoModelPermissions]

    def get_queryset(self):
        if self.request.user.is_staff:
            return self.queryset.filter(Q(customer=self._get_customer()) | Q(customer__isnull=True))
        return self.queryset.filter(customer=self._get_customer())

    def create(self, request, *args, **kwargs):
        return Response(status=403)

    def get_serializer_class(self):
        if not self.request.user.is_staff:
            return EndpointProxyStatusSerializer
        if self.action in ('update', 'partial_update'):
            return EndpointProxyEditSerializer
        return EndpointProxySerializer

    def perform_update(self, serializer):

        ip_nets = serializer.validated_data.pop('ip_nets', [])
        obj = serializer.save(ip_nets=[], customer=self.get_object().customer or self._get_customer())
        if not obj.ts_activated:
            obj.activate()

        def _clean(net):
            try:
                return IPv4Interface(net.replace('*.*', '.0.0/20').replace('.*', '.0/24')).network
            except ValueError:
                return None

        ip_nets = list(map(_clean, ip_nets))

        for net in ip_nets:
            if not net:
                continue

            EndpointProxyIPNet.objects.get_or_create(proxy=self.get_object(), ip_net=net)

        EndpointProxyIPNet.objects.filter(proxy=self.get_object()).exclude(ip_net__in=ip_nets).delete()

    @action(detail=True, methods=['POST'])
    def activate(self, request, pk=None):

        proxy = self.get_object()
        if request.data.get('name'):
            proxy.name = request.data['name']
        proxy.customer = proxy.customer or self._get_customer()
        proxy.activate()

        return Response(EndpointProxySerializer(proxy).data)


class EndpointProxyStatusChangeViewSet(CustomerRelationMixin, viewsets.ReadOnlyModelViewSet):

    serializer_class = EndpointProxyStatusChangeSerializer
    queryset = EndpointProxyStatusChange.objects.all().order_by('-ts_created')

    def get_queryset(self):
        queryset = self.queryset  # note: not super(), customer is only set on proxy-fk
        if self.request.GET.get('proxy'):
            queryset = queryset.filter(proxy=self.request.GET['proxy'])
        if self.request.user.is_staff:
            return queryset.filter(
                Q(proxy__customer=self._get_customer()) | Q(proxy__customer__isnull=True)
            )
        return queryset.filter(proxy__customer=self._get_customer())

    @action(detail=False, methods=['GET'])
    def per_proxy(self, request):

        latest_ids = self.get_queryset().order_by().values_list('proxy_id').annotate(m=Max('id'))
        queryset = self.get_queryset().filter(id__in=(pid[1] for pid in latest_ids))

        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['GET'])
    def latest(self, request):
        queryset = self.get_queryset().order_by('-ts_created')[:10]

        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)

