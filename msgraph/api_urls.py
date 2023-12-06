from rest_framework import routers

from . import api_views

router = routers.SimpleRouter()
router.register('msgraph_credentials', api_views.MSGraphCredentialsViewSet)

urlpatterns = router.urls
