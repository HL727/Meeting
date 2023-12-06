from django.urls import path

from . import views
from shared.views import VueSPAView

urlpatterns = [
    path('tms/soap/<address_book_key>/', views.tms_soap),
    path('tms/addressbook/<address_book_key>/search/', views.tms_soap),
    path('epm/addressbook/', VueSPAView.as_view(), name='addressbook_list'),
    path('epm/addressbook/<addressbook_id>/', VueSPAView.as_view(), name='addressbook_details'),
]
