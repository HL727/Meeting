from rest_framework import routers

from .api_views import DemoGeneratorViewSet

router = routers.SimpleRouter()

router.register('demo-generator', DemoGeneratorViewSet, basename='demogenerator')

urlpatterns = router.urls
