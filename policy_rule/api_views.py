from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet

from customer.utils import get_customer_from_request
from datastore.models.pexip import Conference
from policy_rule.models import PolicyRule, get_matching_rules
from policy_rule.serializers import PolicyRuleSerializer, PolicyRuleTraceResponseSerializer, \
    PolicyRuleTraceSerializer
from provider.api.generic.mixins import DynamicAPIMixin


class PolicyRuleViewSet(DynamicAPIMixin, ModelViewSet):

    queryset = PolicyRule.objects.none()
    serializer_class = PolicyRuleSerializer

    def _get_customer(self):
        return get_customer_from_request(self.request)

    def get_queryset(self):
        try:
            return PolicyRule.objects.filter(cluster=self._get_api().cluster)
        except AttributeError:
            return PolicyRule.objects.none()

    def get_serializer_context(self):
        if getattr(self, 'swagger_fake_view', False):
            return super().get_serializer_context()

        return {
            **super().get_serializer_context(),
            'cluster': self._get_api().cluster,
        }

    @action(detail=False, methods=['POST'])
    def sync(self, request, *args, **kwargs):
        PolicyRule.objects.sync_down(self._get_api().cluster)
        return self.list(request, *args, **kwargs)

    @action(detail=False, methods=['GET', 'POST'])
    def trace(self, request, *args, **kwargs):

        serializer = PolicyRuleTraceSerializer(data=request.data or request.GET, context=self.get_serializer_context())
        if not serializer.is_valid():
            return Response(serializer.errors, status=400)

        cluster = self._get_api().cluster

        conference = Conference.objects.match(serializer.validated_data, cluster=cluster)
        rules = get_matching_rules(cluster, **serializer.validated_data)

        result = {
            'conference': conference,
            'rules': rules,
        }
        return Response(PolicyRuleTraceResponseSerializer(result).data)


