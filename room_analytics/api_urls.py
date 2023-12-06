from django.urls import path
from rest_framework.routers import SimpleRouter

from room_analytics import api_views

router = SimpleRouter()
router.register(r'room_statistics', api_views.EPMCallStatisticsViewSet, basename='room_statistics')

urlpatterns = [
    path('room_statistics/dashboard/', api_views.DashboardRoomsStatistics.as_view()),
]

