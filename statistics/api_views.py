from datetime import timedelta

from django.conf import settings
from django.utils.timezone import now
from drf_yasg.utils import swagger_auto_schema
from rest_framework import views, viewsets, permissions
from rest_framework.decorators import action
from rest_framework.request import Request
from rest_framework.response import Response

from provider.docs import StatusResponseSerializer
from shared.exceptions import format_exception
from statistics.forms import StatsForm
from statistics.graph import get_graph
from statistics.models import Server
from statistics.serializers import (
    CallStatisticsSerializer,
    CallStatisticsDataSerializer,
    CallStatisticsGraphsSerializer,
    CallStatisticsSettingsSerializer,
    CallStatisticsDebugResponseSerializer,
    StatisticsServerSerializer,
    ReparseStatisticsSerializer,
    RematchStatisticsSerializer,
)
from statistics.utils.leg_collection import LegCollection
from statistics.view_mixins import CallStatisticsReportMixin


class CallStatisticsViewSet(CallStatisticsReportMixin, viewsets.ViewSet):

    def get_serializer_context(self):
        return {
            **super().get_serializer_context(),
            'request': self.request,
            'customer': self.customer,
            'format': self.format_kwarg,
            'view': self
        }

    def get_form_data(self):
        serializer = CallStatisticsSerializer(data=self.request.GET,
                                 context=self.get_serializer_context(),
                                 )
        serializer.is_valid(raise_exception=True)

        # Use serializer validation where possible. Pass all other values as is
        result = self.request.GET.dict()
        result.update(serializer.validated_data)
        return result

    @swagger_auto_schema(query_serializer=CallStatisticsSerializer, responses={200: CallStatisticsDataSerializer})
    def list(self, request: Request):
        serializer = CallStatisticsDataSerializer(self.get_stats_data(as_json=True)[0], context=self.get_serializer_context())
        return Response(serializer.data)

    @swagger_auto_schema(responses={200: CallStatisticsSettingsSerializer})
    @action(detail=False, methods=['GET'], url_path='settings')
    def get_settings(self, request: Request):
        return Response(self.get_settings_data())

    @swagger_auto_schema(query_serializer=CallStatisticsSerializer, responses={200: CallStatisticsGraphsSerializer})
    @action(detail=False, methods=['GET'])
    def graphs(self, request: Request):
        CallStatisticsSerializer(data=request.GET,
                                 context=self.get_serializer_context(),
                                 ).is_valid(raise_exception=True)
        data, form = self.get_stats_data(as_json=True, target_graphs=True)
        return Response(data['graphs'])

    def allow_debug_stats(self, form=None):
        return self.request.user.is_staff

    @swagger_auto_schema(query_serializer=CallStatisticsSerializer, responses={200: CallStatisticsDebugResponseSerializer})
    @action(detail=False, methods=['GET'])
    def debug(self, request: Request):

        if self.allow_debug_stats() is False:
            return Response(status=403)

        CallStatisticsSerializer(data=request.GET,
                                 context=self.get_serializer_context(),
                                 ).is_valid(raise_exception=True)
        data, form = self.get_stats_data(as_json=True, target_graphs=False, debug=True)

        if not self.allow_debug_stats(form):
            return Response(status=403)

        serializer = CallStatisticsDebugResponseSerializer(data, context=self.get_serializer_context())
        return Response(serializer.data)


class DashboardCallsStatistics(CallStatisticsReportMixin, views.APIView):

    @swagger_auto_schema(query_serializer=CallStatisticsSerializer, responses={200: CallStatisticsDataSerializer})
    def get(self, request: Request):
        return Response(self.get_stats_data()[0])

    def get_form_data(self):

        server_form = StatsForm({'multitenant': True}, user=self.request.user, customer=self.customer)
        servers = server_form.get_servers()

        if not servers:
            return {}

        data = self.request.GET.copy()
        data['server'] = str(servers[0].get('id'))
        data['multitenant'] = True
        data['debug'] = False
        return data

    def get_stats_data(self):
        return super().get_stats_data(as_json=True)

    def get_graphs(self, legs: LegCollection, as_json=False, **kwargs):
        return {
            'seconds_per_hour': get_graph(legs, as_json=as_json, **kwargs, by='hour', total=True),
            # 'sametime_graph': get_sametime_graph(legs, related_data=related_data, as_json=as_json, **kwargs),
        }


