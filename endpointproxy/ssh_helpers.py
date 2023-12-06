import paramiko
from django.conf import settings

SSH_HOST_KEYS = {}


class GetHostsKeyPolicy(paramiko.MissingHostKeyPolicy):
    def missing_host_key(self, client, hostname, key):
        SSH_HOST_KEYS[hostname] = '{} {} {}\n'.format(hostname, key.get_name(), key.get_base64())


def get_remote_host_key(hostname=None, force=False):
    hostname = hostname or settings.EPM_PROXY_HOST

    if SSH_HOST_KEYS.get(hostname) is not None and not force:
        return SSH_HOST_KEYS[hostname]

    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(GetHostsKeyPolicy)
    try:
        client.connect(hostname)
    except Exception:
        if settings.DEBUG:
            raise

    return SSH_HOST_KEYS.get(hostname)
