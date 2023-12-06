from django.urls import re_path
from . import views

urlpatterns = [
    re_path('^core/admin/demo-generator(?:/|$)', views.VueSPAView.as_view()),
    re_path('^epm/admin/demo-generator(?:/|$)', views.VueSPAView.as_view()),
]
