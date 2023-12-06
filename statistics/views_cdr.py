import codecs
import csv
import json
from datetime import datetime, date
from os import mkdir
from os.path import exists
from typing import Tuple, Iterator, Sequence

from cacheout import fifo_memoize
from django.conf import settings
from django.http import Http404, HttpResponse, StreamingHttpResponse
from django.shortcuts import render
from django.template import Template, RequestContext
from django.utils.dateparse import parse_datetime
from django.utils.encoding import force_text
from django.utils.timezone import now
from django.views.decorators.csrf import csrf_exempt
from sentry_sdk import capture_exception

from statistics.mividas_csv import mividas_csv_import_multiprocess
from statistics.models import Server
from statistics.parser.acano import Parser
from statistics.parser.mividas import MividasCSVImportExport
from statistics.parser.pexip import PexipParser
from statistics.parser.utils import check_spam

RERAISE_ERRORS = settings.DEBUG or getattr(settings, 'TEST_MODE', False)


@fifo_memoize(10, ttl=10)
def get_server_by_key(secret_key: str) -> Server:

    try:
        server = Server.objects.get(secret_key=secret_key)
    except Server.DoesNotExist:
        raise Http404()

    return server


@csrf_exempt
def acano_cdr(request, name=None, secret_key=None):

    try:
        server = get_server_by_key(secret_key)
    except Server.DoesNotExist:
        return HttpResponse('Not found', status=404)

    remote_ip = request.META.get('REMOTE_ADDR') or '127.0.0.1'

    # check if spam number scan
    from debuglog.models import AcanoCDRSpamLog
    spam_count = check_spam(force_text(request.body), remote_ip)

    if spam_count is not None:
        try:
            AcanoCDRSpamLog.objects.store(content=request.body, ip=request.META.get('REMOTE_ADDR'))
        except Exception:
            capture_exception()
        Parser(server).add_spam(date.today(), 'unknown_destination', spam_count)
        # TODO remove PossibleSpamLeg
        return HttpResponse('OK')

    from .tasks import handle_acano_cdr
    if settings.ASYNC_CDR_HANDLING and not settings.TEST_MODE:
        if b'type="callLegEnd"' in request.body or b'type="callEnd"' in request.body:
            time_kwargs = {'countdown': 1}  # decrease risk of out of order handling
        else:
            time_kwargs = {}
        handle_acano_cdr.apply_async([server.pk, force_text(request.body), None, remote_ip], **time_kwargs)
    else:
        handle_acano_cdr(server.pk, force_text(request.body), None, remote_ip)

    return HttpResponse('OK')


@csrf_exempt
def pexip_cdr(request, name=None, secret_key=None):
    server = get_server_by_key(secret_key)

    remote_ip = request.META.get('REMOTE_ADDR')

    # queue for processing
    from .tasks import handle_pexip_cdr
    if settings.ASYNC_CDR_HANDLING and not settings.TEST_MODE:
        if b'conference_ended' in request.body or b'participant_disconnected' in request.body:
            time_kwargs = {'countdown': 1}  # decrease risk of out of order handling
        else:
            time_kwargs = {}
        handle_pexip_cdr.apply_async([server.pk, force_text(request.body), None, remote_ip], **time_kwargs)
    else:
        handle_pexip_cdr(server.pk, force_text(request.body), None, remote_ip)

    return HttpResponse('OK')


def _get_csv(request) -> Tuple[Iterator[Sequence[str]], Sequence[str]]:
    if request.FILES.get('csv'):
        import csv
        reader = csv.reader(codecs.iterdecode(request.FILES['csv'], 'utf-8'))
        cols = list(next(reader))
        data = reader
    elif request.content_type == 'text/csv' or not request.body.startswith(b'{'):
        import csv
        reader = csv.reader(force_text(request.body).split('\n'))
        data = list(reader)
        cols = list(data.pop(0))
    else:
        input_data = json.loads(force_text(request.body))
        cols = list(input_data['cols'])
        data = input_data['rows']

    if data and isinstance(data, list) and len(cols) != len(data[0]):
        raise ValueError('Invalid column count between headers and rows')

    return data, cols


