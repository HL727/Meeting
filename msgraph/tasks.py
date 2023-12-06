from datetime import timedelta

from django.conf import settings
from django.utils.timezone import now
from oauthlib.oauth2 import InvalidClientError
from sentry_sdk import capture_exception

from conferencecenter.celery import app
from provider.exceptions import (
    ResponseConnectionError,
    ResponseTimeoutError,
    AuthenticationError,
    ResponseError,
)
from shared.exceptions import format_exception
from shared.utils import partial_update
from .handler import MSGraphHandler
from .models import MSGraphCredentials


USE_INCREMENTAL = settings.DEBUG  # Enable when done/tested


@app.task
def poll_msgraph():
    for cred_obj in MSGraphCredentials.objects.filter(enable_sync=True):
        if not cred_obj.oauth_credential_id:
            continue
        poll_msgraph_single.delay(cred_obj.pk)
        sync_msgraph_rooms.delay(cred_obj.pk)


def _log_error(cred_obj: MSGraphCredentials, message: str, content: str):
    from debuglog.models import ErrorLog

    ErrorLog.objects.store(
        title=message,
        type='msgraph',
        content=content,
        customer=cred_obj.customer,
    )


@app.task(time_limit=15 * 60, soft_time_limit=15 * 60 - 10, expires=15 * 60)
def poll_msgraph_single(cred_obj, incremental=None):

    if isinstance(cred_obj, int):
        cred_obj = MSGraphCredentials.objects.get(pk=cred_obj)

    if incremental is None:
        incremental = not cred_obj.should_sync_full

    try:
        handler = MSGraphHandler(cred_obj)
        if incremental and USE_INCREMENTAL:
            incremental_since = cred_obj.last_incremental_sync or now() - timedelta(days=7)
            handler.sync(now(), now() + timedelta(days=30), incremental_since=incremental_since)
        elif incremental:
            handler.sync(now(), now() + timedelta(days=1))  # sync full but only today
        else:
            handler.sync(now().replace(hour=0), now() + timedelta(days=21))
    except Exception as e:
        _log_error(cred_obj, 'Error syncing ms graph calendar', str(e))

        partial_update(
            cred_obj,
            {
                'last_sync_error': format_exception(e),
                'is_working': False,
            },
        )
        if isinstance(e, InvalidClientError):
            partial_update(
                cred_obj,
                {
                    'enable_sync': False,
                },
            )
        if settings.DEBUG or settings.TEST_MODE:
            raise
        if not isinstance(e, (ResponseConnectionError, ResponseTimeoutError)):
            capture_exception()
        return

    partial_update(cred_obj, {
        'last_sync_error': '',
        'is_working': True,
        **({'last_incremental_sync': now()} if incremental else {'last_sync': now()}),
    })


@app.task
def sync_msgraph_rooms(credential_id=None):

    credentials = MSGraphCredentials.objects.filter(enable_sync=True)
    if credential_id:
        credentials = credentials.filter(pk=credential_id)

    for credential in credentials:
        try:
            credential.sync_rooms()
        except AuthenticationError as e:
            _log_error(credential, 'Error syncing ms graph calendar', str(e))
            partial_update(
                credential,
                {
                    'last_sync_error': format_exception(e),
                    'is_working': False,
                },
            )
        except ResponseError as e:
            _log_error(credential, 'Error syncing ms graph calendar', str(e))
            partial_update(
                credential,
                {
                    'last_sync_error': format_exception(e),
                },
            )
