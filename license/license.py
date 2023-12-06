from __future__ import annotations
from datetime import date, timedelta
from typing import Dict, Optional, Iterable, Union, TYPE_CHECKING, Sequence

from license import AddonType
from license.types import LicenseFlag, AddonDefinitionDict, SettingsDefinitionDict, AddonValueDict

if TYPE_CHECKING:
    from django.db.models import QuerySet

SOFT_LIMIT_DAYS = 10
WARNING_DAYS = 60


class ParsedLicense:
    def __init__(
        self,
        value: str,
        flags: Iterable[LicenseFlag],
        settings: SettingsDefinitionDict,
        addons: AddonValueDict,
        all_addons: Iterable[AddonDefinitionDict],
        valid_until: Optional[date] = None,
        date_parsed=None,
    ):

        self.valid_until = valid_until
        self.value = value
        self.flags = frozenset(flags)
        self.settings = FrozenDict(settings)
        self.date_parsed = date_parsed or date.today()
        self.addons = FrozenDict(self._fallback_addons(addons))
        self.all_addons = tuple(all_addons)

    def has_flag(self, *flag_names: Iterable[LicenseFlag]):
        if not self._get_base_is_valid():
            return False

        if not flag_names:
            return False

        return any(flag in self.flags for flag in flag_names)

    def _fallback_addons(self, addons: AddonValueDict):
        result = {**addons}
        if self.has_flag('core:enable_core') and 'core:mcu' not in addons:
            result['core:mcu'] = -1
        if self.has_flag('core:enable_core') and 'core:cluster' not in addons:
            result['core:cluster'] = -1
        if self.settings.get('core:whitelabel') == 'pexip':
            if 'core:cluster' not in result:
                result['core:cluster'] = 1
            if 'core:mcu' not in result:
                result['core:mcu'] = 1
        elif self.has_flag('core:enable_epm') and not addons:
            result['epm:endpoint'] = -1

        return result

    def recalculate_addons(self, addons: Sequence[AddonDefinitionDict]):
        from .validator import LicenseValidator

        valid = LicenseValidator.filter_addons(addons, allow_future=True)
        return FrozenDict(self._fallback_addons(LicenseValidator.calculate_quantities(valid)))

    def get_setting(self, name: str, default=None):
        return self.settings.get(name, default)

    def get_quantity(self, name: str):

        if self.date_parsed != date.today():
            self.addons = self.recalculate_addons(self.all_addons)

        return self.addons.get(name, 0)

    def get_full_status(self) -> Dict[str, LicenseStatus]:
        from endpoint.models import Endpoint
        from provider.models.provider import Provider, Cluster

        if self.date_parsed != date.today():
            pass  # TODO recalculate

        epm_count = Endpoint.objects.exclude(connection_type=Endpoint.CONNECTION.INCOMING)
        mcu_count = Provider.objects.filter(type=Provider.TYPES.lifesize)
        cluster_count = Cluster.objects.filter(type__in=Cluster.MCU_TYPES)

        if not self._get_base_is_valid():
            epm_count = mcu_count = cluster_count = 0

        return FrozenDict(
            (state.key, state)
            for state in [
                LicenseStatus('epm:endpoint', epm_count, self.get_quantity('epm:endpoint')),
                LicenseStatus('base', self._get_base_is_valid(), 2),
                LicenseStatus('core:mcu', mcu_count, self.get_quantity('core:mcu')),
                LicenseStatus('core:cluster', cluster_count, self.get_quantity('core:cluster')),
            ]
        )

    def _get_base_is_valid(self) -> int:

        if not self.valid_until:
            return 2  # TODO force installer update

        if self.valid_until >= date.today():
            return 2
        elif self.valid_until >= date.today() - timedelta(days=SOFT_LIMIT_DAYS):
            return 1
        else:
            return 0

    def get_warnings(self):
        from django.utils.translation import gettext as _

        result = []
        if not self.valid_until:
            result.append(
                _(
                    'Det körs en för gammal version av Installer på den här servern. Vänligen uppdatera.'
                )
            )
        elif self._get_base_is_valid() == 0:
            result.append(_('Licensen har löpt ut.'))
        elif self._get_base_is_valid() == 1:
            result.append(
                _('Licensen löpte ut {valid_until}. Förnya licensen inom {days} dagar').format(
                    valid_until=self.valid_until,
                    days=SOFT_LIMIT_DAYS - (date.today() - self.valid_until).days,
                )
            )
        elif self.valid_until <= date.today() + timedelta(days=WARNING_DAYS):
            result.append(
                _('Produktlicensen löper ut om {days} dagar').format(
                    days=(self.valid_until - date.today()).days
                )
            )

        return result

    def get_status(self, key: AddonType):

        result = self.get_full_status().get(key)
        if not result and self.has_flag(key):
            return LicenseStatus(key, 0, 1)
        return result or LicenseStatus(key, 0, 0)


class LicenseStatus:
    def __init__(self, key: AddonType, value: Union[int, QuerySet], quantity: int):
        self.key = key
        self._value = value
        self.quantity = quantity

    @property
    def value(self):
        if hasattr(self._value, 'count'):
            self._value = self._value.count()
        return self._value

    @property
    def status(self):
        soft_limit = 5

        if self.value <= self.quantity or self.quantity == -1:
            return 'ok'
        elif self.value < self.quantity + soft_limit:
            return 'warning'
        else:
            return 'limit'

    @property
    def quantity_left(self):
        if self.key == 'epm:endpoint':
            soft_limit = 5
        else:
            soft_limit = 0

        if self.quantity == -1:
            return 9999

        return max(0, (self.quantity + soft_limit) - self.value)

    @property
    def allow_another(self):
        if self.quantity == -1:
            return True

        if not self.quantity:
            return False
        return self.status != 'limit'

    def as_dict(self, only_status=False):
        if only_status:
            return {'status': self.status}
        return {
            'active': self.value,
            'licensed': self.quantity,
            'status': self.status,
        }


class FrozenDict(dict):
    def update(self, *args, **kwargs):
        raise TypeError('This dict is immutable')

    def __setitem__(self, key, value):
        raise TypeError('This dict is immutable')

    def setdefault(self, *args, **kwargs):
        raise TypeError('This dict is immutable')
