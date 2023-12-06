from django.conf.urls import include, url

from django.conf.urls.static import static
from django.conf import settings
from django.http import HttpResponse
from django.urls import re_path
from django.utils.translation import ugettext_lazy as _

from shared.views import VueSPAView
from supporthelpers.views.base import IndexView, LoginView
from supporthelpers.views.onboard import (
    SetFallbackPasswordView,
    BasicSettingsView,
    AcanoSetup,
    VCSSetup,
    settings_list,
    PexipSetup,
    ExtendAcanoSetupView,
    NewClusterSetup,
    NewCallControlClusterSetup,
)
from cdrhooks import views as cdrhooks
from adminusers import views as adminusers
from meeting import api_views as provider
from django.contrib.auth import views as auth
from django.views.i18n import JavaScriptCatalog

from django.contrib import admin
admin.autodiscover()


admin.site.site_header = _('Mividas Core/Rooms backend admin')


urlpatterns = [
    url(r'^$', IndexView.as_view(), name='index'),

    url(r'^setup/$', BasicSettingsView.as_view(), name='onboard_setup'),

    url(r'^setup/cluster/$', NewClusterSetup.as_view(), name='onboard_cluster'),
    url(
        r'^setup/call_control/$',
        NewCallControlClusterSetup.as_view(),
        name='onboard_cluster_callcontrol',
    ),
    url(r'^core/admin/customers/$', VueSPAView.as_view(), name='customer_dashboard'),
    url(r'^setup/cms/(?P<cluster_id>\d+)/$', AcanoSetup.as_view(), name='onboard_acano'),
    url(
        r'^setup/cms/(?P<cluster_id>\d+)/extend/$',
        ExtendAcanoSetupView.as_view(),
        name='onboard_acano_extra',
    ),
    url(r'^setup/vcs/(?P<cluster_id>\d+)/$', VCSSetup.as_view(), name='onboard_vcs'),
    url(r'^setup/pexip/(?P<cluster_id>\d+)/$', PexipSetup.as_view(), name='onboard_pexip'),

    url(r'^setup/settings/$', settings_list, name='onboard_settings'),
    url(r'^accounts/fallback/$', SetFallbackPasswordView.as_view(), name='onboard_fallback_password'),

    url(r'^accounts/profile/$', IndexView.as_view()),
    url(r'^accounts/login/$', LoginView.as_view(template_name='login.html'), name="login"),
    url(r'^accounts/logout/$', auth.logout_then_login, name="logout"),

    url(r'', include('supporthelpers.urls')),
    url(r'', include('meeting.urls')),
    url(r'', include('ui_message.urls')),
    url(r'', include('statistics.urls')),
    url(r'', include('recording.urls')),
    url(r'', include('endpointproxy.urls')),
    url(r'', include('numberseries.urls')),
    url(r'', include('address.urls')),
    url(r'', include('room_analytics.urls')),
    url(r'', include('roomcontrol.urls')),
    url(r'', include('organization.urls')),
    url(r'', include('debuglog.urls')),
    url(r'', include('exchange.urls')),
    url(r'', include('msgraph.urls')),
    url(r'', include('policy.urls')),
    url(r'', include('policy_rule.urls')),
    url(r'', include('theme.urls')),
    url(r'', include('endpoint.urls')),
    url(r'', include('provider.urls')),
    url(r'', include('demo_generator.urls')),

    url(r'^json-api/v1/', include('json_api.urls')),

    url(r'^cospaces/(?P<cospace_id>.+)/hooks/$', cdrhooks.HookFormView.as_view(), name='cospace_hooks'),
    url(r'^adminusers/(?P<pk>\d+)/$', adminusers.DisplayOrganization.as_view(), name='adminusers_organization'),

    url(r'^status/up/$', lambda request: HttpResponse('OK')),
    url(r'^status/$', provider.celery_status, name='celery_status'),
    url(r'^jsoni18n/$', JavaScriptCatalog.as_view(), {'domain': 'djangojs'}),

    re_path('^epm(?:/|$)', VueSPAView.as_view()),

    url(r'^admin/', admin.site.urls),
    url(r'', include('conferencecenter.api_urls')),
]


if settings.DEBUG:
    import debug_toolbar
    urlpatterns = [
        url(r'^__debug__/', include(debug_toolbar.urls)),
    ] + urlpatterns

    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)


def handler500(*args, **kwargs):
    from shared.views import error_handler

    return error_handler(*args, **kwargs)
