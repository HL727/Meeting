import re
import os
from datetime import datetime

from django.conf import settings
from paramiko import SSHClient, AutoAddPolicy
from paramiko.ssh_exception import ChannelException
from collections import namedtuple
from time import sleep
import sys
from django.utils.translation import gettext_lazy as _

now = datetime.now

class AcanoSSHClient:

    def __init__(self, host, port, username, password):
        self.host = host
        self.port = port
        self.username = username
        self.password = password

    ssh_client = None
    sftp_client = None

    def open_ssh(self, sftp=False, force=False):
        if self.ssh_client and not (sftp or force):
            if self.ssh_client.get_transport().is_active():
                if not settings.TEST_MODE:
                    sleep(.05)  # acano has problems with too fast channel creations
                return self.ssh_client

        client = SSHClient()
        client.load_system_host_keys()
        client.set_missing_host_key_policy(AutoAddPolicy)
        client.connect(self.host, self.port, self.username, self.password)

        if not sftp:
            self.ssh_client = client
        return client

    def open_sftp(self, force=False):
        if self.sftp_client and not force:
            if self.sftp_client.get_channel().get_transport().is_active():
                return self.sftp_client
        client = self.open_ssh(sftp=True).open_sftp()
        self.sftp_client = client
        return client

    def exec_command(self, cmd, input=None, timeout=3):

        client = self.open_ssh()
        try:
            stdin, stdout, stderr = client.exec_command(cmd, timeout=timeout)
        except ChannelException:
            if not settings.TEST_MODE:
                sleep(.1)
            stdin, stdout, stderr = client.exec_command(cmd, timeout=timeout)
        if input is not None:
            stdin.write(input)
        output = stdout.read() + stderr.read()
        for fd in (stdin, stdout, stderr):
            fd.close()
        return output

    def backup(self):

        basename = 'bak-{}'.format(now().isoformat().replace(':', '').split('.')[0])
        output = self.exec_command('backup snapshot {}'.format(basename))
        if 'ready for download' not in output:
            raise ValueError(_('Backup failed'), output)

        fd = None
        try:
            fd = self.open_sftp().open('/{}.bak'.format(basename), 'rb')
            result = fd.read()
        finally:
            if fd:
                fd.close()

            self.open_sftp().unlink('/{}.bak'.format(basename))

        return result

    AcanoUser = namedtuple('AcanoUser', 'username role, expiry, status')

    def user_list(self):

        output = self.exec_command('user list')
        lines = output.strip().split('\n')[1:]

        result = []
        for line in lines:
            cur = self.AcanoUser(*line.split()[:4])
            result.append(cur._replace(expiry=datetime.strptime(cur.expiry, '%Y-%b-%d').date()))
        return result

    def get_ips(self):

        r = re.compile(r'Addresses:[\s\n]+([\d\.]+)')

        result = {}
        for nic in 'a b c d':
            output = self.exec_command('ipv4 {}'.format(nic))

            match = r.search(output)
            if match:
                result[nic] = match.group(1)

        return result

    SERVICES = {'callbridge', 'webbridge', 'webbridge3', 'xmpp', 'sipedge', 'webadmin', 'recorder', 'streamer', 'h323_gateway'}

    def status(self, subsystem):
        if subsystem not in self.SERVICES:
            raise KeyError('{} not a valid server'.format(subsystem))
        output = self.exec_command(subsystem)
        if output.startswith('Unknown command'):
            raise KeyError('{} not a valid server'.format(subsystem))

        if re.search(r'Enabled\s*:\s*true', output):
            return True, output
        return False, output

    def restart(self, subsystem):
        if subsystem not in self.SERVICES:
            raise KeyError('{} not a valid server'.format(subsystem))

        return self.exec_command('{} restart'.format(subsystem))

    def webadmin_status(self):
        status, output = self.status('webadmin')
        if 'webadmin running' in output:
            nic_match = re.search(r'interface\s*:\s*([A-z])', output)
            port_match = re.search(r'port\s*:\s*(\d+)', output)
            if nic_match and port_match:
                ips = self.get_ips()
                nic_ip = ips.get(nic_match.group(1))
                if nic_ip:
                    return True, '{}:{}'.format(nic_ip, port_match.group(1))
            return True, ''
        return False, ''

    DF = namedtuple('DF', 'filesystem size used free used_percent device')

    def df(self):

        result = {'size': {}, 'inodes': {}}

        sub = 'size'
        lines = self.exec_command('df').strip().split('\n')
        for line in lines:
            cols = line.split()
            if cols[0] == 'Filesystem' and cols[1] == 'Size':
                sub = 'size'
            elif cols[0] == 'Filesystem' and cols[1] == 'Inodes':
                sub = 'inodes'
            else:
                result[sub][cols[0]] = self.DF(*cols)
        return result

    def get_log(self, last_bytes=None):

        fd = self.open_sftp().open('log')
        if last_bytes:
            try:
                fd.seek(-last_bytes, os.SEEK_END)
            except IOError:
                pass
        return fd.read()


def run(host, port, username, password):
    t = AcanoSSHClient(host, port, username, password)

    print(len(t.backup()))
    print(t.get_ips())
    print(t.user_list())
    print(t.webadmin_status())
    print(t.df())

    for s in t.SERVICES:
        print(s)
        try:
            print(t.status(s))
        except KeyError:
            pass
        except Exception as e:
            print('Exception', e)

if __name__ == '__main__':
    if len(sys.argv) != 5:
        print('{} <host> <port> <username> <password>'.format(sys.argv[0]))
        sys.exit(1)
    run(*sys.argv[1:])
