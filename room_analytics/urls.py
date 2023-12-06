from django.urls import path

from . import views


urlpatterns = [
    path('epm/statistics/calls/', views.EPMStatsView.as_view(), name='endpoint_statistics'),
    path('epm/statistics/rooms/', views.EPMStatsView.as_view(), name='endpoint_statistics_rooms'),
    path('epm/statistics/excel/', views.EPMExcelView.as_view(), name='endpoint_statistics_excel'),
    path('epm/statistics/excel/debug/', views.EPMStatsDebugExcelView.as_view(), name='endpoint_stats_excel_debug'),
]

