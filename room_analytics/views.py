from datetime import timedelta
from django.utils.timezone import now

from room_analytics.forms import EPMCallStatsForm, HeadCountStatsForm
from statistics import views as stats
from statistics.utils.leg_collection import LegCollection
from statistics.view_mixins import CallStatisticsReportMixin


class EPMCallStatisticsReportMixin(CallStatisticsReportMixin):

    excel_url_name = 'endpoint_statistics_excel'
    debug_excel_url_name = 'endpoint_stats_excel_debug'
    pdf_url_name = 'stats_pdf'
    form_class = EPMCallStatsForm
    form: EPMCallStatsForm

    def get_graphs(self, legs: LegCollection, as_json=False, **kwargs):

        from statistics.graph import get_graph
        return {
            'graph': get_graph(legs, as_json=as_json, **kwargs),
        }



class EPMStatsView(EPMCallStatisticsReportMixin, stats.StatsView):
    pass


class EPMExcelView(EPMStatsView, stats.StatsExcelView):

    include_cospaces = False

    def get_graphs(self, legs: LegCollection, as_json=False, **kwargs):
        return {}


class EPMStatsDebugExcelView(EPMStatsView, stats.StatsDebugExcelView):

    def get_graphs(self, legs: LegCollection, as_json=False, **kwargs):
        return {}
