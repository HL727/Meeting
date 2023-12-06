from django.utils.translation import ugettext_lazy as _
from django.db import models


class Theme(models.Model):
    logo_image = models.FileField(verbose_name=_('Logo'), upload_to='theme', blank=True)
    favicon = models.FileField(verbose_name=_('Favicon'), upload_to='theme', blank=True)
    dark_mode = models.BooleanField(_('Använd mörk bakgrund där logotyp visas'), default=True)
