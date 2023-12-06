from enum import IntEnum

from django.db import models
from django.utils.timezone import now
from django.utils.translation import ugettext_lazy as _

from customer.models import Customer


class EndpointBrandingProfile(models.Model):

    customer = models.ForeignKey(Customer, on_delete=models.CASCADE)
    name = models.CharField(_('Namn'), max_length=100, blank=True)
    ts_created = models.DateTimeField(default=now)


class EndpointBrandingFile(models.Model):

    class BrandingType(IntEnum):
        Background = 1
        Branding = 2

        HalfwakeBackground = 3
        HalfwakeBranding = 4

        CameraBackground1 = 5  # Special handling in cisco_ce.py
        # CAMERA_BACKGROUND2 = 6

        labels: dict

    BrandingType.labels = {
        BrandingType.Background.value: _('Bakgrund, aktiv skärm'),
        BrandingType.Branding.value: _('Logotyp'),
        BrandingType.HalfwakeBackground.value: _('Bakgrund, ej aktiv skärm'),
        BrandingType.HalfwakeBranding.value: _('Logotyp, ej aktiv skärm'),
        BrandingType.CameraBackground1.value: _('Virtuell bakgrund kamera'),
    }

    BrandingType.help_texts = {
        BrandingType.Background.value: (
            'The brand image will be displayed as a background on both the main screen and on '
            'the touch panel when the video system is in the awake state. The recommended '
            'image size is 3840×2160 pixels. Note! This will disable OBTP and meeting info'
        ),
        BrandingType.Branding.value: (
            'This light brand logo will be displayed on a dark background in the bottom right corner '
            'on both the main screen and the touch panel. For best results, the logo should be an all white '
            'version without padding, in png format with a transparent background. The recommended '
            'size is 272×272 pixels'
        ),
        BrandingType.HalfwakeBackground.value: (
            'The brand image will be displayed as a background on both '
            'the main screen and on the touch panel when the video system '
            'is in the halfwake state. The recommended image size is '
            '3840×2160 pixels, in png or jpeg format'
        ),
        BrandingType.HalfwakeBranding.value: (
            'This light brand logo will be displayed on a dark background in the bottom right corner '
            'on both the main screen and the touch panel. For best results, the logo should be an all white '
            'version without padding, in png format with a transparent background. The recommended '
            'size is 272×272 pixels'
        ),
        BrandingType.CameraBackground1.value: _('Virtuell bakgrund kamera'),
    }

    profile = models.ForeignKey(EndpointBrandingProfile, on_delete=models.CASCADE, related_name='files')
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE)

    type = models.SmallIntegerField(choices=[(int(t.value), t.name) for t in BrandingType])
    file = models.ImageField(upload_to='branding')
    use_standard = models.BooleanField(default=False, blank=True)

    class Meta:
        unique_together = ('profile', 'type')

    def save(self, *args, **kwargs):
        if not self.customer_id and self.profile_id:
            self.customer = self.profile.customer
        super().save(*args, **kwargs)


