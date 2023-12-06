VALID_NAMES = {
    'KeyError',
    'IndexError',
    'ParseError',
    'AuthenticationError',
    'ResponseConnectionError',
}


def format_exception(ex: Exception):
    try:
        return _format_exception(ex)
    except Exception:
        try:
            return str(ex)
        except Exception:
            return 'Error: Unserializable exception'


def _format_exception(ex: Exception):
    from provider.exceptions import ResponseError

    if isinstance(ex, str):
        return ex[:200]

    prefix = ''
    if ex.__class__.__name__ in VALID_NAMES:
        prefix = '{}: '.format(ex.__class__.__name__)
        if isinstance(ex, ResponseError):
            msg = ex.get_message()
        else:
            msg = str(ex)
    else:
        msg = ex.__class__.__name__

    return str(prefix + msg)[:200]
