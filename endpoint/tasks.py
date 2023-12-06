
import concurrent
import contextlib
import logging
from collections import defaultdict
from datetime import timedelta
from typing import TYPE_CHECKING, Any, DefaultDict, List, Mapping, Optional, Set, Tuple, Union

import celery
from celery import Task, chain
from django.conf import settings
from django.core.cache import cache
from django.db import transaction
from django.db.models import Q
from django.http import Http404
from django.utils.encoding import force_bytes
from django.utils.timezone import now
from sentry_sdk import capture_exception

from address.models import AddressBook
from conferencecenter.celery import app
from endpoint.consts import CONNECTION, STATUS, TASKSTATUS
from endpoint.threading import endpoint_thread_pool
from provider.exceptions import ResponseConnectionError

if TYPE_CHECKING:
    from endpoint.ext_api.cisco_ce import CiscoCEProviderAPI
    from endpoint.models import Endpoint
    from endpoint_data.models import EndpointDataFileBase

logger = logging.getLogger(__name__)


@app.task(bind=True)
def backup_endpoint(self: Task, endpoint_id: int):

    from .models import Endpoint
    try:
        obj = Endpoint.objects.get(pk=endpoint_id)
    except Endpoint.DoesNotExist:
        return

    obj.backup(sync=True)


def sync_endpoint_bookings_locked_delay(endpoint_id: int):
    cache_key = 'sync_endpoint_bookings.{}'.format(endpoint_id)
    if cache.get(cache_key):
        return

    cache.set(cache_key, 1, 60)
    sync_endpoint_bookings.apply_async([endpoint_id], countdown=1.5)


@app.task(bind=True)
def sync_endpoint_bookings(self: Task, endpoint_id: int):
    cache_key = 'sync_endpoint_bookings.{}'.format(endpoint_id)
    cache.delete(cache_key)

    from .models import Endpoint
    try:
        obj = Endpoint.objects.get(pk=endpoint_id)
    except Endpoint.DoesNotExist:
        return

    error: Union[Exception, bool] = False

    if obj.has_direct_connection:
        try:
            obj.sync_bookings()
        except ResponseConnectionError:
            error = True
        except Exception as e:
            error = e
    elif obj.connection_type in (Endpoint.CONNECTION.PROXY, ):
        error = True

    if error:
        if isinstance(error, Exception):
            message = str(error)
        else:
            message = 'Could not send bookings, no active connection available'

        from debuglog.models import EndpointCiscoProvision
        EndpointCiscoProvision.objects.store(message, endpoint=obj, event='bookings')


@app.task(bind=True)
def update_active_meeting(self: Task, endpoint_id: int):
    from .models import Endpoint
    try:
        endpoint = Endpoint.objects.get(pk=endpoint_id)
    except Endpoint.DoesNotExist:
        return

    endpoint.update_active_meeting()


@app.task(bind=True)
def sync_upcoming_endpoint_bookings(self):

    from .models import Endpoint

    for endpoint in Endpoint.objects.distinct().filter(
        meetings__ts_stop__gt=now(),
        meetings__ts_start__lte=now() + timedelta(hours=4),
        meetings__backend_active=True
    ):
        sync_endpoint_bookings_locked_delay(endpoint.pk)


@app.task(bind=True, time_limit=15 * 60, soft_time_limit=15 * 60 - 30)
def update_all_endpoint_status(self: Task, extra_filter=None):
    """
    Fetch status for all endpoints that has not been sending events.
    """
    UpdateEndpointStatusRunner(extra_filter=extra_filter, timeout=15 * 60 - 30).run()