class ServerViewSet(viewsets.ModelViewSet):

    serializer_class = StatisticsServerSerializer
    queryset = Server.objects.all()

    permission_classes = [permissions.IsAdminUser, permissions.DjangoModelPermissions]

    @swagger_auto_schema(
        responses={200: StatusResponseSerializer(), 400: StatusResponseSerializer()},
        request_body=ReparseStatisticsSerializer(),
    )
    @action(methods=['POST'], detail=True)
    def reparse_api_history(self, request, pk=None):

        obj: Server = self.get_object()

        if not (obj.is_pexip or obj.is_vcs) or not obj.cluster:
            return Response(
                {'status': 'error', 'error': 'Only supported for Pexip and VCS servers'}, status=400
            )

        from statistics import tasks

        serializer = ReparseStatisticsSerializer(
            data=request.data, context=self.get_serializer_context()
        )
        serializer.is_valid(raise_exception=True)

        limit = now() - timedelta(days=serializer.validated_data.get('days') or 90)
        if obj.is_pexip:

            if settings.TEST_MODE:
                tasks.reparse_api_history(obj)
            else:
                tasks.reparse_api_history.delay(obj.pk, limit)

        return Response({'status': 'Running in background'})

    @swagger_auto_schema(
        responses={200: StatusResponseSerializer(), 400: StatusResponseSerializer()},
        request_body=ReparseStatisticsSerializer(),
    )
    @action(methods=['POST'], detail=True)
    def reparse_logs(self, request, pk=None):

        obj: Server = self.get_object()

        if not (obj.is_pexip or obj.is_vcs) or not obj.cluster:
            return Response(
                {'status': 'error', 'error': 'Only supported for Pexip and VCS servers'}, status=400
            )

        from statistics import tasks

        serializer = ReparseStatisticsSerializer(
            data=request.data, context=self.get_serializer_context()
        )
        serializer.is_valid(raise_exception=True)

        limit = now() - timedelta(days=serializer.validated_data.get('days') or 90)
        if obj.is_pexip:

            if settings.TEST_MODE:
                tasks.reparse_pexip_logs(obj)
            else:
                tasks.reparse_pexip_logs.delay(obj.pk, limit)

        elif obj.is_vcs:

            if settings.TEST_MODE:
                tasks.reparse_vcs_logs(obj)
            else:
                tasks.reparse_vcs_logs.delay(obj.pk, limit)

        return Response({'status': 'Running in background'})

    @swagger_auto_schema(
        responses={200: StatusResponseSerializer(), 400: StatusResponseSerializer()},
        request_body=RematchStatisticsSerializer(),
    )
    @action(methods=['POST'], detail=True)
    def rematch_stats(self, request, pk=None):

        obj: Server = self.get_object()

        if not (obj.is_pexip or obj.is_acano) or not obj.cluster:
            return Response(
                {'status': 'error', 'error': 'Only supported for Pexip and CMS'}, status=400
            )

        from provider import tasks

        serializer = RematchStatisticsSerializer(
            data=request.data, context=self.get_serializer_context()
        )
        serializer.is_valid(raise_exception=True)

        limit = now() - timedelta(days=serializer.validated_data.get('days') or 90)
        if settings.TEST_MODE:
            tasks.recount_stats(
                ts_start=limit,
                extra_filters={'server': obj.pk},
                force_rematch=serializer.validated_data.get('force_rematch'),
            )
        else:
            tasks.recount_stats.delay(
                ts_start=limit,
                extra_filters={'server': obj.pk},
                force_rematch=serializer.validated_data.get('force_rematch'),
            )

        return Response({'status': 'Running in background'})
