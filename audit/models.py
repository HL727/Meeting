import logging
from typing import TYPE_CHECKING, Optional

from django.contrib.auth.signals import user_logged_in, user_logged_out, user_login_failed
from django.dispatch import receiver

from django.conf import settings
from django.db import models
from django.http import HttpRequest

from compressed_store.models import CompressStoreModel, CompressedStoreManager

logger = logging.getLogger('audit')

if TYPE_CHECKING:
    from customer.models import Customer as CustomerFK  # noqa
    from provider.models import Cluster as ClusterFK  # noqa
else:
    CustomerFK = 'provider.Customer'
    ClusterFK = 'provider.Cluster'


class AuditLogManager(CompressedStoreManager['AuditLog']):
    def store_request(self, request: Optional[HttpRequest], content=None, response=None, **kwargs):

        if not request:
            return self.store(content, **kwargs)

        orig_remote_addr = request.META.get('ORIG_REMOTE_ADDR', '')

        if not kwargs.get('action'):
            kwargs['action'] = self.get_action(request)
        if not kwargs.get('type'):
            kwargs['type'] = self.get_type(request)
        if not kwargs.get('username'):
            kwargs['username'] = request.user.username if request.user.is_authenticated else '-'
        if not kwargs.get('scope'):
            kwargs['scope'] = self.get_scope(request)
        if not kwargs.get('ip'):
            kwargs['ip'] = AuditLog.get_ip(request)
        if not kwargs.get('X-Orig-IP') and request.META.get('HTTP_X_ORIG_IP'):
            kwargs['X-Orig-IP'] = request.META.get('HTTP_X_ORIG_IP')

        if not kwargs.get('X-Forwarded-For') and request.META.get('HTTP_X_FORWARDED_FOR'):
            kwargs['X-Forwarded-For'] = request.META['HTTP_X_FORWARDED_FOR']
            if orig_remote_addr and not kwargs['X-Forwarded-For'].startswith(orig_remote_addr):
                kwargs['X-Orig-Remote-Addr'] = request.META['ORIG_REMOTE_ADDR']
        elif orig_remote_addr and request.META['REMOTE_ADDR'] != orig_remote_addr:
            kwargs['X-Orig-Remote-Addr'] = orig_remote_addr

        if not kwargs.get('User-Agent') and request.META.get('HTTP_USER_AGENT'):
            kwargs['User-Agent'] = request.META['HTTP_USER_AGENT']

        if not kwargs.get('customer'):
            from customer.utils import get_customer_from_request

            try:
                kwargs['customer'] = get_customer_from_request(request)
            except Exception:
                pass

        if not content:
            content = '{} {}{} (status {})'.format(
                request.method,
                request.get_host(),
                request.get_full_path(),
                response.status_code if response else 'unknown',
            )

        result = None
        try:
            result = AuditLog.objects.store(
                content,
                path=request.path[:255],
                **kwargs,
            )
        finally:
            if result:
                request.audit_logged = True
        return result

    def get_type(self, request):
        static = {
            '/tms/document/': 'passive_document',
            '/tms/event/': 'http_event',
            '/tms/': 'passive',
        }
        path = request.path
        for prefix, result in static.items():
            if path.startswith(prefix):
                return result

        remove_prefixes = (
            '/epm/',
            '/tms/',
            '/json-api/v1/',
            '/api/v1/',
        )
        for prefix in remove_prefixes:
            if path.startswith(prefix):
                return path[len(prefix) :].split('/', 1)[0]

        return None

    def get_action(self, request):
        if request.method == 'DELETE' or any(
            [
                'remove' in request.path,
                'delete' in request.path,
            ]
        ):
            return 'delete_request'

        if request.path == '/epm/proxy/check_active/':
            return 'heartbeat'
        if request.path == '/epm/proxy/':
            return 'handshake'

        if request.path in ('/api/v1/user/status/', '/api/v1/status/'):
            return 'status_check'

        if request.method in ('GET', 'HEAD'):
            return 'read_request'
        return 'change_request'

    def get_scope(self, request):

        if settings.API_HOSTNAME != settings.HOSTNAME:
            if request.get_host() == settings.API_HOSTNAME:
                return 'book_api'

        if request.path.startswith('/api/v1/'):
            return 'book_api'

        if settings.EPM_HOSTNAME != settings.EPM_HOSTNAME:
            if request.get_host() == settings.EPM_HOSTNAME:
                return 'endpoint_api'

        if request.path.startswith('/epm/proxy/'):
            return 'proxy'

        if request.path.startswith('/tms/'):
            return 'endpoint_api'

        return 'http'


