from django.urls import include, path
from rest_framework import routers

from . import views
from .api_views import EndpointProxyStatusChangeViewSet, EndpointProxyViewSet

router = routers.SimpleRouter()
router.register(r'endpointproxy', EndpointProxyViewSet)
router.register(r'endpointproxy/status', EndpointProxyStatusChangeViewSet)

urlpatterns = [
    path('json-api/v1/', include(router.urls)),
    path('epm/proxy/', views.registration),
    path('epm/proxy/check_active/', views.check_active),
]