class UpdateEndpointStatusRunner:
    """
    Fetch status and configuration data in separate thread and process the results
    """

    def __init__(self, extra_filter=None, timeout=15 * 60):
        self.extra_filter = extra_filter or {}
        self.limit = now() - timedelta(seconds=15 * 60)
        self.timeout = timeout
        self.timeout_reached = False

    def get_endpoints(self):
        from .models import Endpoint

        return (
            Endpoint.objects.filter(
                Q(status__ts_last_check__isnull=True) | Q(status__ts_last_check__lt=self.limit),
                **(self.extra_filter or {}),
            )
            .exclude(connection_type=CONNECTION.PASSIVE)
            .select_related('status', 'customer')
        )

    def _fetch_data(
        self, api: 'CiscoCEProviderAPI'
    ) -> Tuple['EndpointDataFileBase', 'EndpointDataFileBase']:
        logger.debug('Fetch status for endpoint {}'.format(api.endpoint.id))
        status = api.get_status_data_file(force=True)
        logger.debug('Fetch configuration for endpoint {}'.format(api.endpoint.id))
        configuration = api.get_configuration_data_file(force=True)
        return status, configuration

    def silence_timeout(self, iterable):
        try:
            yield from iterable
        except (concurrent.futures.TimeoutError, celery.exceptions.TimeoutError):
            logger.warning('Timeout error')
            self.timeout_reached = True
            return
        self.timeout_reached = False

    @contextlib.contextmanager
    def ignore_exceptions(self, endpoint, action):
        class Status:
            success = True

        try:
            yield Status
        except (concurrent.futures.TimeoutError, celery.exceptions.TimeoutError):
            logger.info('Error during {}. Endpoint %s'.format(action), endpoint.pk, exc_info=True)
            raise
        except Exception:
            Status.success = False
            logger.info('Error during {}. Endpoint %s'.format(action), endpoint.pk, exc_info=True)

    def run(self):
        for endpoint, fds in self.silence_timeout(
            endpoint_thread_pool(
                self.get_endpoints().iterator(),
                self._fetch_data,
                timeout=self.timeout,
                processes=10,
            )
        ):

            if isinstance(fds, Exception):
                with self.ignore_exceptions(endpoint, 'status fetch'):
                    endpoint.update_status(fds, raise_exceptions=False)
                    logger.info('Error when fetching status for endpoint %s(%s): %s', endpoint.pk, endpoint.hostname, fds)
                continue

            status_fd, configuration_fd = fds
            self.process_status_result(endpoint, status_fd)
            self.process_configuration_result(endpoint, configuration_fd)

        self.set_other_systems_as_offline()

    def process_status_result(self, endpoint: 'Endpoint', status_fd):
        logger.debug('Start parsing status for endpoint %s', endpoint.pk)

        status_data = None  # noqa

        with self.ignore_exceptions(endpoint, 'status parsing') as status:
            status_data = endpoint.get_api().get_status_data(fd=status_fd)
            if not status.success:
                return

        if not status_data:
            return

        with self.ignore_exceptions(endpoint, 'status update'):
            endpoint.update_status(status_data, raise_exceptions=False)

        with self.ignore_exceptions(endpoint, 'feedback slot check'):
            endpoint.get_api().check_events_status(status_data=status_data, delay_fix=True)

    def process_configuration_result(self, endpoint: 'Endpoint', configuration_fd):
        logger.debug('Start parsing configuration for endpoint %s', endpoint.pk)

        configuration_data = None  # noqa

        with self.ignore_exceptions(endpoint, 'configuration parsing') as status:
            configuration_data = endpoint.get_api().get_configuration_data(
                fd=configuration_fd, require_valuespace=False
            )
            print('configuration data:', configuration_data)
            if not status.success:
                return

        with self.ignore_exceptions(endpoint, 'dial info update'):
            endpoint.update_dial_info(configuration_data=configuration_data)

    def set_other_systems_as_offline(self):
        from .models import Endpoint, EndpointStatus

        limit = self.limit
        if self.timeout_reached:
            limit -= timedelta(seconds=20 * 60)

        # offline proxies
        EndpointStatus.objects.filter(
            ts_last_online__lt=limit,
            status=Endpoint.STATUS.ONLINE,
            endpoint__connection_type=Endpoint.CONNECTION.PROXY,
            endpoint__proxy__is_online=False,
        ).update(status=Endpoint.STATUS.UNKNOWN)

        # other
        EndpointStatus.objects.filter(
            ts_last_online__lt=limit,
            status=Endpoint.STATUS.ONLINE,
        ).exclude(endpoint__connection_type=Endpoint.CONNECTION.PROXY,).update(
            status=Endpoint.STATUS.OFFLINE
        )


@app.task(bind=True, time_limit=10 * 60, soft_time_limit=8 * 60 - 10)
def sync_address_books(self: Task, pk=None):

    books = AddressBook.objects.all()
    if pk:
        books = books.filter(pk=pk)

    for book in books:
        book.sync()


@app.task(bind=True)
def update_endpoint_status(self: Task, endpoint_id: int):
    from provider.exceptions import AuthenticationError, ResponseError

    from .models import Endpoint

    endpoint = endpoint_id if isinstance(endpoint_id, Endpoint) else Endpoint.objects.get(pk=endpoint_id)

    try:
        was_online = endpoint.is_online
        endpoint.update_status()
        if not was_online:
            logger.info('Endpoint status changed to online ID {}'.format(endpoint.id))
    except (ResponseError, AuthenticationError):
        pass
    except Exception as ex:
        logger.warn('Error when updating status ID ({}): {}'.format(endpoint.id, ex))
        capture_exception()


