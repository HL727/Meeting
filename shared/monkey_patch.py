from sys import argv
from functools import wraps

from django.db.backends.base.base import BaseDatabaseWrapper
from django.db.models import Field, IntegerField, CharField
from django.db.migrations.operations import AlterModelOptions

from django.db.backends.signals import connection_created
import django_stubs_ext
from django.utils.translation import ngettext


def enable_sqlite_wal(sender, connection: BaseDatabaseWrapper = None, **kwargs):
    """Allow multi threaded access to database"""

    if not connection or connection.vendor != 'sqlite':
        return

    try:
        connection.connection.execute('PRAGMA journal_mode=WAL')
    except Exception as e:
        print('Error enabling WAL', e)


if not ('migrate' in argv or 'makemigrations' in argv):
    connection_created.connect(enable_sqlite_wal)


def patch_method_to_ignore_migration_attrs(old_func):
    @wraps(old_func)
    def deconstruct_with_ignored_attrs(self):
        name, path, args, kwargs = old_func(self)
        for attr in ['choices']:
            if self.__class__.__name__ == 'TimeZoneField':
                continue
            if attr in kwargs:
                kwargs[attr] = ()
        for attr in ['help_text', 'verbose_name']:
            if attr in kwargs:
                kwargs.pop(attr, None)
        if isinstance(self, (CharField, IntegerField)):
            if 'blank' in kwargs:
                kwargs.pop('blank', None)
        return name, path, args, kwargs
    return deconstruct_with_ignored_attrs


if ('migrate' in argv or 'makemigrations' in argv):
    AlterModelOptions.ALTER_OPTION_KEYS.remove('verbose_name')
    AlterModelOptions.ALTER_OPTION_KEYS.remove('verbose_name_plural')
    Field.deconstruct = patch_method_to_ignore_migration_attrs(Field.deconstruct)  # ignore: assignment


def patch_django_test_client():
    """django-axios requires request argument for logging in"""
    from django.test.client import Client

    orig_login = Client.login

    def _client_login(self, **credentials):
        from django.http import HttpRequest

        credentials.setdefault('request', HttpRequest())
        return orig_login(self, **credentials)

    Client.login = _client_login


patch_django_test_client()


def patch_gettext():
    """Ugly hack to return ngettext-version of string with count 1 if not translated"""
    from django.utils.translation import trans_real

    real_gettext = trans_real.gettext

    def patched_gettext(message):
        eol_message = message.replace('\r\n', '\n').replace('\r', '\n')
        result = real_gettext(eol_message)
        if eol_message and result == eol_message:
            return ngettext(eol_message, eol_message, 1)
        return result

    trans_real.gettext = patched_gettext


patch_gettext()

# add Manager[ModelCls] and QuerySet[ModelCls] type support
django_stubs_ext.monkeypatch()

