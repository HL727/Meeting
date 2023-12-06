import re

from django.db import models
from mptt.fields import TreeForeignKey
from mptt.managers import TreeManager
from mptt.models import MPTTModel


class LdapOUManager(TreeManager):

    def get_from_list(self, lst):

        parent = None

        for item in lst:
            parent, created = self.get_or_create(name=item, parent=parent)

        return parent

    def get_from_ldap_string(self, dn):

        ous = re.findall(r'ou=(.*?),', dn, re.IGNORECASE)
        if not ous:
            ous = re.findall(r'cn=(.*?),', dn, re.IGNORECASE)[1:]

        return self.get_from_list(reversed(ous))


class LdapOU(MPTTModel):

    name = models.CharField(max_length=200)

    parent = TreeForeignKey('self', on_delete=models.CASCADE, null=True, blank=True, related_name='children')

    objects = LdapOUManager()

    def __str__(self):
        return self.name
