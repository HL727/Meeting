from rest_framework import routers

from . import api_views

router = routers.SimpleRouter()
router.register('ews_calendar', api_views.CalendarViewSet)

urlpatterns = router.urls
