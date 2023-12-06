from rest_framework import routers
from .api_views import ConferenceViewSet, EndUserViewSet

router = routers.SimpleRouter()
router.register(r'cospace-pexip', ConferenceViewSet, 'cospace-pexip')
router.register(r'user-pexip', EndUserViewSet, 'user-pexip')

urlpatterns = [
]
