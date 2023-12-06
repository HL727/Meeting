import codecs
import csv
from typing import Sequence, Tuple, Iterator, Optional

from cacheout import fifo_memoize
from django.http import HttpResponse, JsonResponse, Http404, StreamingHttpResponse
import re
from os import mkdir
from os.path import exists
from django.conf import settings
import json
import gzip
from datetime import datetime, date, timedelta

from django.utils.dateparse import parse_datetime
from django.utils.timezone import now, localtime
from django.utils.translation import gettext_lazy as _

from django.utils.encoding import force_text
from django.utils.text import slugify
from django.views.decorators.csrf import csrf_exempt
from defusedxml.minidom import parseString as safe_minidom_fromstring

from shared.models import GlobalLock
from statistics.parser.utils import check_spam
from statistics.serializers import CallStatisticsDataSerializer
from .mividas_csv import mividas_csv_import_multiprocess
from .models import Call, Leg, Server
from .parser.acano import Parser
from .forms import StatsForm
from .parser.mividas import MividasCSVImportExport
from .parser.pexip import PexipParser, PexipEventParser
from statistics.utils.report import excel_export, debug_excel_export
from .graph import get_graph, get_sametime_graph
from sentry_sdk import capture_exception
from customer.view_mixins import LoginRequiredMixin, CustomerMixin
from django.views.generic import TemplateView
from django_xhtml2pdf.views import PdfMixin
from collections import OrderedDict, Counter
from datastore.models import acano as datastore
from .utils.leg_collection import LegCollection
from .view_mixins import CallStatisticsReportMixin


class StatsView(LoginRequiredMixin, CallStatisticsReportMixin, CustomerMixin, TemplateView):

    template_name = 'statistics/calls.html'

    excel_url_name = 'stats_excel'
    pdf_url_name = 'stats_pdf'

    form_class = StatsForm

    def get(self, request, *args, **kwargs):
        if request.GET.get('ajax') and request.GET.get('only_settings'):
            return JsonResponse(self.get_settings_data())

        # TODO move to real API, or remove?
        if request.user.is_staff and request.GET.get('recount_stats'):
            if GlobalLock.is_locked('stats.recount_stats'):
                return HttpResponse(_('Already running'), status=503)
            from provider import tasks
            tasks.recount_stats.delay()
            return HttpResponse(request.path)

        if request.GET.get('ajax'):
            graphs = bool(request.GET.get('only_graphs')) or None
            if request.GET.get('only_data'):
                graphs = False

            data, form = self.get_stats_data(
                as_json=True, target_graphs=graphs, debug=bool(request.GET.get('debug'))
            )

            #return HttpResponse('<html><body>OK</body></html>')

            if data.get('errors'):
                return JsonResponse(data, status=400)

            if graphs:
                return JsonResponse(data)

            serializer = CallStatisticsDataSerializer(data, context=self.get_serializer_context())
            return JsonResponse(serializer.data)
        return super().get(request, *args, **kwargs)

    def get_context_data(self):

        context = super().get_context_data()

        stats_data, form = self.get_stats_data()
        context['form'] = form
        context.update(stats_data)
        context.update(stats_data.get('graphs') or {})

        return context


class StatsVueView(StatsView):

    template_name = 'base_vue.html'

    def get_context_data(self):
        context = super().get_context_data()
        return context


class StatsPDFView(PdfMixin, StatsView):

    template_name = 'statistics/report.html'

    def get_graphs(self, legs: LegCollection, as_json=False, **kwargs):

        from base64 import b64encode

        def _b64data(bytes):
            return 'data:image/png;base64,' + b64encode(bytes).decode('ascii')

        return {
            'graph': _b64data(get_graph(legs, as_image=True, **kwargs) or b''),
            'sametime_graph': _b64data(get_sametime_graph(legs, as_image=True, **kwargs) or b''),
        }

    def render_to_response(self, context, **response_kwargs):
        response = super().render_to_response(context, **response_kwargs)
        form = getattr(self, 'form', None) or self.get_form()

        tenant = date_start = date_stop = None
        try:
            if form.is_valid():
                tenant = dict(form.get_ldap_tenants()[0]).get(form.cleaned_data.get('tenant'))
                date_start = str(form.cleaned_data.get('ts_start').date())
                date_stop = str(form.cleaned_data.get('ts_stop').date())
        except Exception:
            pass

        basename = '{}_{}-{}'.format(slugify(tenant).title() if tenant else 'Report', date_start or '', date_stop or '').rstrip('-_')
        response['Content-Disposition'] = '{}; filename={}.pdf'.format('inline' if settings.DEBUG else 'attachment', basename)
        return response


