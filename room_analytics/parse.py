from typing import Optional, Union
from xml.etree.ElementTree import Element

from endpoint.ext_api.parser.cisco_ce import NestedXMLResult
from endpoint.models import Endpoint


def _try_bool(v: str) -> Optional[bool]:
    if v and v in ('Yes', 'No'):
        return v == 'Yes'
    return None


def _try_int(v: str) -> Optional[int]:
    try:
        return int(v.strip()) if v is not None else None
    except ValueError:
        return None


def _try_decimal_int(v: str) -> Optional[int]:
    try:
        if v and '.' in v:
            main, dec = v.split('.', 1)
            return int(main) * 100 + int(dec[:1])
        return int(v.strip()) * 100 if v is not None else None
    except ValueError:
        return None


def parse_cisco_ce(status_root: Union[Element, NestedXMLResult]):

    return {
        'presence': _try_bool(status_root.findtext('./RoomAnalytics/PeoplePresence', None)),
        'head_count': _try_int(status_root.findtext('./RoomAnalytics/PeopleCount/Current', None)),
        'temperature': _try_int(
            status_root.findtext(
                './Peripherals/ConnectedDevice/RoomAnalytics/AmbientTemperature', None
            )
        ),
        'humidity': _try_int(
            status_root.findtext(
                './Peripherals/ConnectedDevice/RoomAnalytics/RelativeHumidity', None
            )
        ),
        'air_quality': _try_int(
            status_root.findtext(
                './Peripherals/ConnectedDevice/RoomAnalytics/AirQuality/Index', None
            )
        ),
    }


def store_cisco_ce(status_root: Union[Element, NestedXMLResult], endpoint: Endpoint):

    from . import models

    presence = _try_bool(status_root.findtext('./RoomAnalytics/PeoplePresence', None))
    if presence is not None:
        models.EndpointRoomPresence.objects.create(endpoint=endpoint, value=1 if presence else 0)

    head_count = _try_int(status_root.findtext('./RoomAnalytics/PeopleCount/Current', None))
    if head_count is not None:
        if head_count >= 0:  # TODO: What does -1 mean?
            models.EndpointHeadCount.objects.create(endpoint=endpoint, value=head_count)

    temperature = _try_int(
        status_root.findtext('./Peripherals/ConnectedDevice/RoomAnalytics/AmbientTemperature', None)
    )
    if temperature is not None:
        models.EndpointTemperature.objects.create(endpoint=endpoint, value=temperature)

    humidity = _try_int(
        status_root.findtext('./Peripherals/ConnectedDevice/RoomAnalytics/RelativeHumidity', None)
    )
    if humidity is not None:
        models.EndpointHumidity.objects.create(endpoint=endpoint, value=humidity)

    air_quality = _try_int(
        status_root.findtext('./Peripherals/ConnectedDevice/RoomAnalytics/AirQuality/Index', None)
    )
    if air_quality is not None:
        models.EndpointAirQuality.objects.create(endpoint=endpoint, value=air_quality)
