import logging
from datetime import timedelta

from celery import Task
from django.utils.timezone import now

from conferencecenter.celery import app

logger = logging.getLogger(__name__)


@app.task(bind=True, time_limit=3 * 60, soft_time_limit=3 * 60 - 10)
def update_proxy_status(self: Task):
    from .models import EndpointProxy

    active_limit = now() - timedelta(minutes=5)

    for p in EndpointProxy.objects.filter(last_active__lt=active_limit):
        p.check_active()
        # TODO skip proxies with really old last connect

