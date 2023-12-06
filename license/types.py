from typing import List, Dict

from typing_extensions import Literal, TypedDict

LicenseFlag = Literal[
    'core:enable_core',
    'core:enable_analytics',
    'core:enable_branding',
    'core:enable_demo',
    'core:portal_enable_secure_meeting',
    'core:portal_enable_patient_sip',
    'core:enable_epm',
]

AddonType = Literal['base', 'epm:endpoint', 'core:mcu', 'core:cluster', LicenseFlag]

AddonValueDict = Dict[AddonType, int]
SettingsDefinitionDict = Dict[str, str]


class AddonDefinitionDict(TypedDict):
    type: AddonType
    value: int
    valid_from: str
    valid_until: str


class InputLicenseDict(TypedDict):

    value: str
    addons: List[AddonDefinitionDict]
    flags: List[LicenseFlag]
    settings: Dict[str, str]
    valid_until: str
