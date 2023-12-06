import json
import sys
from base64 import b64decode
from datetime import date
from typing import Optional, Sequence, List

from django.utils.dateparse import parse_date
from typing_extensions import Counter

from license.types import (
    InputLicenseDict,
    LicenseFlag,
    SettingsDefinitionDict,
    AddonDefinitionDict,
    AddonValueDict,
    AddonType,
)

ENABLE_UNSIGNED_LICENSES = True


class LicenseValidator:
    def __init__(
        self,
        value: str,
        flags: Optional[Sequence[LicenseFlag]] = None,
        extra_settings: Optional[SettingsDefinitionDict] = None,
    ):
        self.value = value
        self.deprecated_flags = flags
        self.deprecated_settings = extra_settings

    def unpack(self) -> InputLicenseDict:
        if not self.value and ENABLE_UNSIGNED_LICENSES:
            return self._merge_extra({})
        if self.value.startswith('{') and ENABLE_UNSIGNED_LICENSES:
            return self._merge_extra(json.loads(self.value))
        return self.validate(self.value)

    def _merge_extra(self, result: dict) -> InputLicenseDict:

        if self.deprecated_flags and 'flags' not in result:
            result['flags'] = self.deprecated_flags

        if self.deprecated_settings and 'settings' not in result:
            result['settings'] = self.deprecated_settings
        return result

    def validate(self, value: str) -> InputLicenseDict:

        content, timestamp, signature = value.split('-')
        return json.loads(b64decode(content).decode('utf-8'))

    def get_flags(self):
        return self.unpack().get('flags') or {}

    def get_settings(self):
        return self.unpack().get('settings') or {}

    def get_addons(self) -> List[AddonDefinitionDict]:
        return sorted(self.unpack().get('addons') or [], key=lambda a: a['valid_from'])

    def get_valid_until(self) -> Optional[date]:
        valid_until = self.unpack().get('valid_until')
        if not valid_until:
            return None
        return parse_date(valid_until)

    def get_valid_addons(self, allow_future=False) -> List[AddonDefinitionDict]:
        return self.filter_addons(self.get_addons(), allow_future=allow_future)

    def parse_quantities(self):
        return self.calculate_quantities(self.get_valid_addons())

    @classmethod
    def filter_addons(
        cls, addons: Sequence[AddonDefinitionDict], allow_future=True
    ) -> List[AddonDefinitionDict]:
        result = []
        today = str(date.today())

        for addon in addons:
            if not allow_future and addon['valid_from'] > today:
                continue
            if addon['valid_until'] < today:
                continue
            result.append(addon)

        return result

    @classmethod
    def calculate_quantities(cls, addons: Sequence[AddonDefinitionDict]) -> AddonValueDict:

        result = Counter[AddonType]()
        for addon in addons:
            name = addon['type']
            if addon['value'] == -1 or result.get(name) == -1:
                result[name] = -1
            else:
                result[name] += addon['value']

        # add addons to base license (deprecated)
        for k in list(result.keys()):
            if k.endswith('_addon'):
                target: AddonType = k[: -len('_addon')]  # type: ignore
                if result.setdefault(target, 0) == -1:
                    result.pop(k)
                else:
                    result[target] += result.pop(k)

        return result

    def parse_full(self):
        try:
            return self._parse_full_real()
        except Exception as e:
            print(e, file=sys.stderr)
            print(
                'Make sure to not import any django-dependent code in license.license',
                file=sys.stderr,
            )
            raise

    def _parse_full_real(self):
        from license.license import FrozenDict, ParsedLicense
        return ParsedLicense(
            value=self.value,
            flags=frozenset(self.get_flags()),
            settings=FrozenDict(self.get_settings()),
            addons=FrozenDict(self.parse_quantities()),
            all_addons=tuple(self.get_valid_addons(allow_future=True)),
            valid_until=self.get_valid_until(),
        )
