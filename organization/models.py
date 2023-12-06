from django.db import models
from django.db.models import Q
from mptt.models import MPTTModel, TreeForeignKey, TreeManager
import re

ORGANISATION_UNIT_NAME_SEPARATOR = re.compile(r'[>/]+')


class OrganizationUnitManager(TreeManager):
    def get_or_create_by_full_name(self, full_name, customer, parent=None):
        names = [s.strip() for s in ORGANISATION_UNIT_NAME_SEPARATOR.split(full_name) if s.strip()]
        if parent:
            names.insert(0, parent)
        return self.get_or_create_by_list(names, customer=customer)

    def get_or_create_by_list(self, lst, customer=None):

        parent = None
        created = False

        from customer.models import Customer
        default_customer = Customer.objects.all()[0]

        if lst and isinstance(lst[0], OrganizationUnit):
            parent = lst.pop(0)
            if not customer and parent:
                customer = parent.customer

        if not customer:
            customer = default_customer
        elif isinstance(customer, int):
            customer = Customer(pk=customer)

        for name in lst:
            parent, created = self.get_or_create(name__iexact=name, parent=parent,
                                                 customer=customer,
                                                 defaults={
                                                     'name': name, 'parent': parent,
                                                 })
        return parent, created

    def get_filter(self, org_unit, attr: str = 'organization_unit') -> Q:
        if isinstance(org_unit, (int, str)):
            org_unit = self.get(pk=org_unit)
        return org_unit.get_search_filter(attr)


class OrganizationUnit(MPTTModel):
    customer = models.ForeignKey('provider.Customer', null=True,
                                 on_delete=models.SET_NULL, editable=False)
    name = models.CharField(max_length=200)
    parent = TreeForeignKey('self', on_delete=models.CASCADE, null=True, blank=True, related_name='children')
    objects = OrganizationUnitManager()

    @property
    def full_name(self):
        current = self
        names = []
        while current:
            names.append(current.name)
            current = current.parent

        return (' {} '.format('/')).join(reversed(names))

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.customer_id and self.parent_id:
            self.customer = self.parent.customer
        super().save(*args, **kwargs)

    def get_search_filter(self, attr: str = 'organization_unit'):
        org_units = self.get_descendants(include_self=True)
        return Q(**{attr + '__in': org_units})


class CoSpaceUnitRelationManager(models.Manager):
    def create_and_assign_organization_unit_to_cospace(self, organization_unit_full_name, cospace_provider_ref, customer):
        self.filter(unit__customer=customer, provider_ref=cospace_provider_ref).delete()

        if organization_unit_full_name:
            unit, _ = OrganizationUnit.objects.get_or_create_by_full_name(organization_unit_full_name, customer=customer)
            self.get_or_create(provider_ref=cospace_provider_ref, unit=unit)


class CoSpaceUnitRelation(models.Model):
    provider_ref = models.CharField(max_length=64)
    unit = TreeForeignKey(OrganizationUnit, on_delete=models.CASCADE, related_name='cospaces')
    objects = CoSpaceUnitRelationManager()


class UserUnitRelation(models.Model):

    user_jid = models.CharField(max_length=200)
    unit = TreeForeignKey(OrganizationUnit, on_delete=models.CASCADE, related_name='users')
