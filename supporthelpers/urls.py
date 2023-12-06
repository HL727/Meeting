from django.conf.urls import url
from django.shortcuts import redirect

from shared.views import VueSPAView
from .views import users
from .views import base
from .views import cospace as cospace
from .views import callcontrol as calls
from .views import admin as admin
from .views import webinar as webinar
from .views import rest as rest


def redirect_to(target):
    def _inner_redirect(request, **kwargs):
        return redirect(target, **kwargs)
    return _inner_redirect


urlpatterns = [

    url(r'^webinar/$', webinar.WebinarView.as_view(), name='webinar'),

    # deprecated:
    url(r'^cospaces/list/?$', redirect_to('cospaces')),
    url(r'^cospaces/(?P<cospace_id>[^/]+)/view/$', redirect_to('cospaces_details')),
    # /deprecated

    url(r'^cospaces/$', cospace.CoSpaceListView.as_view(), name='cospaces'),
    url(r'^cospaces/$', cospace.CoSpaceListView.as_view(), name='cospaces_list'),

    url(r'^cospaces/add/?$', VueSPAView.as_view(), name='cospaces_add'),
    url(r'^cospaces/add_old/$', cospace.CoSpaceFormView.as_view(), name='cospaces_add_old'),
    url(r'^cospaces/changes/$', cospace.CoSpaceChangeListView().as_view(), name='cospaces_changes'),

    url(r'^cospaces/(?P<cospace_id>[^/]+)/edit/$', cospace.CoSpaceFormView.as_view(), name='cospaces_edit'),
    url(r'^cospaces/(?P<cospace_id>[^/]+)/invite/$', cospace.CospaceInviteView.as_view(), name='cospaces_invite'),
    url(r'^cospaces/(?P<cospace_id>[^/]+)/pexip/?$', VueSPAView.as_view(), name='pexip_cospaces_details'),

    url(r'^cospaces/(?P<cospace_id>[^/]+)/pexip/?$', VueSPAView.as_view(), name='pexip_cospaces_details'),
    url(r'^cospaces/(?P<cospace_id>[^/]+)/?$', cospace.CoSpaceIndexView.as_view(), name='cospaces_details'),

    url(r'^users/$', users.UserListView.as_view(), name='users'),
    url(r'^users/$', users.UserListView.as_view(), name='user_list'),
    url(r'^users/changes/$', users.UserChangeListView.as_view(), name='user_changes'),
    url(r'^users/(?P<user_id>[^/]+)/view/$', redirect_to('user_details')),
    url(r'^users/(?P<user_id>[^/]+)/$', users.UserDetails.as_view(), name='user_details'),
    url(r'^users/(?P<user_id>[^/]+)/invite/$', users.UserInviteView.as_view(), name='user_invite'),
    url(r'^users/(?P<user_id>[^/]+)/pexip/?$', VueSPAView.as_view(), name='pexip_user_details'),

    url(r'^calls/?$', VueSPAView.as_view(), name='calls'),
    url(r'^calls/pexip/(?P<call_id>[^/]+)/?$', VueSPAView.as_view(title='Control call'), name='call_handler'),
    url(r'^calls/(?P<call_id>[^/]+)/$', calls.CallHandler.as_view(), name='call_handler'),
    url(r'^core/admin/tenants/$', admin.TenantView.as_view(), name='tenants'),
    url(r'^core/admin/restclient/$', rest.RestClient.as_view(), name='rest_client'),
    url(r'^change_password/$', base.ChangePasswordView.as_view(), name='change_password'),
]
