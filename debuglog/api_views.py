from typing import Type

import django_filters
from django.http import Http404
from rest_framework import viewsets
from rest_framework import pagination
from rest_framework.routers import DefaultRouter
from rest_framework import permissions

from audit.models import AuditLog
from .serializers import get_serializer
from tracelog.serializers import ActiveTraceLogSerializer

import django.db.models
from .models import (
    AcanoCDRLog,
    AcanoCDRSpamLog,
    EmailLog,
    VCSCallLog,
    EndpointCiscoEvent,
    EndpointCiscoProvision,
    PexipEventLog,
    PexipHistoryLog,
    PexipPolicyLog,
    ErrorLog,
    EndpointPolyProvision,
)
from tracelog.models import ActiveTraceLog, TraceLog


class Paginator(pagination.LimitOffsetPagination):
    default_limit = 5
    max_limit = 50


class DebugBaseViewSet(viewsets.ReadOnlyModelViewSet):

    permission_classes = [permissions.IsAdminUser]
    pagination_class = Paginator
    page_size = 5


def get_viewset(model, fields=(), filter_fields=None) -> Type[DebugBaseViewSet]:

    filters = {}
    if filter_fields is None:
        filter_fields = fields

    for f in filter_fields:
        if isinstance(model._meta.get_field(f), django.db.models.DateTimeField):
            filters[f] = ['exact', 'gte', 'lte']
        elif isinstance(model._meta.get_field(f), django.db.models.ForeignKey):
            filters[f] = ['exact']
        else:
            filters[f] = ['exact', 'startswith']

    filter_class = type('{}Filter'.format(model.__name__), (django_filters.FilterSet,), {
        'Meta': type('Meta', (), {
            'model': model,
            'fields': {
                'ts_created': ['exact', 'lt', 'gt', 'lte', 'gte'],
                **filters,
            },
            'filter_overrides': {
                django.db.models.DateTimeField: {'filter_class': django_filters.IsoDateTimeFilter},
            }
        })
    })

    return type('{}ViewSet'.format(model.__name__),
        (DebugBaseViewSet,),
        {
            'serializer_class': get_serializer(model, fields),
            'queryset': model.objects.all().order_by('-ts_created'),
            'filterset_class': filter_class,

        })


AcanoCDRLogViewSet = get_viewset(AcanoCDRLog, ('ip', 'count', 'types'), ('ip',))
AcanoCDRSpamLogViewSet = get_viewset(AcanoCDRSpamLog, ('ip',))
EmailLogViewSet = get_viewset(EmailLog, ('sender', 'subject', 'parts'), ('sender',))
VCSCallLogViewSet = get_viewset(VCSCallLog, ('ts_start', 'ts_stop'), ())
EndpointCiscoEventViewSet = get_viewset(EndpointCiscoEvent, ('ip', 'endpoint', 'event'))
EndpointCiscoProvisionViewSet = get_viewset(EndpointCiscoProvision, ('ip', 'endpoint', 'event'))
EndpointPolyProvisionViewSet = get_viewset(EndpointPolyProvision, ('ip', 'endpoint', 'event'))
PexipEventLogViewSet = get_viewset(
    PexipEventLog,
    (
        'ip',
        'type',
        'uuid_start',
        'cluster_id',
    ),
)
PexipHistoryLogViewSet = get_viewset(
    PexipHistoryLog,
    ('type', 'count', 'first_start', 'last_start', 'cluster_id'),
    ('cluster_id', 'first_start', 'last_start'),
)
PexipPolicyLogViewSet = get_viewset(
    PexipPolicyLog, ('ip', 'type', 'service_tag', 'cluster_id', 'action')
)
ErrorLogViewSet = get_viewset(
    ErrorLog,
    ('title', 'type', 'endpoint'),
)
TraceLogViewSet = get_viewset(
    TraceLog,
    ('cluster_id', 'provider_id', 'endpoint_id', 'customer_id', 'method', 'url_base'),
)
AuditLogViewSet = get_viewset(
    AuditLog,
    (
        'ip',
        'scope',
        'action',
        'type',
        'username',
        'path',
    ),
)


class ActiveTraceLogViewSet(viewsets.ModelViewSet):

    permission_classes = [permissions.IsAdminUser, permissions.DjangoModelPermissions]
    queryset = ActiveTraceLog.objects.all()
    serializer_class = ActiveTraceLogSerializer

    def perform_create(self, serializer):
        return serializer.save(user=str(self.request.user))

    def update(self, request, *args, **kwargs):
        raise Http404()


core_router = DefaultRouter()
core_router.register('acanocdr', AcanoCDRLogViewSet)
core_router.register('acanocdrspam', AcanoCDRSpamLogViewSet)
core_router.register('pexip_event', PexipEventLogViewSet)
core_router.register('pexip_history', PexipHistoryLogViewSet)
core_router.register('pexip_policy', PexipPolicyLogViewSet)

epm_router = DefaultRouter()
epm_router.register('email', EmailLogViewSet)
core_router.register('vcs', VCSCallLogViewSet)
epm_router.register('cisco', EndpointCiscoEventViewSet)
epm_router.register('cisco_provision', EndpointCiscoProvisionViewSet)
epm_router.register('poly_provision', EndpointPolyProvisionViewSet)

shared_router = DefaultRouter()
shared_router.register('audit_log', AuditLogViewSet)
shared_router.register('error_log', ErrorLogViewSet)
shared_router.register('trace_log', TraceLogViewSet)

shared_router.register('active_trace_log', ActiveTraceLogViewSet)

urlpatterns = [*core_router.urls, *epm_router.urls, shared_router.urls]