class StatsExcelView(StatsView):

    template_name = 'statistics/report.html'
    include_cospaces = True

    def get_graphs(self, legs: LegCollection, as_json=False, **kwargs):
        return {}

    def render_to_response(self, context, **response_kwargs):

        cleaned = context['form'].cleaned_data if context['form'].is_valid() else {}
        excel = excel_export(context['legs'], related_data=context.get('related_data'), summary_data=context['summary'],
                             include_cospaces=self.include_cospaces,
                             ts_start=cleaned.get('ts_start'), ts_stop=cleaned.get('ts_stop'))

        response = HttpResponse(content_type="application/ms-excel")
        response['Content-Disposition'] = 'attachment; filename=stats-{}.xls'.format(date.today())

        excel.save(response)

        return response


class StatsDebugExcelView(StatsExcelView):

    def dispatch(self, request, *args, **kwargs):
        return super().dispatch(request, *args, **kwargs)

    def render_to_response(self, context, **response_kwargs):

        if not self.allow_debug_stats(context['form']):
            return HttpResponse(_('Din användare har inte behörighet till denna vy'), status=403)

        cleaned = context['form'].cleaned_data if context['form'].is_valid() else {}
        excel = debug_excel_export(context['legs'],
                                   ts_start=cleaned.get('ts_start'), ts_stop=cleaned.get('ts_stop'))

        response = HttpResponse(content_type="application/ms-excel")
        excel.save(response)

        def _format_ts(ts: Optional[datetime]):
            if not ts:
                return 'unknown'
            return localtime(ts).replace(microsecond=0).strftime('%Y-%m-%d_%H%M')

        filename = 'stats-debug_{}-{}_to_{}.xlsx'.format(
            _format_ts(now()),
            _format_ts(cleaned.get('ts_start')),
            _format_ts(cleaned.get('ts_stop')),
        )
        response['Content-Disposition'] = 'attachment; filename={}'.format(
            filename.replace(':', '')
        )
        return response


