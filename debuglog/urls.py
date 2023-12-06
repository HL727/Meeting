from django.urls import re_path
from . import views

urlpatterns = [
    re_path('^debug(?:/|$)', views.VueSPAView.as_view()),
]

