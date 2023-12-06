from rest_framework import routers

from . import api_views

router = routers.SimpleRouter()
router.register('ews_credentials', api_views.EWSCredentialsViewSet)

urlpatterns = router.urls
