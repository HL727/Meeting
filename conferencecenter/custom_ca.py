import os
from os import environ
from tempfile import NamedTemporaryFile


BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

_default_cache = ''


def get_system_default_ca_certs_content():

    global _default_cache
    if _default_cache:
        return _default_cache

    filename = get_system_default_ca_certs_file()

    with open(filename) as orig:
        _default_cache = orig.read().rstrip()
        return _default_cache


def get_system_default_ca_certs_file():

    try:
        import certifi
    except ImportError:
        where = str
    else:
        where = getattr(certifi.where, 'orig_where', None) or certifi.where

    cert_files = [environ.get('SSL_CERT_FILE'), '/etc/ssl/certs/ca-certificates.crt', where()]

    return [cf for cf in cert_files if cf and os.path.exists(cf)][0]


def write_ca(content, include_default=True):
    temp = NamedTemporaryFile(
        prefix='ca_', suffix='.pem', delete=False, mode='w+t', encoding='utf-8'
    )
    if include_default:
        temp.write(get_system_default_ca_certs_content().rstrip())
        temp.write('\r\n')
    temp.write(content)
    os.chmod(temp.name, 0o0644)
    return temp.name


def read_env():
    from environ import Env

    env = Env()

    ENV_FILE = os.environ.get('ENV_FILE') or os.path.join(BASE_DIR, '.env')

    if os.path.exists(ENV_FILE):
        env.read_env(ENV_FILE)

    return parse_env_variables()


def parse_env_variables():
    from environ import Env

    env = Env()

    CUSTOM_CA = env.str('CUSTOM_CA', '', multiline=True)
    CLEAR_DEFAULT_CA = env.str('CLEAR_DEFAULT_CA', '') in ('1', 'true', 'True')

    if not CUSTOM_CA:
        return {}

    if '---BEGIN' not in CUSTOM_CA:
        return {}

    if '---END' in CUSTOM_CA.strip().split('\n')[0]:
        return {}

    return {
        'ca_content': CUSTOM_CA,
        'include_default': not CLEAR_DEFAULT_CA,
    }


def get_override_env(filename):

    return {
        'CURL_CA_BUNDLE': filename,
        'REQUESTS_CA_BUNDLE': filename,
        'SSL_CERT_FILE': filename,
        'MIVIDAS_CUSTOM_CA_FILE': filename,
    }


def update_ca(print_env=False, force_update=False):

    env = parse_env_variables()

    if print_env:
        for k, v in env.items():
            print('export {}="{}"'.format(k, v))

    if not env:
        return

    return apply_ca_content(**env, force_update=force_update)


def apply_ca_content(ca_content, include_default=True, force_update=False):

    filename = environ.get('MIVIDAS_CUSTOM_CA_FILE')
    if not filename or force_update:
        filename = write_ca(ca_content, include_default=include_default)

    env = get_override_env(filename)
    monkey_patch(env, filename)

    environ.update(env)

    return env


def get_ca_file():

    filename = environ.get('MIVIDAS_CUSTOM_CA_FILE')
    if not filename:
        filename = get_system_default_ca_certs_file()

    return filename


def monkey_patch(env, filename):
    monkey_patch_certifi(env, filename)


def monkey_patch_certifi(env, filename):
    import certifi

    def custom_ca_where():
        return env['MIVIDAS_CUSTOM_CA_FILE']

    custom_ca_where.orig_where = getattr(certifi.where, 'orig_where', None) or certifi.where

    def custom_ca_contents():
        with open(env['MIVIDAS_CUSTOM_CA_FILE']) as fd:
            return fd.read()

    custom_ca_contents.orig_contents = (
        getattr(certifi.contents, 'orig_contents', None) or certifi.contents
    )

    certifi.where = custom_ca_where
    certifi.contents = custom_ca_contents


if __name__ == '__main__':
    read_env()
    update_ca(print_env=True)