@app.task(bind=True, time_limit=600, soft_time_limit=540)
def update_all_data(self: Task, endpoint_ids):

    if isinstance(endpoint_ids, int):
        endpoint_ids = [endpoint_ids]

    from endpoint.models import Endpoint

    endpoints = Endpoint.objects.filter(pk__in=endpoint_ids).select_related('status')

    for _r in endpoint_thread_pool(
        endpoints, lambda api: api.endpoint.update_all_data(), timeout=540
    ):
        pass


@app.task(bind=True)
def update_endpoint_task_constraint_times(self):

    from endpoint_provision.models import EndpointProvision
    EndpointProvision.objects.update_constraint_times()


@app.task(bind=True)
def queue_pending_endpoint_tasks(self: Task, endpoint_ids=None, endpoint_id=None, count=80):

    from endpoint.models import Endpoint
    from endpoint_provision.models import EndpointTask

    if endpoint_id:  # TODO remove when all historic tasks with argument is done
        endpoint_ids = [endpoint_id]

    if endpoint_ids:
        if isinstance(endpoint_ids, int):
            endpoint_ids = [endpoint_ids]
        unknown_status = Endpoint.objects.filter(
            pk__in=endpoint_ids, status__status__lte=STATUS.UNKNOWN
        )
        if settings.TEST_MODE:
            [e.check_online() for e in unknown_status]
        else:
            update_all_endpoint_status(
                extra_filter={'id__in': unknown_status.values_list('pk', flat=True)}
            )

    limit = now() - timedelta(minutes=10)

    tasks = EndpointTask.objects.filter(
            Q(ts_last_attempt__isnull=True) | Q(ts_last_attempt__lt=limit),
            Q(ts_schedule_attempt__isnull=True) | Q(ts_schedule_attempt__lte=now()),
            status=TASKSTATUS.PENDING,
            endpoint__status__status__gt=STATUS.UNKNOWN,
            endpoint__connection_type__in=[CONNECTION.DIRECT, CONNECTION.PROXY],
            **({'endpoint__in': endpoint_ids} if endpoint_ids else {}),
    )

    logger.info('Started running tasks')

    run_tasks: DefaultDict[int, List[int]] = defaultdict(list)
    run_slow_tasks: DefaultDict[int, List[int]] = defaultdict(list)

    offline_tasks = defaultdict(list)

    currently_queued = EndpointTask.objects.filter(status=TASKSTATUS.QUEUED).count()
    if currently_queued > 200:
        count = 10
    elif currently_queued > 100:
        count = 30
    else:
        count = 150

    with transaction.atomic():
        for task in tasks.select_related('provision', 'endpoint').select_for_update(skip_locked=True, of=('self',))[:count]:
            if not task.endpoint or not task.provision:
                continue
            assert task.endpoint_id

            if not task.endpoint.has_direct_connection or not task.endpoint.is_online:
                offline_tasks[task.endpoint_id].append(task.id)
                continue

            if not task.provision.check_constraint(timezone=task.endpoint.timezone):
                continue

            if task.is_slow:
                run_slow_tasks[task.endpoint_id].append(task.pk)
            else:
                run_tasks[task.endpoint_id].append(task.pk)

        all_tasks = {v for lst in run_tasks.values() for v in lst} | {
            v for lst in run_slow_tasks.values() for v in lst
        }
        EndpointTask.objects.filter(pk__in=all_tasks).update(
            status=EndpointTask.TASKSTATUS.QUEUED, ts_last_attempt=now()
        )

        EndpointTask.objects.filter(pk__in=offline_tasks).update(ts_last_attempt=now())

    # run each task grouped by endpoint. TODO: merge multiple configuration/commands
    for task_ids in run_tasks.values():
        chain([run_task.si(task_id) for task_id in task_ids]).delay()
    for task_ids in run_slow_tasks.values():
        chain([run_slow_task.si(task_id) for task_id in task_ids]).delay()


@app.task
def reset_old_queued_task():

    from endpoint_provision.models import EndpointTask

    limit = now() - timedelta(minutes=60)

    EndpointTask.objects.filter(status=EndpointTask.TASKSTATUS.QUEUED).filter(
        Q(ts_last_attempt__isnull=True) | Q(ts_last_attempt__lt=limit)
    ).update(status=EndpointTask.TASKSTATUS.PENDING)


@app.task(bind=True)
def update_endpoint_statistics(self: Task, endpoint_id: int, limit: int = None):

    from .models import Endpoint

    try:
        endpoint = endpoint_id if isinstance(endpoint_id, Endpoint) else Endpoint.objects.get(pk=endpoint_id)
    except Endpoint.DoesNotExist:
        return

    if not endpoint.has_direct_connection:
        return

    try:
        endpoint.get_api().update_statistics(**({'limit': limit} if limit else {}))
    except ResponseConnectionError:
        pass
    except Exception:
        capture_exception()
        if settings.TEST_MODE:
            raise


