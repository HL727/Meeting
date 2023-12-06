from django.core import validators
from django.db import models
from rest_framework import serializers


class NullableRemoteObjectRelationField(models.PositiveIntegerField):

    def __init__(self, related_system_type=None, *args, **kwargs):
        self.related_system_type = related_system_type
        kwargs['null'] = True
        super().__init__(*args, **kwargs)

    default_validators = [validators.MinValueValidator(limit_value=1)]


class FakeIntegerRelationField(serializers.IntegerField):

    has_relation = True


serializers.ModelSerializer.serializer_field_mapping[NullableRemoteObjectRelationField] = FakeIntegerRelationField
