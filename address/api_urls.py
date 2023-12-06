from django.urls import path, include
from rest_framework import routers
from . import api_views

router = routers.SimpleRouter()
router.register(r'addressbook', api_views.AddressBookViewSet)
router.register(r'addressbook_group', api_views.GroupViewSet)
router.register(r'addressbook_item', api_views.ItemViewSet)


urlpatterns = [
    path('json-api/v1/', include(router.urls)),
]
