from django.conf.urls import url
from django.http import HttpResponse

import statistics.views_cdr
from . import views

urlpatterns = [
    url(r'^cdr_receiver$', statistics.views_cdr.acano_cdr, name='cdr_receiver'),
    url(r'^cdr_receiver/(?P<secret_key>.+?)/?$', statistics.views_cdr.acano_cdr, name='cdr_receiver'),
    url(r'^status/up/$', lambda request: HttpResponse('OK')),
    url(r'^cdr/cms/(?P<secret_key>[^/]*)/?$', statistics.views_cdr.acano_cdr),
    url(r'^cdr/pexip/(?P<secret_key>[^/]*)/?$', statistics.views_cdr.pexip_cdr),
    url(r'^cdr/pexip/(?P<secret_key>[^/]*)/(?P<data_type>.*)/csv/$', statistics.views_cdr.pexip_csv),
    url(r'^cdr/csv/(?P<secret_key>[^/]*)/(?P<data_type>.*)/export/$', statistics.views_cdr.mividas_csv_export),
    url(r'^cdr/csv/(?P<secret_key>[^/]*)/(?P<data_type>.*)/import/$', statistics.views_cdr.mividas_csv_import_handler),

    url(r'^stats/?$', views.StatsVueView.as_view(), name='stats'),
    url(r'^analytics/?$', views.StatsVueView.as_view()),
    url(r'^analytics/calls/?$', views.StatsVueView.as_view()),
    url(r'^analytics/rooms/?$', views.StatsVueView.as_view()),
    url(r'^stats/old/?$', views.StatsView.as_view(), name='stats_old'),
    url(r'^stats/pdf/$', views.StatsPDFView.as_view(), name='stats_pdf'),
    url(r'^stats/excel/$', views.StatsExcelView.as_view(), name='stats_excel'),
    url(r'^stats/excel/debug/$', views.StatsDebugExcelView.as_view(), name='stats_excel_debug'),
    url(r'^stats/debug/(?P<type>call|leg)/(?P<guid>.*)/$', views.DebugView.as_view(), name='stats_debug'),
    url(r'^stats/debug/(?P<guid>.*)/$', views.DebugView.as_view(), {'type': 'call'}, name='stats_debug'),

    url(r'^epm/people_count/?$', views.StatsVueView.as_view()),
]
