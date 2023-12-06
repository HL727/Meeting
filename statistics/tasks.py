from __future__ import annotations
import logging
import json
from datetime import timedelta, datetime
from random import randint
from typing import TYPE_CHECKING, Optional, Union, Tuple, List

from cacheout import fifo_memoize
from celery import Task
from django.conf import settings
from django.db import transaction
from django.utils.dateparse import parse_datetime
from django.utils.encoding import force_text, force_bytes
from django.utils.timezone import now
from sentry_sdk import capture_exception

from conferencecenter.celery import app

if TYPE_CHECKING:
    from statistics.models import Server


logger = logging.getLogger(__name__)


RERAISE_ERRORS = settings.DEBUG or settings.TEST_MODE


@fifo_memoize(10, ttl=10)
def get_server_by_id(id: int) -> Optional['Server']:
    from statistics.models import Server
    return Server.objects.filter(pk=id).first()


@app.task
def handle_acano_cdr(server_id: int, payload: Union[str, bytes], cdr_log_id=None, remote_ip: str = None):

    server = get_server_by_id(server_id)
    if not server:
        return

    cdr_log = None
    if cdr_log_id:  # deprecated. remove after task signature is updated
        from debuglog.models import AcanoCDRLog
        cdr_log = AcanoCDRLog.objects.only('id').filter(pk=cdr_log_id).first()
    else:  # log request
        from debuglog.models import AcanoCDRLog

        try:
            cdr_log = AcanoCDRLog.objects.store(content=payload, ip=remote_ip)
        except Exception:
            capture_exception()

    try:
        from statistics.parser.acano import Parser
        Parser(server, cdr_log=cdr_log).parse_xml(force_bytes(payload))
    except Exception:
        if settings.DEBUG or settings.TEST_MODE:
            raise
        capture_exception()


@app.task
def handle_pexip_cdr(server_id: int, payload: Union[str, bytes], cdr_log_id=None, remote_ip: str = None):

    server = get_server_by_id(server_id)
    if not server:
        return

    if len(payload) < 4:
        logger.warning('Invalid pexip event sink data from %s, %s bytes', remote_ip, len(payload))
        return

    if cdr_log_id:
        from debuglog.models import PexipEventLog
        cdr_log = PexipEventLog.objects.only('id').filter(pk=cdr_log_id).first()
    else:
        cdr_log = log_pexip_event(server, force_text(payload), remote_ip)

    try:
        from statistics.parser.pexip import PexipEventParser
        data = json.loads(force_text(payload))
        PexipEventParser(server).parse_eventsink_event(data, cdr_log=cdr_log)
    except Exception:
        if settings.DEBUG or settings.TEST_MODE:
            raise
        capture_exception()


def log_pexip_event(server: 'Server', payload: str, remote_ip: str):

    from debuglog.models import PexipEventLog

    cdr_log = None

    data = {}
    uuid_start = None
    server = None

    # extract data for log
    try:
        data = json.loads(force_text(payload))
        data.get('event')
        if 'data' in data:
            uuid_start = (data['data'].get('call_id') or data['data'].get('uuid') or
                          data['data'].get('conference_name') or data['data'].get('name') or '')[:36]

    except Exception:
        if RERAISE_ERRORS:
            raise
        capture_exception()
    finally:
        try:
            cdr_log = PexipEventLog.objects.store(content=payload,
                                        ip=remote_ip,
                                        type=data.get('event', ''),
                                        cluster_id=server.cluster_id if server else None,
                                        uuid_start=uuid_start or '')
        except Exception:
            capture_exception()

    return cdr_log


def _load_reparse_log_arguments(
    server: Union[Server, int], limit: Union[datetime, str, None] = None
) -> Tuple[Server, datetime]:
    from statistics.models import Server

    if isinstance(server, int):
        server = Server.objects.get(pk=server)

    if not limit:
        limit = now() - timedelta(days=90)
    elif isinstance(limit, str):
        limit = parse_datetime(limit)

    return server, limit


@app.task()
def reparse_pexip_logs(server: Union[Server, int], limit: Union[datetime, str, None] = None):
    from statistics.parser.pexip import PexipParser
    from debuglog.models import PexipHistoryLog

    try:
        server, limit = _load_reparse_log_arguments(server, limit)
    except Server.DoesNotExist:
        return

    parser = PexipParser(server)
    for log in PexipHistoryLog.objects.filter(ts_created__gt=limit).iterator():
        if log.type == 'conference':
            for call in log.content_json['objects']:
                parser.parse_call(call)
        elif log.type == 'participant':
            for leg in log.content_json['objects']:
                parser.parse_participant(leg)


@app.task()
def reparse_vcs_logs(server: Union[Server, int], limit: Union[datetime, str, None] = None):
    from customer.models import Customer
    from debuglog.models import VCSCallLog
    from statistics.parser.vcse import VCSEParser

    try:
        server, limit = _load_reparse_log_arguments(server, limit)
    except Server.DoesNotExist:
        return

    api = server.cluster.get_api(Customer.objects.first())

    parser = VCSEParser(server, timezone=api.get_timezone())
    for log in VCSCallLog.objects.filter(ts_created__gt=limit).iterator():
        parser.parse_json(log.content_json)


@app.task()
def reparse_api_history(server: Union[Server, int], limit: Union[datetime, str, None] = None):

    try:
        server, limit = _load_reparse_log_arguments(server, limit)
    except Server.DoesNotExist:
        return

    if not (server.is_pexip or server.is_vcs) or not server.cluster:
        raise ValueError('Only pexip or vcs servers can be reparsed')

    from customer.models import Customer

    api = server.cluster.get_api(Customer.objects.first())

    return api.update_stats(incremental=False)


@app.task(bind=True, max_retries=3)
def move_call_legs_to_call(self: Task, server_id: int, call_id: int, leg_guids: List[str]):
    from statistics.models import Leg, Call
    from django.db.models import Q

    try:
        call = Call.objects.get(pk=call_id, server_id=server_id)
    except Call.DoesNotExist:
        return

    legs = (
        Leg.objects.filter(server=server_id)
        .exclude(call=call_id)
        .filter(Q(guid__in=leg_guids) | Q(guid2__in=leg_guids))
    )
    with transaction.atomic():
        try:
            locked_legs = legs.select_for_update(of=('self',), nowait=True).only('id')
            list(locked_legs)
        except Exception:
            locked_legs = list(legs.select_for_update(of=('self',), skip_locked=True).only('id'))
            self.retry(countdown=10 * 60 + randint(1, 90))

        locked_legs.update(call=call)
