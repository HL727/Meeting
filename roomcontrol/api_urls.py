from rest_framework import routers

from roomcontrol.api_views import RoomControlViewSet, RoomControlFileViewSet, RoomControlTemplateViewSet

router = routers.SimpleRouter()

router.register(r'roomcontrols', RoomControlViewSet)
router.register(r'roomcontrol_files', RoomControlFileViewSet)
router.register(r'roomcontrol_templates', RoomControlTemplateViewSet)

urlpatterns = router.urls
