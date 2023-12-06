from rest_framework import routers

from endpoint_backup.api_views import EndpointBackupViewSet
from endpoint_provision.api_views import (
    EndpointFirmwareViewSet,
    EndpointTaskViewSet,
    EndpointTemplateViewSet,
)

from .api_views import CustomerSettingsViewSet, EndpointViewSet

router = routers.SimpleRouter()
router.register(r'endpoint', EndpointViewSet)
router.register(r'endpointbackup', EndpointBackupViewSet)
router.register(r'endpointfirmware', EndpointFirmwareViewSet)
router.register(r'endpointtemplate', EndpointTemplateViewSet)
router.register(r'endpointsettings', CustomerSettingsViewSet)
router.register(r'endpointtask', EndpointTaskViewSet)

urlpatterns = router.urls