@csrf_exempt
def pexip_csv(request, data_type=None, secret_key=None):

    from debuglog.models import PexipEventLog

    if not data_type or data_type not in ('participant', 'conference'):
        return HttpResponse('Type must be specified or be call|leg. not {}'.format(data_type), status=400)

    data = []
    cols = []
    server = None

    try:
        data, cols = _get_csv(request)
        server = Server.objects.get(secret_key=secret_key)
    except Exception:
        if RERAISE_ERRORS:
            raise
        capture_exception()
    finally:
        try:
            PexipEventLog.objects.store(content='{{"not_logged": true, "rows": {}}}'.format(len(data)),
                                        ip=request.META.get('REMOTE_ADDR'),
                                        type='csv_{}'.format(data_type),
                                        cluster_id=server.cluster_id if server else None,
                                        uuid_start='nolog')
        except Exception:
            capture_exception()

    try:
        parser = PexipParser(server)
        if data_type == 'conference':
            for row in data:
                if not row:
                    continue
                parser.parse_call(dict(zip(cols, row)))

        elif data_type == 'participant':
            for row in data:
                if not row:
                    continue
                parser.parse_participant(dict(zip(cols, row)))
    except Exception:
        if RERAISE_ERRORS:
            raise
        capture_exception()

    return HttpResponse('OK')


@csrf_exempt
def mividas_csv_import_handler(request, data_type=None, secret_key=None):

    if not data_type or data_type not in ('call', 'leg'):
        return HttpResponse('Type must be specified or be call|leg. not {}'.format(data_type), status=400)

    server = get_server_by_key(secret_key=secret_key)

    if request.method == "GET":
        return HttpResponse(
            Template(
                '''
            {% extends 'admin/base_site.html' %}
            {% block content %}
            <p>
            Type: <a href="{{ call_url }}" class="button">call</a>
            <a class="button" href="{{ leg_url }}">participants</a>
            </p>

            <form method="post" enctype="multipart/form-data">
            <input type="file" name="csv" /><input type="submit" value="upload" />
            </form>
            {% endblock %}
            '''
            ).render(
                RequestContext(
                    request,
                    {
                        'call_url': server.get_import_path('call'),
                        'leg_url': server.get_import_path('leg'),
                    },
                )
            )
        )

    def _iter_response():
        try:
            data, cols = _get_csv(request)
            yield 'Starting import using multiple processes\n'
            it = mividas_csv_import_multiprocess(server.pk, data_type, rows=data, cols=cols)
            full_total = 0
            for valid, total, duration in it:
                yield '{}: Process imported {} of {} rows in {}s. Acc count is {}\n'.format(
                    now().replace(microsecond=0).isoformat(), valid, total, duration, full_total
                )
                full_total += total
        except Exception as e:
            if RERAISE_ERRORS:
                raise
            yield 'Error: {}'.format(e)
        else:
            yield 'OK'

    return StreamingHttpResponse(_iter_response(), content_type='text/plain')


@csrf_exempt
def mividas_csv_export(request, data_type=None, secret_key=None):

    if not request.user.is_staff:
        return HttpResponse('Access forbidden', status=403)

    if not data_type or data_type not in ('call', 'leg'):
        return HttpResponse('Type must be specified or be call|leg. not {}'.format(data_type), status=400)

    server = get_server_by_key(secret_key=secret_key)

    if not request.GET.get('export'):
        return HttpResponse(
            Template(
                '''
            {% extends 'admin/base_site.html' %}
            {% block content %}
            <p>
            Type: <a href="{{ call_url }}" class="button">call</a>
            <a class="button" href="{{ leg_url }}">participants</a>
            </p>

            <form>
            <div>Start time: <input name="ts_start" value="2000-01-01T00:00:00Z" /></div>
            <div>End time: <input name="ts_stop" value="2030-12-11T00:00:00Z" /></div>
            <div class="submit-row">
                <input type="hidden" name="export" value="1" />
                <input class="button" type="submit" value="Export" />
            </div>
            </form>
            {% endblock %}
            '''
            ).render(
                RequestContext(
                    request,
                    {
                        'call_url': server.get_export_path('call'),
                        'leg_url': server.get_export_path('leg'),
                    },
                )
            )
        )

    def _iter_csv(fields, rows):
        class LoopbackWriter:
            @staticmethod
            def write(value):
                return value

        writer = csv.writer(LoopbackWriter())

        yield writer.writerow([str(c) for c in fields])

        try:
            for row in rows:
                yield writer.writerow([str(c) for c in row])
        except Exception:
            capture_exception()
            raise

    try:
        parser = MividasCSVImportExport(server)

        ts_start = parse_datetime(request.GET.get('ts_start') or '2000-01-01T00:00:00Z')
        ts_stop = parse_datetime(request.GET.get('ts_stop') or '2040-01-01T00:00:00Z')

        if data_type == 'call':
            fields, rows = parser.export_calls(ts_start, ts_stop)
        elif data_type == 'leg':
            fields, rows = parser.export_legs(ts_start, ts_stop)
        else:
            return

        response = StreamingHttpResponse(_iter_csv(fields, rows), content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="cdr_{}-{}-{}-export.csv"'.format(
            server.pk, datetime.now().replace(microsecond=0).isoformat().replace(':', ''), data_type
        )

        return response

    except Exception:
        if RERAISE_ERRORS:
            raise
        capture_exception()

    return HttpResponse('OK')