class DebugView(LoginRequiredMixin, CustomerMixin, TemplateView):

    template_name = 'statistics/debug.html'

    def get_objects(self):
        if self.kwargs.get('type') in (None, 'call'):
            call = Call.objects.prefetch_related('legs').filter(guid=self.kwargs['guid']).first()
            if not call:
                call = Call.objects.prefetch_related('legs').filter(id=self.kwargs['guid']).first()
            if not call:
                raise Http404()

            leg = None
            self._check_tenant_customer(call.tenant)
        else:
            leg = Leg.objects.select_related('call').filter(guid=self.kwargs['guid']).first()
            if not leg:
                leg = Leg.objects.select_related('call').filter(id=self.kwargs['guid']).first()

            if not leg:
                raise Http404()

            call = leg.call if leg.call_id else None
            self._check_tenant_customer(leg.tenant)

        return call, leg

    def get_files(self):

        try:
            call, leg = self.get_objects()
        except Exception:
            raise Http404()

        date = call.ts_start.date() if call else None
        if leg and leg.ts_start:
            date = leg.ts_start.date()

        files = getattr(settings, 'CDR_LOG_FILES', ())
        if date:
            files = files + (
                '{}/log-{}.txt.gz'.format(settings.LOG_DIR, date),
                '{}/log-{}.log.gz'.format(settings.LOG_DIR, date),
                '{}/cms-cdr-{}.log.gz'.format(settings.LOG_DIR, date),
                )

        return files

    def get_log_content(self, guids, ts_start=None, ts_stop=None):

        files = self.get_files()
        file_result = self.get_log_content_from_files(files, guids) or []

        log_result = self.get_log_content_from_database(files, guids, ts_start=ts_start, ts_stop=ts_stop) or []
        return file_result + log_result

    def get_log_content_from_files(self, files, guids):

        result = []

        for f in files:

            if not exists(f):
                continue

            if f.endswith('.gzip') or f.endswith('.gz'):

                fd = gzip.open(f)
            else:
                fd = open(f)

            for l in fd:

                for g in guids:
                    if g in l:
                        break
                else:
                    continue

                if not l.startswith(b'{"') and b'{"' in l:  # corrupt file
                    l = l[l.find(b'{"'):]
                try:
                    cur = json.loads(l.decode('utf-8'))['rawpost']
                except Exception:
                    continue

                if cur:
                    result.append(cur)

            fd.close()

        return result

    def get_log_content_from_database(self, files, guids, ts_start=None, ts_stop=None):

        result = []
        try:
            call, leg = self.get_objects()
        except Exception:
            call = leg = None

        from debuglog.models import AcanoCDRLog, PexipEventLog

        if call:
            result.extend(call.pexip_cdr_event_logs.all())
            result.extend(call.acano_cdr_event_logs.all())
        if leg:
            result.extend(leg.pexip_cdr_event_logs.all())
            result.extend(leg.acano_cdr_event_logs.all())

        result.extend(AcanoCDRLog.objects.search_ids(guids, ts_start=ts_start, ts_stop=ts_stop))
        result.extend(PexipEventLog.objects.search_ids(guids, ts_start=ts_start, ts_stop=ts_stop))

        def _get_time(xml):
            if xml.startswith('{'):
                return json.loads(xml).get('time')
            try:
                return re.search(r'time="(.*?)"', xml).group(1)
            except AttributeError:
                return xml

        def _prettify(result):
            for r in result:
                try:
                    cur = safe_minidom_fromstring(r.strip()).toprettyxml()
                except Exception:
                    cur = r.replace('<', '\n<')
                yield cur.replace('<?xml version="1.0"?>', '').strip()

        text = sorted(
            set(r.content_text or '' for r in result), key=_get_time
        )  # data should be sortable by timestamp in first tag
        return list(_prettify(text))

    def get_context_data(self, **kwargs):

        try:
            call, leg = self.get_objects()
        except Exception:
            raise Http404()

        guids = set()
        if call:
            guids.add(call.guid)
            # guids.add(call.cospace)  # ignore pexip call event for now. needs specific time filter
            for l in call.legs.all():
                guids.add(l.guid)
        if leg:
            guids.add(leg.guid)

        guids = {g.encode('utf-8') for g in guids if g}  # handle corrupt lines

        if call:
            legs = OrderedDict()
            reconnects = Counter()
            for leg in call.legs.all():
                target = leg.target if leg.target not in ('guest', 'webrtc', 'phone') else leg.remote
                legs.setdefault(target, []).append(self._get_all_fields_from_model(leg))

            users = dict(datastore.User.objects.filter(username__in=legs.keys()).values_list('username', 'uid'))

            for grouped in legs.values():
                grouped[0]['user_id'] = users.get(grouped[0]['target'])
                reconnects[len(grouped) - 1] += 1
        else:
            legs = {leg.target: [self._get_all_fields_from_model(leg)]}
            reconnects = {}

        times = [call.ts_start] if call and call.ts_start else []
        times.extend(l['ts_start'] for grouped in legs.values() for l in grouped if l['ts_start'])

        ts_start = sorted(times)[0] if times else None
        ts_stop = sorted(times)[-1] + timedelta(hours=2) if times else None

        file_content = self.get_log_content(guids, ts_start=ts_start, ts_stop=ts_stop)

        data = {
            'server': call.server if call else None,
            'leg': self._get_all_fields_from_model(leg),
            'call': self._get_all_fields_from_model(call),
            'grouped_legs': legs.values(),
            'legs': [l for grouped in legs.values() for l in grouped],
            'reconnects': sorted(reconnects.items()),
            'lines': file_content,
        }

        return data

    def _get_all_fields_from_model(self, obj):
        if not obj:
            return
        result = {}
        for f in obj._meta.fields:
            if f.name.endswith('_fk'):
                continue
            result[f.name] = getattr(obj, f.name)
            if hasattr(result[f.name], '_meta'):
                result[f.name] = result[f.name].pk

        if result.get('ts_start') and result.get('ts_stop'):
            duration = str(result['ts_stop'] - result['ts_start'])
            if duration.startswith('00:'):
                duration = duration[3:]
            elif duration.startswith('0:'):
                duration = duration[2:]
            result['duration'] = duration
        if result.get('protocol') is not None:
            result['protocol_str'] = obj.protocol_str
        if result.get('target') in ('guest', 'webrtc', 'phone'):
            result['target'] = result.get('remote') or result['target']
        return result

