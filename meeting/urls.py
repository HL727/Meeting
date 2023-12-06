from django.conf.urls import url
from django.shortcuts import redirect

from shared.views import VueSPAView
from meeting import views

urlpatterns = [
    url(r'^meeting/$', views.MeetingList.as_view(), name='meetings'),
    url(r'^meeting/list/$', lambda request: redirect('meetings'), name='meeting_debug_list'),
    url(r'^meeting/add/$', views.BookMeetingView.as_view(), name='meeting_add'),
    url(r'^meeting/(?P<meeting_id>\d+)/$', views.MeetingDebugDetails.as_view(), name='meeting_debug_details'),
    url(r'^epm/bookings/$', VueSPAView.as_view(), name='epm_bookings'),
    url(r'^epm/meeting/(?P<meeting_id>\d+)/$', views.MeetingDebugDetails.as_view(), name='meeting_debug_details_epm'),
    url(r'^meeting/(?P<meeting_id>\d+)/invite/$', views.MeetingInviteView.as_view(), name='meeting_invite'),
]
