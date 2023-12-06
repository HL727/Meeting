# -*- coding: utf-8 -*-
from datetime import timedelta

from django.conf import settings
from django.utils.timezone import now
from requests import Timeout
from sentry_sdk import capture_exception

from conferencecenter.celery import app
from provider.exceptions import ResponseConnectionError, ResponseTimeoutError, AuthenticationError
from shared.exceptions import format_exception
from shared.utils import partial_update
from .handler import ExchangeHandler
from .models import EWSCredentials


USE_INCREMENTAL = settings.DEBUG  # Enable when done/tested


@app.task
def poll_ews():
    for cred_obj in EWSCredentials.objects.filter(enable_sync=True):

        poll_ews_single.delay(cred_obj.pk)
        sync_ews_rooms.delay(credential_id=cred_obj.pk)


@app.task(time_limit=15 * 60, soft_time_limit=15 * 60 - 10, expires=15 * 60)
def poll_ews_single(cred_obj, incremental=None):

    if isinstance(cred_obj, int):
        cred_obj = EWSCredentials.objects.get(pk=cred_obj)

    if incremental is None:
        incremental = not cred_obj.should_sync_full

    try:
        handler = ExchangeHandler(cred_obj)
        if incremental and USE_INCREMENTAL:
            incremental_since = cred_obj.last_incremental_sync or now() - timedelta(days=7)
            handler.sync(now(), now() + timedelta(days=30), incremental_since=incremental_since)
        elif incremental:
            handler.sync(now(), now() + timedelta(days=1))  # sync full but only today
        else:
            handler.sync(now().replace(hour=0), now() + timedelta(days=21))
    except Exception as e:
        _log_error(cred_obj, 'Error syncing EWS calendar', str(e))

        partial_update(
            cred_obj,
            {
                'last_sync_error': format_exception(e),
                'is_working': False,
            },
        )
        if settings.DEBUG or settings.TEST_MODE:
            raise
        if not isinstance(e, (ResponseConnectionError, ResponseTimeoutError, Timeout)):
            capture_exception()
        return

    partial_update(cred_obj, {
        'last_sync_error': '',
        'is_working': True,
        **({'last_incremental_sync': now()} if incremental else {'last_sync': now()}),
    })


@app.task(time_limit=10 * 60, soft_time_limit=10 * 60 - 10, expires=10 * 60)
def sync_ews_rooms(credential_id=None):

    credentials = EWSCredentials.objects.filter(enable_sync=True)
    if credential_id:
        credentials = credentials.filter(pk=credential_id)

    for credential in credentials:
        try:
            credential.sync_rooms()
        except AuthenticationError as e:
            _log_error(credential, 'Error syncing EWS rooms', str(e))

            partial_update(
                credential,
                {
                    'last_sync_error': format_exception(e),
                    'is_working': False,
                },
            )
        except Exception as e:
            _log_error(credential, 'Error syncing EWS rooms', str(e))
            capture_exception()
            continue


def _log_error(cred_obj: EWSCredentials, message: str, content: str):
    from debuglog.models import ErrorLog

    ErrorLog.objects.store(
        title=message,
        type='ews',
        content=content,
        customer=cred_obj.customer,
    )
