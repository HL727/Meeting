
from rest_framework.routers import SimpleRouter

from policy_auth import api_views

router = SimpleRouter()
router.register('policy_authorization_override', api_views.PolicyAuthorizationOverrideViewSet)
router.register('policy_authorization', api_views.PolicyAuthorizationViewSet)

urlpatterns = [
]

