from django.conf import settings
from django.urls import path

from .api_views import provider, status
from .api.generic.callcontrol import GenericCallViewSet, GenericCallLegViewSet
from .api.generic.user import GenericUserViewSet
from .api.generic.cospace import GenericCoSpaceViewSet

from rest_framework.routers import SimpleRouter

router = SimpleRouter()
router.register('cluster', provider.ClusterViewSet)
router.register('provider', provider.ProviderViewSet)

if settings.ENABLE_CORE:
    router.register('vcsprovider', provider.VCSProviderViewSet)
    router.register('recordingprovider', provider.RecordingProviderViewSet)

    router.register('cospace', GenericCoSpaceViewSet, basename='cospace')
    router.register('user', GenericUserViewSet, basename='user')
    router.register('calls', GenericCallViewSet, basename='calls')
    router.register('call_legs', GenericCallLegViewSet, basename='call_legs')

urlpatterns = [
    path('provider/load/', provider.ProviderLoadViewSet.as_view()),
    path('provider/status/', status.ProviderStatusAPIView.as_view()),
]
