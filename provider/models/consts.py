import logging

from django.conf import settings

ENABLE_CELERY = getattr(settings, 'ACTIVATE_CELERY', None) or getattr(settings, 'CELERY_TASK_ALWAYS_EAGER', None)

TASK_DELAY = 5

# Sync with `provider.models.provider.Provider.TYPES`
MCU_CLUSTER_TYPES = (4, 6)
CLEARSEA_CLUSTER_TYPES = (1,)
