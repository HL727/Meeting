from rest_framework import routers

from . import api_views as views

router = routers.SimpleRouter()
# router.register(r'endpointbranding/files/', views.BrandingFileViewSet)
router.register(r'endpointbranding', views.BrandingProfileViewSet)

urlpatterns = router.urls
