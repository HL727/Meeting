from enum import Enum, IntEnum
from typing import get_args

from typing_extensions import Literal


class STATUS(IntEnum):
    CONNECTION_ERROR = -2
    AUTH_ERROR = -1
    OFFLINE = 0
    UNKNOWN = 1
    ONLINE = 10
    IN_CALL = 20


class CONNECTION(IntEnum):

    INCOMING = -10
    PASSIVE = 0
    DIRECT = 1
    PROXY = 2


class MANUFACTURER(IntEnum):
    # OTHER = 0
    CISCO_CE = 10
    POLY_TRIO = 20
    POLY_STUDIO_X = 21
    POLY_GROUP = 22
    POLY_HDX = 23
    OTHER = 90
    # CISCO_CMS = 20


class TASKSTATUS(IntEnum):

    ERROR = -10
    CANCELLED = -1
    PENDING = 0
    QUEUED = 5
    COMPLETED = 10


class DIAL_PROTOCOL(Enum):

    SIP = "SIP"
    H323 = "H323"
    H320 = "H320"
    SPARK = "SPARK"


class HTTP_MODES(IntEnum):

    HTTPS = 0
    HTTP = 10


class MeetingStatus(IntEnum):

    NO_MEETING = 0
    ACTIVE_MEETING = 1
    GHOST_MEETING = 5
    CONNECTED = 10


CallControlAction = Literal[
    'dial',
    'answer',
    'reject',
    'disconnect',
    'mute',
    'reboot',
    'volume',
    'presentation',
    'presentation_stop',
]

CALLCONTROL_ACTIONS = get_args(CallControlAction)

GHOST_TIMEOUT = 10
DEFAULT_CAPACITY = 4  # TODO setting

PLACEHOLDER_PASSWORD = '_***_'