@app.task(bind=True, time_limit=5 * 60, soft_time_limit=5 * 60 - 10)
def run_slow_task(self: Task, task_id: int):
    _lock_and_run_task(self, task_id)


@app.task(bind=True)
def run_task(self: Task, task_id: int):
    _lock_and_run_task(self, task_id)


def _lock_and_run_task(self: Task, task_id: int):
    from endpoint_provision.models import EndpointTask
    start = now()

    with transaction.atomic():
        try:
            task = EndpointTask.objects\
                .select_for_update(of=('self',))\
                .filter(status__in=(EndpointTask.TASKSTATUS.PENDING, EndpointTask.TASKSTATUS.QUEUED))\
                .get(pk=task_id)
        except EndpointTask.DoesNotExist:
            return
        else:
            try:
                _run_endpoint_task(task)
            except Exception as e:
                logger.info('Got exception %s after %s', e, (now() - start).total_seconds())
                raise


def _run_endpoint_task(task):

    from provider.exceptions import AuthenticationError, ResponseError
    try:
        logger.info('Running task ID {}'.format(task.id))
        task.run()
    except AuthenticationError as e:
        logger.info('Authentication error when running task ID ({}): {}'.format(task.id, e))
    except ResponseError as e:
        logger.info('Response-error when running task ID ({}): {}'.format(task.id, e))
    except Exception as e:
        logger.warn('Error when running task ID ({}): {}'.format(task.id, e))
        capture_exception()
        if settings.TEST_MODE:
            raise
    else:
        logger.info('Finished task ID {}'.format(task.id))
        return

    if task.status == task.TASKSTATUS.QUEUED:
        raise ValueError('Task should not be queued')  # FIXME remove TEMP


@app.task
def handle_endpoint_event(
    payload: Union[str, bytes], remote_ip: Optional[str], customer_secret=None, endpoint_secret=None
):

    from endpoint.models import Endpoint

    from .views import handle_tms_event as _handle

    try:
        _handle(
            force_bytes(payload),
            remote_ip,
            customer_secret=customer_secret,
            endpoint_secret=endpoint_secret,
        )
    except Endpoint.DoesNotExist:  # debug mode
        pass
    except Http404:
        pass


@app.task
def handle_tms_document(
    payload: Union[str, bytes],
    customer_secret: str = None,
    endpoint_secret: str = None,
    remote_ip: Optional[str] = None,
):
    from endpoint.models import Endpoint
    from endpoint_provision.views_tms_provision import handle_tms_document as _handle_tms_document

    try:
        _handle_tms_document(
            force_bytes(payload),
            customer_secret=customer_secret,
            endpoint_secret=endpoint_secret,
            remote_ip=remote_ip,
        )
    except Endpoint.DoesNotExist:  # debug mode
        pass


@app.task
def register_devices(
    endpoint_ids: Union[List['Endpoint'], List[int]], dial_info: Mapping[str, Any]
) -> Union[None, Set[str]]:

    if not endpoint_ids:
        return None

    if isinstance(endpoint_ids[0], int):
        from endpoint.models import Endpoint
        endpoints = Endpoint.objects.filter(pk__in=endpoint_ids).prefetch_related('customer')
    else:
        endpoints = endpoint_ids

    api = endpoints[0].customer.get_api()
    if not api.cluster.is_pexip:
        return None

    result = set()

    for endpoint in endpoints:
        endpoint_dial_info = {**dial_info}

        if endpoint_dial_info.get('sip_proxy_password'):
            endpoint_dial_info['sip_proxy_password'] = endpoint.get_api()._get_sip_proxy_password(
                endpoint_dial_info['sip_proxy_password'], endpoint.customer, endpoint_dial_info
            )

        for k in ('sip', 'h323', 'h323_e164'):
            if not endpoint_dial_info.get(k) and getattr(endpoint, k, None):
                endpoint_dial_info[k] = getattr(endpoint, k)

        if not any(endpoint_dial_info.get(k) for k in ('sip', 'h323', 'h323_e164')):
            from debuglog.models import ErrorLog

            logger.warning(
                'Could not register endpoint %s (%s) to Pexip Infinity, no alias data available',
                endpoint.pk,
                endpoint,
            )

            ErrorLog.objects.store(
                'No SIP/H323/e.164 set',
                customer=api.customer,
                endpoint=endpoint,
                title='Could not register endpoint to Pexip Infinity',
                type='endpoint',
            )
            continue

        try:
            result |= api.register_device_endpoint(
                endpoint_dial_info,
                description=str(endpoint),
                username=endpoint_dial_info.get('sip_proxy_username'),
                password=endpoint_dial_info.get('sip_proxy_password'),
            )
        except Exception:
            if settings.TEST_MODE or settings.DEBUG:
                raise

    return result