class AuditLog(CompressStoreModel):
    log_type = 'audit'
    log_basename = 'audit'

    SCOPES = (
        ('auth', 'Authentication'),
        ('http', 'API requests'),
        ('book_api', 'Book-API requests'),
    )
    ACTIONS = (
        ('login', 'Login'),
        ('login_failed', 'Login failed'),
        ('logout', 'Log out'),
        ('change_request', 'Change object'),
        ('delete_request', 'Delete object'),
        ('read_request', 'Read object'),
    )

    ip = models.GenericIPAddressField(null=True)
    scope = models.CharField(max_length=100, choices=SCOPES, blank=True)
    action = models.CharField(max_length=100, choices=ACTIONS, blank=True)
    type = models.CharField(max_length=100, blank=True, null=True)
    username = models.CharField(max_length=255, blank=True, null=True)
    path = models.CharField(max_length=255, blank=True, null=True)
    customer = models.ForeignKey(
        CustomerFK,
        db_constraint=False,
        db_index=False,
        blank=True,
        null=True,
        on_delete=models.DO_NOTHING,
    )
    cluster = models.ForeignKey(
        ClusterFK,
        db_constraint=False,
        db_index=False,
        blank=True,
        null=True,
        on_delete=models.DO_NOTHING,
    )

    objects = AuditLogManager()

    class Meta:
        index_together = (
            ('action', 'ts_created'),
            ('type', 'ts_created'),
            ('username', 'ts_created'),
        )

        indexes = (
            models.Index(
                name='audit_customer',
                fields=('customer', 'ts_created'),
                condition=models.Q(customer__isnull=True),
            ),
            models.Index(
                name='audit_cluster',
                fields=('cluster', 'ts_created'),
                condition=models.Q(cluster__isnull=True),
            ),
        )

    @classmethod
    def get_ip(cls, request):
        if not request:
            return None
        return request.META.get('REMOTE_ADDR')


@receiver(user_logged_in)
def user_logged_in_callback(sender, request, user, **kwargs):
    ip = AuditLog.get_ip(request)

    msg, args = 'User %s logged in from IP: %s', (
        user.username,
        ip,
    )
    if not settings.TEST_MODE:
        logger.info(msg, *args)
    AuditLog.objects.store_request(
        request, msg % args, username=user.username, ip=ip, scope='auth', action='login'
    )


@receiver(user_logged_out)
def user_log_out_callback(sender, request, user, **kwargs):
    ip = AuditLog.get_ip(request)

    msg, args = 'User %s logged out from IP: %s', (
        user.username,
        ip,
    )
    if not settings.TEST_MODE:
        logger.info(msg, *args)
    AuditLog.objects.store_request(
        request, msg % args, username=user.username, ip=ip, scope='auth', action='logout'
    )


@receiver(user_login_failed)
def user_login_failed_callback(sender, request, credentials, **kwargs):
    ip = AuditLog.get_ip(request)
    username = credentials.get('username')

    msg, args = 'Failed login for %s from IP: %s', (
        username,
        ip,
    )
    logger.info(msg, *args)
    AuditLog.objects.store_request(
        request, msg % args, username=username, ip=ip, scope='auth', action='login_failed'
    )
