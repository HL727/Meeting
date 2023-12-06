from django.urls import path

from . import views

urlpatterns = [
    path('core/admin/settings/', views.VueSPAView.as_view(), name='settings'),
]

