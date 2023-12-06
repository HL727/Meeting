import concurrent.futures
import os
from typing import Callable, Iterator, Tuple, TypeVar

import celery.exceptions
from django.conf import settings
from sentry_sdk import capture_exception

from endpoint.ext_api.cisco_ce import CiscoCEProviderAPI
from endpoint.models import Endpoint
from provider.exceptions import AuthenticationError, ResponseError

TR = TypeVar('TR')


def endpoint_thread_pool(
    endpoints: Iterator[Endpoint],
    callback: Callable[[CiscoCEProviderAPI], TR],
    processes: int = None,
    raise_exceptions=False,
    timeout: float = None,
) -> Iterator[Tuple[Endpoint, TR]]:

    if not processes:
        processes = max(3, os.cpu_count() or 1)

    if settings.TEST_MODE:
        processes = 1

    def _catch_callback(_api: CiscoCEProviderAPI) -> TR:
        try:
            return _api.endpoint, callback(_api)
        except (ResponseError, AuthenticationError) as e:
            return _api.endpoint, e
        except (concurrent.futures.TimeoutError, celery.exceptions.TimeoutError):
            raise
        except Exception as e:
            capture_exception()
            return _api.endpoint, e
        finally:
            _api.endpoint._api = None
            del _api

    with concurrent.futures.ThreadPoolExecutor(max_workers=processes) as executor:

        for endpoint, result in executor.map(
            _catch_callback, map(lambda e: e.get_api(), endpoints), timeout=timeout
        ):

            if raise_exceptions and isinstance(result, Exception):
                raise result
            yield endpoint, result
