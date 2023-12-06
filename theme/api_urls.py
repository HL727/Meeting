from rest_framework import routers
from .api_views import ThemeSettingsViewSet

router = routers.SimpleRouter()
router.register(r'themesettings', ThemeSettingsViewSet)

urlpatterns = router.urls
