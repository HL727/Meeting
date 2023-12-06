from django.conf import settings
from django.contrib import admin
from . import models


if settings.ENABLE_CORE:
    admin.site.register(models.SeeviaSync)
    admin.site.register(models.LdapSync)
