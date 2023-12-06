from time import time

from django.utils.timezone import now


class PolicyResponse(Exception):
    def __init__(self, response, *args):
        self.response = response
        super().__init__(*args)


class PolicyExitResponse(PolicyResponse):
    def __init__(self, *args):
        super().__init__({})


def send_response(response, _extra=None, **overrides):
    raise PolicyResponse(
        {
            'status': 'success',
            'action': 'continue',
            **(_extra or {}),
            'result': {**(response.get('result') or {}), **overrides},
        }
    )


def response_exit(reason: str = '', _extra=None):
    raise PolicyExitResponse(
        {'status': 'success', 'action': 'continue', '_reason': reason, **(_extra or {})}
    )


def deny(reason: str = '', _extra=None):
    raise PolicyResponse(
        {'status': 'success', 'action': 'reject', '_reason': reason, **(_extra or {})}
    )


def get_globals():

    return {
        'send_response': send_response,
        'deny': deny,
        'exit': response_exit,
        'time': time,
        'now': now,
        'null': None,
        'true': True,
        'false': False,
    }
