from django.conf import settings
from rest_framework import routers
from .api_views import CustomerViewSet, CustomerKeyViewSet, CustomerMatchViewSet

router = routers.SimpleRouter()
router.register(r'customer', CustomerViewSet)
router.register(r'customerkey', CustomerKeyViewSet)

if settings.ENABLE_CORE:
    router.register(r'customer_match', CustomerMatchViewSet)

urlpatterns = router.urls

