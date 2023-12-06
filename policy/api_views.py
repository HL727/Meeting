from datetime import timedelta

from django.utils.timezone import now
from drf_yasg.utils import swagger_auto_schema
from rest_framework import permissions, viewsets, pagination
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView

from debuglog.models import PexipEventLog, PexipHistoryLog
from policy.docs import PolicyReportResponseSerializer
from policy.models import CustomerPolicy, CustomerPolicyState, PolicyLog, ExternalPolicyLog, ActiveParticipant
from policy.serializers import PolicySerializer, CustomerPolicySerializer, CustomerPolicyStateSerializer, \
    CustomerPolicyLimitSerializer, ExternalPolicyLogSerializer, PolicyLogSerializer, \
    ActiveParticipantSerializer, LegDebugFilterSerializer, LegDebugSerializer
from policy.utils import create_from_statistics, report_to_graphs
from shared.serializers import rest_filterset_factory


class PolicyReportView(APIView):

    permission_classes = [permissions.IsAdminUser]

    @swagger_auto_schema(query_serializer=PolicySerializer(many=True), responses={200: PolicyReportResponseSerializer(many=True)})
    def get(self, request):

        serializer = PolicySerializer(data=request.GET)
        if not serializer.is_valid():
            return Response(serializer.errors, status=400)

        result = create_from_statistics(user=request.user, **serializer.validated_data)

        if serializer.validated_data.get('as_graph'):
            result = report_to_graphs(result)
        else:
            result = dict(zip(('soft_limit', 'soft_limit_30', 'hard_limit', 'count'), result))

        return Response(result)


class CustomerPolicyViewSet(viewsets.ModelViewSet):

    permission_classes = [permissions.IsAdminUser]
    queryset = CustomerPolicy.objects.all().select_related('customer')
    serializer_class = CustomerPolicySerializer

    @action(detail=False, methods=['GET'])
    @swagger_auto_schema(responses={200: CustomerPolicyLimitSerializer(many=True)})
    def limits(self, request):
        context = {
            **self.get_serializer_context(),
            'states': {p.customer_id: p for p in CustomerPolicyState.objects.all()}
        }

        serializer = CustomerPolicyLimitSerializer(self.get_queryset(), context=context, many=True)

        return Response(serializer.data)


class CustomerPolicyStateViewSet(viewsets.ReadOnlyModelViewSet):

    permission_classes = [permissions.IsAdminUser]
    queryset = CustomerPolicyState.objects.all().order_by('-active_participants')
    serializer_class = CustomerPolicyStateSerializer


# Debug logs


class Paginator(pagination.LimitOffsetPagination):
    default_limit = 100
    max_limit = 300


filter_fields = {
    'message': ['exact', 'contains', 'icontains'],
    'cluster': ['exact'],
    'customer': ['exact'],
    'id': ['gt'],
    'ts': ['gt', 'lt', 'gte', 'lte'],

}

class PolicyLogViewSet(viewsets.ReadOnlyModelViewSet):

    permission_classes = [permissions.IsAdminUser]
    queryset = PolicyLog.objects.all().order_by('-ts')
    serializer_class = PolicyLogSerializer
    pagination_class = Paginator
    filterset_class = rest_filterset_factory(PolicyLog, {**filter_fields, 'guid': ['exact']})


class ExternalPolicyLogViewSet(viewsets.ReadOnlyModelViewSet):

    permission_classes = [permissions.IsAdminUser]
    queryset = ExternalPolicyLog.objects.all().order_by('-ts')
    serializer_class = ExternalPolicyLogSerializer
    pagination_class = Paginator
    filterset_class = rest_filterset_factory(ExternalPolicyLog, filter_fields)


class ActiveParticipantViewSet(viewsets.ReadOnlyModelViewSet):

    permission_classes = [permissions.IsAdminUser]
    queryset = ActiveParticipant.objects.all().order_by('-ts_created')
    serializer_class = ActiveParticipantSerializer


class LegDebugInfo(APIView):

    permission_classes = [permissions.IsAdminUser]

    @swagger_auto_schema(query_serializer=LegDebugFilterSerializer, responses={200: LegDebugSerializer(many=True)})
    def get(self, request):

        serializer = LegDebugFilterSerializer(data=request.GET)
        serializer.is_valid()

        guid = serializer.validated_data['guid']
        ts = serializer.validated_data.get('ts_start') or now() - timedelta(days=7)

        from statistics.models import Leg
        legs = {l.pk: l for l in Leg.objects.filter(conversation__guid=guid).union(Leg.objects.filter(guid=guid))}.values()

        return Response({
            'legs': [{f.name: getattr(l, f.name) for f in Leg._meta.fields if not f.is_relation} for l in legs],
            'cdr': [{**e.content_json, 'ts': e.ts_created} for e in PexipEventLog.objects.filter(ts_created__gt=ts, statistics_legs__in=legs).order_by('ts_created')],
            'history': [{**o, 'ts': h.ts_created} for h in PexipHistoryLog.objects.filter(ts_created__gt=ts, statistics_legs__in=legs).order_by('ts_created') for o in h.find_objects(guid=guid)],
        })

