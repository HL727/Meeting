from __future__ import annotations
from datetime import timedelta
from typing import Union, TYPE_CHECKING, TypeVar

from django.db import models
from django.db.models import Max, Aggregate, Min
from django.utils.timezone import localtime, now

from endpoint.models import Endpoint, EndpointMeetingParticipant
from room_analytics.consts import SensorType

if TYPE_CHECKING:
    from customer.models import Customer as CustomerFK  # noqa
else:
    CustomerFK = 'provider.Customer'


def get_qs_for_time(qs, endpoint, ts_start, ts_stop=None):
    qs = qs.filter(endpoint=endpoint, ts__gt=ts_start - timedelta(hours=1))

    last_before = qs.filter(ts__lt=ts_start).order_by('-ts').values_list('ts', flat=True).first()
    if last_before:
        qs = qs.filter(ts__gte=last_before)

    if ts_stop:
        qs = qs.filter(ts__lt=ts_stop)
    elif not last_before:
        qs = qs.filter(ts__lt=ts_start + timedelta(minutes=10))

    return qs



M = TypeVar('M', bound='EndpointSensorValue')


class EndpointSensorValueManager(models.Manager[M]):

    value_type: SensorType = None
    aggregate: Aggregate = Max('value')

    def get_queryset(self: models.Manager[M]) -> models.QuerySet[M]:
        return super().get_queryset().filter(value_type=self.value_type)

    def get_for_time(self, endpoint, ts_start, ts_stop=None) -> Union[int, None]:

        qs = get_qs_for_time(self.get_queryset(), endpoint, ts_start=ts_start, ts_stop=ts_stop)
        return qs.order_by().aggregate(agg=self.aggregate)['agg']

    @classmethod
    def get_proxy_manager(
        cls, value_type: SensorType, aggregate: Aggregate
    ) -> 'EndpointSensorValueManager[M]':
        result = cls()
        result.value_type = value_type
        result.aggregate = aggregate
        return result


class EndpointSensorValue(models.Model):

    ts = models.DateTimeField(default=localtime, db_index=True)
    customer = models.ForeignKey(
        CustomerFK,
        null=True,
        blank=True,
        on_delete=models.DO_NOTHING,
        db_constraint=False,
        db_index=False,
    )
    endpoint = models.ForeignKey(Endpoint, db_constraint=False, on_delete=models.DO_NOTHING)
    value_type = models.SmallIntegerField(choices=[(t.value, t.name) for t in SensorType])
    value = models.SmallIntegerField(default=0)

    objects: EndpointSensorValueManager[EndpointSensorValue] = EndpointSensorValueManager()

    _value_type: SensorType = None

    class Meta:
        indexes = (
            models.Index(fields=('endpoint', 'value_type', 'ts')),
            models.Index(fields=('customer', 'ts')),
        )

    def save(self, *args, **kwargs):

        if self.value_type is None:
            self.value_type = self._value_type

        if not self.customer and self.endpoint.customer:
            self.customer = self.endpoint.customer
        super().save(*args, **kwargs)
        self.update_endpoint_status()

    def update_endpoint_status(self):
        if self.ts < now() - timedelta(seconds=10):
            return

        status_key = SensorType.endpoint_status_key.get(self.value_type)
        status_kwargs = {status_key: self.value}

        if self.value_type == SensorType.HEAD_COUNT:
            status_kwargs['ts_last_head_count'] = now()
        elif self.value_type == SensorType.PRESENCE:
            status_kwargs['ts_last_presence'] = now()

        if status_key:
            self.endpoint.set_status(**status_kwargs)

        if self.value_type == SensorType.HEAD_COUNT and self.endpoint.status.active_meeting:
            if (self.endpoint.status.active_meeting.head_count or 0) < self.value:
                EndpointMeetingParticipant.objects.filter(
                    pk=self.endpoint.status.active_meeting.id,
                ).update(head_count=self.value)

        elif self.value_type == SensorType.PRESENCE and self.endpoint.status.active_meeting:
            if self.value:
                EndpointMeetingParticipant.objects.filter(
                    pk=self.endpoint.status.active_meeting.id,
                ).update(presence=bool(self.value))

        elif self.value_type == SensorType.AIR_QUALITY and self.endpoint.status.active_meeting:
            if (self.endpoint.status.active_meeting.air_quality or 0) < self.value:
                EndpointMeetingParticipant.objects.filter(
                    pk=self.endpoint.status.active_meeting.id,
                ).update(air_quality=self.value)


class EndpointHeadCount(EndpointSensorValue):

    objects: EndpointSensorValueManager[
        EndpointHeadCount
    ] = EndpointSensorValueManager.get_proxy_manager(SensorType.HEAD_COUNT, Max('value'))

    _value_type = SensorType.HEAD_COUNT

    class Meta:
        proxy = True


class EndpointAirQuality(EndpointSensorValue):

    objects: EndpointSensorValueManager[
        EndpointAirQuality
    ] = EndpointSensorValueManager.get_proxy_manager(SensorType.AIR_QUALITY, Min('value'))

    _value_type = SensorType.AIR_QUALITY

    class Meta:
        proxy = True


class EndpointHumidity(EndpointSensorValue):

    objects: EndpointSensorValueManager[
        EndpointHumidity
    ] = EndpointSensorValueManager.get_proxy_manager(SensorType.HUMIDITY, Min('value'))

    _value_type = SensorType.HUMIDITY

    class Meta:
        proxy = True


class EndpointTemperature(EndpointSensorValue):

    objects: EndpointSensorValueManager[
        EndpointTemperature
    ] = EndpointSensorValueManager.get_proxy_manager(SensorType.TEMPERATURE, Min('value'))

    _value_type = SensorType.TEMPERATURE

    class Meta:
        proxy = True


class EndpointRoomPresence(EndpointSensorValue):

    objects: EndpointSensorValueManager[
        EndpointRoomPresence
    ] = EndpointSensorValueManager.get_proxy_manager(SensorType.PRESENCE, Max('value'))

    _value_type = SensorType.PRESENCE

    class Meta:
        proxy = True


class EndpointOldHeadCount(models.Model):

    ts = models.DateTimeField(default=localtime, db_index=True)
    endpoint = models.ForeignKey(Endpoint, db_constraint=False, on_delete=models.CASCADE)
    count = models.SmallIntegerField(default=0)

    class Meta:
        db_table = 'room_analytics_endpointheadcount'


class EndpointOldRoomPresence(models.Model):

    ts = models.DateTimeField(auto_now_add=True, db_index=True)
    endpoint = models.ForeignKey(Endpoint, db_constraint=False, on_delete=models.CASCADE)
    presence = models.BooleanField(default=False)

    class Meta:
        db_table = 'room_analytics_endpointroompresence'

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        self.update_endpoint_status()

    def update_endpoint_status(self):
        if self.ts < now() - timedelta(seconds=10):
            return

        self.endpoint.set_status(presence=self.presence, ts_last_presence=now())
