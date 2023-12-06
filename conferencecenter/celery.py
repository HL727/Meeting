import logging

from celery import Celery
from celery.schedules import crontab

from os import environ

from kombu import Queue

environ.setdefault('DJANGO_SETTINGS_MODULE', 'conferencecenter.settings')

from django.conf import settings


from datetime import timedelta


logger = logging.getLogger(__name__)

app = Celery('provider.tasks')
app.config_from_object('django.conf:settings', namespace='CELERY')

app.autodiscover_tasks()


def get_task_routes():
    """
    Override queue for specific tasks
    """

    slow_tasks = [
        'endpointproxy.tasks.update_proxy_status',
        'policy.tasks.recheck_policy_states',
        'provider.tasks.store_provider_load',
        'provider.tasks.unbook_expired',
        'endpoint.tasks.run_slow_task',
        'endpoint.tasks.update_all_endpoint_status',
        'endpoint.tasks.update_all_data',
    ]

    sync_tasks = [
        'endpoint.tasks.sync_address_books',
        'provider.tasks.cache_ldap_data',
        'provider.tasks.set_cospace_stream_urls',
        'provider.tasks.update_pexip_statistics',
        'provider.tasks.update_vcse_statistics ',
        'exchange.tasks.sync_ews_rooms',
        'exchange.tasks.poll_ews_single',
        'exchange.tasks.sync_msgraph_rooms',
        'exchange.tasks.poll_msgraph_single',
    ]

    slow_sync_tasks = [
        'provider.tasks.cache_cluster_data',
        'provider.tasks.cache_single_cluster_data',
        'provider.tasks.cache_cluster_data_incremental',
        'provider.tasks.cache_single_cluster_data_incremental',
    ]

    cdr_tasks = [
        'statistics.tasks.handle_acano_cdr',
        'statistics.tasks.handle_pexip_cdr',
        'endpoint.tasks.handle_endpoint_event',
    ]

    return [
        [(task, {'queue': 'slow'}) for task in slow_tasks],
        [(task, {'queue': 'sync'}) for task in sync_tasks],
        [(task, {'queue': 'sync'}) for task in slow_sync_tasks],
        [(task, {'queue': 'cdr'}) for task in cdr_tasks],
    ]


app.conf.task_routes = get_task_routes()
app.conf.task_queues = [
    Queue('celery'),
    Queue('cdr'),
    Queue('slow'),
    Queue('sync'),
]


