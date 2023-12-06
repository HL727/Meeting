from django.conf.urls import url
from django.conf import settings
from django.urls import include, path
from drf_yasg.renderers import SwaggerUIRenderer
from rest_framework.routers import DefaultRouter
from drf_yasg.views import get_schema_view
from drf_yasg import openapi
from django.utils.translation import gettext_lazy as _

import shared.api_views
from json_api.views import CallLegs, CallLegMuteAudio, CallLegMuteVideo, CallMuteAllAudio, \
    CallMuteAllVideo, CallLegDetails, CallLegSetLayout, CallLegHangup, session_status

from debuglog import api_views as debuglog
from endpoint import api_urls as endpoint
from exchange import api_urls as exchange
from msgraph import api_urls as msgraph
from meeting import api_urls as meeting
from api_key import api_urls as api_key
from calendar_invite import api_urls as calendar_invite
from provider.api.acano import api_urls as cospace
from provider.api.pexip import api_urls as pexip_cospace
from endpointproxy import urls as endpointproxy
from organization import urls as organization
from endpoint_branding import urls as branding
from address import api_urls as address
from customer import api_urls as customer
from policy import api_urls as policy
from statistics import api_urls as statistics
from provider import api_urls as provider
from policy_rule import api_urls as policy_rule
from policy_auth import api_urls as policy_auth
from theme import api_urls as theme
from room_analytics import api_urls as room_analytics
from roomcontrol import api_urls as roomcontrol
from demo_generator import api_urls as demo_generator


epm_router = DefaultRouter()
epm_router.registry.extend(endpoint.router.registry)
epm_router.registry.extend(endpointproxy.router.registry)
epm_router.registry.extend(organization.router.registry)
epm_router.registry.extend(address.router.registry)
epm_router.registry.extend(branding.router.registry)
epm_router.registry.extend(roomcontrol.router.registry)
epm_router.registry.extend(room_analytics.router.registry)

if settings.EPM_ENABLE_CALENDAR:
    epm_router.registry.extend(exchange.router.registry)
    epm_router.registry.extend(msgraph.router.registry)
    epm_router.registry.extend(calendar_invite.router.registry)
    epm_router.registry.extend(api_key.router.registry)

shared_router = DefaultRouter()
shared_router.registry.extend(customer.router.registry)
shared_router.registry.extend(theme.router.registry)
shared_router.registry.extend(statistics.router.registry)
if settings.ENABLE_DEMO:
    shared_router.registry.extend(demo_generator.router.registry)
shared_router.registry.extend(provider.router.registry)

core_router = DefaultRouter()
core_router.registry.extend(policy.router.registry)

core_router.registry.extend(cospace.router.registry)
core_router.registry.extend(pexip_cospace.router.registry)
core_router.registry.extend(policy_auth.router.registry)
core_router.registry.extend(policy_rule.router.registry)

urlpatterns = [
    url(r'^call-legs/mute-audio/$', CallLegMuteAudio.as_view(), name='json_api_call_leg_mute_audio'),
    url(r'^call-legs/mute-video/$', CallLegMuteVideo.as_view(), name='json_api_call_leg_mute_video'),
    url(r'^call-legs/details/$', CallLegDetails.as_view(), name='json_api_call_leg_details'),
    url(r'^call-legs/set-layout/$', CallLegSetLayout.as_view(), name='json_api_call_leg_set_layout'),
    url(r'^call-legs/hangup/$', CallLegHangup.as_view(), name='json_api_call_leg_hangup'),
    url(r'^calls/mute-all-audio/$', CallMuteAllAudio.as_view(), name='json_api_call_mute_all_audio'),
    url(r'^calls/mute-all-video/$', CallMuteAllVideo.as_view(), name='json_api_call_mute_all_video'),
    url(r'^calls/(?P<call_id>.+)/legs_old/$', CallLegs.as_view(), name='json_api_call_legs'),
    url(r'^call-legs/$', CallLegs.as_view(), name='json_api_call_legs'),

    url(r'^session/', session_status),
    url(r'^', include(provider.urlpatterns)),
    url(r'^', include(room_analytics.urlpatterns)),
    url(r'^', include(statistics.urlpatterns)),
    url(r'^', include(policy.urlpatterns)),
    url(r'^', include(pexip_cospace.urlpatterns)),
    url(r'^', include(meeting.urlpatterns)),

    path('excel/read/', shared.api_views.ExcelGetContent.as_view(), name='excel_input'),
    path('excel/write/', shared.api_views.ExcelCreateFile.as_view(), name='excel_outout'),
    path('language/', shared.api_views.SetLanguage.as_view(), name='set_language'),
]

if settings.ENABLE_EPM:
    urlpatterns.append(url(r'^', include(epm_router.urls)))
    urlpatterns.append(url(r'^debug/', include(debuglog.epm_router.urls)))
urlpatterns.append(url(r'^', include(shared_router.urls)))
urlpatterns.append(url(r'^debug/', include(debuglog.shared_router.urls)))

if settings.ENABLE_CORE:
    urlpatterns.append(url(r'^', include(core_router.urls)))
    urlpatterns.append(url(r'^debug/', include(debuglog.core_router.urls)))

swagger_info = openapi.Info(
    title="Mividas Core + Rooms",
    default_version='v1',
    description="API for Mividas Core + Rooms. Always include header `X-Mividas-Customer: <customerId>` "
    "if your user have access to multiple customers. See `GET /json-api/v1/customers/`. "
    "Use Basic Auth to authenticate.",
)

schema_view = get_schema_view(
    swagger_info,
    patterns=[path('json-api/v1/', include(urlpatterns))],
    public=False,
)

SwaggerUIRenderer.template = 'swagger.html'

urlpatterns = [
   url(r'^swagger(?P<format>\.json|\.yaml)$', schema_view.without_ui(cache_timeout=0), name='schema-json'),
   url(r'^$', schema_view.with_ui('swagger', cache_timeout=60), name='schema-swagger-ui'),
   url(r'^swagger/$', schema_view.with_ui('swagger', cache_timeout=60)),
   url(r'^redoc/$', schema_view.with_ui('redoc', cache_timeout=60), name='schema-redoc'),
] + urlpatterns
