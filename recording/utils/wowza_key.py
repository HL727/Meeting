from urllib.parse import urlencode
from base64 import b64encode
import hashlib


def calculate_key(secret, path, query_list, ip=''):

    parts = list(query_list)
    if ip:
        parts.append((ip, ''))
    parts.append((secret, ''))

    query = urlencode(sorted(parts)).replace('=&', '&')

    full = '{}?{}'.format(path, query)

    m = hashlib.sha256()
    m.update(full.encode('utf-8'))

    return full, b64encode(m.digest()).decode('ascii').replace('/', '_').replace('+', '-')


def get_url(secret, path, query_list, ip='', prefix=''):

    query_list = list(query_list)

    full_path, key = calculate_key(secret, path, query_list, ip=ip)
    return '/{}&{}hash={}'.format(full_path, prefix, key)


def _test_key():
    "from example https://www.wowza.com/docs/how-to-protect-streaming-using-securetoken-in-wowza-streaming-engine"

    query = (
            ('myTokenPrefixstarttime', '1395230400'),
            ('myTokenPrefixendtime', '1500000000'),
            ('myTokenPrefixCustomParameter', 'abcdef'),
    )

    secret = 'mySharedSecret'
    full, key = calculate_key(secret, 'vod/sample.mp4', query, ip='192.168.1.2')

    url = get_url(secret, 'vod/sample.mp4', query, ip='192.168.1.2', prefix='myTokenPrefix')

    correct = 'TgJft5hsjKyC5Rem_EoUNP7xZvxbqVPhhd0GxIcA2oo='

    if key != correct:
        raise ValueError('{} does not match {}'.format(key, correct))

    correct_url = '/{}&myTokenPrefixhash={}'.format(full, correct)

    if url != correct_url:
        raise ValueError('{} does not match url {}'.format(url, correct_url))

    print('All is well!')
