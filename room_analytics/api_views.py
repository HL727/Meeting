from datetime import timedelta

from django.utils.timezone import now, localtime
from drf_yasg.utils import swagger_auto_schema
from rest_framework import views
from rest_framework.decorators import action
from rest_framework.response import Response

from customer.view_mixins import CustomerAPIMixin
from room_analytics.forms import EPMCallStatsForm, HeadCountStatsForm
from statistics.api_views import CallStatisticsViewSet
from statistics.serializers import CallStatisticsDataSerializer, HeadCountStatisticsSerializer, \
    HeadCountStatisticsResponseSerializer
from .serializers import EndpointRoomStatusSerializer
from .utils.report import GroupedHeadCountStats
from .views import EPMCallStatisticsReportMixin


class EPMCallStatisticsViewSet(EPMCallStatisticsReportMixin, CallStatisticsViewSet):

    form_class = EPMCallStatsForm

    @action(detail=False, methods=['GET'])
    @swagger_auto_schema(query_serializer=HeadCountStatisticsSerializer(), responses={200: HeadCountStatisticsResponseSerializer()})
    def head_count(self, request):
        print('==============HEAD COUNT==========')
        serializer = HeadCountStatisticsSerializer(data=request.GET, context={
            **self.get_serializer_context(),
            'form_class': None,
        })
        serializer.is_valid(raise_exception=True)

        graphs = self.get_head_count_graphs(serializer.form)
        return Response(HeadCountStatisticsResponseSerializer({
            'graphs': graphs,
            'loaded': True,
            'has_data': any(isinstance(v, dict) and not v.get('empty') for v in graphs.values()),
        }).data)

    def get_head_count_graphs(self, form: HeadCountStatsForm):
        from room_analytics.utils.report import GroupedHeadCountStats

        endpoints = form.cleaned_data['endpoints']
        now_grouper = GroupedHeadCountStats(endpoints, now() - timedelta(hours=2), now())

        return {
            **form.get_all_individual_graphs(),
            'now': now_grouper.get_invididual_graph('now', ignore_empty=True, as_json=True),
        }

    def allow_debug_stats(self, form=None):
        from endpoint.models import CustomerSettings

        if self.request.user.is_staff:
            return True

        c_settings = CustomerSettings.objects.get_for_customer(self._get_customer())
        if form is None:  # await real form
            return None if c_settings.enable_user_debug_statistics else False
        return c_settings.enable_user_debug_statistics

    @action(detail=False, methods=['GET'])
    def endpoint_status(self, request):

        from endpoint.models import EndpointStatus
        status = EndpointStatus.objects.filter(endpoint__customer=self.customer).select_related('active_meeting', 'active_meeting__meeting')
        return Response(EndpointRoomStatusSerializer(status, many=True).data)


class DashboardRoomsStatistics(CustomerAPIMixin, views.APIView):

    @swagger_auto_schema(responses={200: CallStatisticsDataSerializer})
    def get(self, request):
        return Response({
            'graphs': self.get_graphs()
        })

    def get_form(self):
        customer = self._get_customer()

        form = HeadCountStatsForm({'multitenant': True}, self.request.GET, user=self.request.user, customer=customer)
        form.is_valid()
        return form

    def get_graphs(self):
        form = self.get_form()

        now_grouper = GroupedHeadCountStats(
            [], now() - timedelta(hours=1), now()
        )  # TODO: fix real data

        c = form.cleaned_data

        ts_start = c.get('ts_start') or localtime().replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=6)

        graph_grouper = GroupedHeadCountStats(form.cleaned_data['endpoints'], ts_start, c.get('ts_stop') or now(),
                                              only_days=c['only_days'], only_hours=c['only_hours'])
        graph_kwargs = dict(as_percent=c.get('as_percent'), ignore_empty=c.get('ignore_empty', False), fill_gaps=c.get('fill_gaps', False), as_json=True)

        return {
            'now': now_grouper.get_graph('now', ignore_empty=True, as_json=True),
            # **self.form.get_headcount_graphs(form.cleaned_data['endpoints']),
            'per_hour': graph_grouper.get_sum_max_values_graph('hour_single', **graph_kwargs),
            'per_day': graph_grouper.get_sum_max_values_graph('date_single', **graph_kwargs),
        }
