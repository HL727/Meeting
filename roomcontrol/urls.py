from django.urls import re_path

from . import views

urlpatterns = [
    re_path('^epm/roomcontrol/package/?$', views.package, name='roomcontrol-package'),
    re_path('^epm/roomcontrol(?:/|$)', views.VueSPAView.as_view()),
    re_path('^tms/roomcontrol/(?P<secret_key>.*).zip$', views.zipfile, name='roomcontrol-zip'),
]

