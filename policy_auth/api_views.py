import django_filters
from rest_framework import viewsets

from endpoint.view_mixins import CustomerRelationMixin
from policy_auth.models import PolicyAuthorizationOverride, PolicyAuthorization
from policy_auth.serializers import PolicyAuthorizationOverrideSerializer, PolicyAuthorizationSerializer


class WhitelistFilter(django_filters.FilterSet):
    class Meta:
        model = PolicyAuthorizationOverride
        fields = {
            'customer': ['exact'],
            'cluster': ['exact'],
        }


class PolicyAuthorizationOverrideViewSet(CustomerRelationMixin, viewsets.ModelViewSet):

    queryset = PolicyAuthorizationOverride.objects.all().select_related('customer')
    serializer_class = PolicyAuthorizationOverrideSerializer
    filterset_class = WhitelistFilter


class AuthorizationFilter(django_filters.FilterSet):
    class Meta:
        model = PolicyAuthorization
        fields = {
            'customer': ['exact'],
            'cluster': ['exact'],
            'local_alias': ['exact', 'startswith'],
            'valid_from': ['lt', 'gt', 'lte', 'gte'],
            'valid_to': ['lt', 'gt', 'lte', 'gte'],
            'source': ['exact'],
            'external_id': ['exact'],
        }


class PolicyAuthorizationViewSet(CustomerRelationMixin, viewsets.ModelViewSet):

    queryset = PolicyAuthorization.objects.all().select_related('customer')
    serializer_class = PolicyAuthorizationSerializer
    filterset_class = AuthorizationFilter

    def perform_create(self, serializer):
        return serializer.save()  # dynamic customer depending on match

