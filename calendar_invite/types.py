from datetime import datetime
from typing import NamedTuple, Sequence, List, Optional, TYPE_CHECKING
from typing_extensions import TypedDict
from datetime import tzinfo


if TYPE_CHECKING:
    from endpoint.models import Endpoint
    from calendar_invite.models import Calendar, CalendarItem
    from meeting.models import Meeting


class InviteMessageParseDict(TypedDict, total=False):
    subject: str
    creator_name: str
    creator: str
    participants: List[str]
    skype_conference: str

    ts_start: Optional[datetime]
    ts_stop: Optional[datetime]
    timezone: Optional[tzinfo]

    uid: str
    dialstring: str

    is_recurring: bool
    recurrence_id: str
    recurring: Optional[str]  # rule
    recurring_exceptions: str

    envelope: str
    error: Optional[str]
    cancelled: bool
    is_private: bool

    room_info: Optional[str]
    settings: Optional[str]

    extra_events: Optional[Sequence['InviteMessageParseDict']]

    endpoints: Optional[Sequence['Endpoint']]
    has_body: bool

    pass  # TODO key/values


class CalendarInviteParseDict(InviteMessageParseDict):
    calendar: 'Calendar'
    changekey: Optional[str]


class SyncResult(NamedTuple):
    new: List['CalendarItem']
    changed: List['CalendarItem']
    removed: List['CalendarItem']


class ChangedItemTuple(NamedTuple):
    local_item: 'CalendarItem'
    exchange_item: CalendarInviteParseDict


class SyncChangesTuple(NamedTuple):
    new_items: Sequence[CalendarInviteParseDict]
    changed: Sequence[ChangedItemTuple]
    removed: Sequence['CalendarItem']
