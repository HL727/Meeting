import io
from datetime import datetime
from typing import Dict, List, Mapping, NamedTuple, Optional, Sequence, Union

from typing_extensions import Literal, NotRequired, TypedDict

from endpoint.consts import STATUS


class StatusDict(TypedDict):
    has_direct_connection: Optional[bool]
    uptime: int
    status: STATUS
    incoming: str
    in_call: str
    muted: bool
    volume: str
    inputs: List[Dict[str, str]]
    presentation: List[Dict[str, str]]
    call_duration: int
    upgrade: Dict[str, str]
    warnings: List[str]
    diagnostics: List[Dict[str, str]]


class BasicDataDict(TypedDict):
    serial_number: str
    product_name: str
    mac_address: str
    ip: str
    software_version: str
    software_release: Optional[datetime]
    has_head_count: bool
    webex_registration: str
    sip_registration: str
    sip_uri: str
    sip_display_name: str


class DialInfoDictOptional(TypedDict, total=False):
    sip_proxy_username: str
    sip_proxy_password: str


class DialInfoDict(DialInfoDictOptional):

    name: str
    sip: str
    sip_display_name: str
    h323: str
    h323_e164: str
    sip_proxy: str
    h323_gatekeeper: str


class CallHistoryDict(TypedDict):

    number: str
    name: str
    ts_start: datetime
    type: str
    count: int
    history_id: str
    id: str


class CommandDict(TypedDict):
    command: Sequence[str]
    arguments: Mapping[str, Union[str, List[str]]]
    body: NotRequired[Union[None, str, bytes, io.IOBase]]


class ConfigurationDict(TypedDict):
    key: Sequence[str]
    value: str


class CaCertificate(NamedTuple):
    content: str
    sha1_fingerprint: str
    sha256_fingerprint: str
    not_valid_after: str


ProvisionTypes = Literal['ca_certificates', 'branding']
