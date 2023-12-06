from django.conf.urls import url
from meeting import views

urlpatterns = [
    url(r'^meeting/$', views.MeetingListApiView.as_view(), name='meetings_api'),
]
