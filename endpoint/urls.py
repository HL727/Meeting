
from django.urls import path, re_path

import endpoint_provision.views_poly_provision
import endpoint_provision.views_tms_provision
from shared.views import VueSPAView

from . import views

urlpatterns = [
    path('epm/', views.DashboardView.as_view(), name='endpoint_index'),
    path('epm/endpoint/', VueSPAView.as_view(), name='epm_list'),
    path('epm/endpoint/<endpoint_id>/', VueSPAView.as_view(), name='endpoint_details'),
    path('tms/', endpoint_provision.views_tms_provision.tms),
    path(
        'tms/public/external/management/systemmanagementservice.asmx',
        endpoint_provision.views_tms_provision.tms,
    ),
    path('tms/public/feedback/code.aspx', views.tms_event),
    path(
        'tms/public/feedback/postdocument.aspx', endpoint_provision.views_tms_provision.tms_document
    ),
    path('tms/event/', views.tms_event),
    path('tms/event/document/', endpoint_provision.views_tms_provision.tms_document),
    re_path(
        '^tms/document/(?P<customer_secret>[^/]+)/?$',
        endpoint_provision.views_tms_provision.tms_document,
    ),
    re_path(
        '^tms/document/(?P<customer_secret>[^/]+)/(?P<endpoint_secret>[^/]+)/?$',
        endpoint_provision.views_tms_provision.tms_document,
    ),
    re_path(r'^tms/event/(?P<customer_secret>[^/]+)/?$', views.tms_event),
    re_path(
        r'^tms/event/(?P<customer_secret>[^/]+)/(?P<endpoint_secret>[^/]+)/?$', views.tms_event
    ),
    re_path(r'^tms/.*\.asmx', endpoint_provision.views_tms_provision.tms),
    re_path(r'^tms/(?P<customer_secret>[^/]+)/?$', endpoint_provision.views_tms_provision.tms),
    re_path(
        r'^tms/(?P<customer_secret>[^/]+)/+(?P<endpoint_serial>[A-z0-9]{12,14}).cfg$',
        endpoint_provision.views_poly_provision.poly_directory_root_passive_provision,
    ),
    re_path(
        r'^tms/(?P<customer_secret>[^/]+)/(?P<endpoint_secret>[^/]+)/?$',
        endpoint_provision.views_tms_provision.tms,
    ),
    re_path(
        r'^PlcmRmWeb/device/provisionProfile$',
        endpoint_provision.views_poly_provision.poly_rprm_provision,
    ),
    re_path(
        r'^(?P<endpoint_serial>[A-z0-9]{12,14}).cfg',
        endpoint_provision.views_poly_provision.poly_directory_root_passive_provision,
    ),
    re_path(
        r'^config-(?P<endpoint_serial>[A-z0-9]{12,14}).cfg',
        endpoint_provision.views_poly_provision.poly_rprm_provision,
    ),
    re_path(
        r'^dms/(?P<customer_secret>[^/]+)/(groupseries|trio)-(.*).cfg',
        endpoint_provision.views_poly_provision.poly_directory_root_passive_provision,
    ),
    re_path(
        r'^ep/poly/(?P<customer_secret>[^/]+)//?(?P<endpoint_serial>.+)\.cfg$',
        endpoint_provision.views_poly_provision.poly_directory_root_passive_provision,
    ),
    re_path(
        r'^ep/poly/(?P<customer_secret>[^/]+)/(?P<endpoint_secret>[^/]+)//?(?P<endpoint_serial>.+).cfg$',
        endpoint_provision.views_poly_provision.poly_directory_root_passive_provision,
    ),
]

