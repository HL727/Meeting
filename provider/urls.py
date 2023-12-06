from django.urls import path

from shared.views import VueSPAView

urlpatterns = [
    path('epm/admin/provider/', VueSPAView.as_view(), name='cloud_dashboard_epm'),
    path('core/admin/provider/', VueSPAView.as_view(), name='provider_dashboard'),
]
