from django.urls import path, include
from rest_framework import routers
from . import api_views

router = routers.SimpleRouter()
router.register(r'organizationunit', api_views.OrganizationUnitViewSet)


urlpatterns = [
    path('json-api/v1/', include(router.urls)),
]