from django.urls import path
from rest_framework.routers import SimpleRouter

from statistics import api_views

router = SimpleRouter()
router.register(r'call_statistics', api_views.CallStatisticsViewSet, basename='call_statistics')
router.register(r'callstatistics_server', api_views.ServerViewSet, basename='callstatistics_server')


urlpatterns = [
    path('call_statistics/dashboard/', api_views.DashboardCallsStatistics.as_view()),
]

