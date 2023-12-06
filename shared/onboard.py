from datetime import timedelta

from celery.schedules import crontab
from django.conf import settings
from django.contrib.auth.models import User
from django.contrib.sites.models import Site

from django.utils import translation
from sentry_sdk import capture_exception

from customer.models import Customer, CustomerKey
from license.models import License


def init_db(first_install=False):
    lang = translation.get_language()
    translation.activate(settings.DEFAULT_LANGUAGE)

    should_create_user = False
    if not User.objects.all():
        should_create_user = True  # TODO check ldap?

    if should_create_user:
        User.objects.create(username='mividas_fallback', is_staff=True, is_superuser=True,
                                   password='')

    if not Customer.objects.all():
        customer = Customer.objects.create(title='')
        for k in settings.API_KEYS:
            CustomerKey.objects.create(customer=customer, shared_key=k)

    Site.objects.update_or_create(
        id=1, defaults=dict(name=settings.HOSTNAME[:50], domain=settings.HOSTNAME[:100])
    )

    from api_key.models import BookingAPIKey
    BookingAPIKey.objects.populate_system_keys()

    try:
        from provider.ext_api.acano import AcanoAPI
        AcanoAPI.sync_profiles_all()
    except Exception:
        capture_exception()

    from ui_message.models import Message

    Message.objects.init_default()

    cleanup_old_celery_tasks()

    License.objects.sync_from_settings()

    translation.activate(lang)

    try:
        from address.models import AddressBook, Group

        if not Group.objects.filter(sync_group__isnull=False).exists():
            for book in AddressBook.objects.all():
                book.merge_groups()
    except Exception:
        capture_exception()


def cleanup_old_celery_tasks():

    from django_celery_beat.models import PeriodicTask
    from conferencecenter.celery import CELERYBEAT_SCHEDULE

    deprecated = [
        'endpoint.tasks.run_pending_endpoint_tasks',
        'endpoint.tasks.update_endpoint_task_contraint_times',
        'exchange.tasks.poll_ews_incremental',
        'msgraph.tasks.poll_msgraph_incremental',
    ]
    PeriodicTask.objects.filter(task__in=deprecated).delete()

    # migrate tasks with both interval and crontab (changed from one to the other)
    for task in PeriodicTask.objects.all():
        schedule = CELERYBEAT_SCHEDULE.get(task.name, {}).get('schedule')
        if isinstance(schedule, crontab) and task.interval:
            task.delete()  # recreate
        elif isinstance(schedule, timedelta) and task.crontab:
            task.delete()  # recreate

