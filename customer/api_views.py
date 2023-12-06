from rest_framework import viewsets, permissions
from django.http import Http404
from rest_framework.permissions import BasePermission

from shared.mixins import CreateRevisionViewSetMixin
from .serializers import CustomerSerializer, CustomerKeySerializer, CustomerMatchSerializer, \
    CustomerNameOnlySerializer, CustomerAdminSerializer

from customer.models import Customer, CustomerKey, CustomerMatch
from .utils import get_customers_from_request


class IsSuperUserOrListOnly(BasePermission):
    def has_permission(self, request, view):
        if request.user and request.user.is_superuser:
            return True
        action = getattr(view, 'action', None)
        return bool(request.user.is_authenticated and request.method == "GET" and action == "list")


class CustomerViewSet(CreateRevisionViewSetMixin, viewsets.ModelViewSet):

    permission_classes = [IsSuperUserOrListOnly]
    queryset = Customer.objects.all()
    serializer_class = CustomerSerializer

    def get_queryset(self):
        if self.request.user.is_superuser:
            return self.queryset.filter()  # dont filter to customer. use filter to clear cache

        if self.action == 'list':
            return Customer.objects.filter(pk__in=get_customers_from_request(self.request))

        return Customer.objects.none()

    def get_serializer_class(self):
        if not self.request.user.is_superuser:
            return CustomerNameOnlySerializer

        if self.request.user.is_superuser:
            return CustomerAdminSerializer

        return self.serializer_class

    def get_serializer_context(self):
        context = super().get_serializer_context()
        if self.request.user.is_superuser:
            context['usage_count'] = Customer.objects.get_usage_counts_cached()
        return context


class CustomerKeyViewSet(CreateRevisionViewSetMixin, viewsets.ModelViewSet):

    permission_classes = [permissions.IsAdminUser]
    queryset = CustomerKey.objects.all()
    serializer_class = CustomerKeySerializer

    def get_queryset(self):
        if not self.request.user.is_superuser:
            raise Http404()
        return self.queryset.filter()  # dont filter to customer. use filter to clear cache


class CustomerMatchViewSet(CreateRevisionViewSetMixin, viewsets.ModelViewSet):

    permission_classes = [permissions.IsAdminUser]
    serializer_class = CustomerMatchSerializer
    queryset = CustomerMatch.objects.order_by('priority', 'id')


