from rest_framework import routers

from . import api_views

router = routers.SimpleRouter()
router.register('msgraph_oauth', api_views.OAuthCredentialViewSet)

urlpatterns = router.urls
