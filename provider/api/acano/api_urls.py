from rest_framework import routers
from .api_views import CoSpaceViewSet

router = routers.SimpleRouter()
router.register(r'cospace-acano', CoSpaceViewSet, 'cospace')

urlpatterns = router.urls
