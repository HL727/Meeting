from django.urls import re_path
from . import views

urlpatterns = [
    re_path(r'^recording/(?P<secret_key>[^/]+)/', views.RecordingView.as_view(), name='recording')
]