import enum
from typing import Dict


class SensorType(enum.IntEnum):

    HEAD_COUNT = 0
    PRESENCE = 1
    TEMPERATURE = 5
    HUMIDITY = 10
    AIR_QUALITY = 20

    endpoint_status_key: Dict[int, str]


SensorType.endpoint_status_key = {
    SensorType.HEAD_COUNT: 'head_count',
    SensorType.PRESENCE: 'presence',
    SensorType.HUMIDITY: 'humidity',
    SensorType.AIR_QUALITY: 'air_quality',
    SensorType.TEMPERATURE: 'temperature',
}
