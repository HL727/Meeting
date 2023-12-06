from __future__ import annotations

from contextlib import contextmanager
from typing import TYPE_CHECKING

from license.types import AddonType

if TYPE_CHECKING:
    from license.license import ParsedLicense


def get_license() -> ParsedLicense:

    from django.conf import settings

    return settings.LICENSE


def license_allow_another(addon: AddonType):
    return get_license().get_status(addon).allow_another


def license_quantity_left(addon: AddonType) -> int:
    return get_license().get_status(addon).quantity_left


@contextmanager
def lock_license(addon: AddonType = None):

    from shared.models import run_locked

    cache_key = 'license.{}'.format(addon.replace(':', '_') if addon else 'base')

    with run_locked(cache_key):
        yield
