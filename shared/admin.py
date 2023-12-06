from django.conf import settings
from django.contrib import admin

UNREGISTER_APPS = (
    'adminusers',
    'django_celery_beat',
    'ui_message',
    'sites',
)


def unregister():
    for model in list(admin.site._registry.keys()):

        if model._meta.app_label in UNREGISTER_APPS:
            admin.site.unregister(model)

        elif model._meta.app_label == 'axes' and 'AccessLog' in model.__name__:
            admin.site.unregister(model)


if not settings.DEBUG or 1:
    unregister()