CELERYBEAT_SCHEDULE = {
        'sync-cospace-ids': {
            'task': 'provider.tasks.sync_cospace_callids',
            'schedule': timedelta(seconds=60 * 60),
            'args': (),
            'options': {
                'expires': 60 * 60,
            },
        },
        'update_status_file': {
            'task': 'provider.tasks.update_status_file',
            'schedule': timedelta(seconds=60),
            'args': (),
            'options': {
                'expires': 120 - 1,
            },
        },
        'sync_acano_users': {
            'task': 'provider.tasks.sync_acano_users',
            'schedule': timedelta(minutes=60),
            'args': (),
            'options': {
                'expires': 60 * 60 - 1,
            },
        },
        'check_hook_sessions': {
            'task': 'provider.tasks.check_hook_sessions',
            'schedule': timedelta(minutes=5),
            'args': (),
            'options': {
                'expires': 5 * 60 - 1,
            },
        },
        'unbook_expired': {
            'task': 'provider.tasks.unbook_expired',
            'schedule': timedelta(minutes=10),
            'args': (),
            'options': {
                'expires': 10 * 60 - 10,
            },
        },
        'clean_stale_data': {
            'task': 'provider.tasks.clean_stale_data',
            'schedule': timedelta(days=1),
            'args': (),
            'options': {
                'expires': 24 * 60 * 60 - 1,
            },
        },
        'sync_ldap': {
            'task': 'provider.tasks.sync_ldap',
            'schedule': timedelta(hours=1),
            'args': (),
            'options': {
                'expires': 60 * 60 - 1,
            },
        },
        'update_vcse_statistics': {
            'task': 'provider.tasks.update_vcse_statistics',
            'schedule': timedelta(minutes=20),
            'args': (),
            'options': {
                'expires': 20 * 60 - 1,
            },
        },
        'update_pexip_statistics': {
            'task': 'provider.tasks.update_pexip_statistics',
            'schedule': timedelta(minutes=10),
            'args': (),
            'options': {
                'expires': 10 * 60 - 1,
            },
        },
        'store_provider_load': {
            'task': 'provider.tasks.store_provider_load',
            'schedule': timedelta(minutes=3),
            'args': (),
            'options': {
                'expires': 3 * 60 - 1,
            },
        },
        'clean_ghost_calls': {
            'task': 'provider.tasks.clean_ghost_calls',
            'schedule': timedelta(minutes=60),
            'args': (),
            'options': {
                'expires': 60 * 60 - 1,
            },
        },
        'clear_old_call_chat_messages': {
            'task': 'provider.tasks.clear_old_call_chat_messages',
            'schedule': timedelta(minutes=settings.CLEAR_CHAT_INTERVAL or 24 * 60 * 60),
            'args': (),
            'options': {
                'expires': (settings.CLEAR_CHAT_INTERVAL or 2) * 60 - 1,
            },
        },
        'check_recordings': {
            'task': 'provider.tasks.check_recordings',
            'schedule': timedelta(minutes=5),
            'args': (),
            'options': {
                'expires': 5 * 60 - 1,
            },
        },
        'set_cospace_stream_urls': {
            'task': 'provider.tasks.set_cospace_stream_urls',
            'schedule': timedelta(minutes=60),
            'args': (),
            'options': {
                'expires': 60 * 60 - 1,
            },
        },
        'cache_cluster_data': {
            'task': 'provider.tasks.cache_cluster_data',
            'schedule': crontab(minute='5,20,35,50'),
            'args': (),
            'options': {
                'expires': 2 * 60 * 60 - 1,
            },
        },
        'cache_ldap_data': {
            'task': 'provider.tasks.cache_ldap_data',
            'schedule': timedelta(minutes=2* 60),
            'args': (),
            'options': {
                'expires': 2* 60 * 60 - 1,
            },
        },
        'send_call_stats': {
            'task': 'provider.tasks.send_call_stats',
            'schedule': timedelta(minutes=10),
            'args': (),
            'options': {
                'expires': 10 * 60 - 1,
            },
        },
        'update_all_endpoint_status': {
            'task': 'endpoint.tasks.update_all_endpoint_status',
            'schedule': timedelta(minutes=10),
            'args': (),
            'options': {
                'expires': 10 * 60 - 1,
            },
        },
        'sync_upcoming_endpoint_bookings': {
            'task': 'endpoint.tasks.sync_upcoming_endpoint_bookings',
            'schedule': timedelta(minutes=30),
            'args': (),
            'options': {
                'expires': 30 * 60 - 1,
            },
        },
        'update_all_endpointproxy_status': {
            'task': 'endpointproxy.tasks.update_proxy_status',
            'schedule': timedelta(minutes=10),
            'args': (),
            'options': {
                'expires': 10 * 60 - 1,
            },
        },
        'recheck_policy_states': {
            'task': 'policy.tasks.recheck_policy_states',
            'schedule': timedelta(minutes=30),
            'args': (),
            'options': {
                'expires': 30 * 60 - 1,
            },
        },
        'update_endpoint_task_constraint_times': {
            'task': 'endpoint.tasks.update_endpoint_task_constraint_times',
            'schedule': timedelta(hours=1),
            'args': (),
            'options': {
                'expires': 1 * 60 * 60 - 1,
            },
        },
        'queue_pending_endpoint_tasks': {
            'task': 'endpoint.tasks.queue_pending_endpoint_tasks',
            'schedule': timedelta(minutes=1),
            'args': (),
            'options': {
                'expires': 1 * 60 - 1,
            },
        },
        'reset_old_queued_task': {
            'task': 'endpoint.tasks.reset_old_queued_task',
            'schedule': timedelta(minutes=10),
            'args': (),
            'options': {
                'expires': 10 * 60 - 1,
            },
        },
        'sync_address_books': {
            'task': 'endpoint.tasks.sync_address_books',
            'schedule': timedelta(minutes=60),
            'args': (),
            'options': {
                'expires': 1 * 60 - 1,
            },
        },
        'poll_ews': {
            'task': 'exchange.tasks.poll_ews',
            'schedule': timedelta(minutes=3),
            'args': (),
            'options': {
                'expires': 3 * 60 - 1,
            },
        },
        'poll_msgraph': {
            'task': 'msgraph.tasks.poll_msgraph',
            'schedule': timedelta(minutes=3),
            'args': (),
            'options': {
                'expires': 3 * 60 - 1,
            },
        },
    }

if not settings.CELERY_DISABLE_BEAT:
    app.conf.CELERYBEAT_SCHEDULE = CELERYBEAT_SCHEDULE

