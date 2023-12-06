from typing import Type

from django.db.models import Q
from rest_framework import serializers
from rest_framework.exceptions import ValidationError
from rest_framework.relations import RelatedField

from customer.utils import get_customer_from_request


class CustomerRelationMixin:

    customer_through_field = 'customer'

    @property
    def serializer_related_field(self) -> Type[RelatedField]:
        return CustomerFilteredPrimaryKeyField

    def _get_customer(self):
        if hasattr(self, 'request'):
            return get_customer_from_request(self.request)
        if hasattr(self, 'context') and self.context.get('customer'):
            return self.context['customer']
        if hasattr(self, 'context') and self.context.get('request'):
            return get_customer_from_request(self.context['request'])

    def get_queryset(self):
        "make sure to include customer filter when overriding get_queryset!"
        return super().get_queryset().filter(**{self.customer_through_field: self._get_customer()})

    def validate_customer(self, value):
        from customer.models import Customer
        if not any(c.pk == getattr(value, 'pk', value) for c in Customer.objects.get_for_user(self.request.user)):
            raise ValidationError('Invalid customer')
        return value

    def build_nested_field(self, field_name, relation_info, nested_depth):
        cls, kwargs = super().build_nested_field(field_name, relation_info, nested_depth)
        try:
            relation_info.related_model._meta.get_field(self.customer_through_field)
        except Exception:
            return cls, kwargs
        else:
            new_cls = type('CustomerNested', (CustomerRelationMixin, cls), {})
            return new_cls, kwargs

    def get_serializer_context(self):
        return {'customer': self._get_customer(), **super().get_serializer_context()}

    def perform_create(self, serializer):

        return serializer.save(customer=self._get_customer())


class CustomerFilteredPrimaryKeyField(CustomerRelationMixin, serializers.PrimaryKeyRelatedField):
    customer_through_field = 'customer'

    def __init__(self, *args, customer_through_field: str = None, **kwargs):
        self.customer_through_field = customer_through_field or self.customer_through_field
        super().__init__(*args, **kwargs)


class CustomerOrGlobalFilteredPrimaryKeyField(CustomerRelationMixin, serializers.PrimaryKeyRelatedField):

    customer_through_field = 'customer'

    def __init__(self, *args, customer_through_field: str = None, **kwargs):
        self.customer_through_field = customer_through_field or self.customer_through_field
        super().__init__(*args, **kwargs)

    def get_queryset(self):
        return super(CustomerRelationMixin, self).get_queryset().filter(Q(**{self.customer_through_field: self._get_customer()}) | Q(is_global=True))
