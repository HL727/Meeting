from dataclasses import dataclass
from typing import List, Any, Dict, Callable

import requests


@dataclass
class LoggedResponse:
    method: str
    url: str
    args: List[Any]
    data: Dict[str, Any]
    kwargs: Dict[str, Any]
    response: requests.Response


class LoggedResponsesList(list):
    def find_urls_all(self, url):
        result = []

        for response in reversed(self):
            url_with_method = '{} {}'.format(response.method, response.url).rstrip('/')
            if hasattr(url, 'match'):
                if url.match(response.url.rstrip('/')) or url.match(url_with_method):
                    result.append(response)
            elif response.url.rstrip('/') == url.rstrip('/') or url_with_method == url.rstrip('/'):
                result.append(response)

        return result

    def find_url(self, url):
        try:
            return self.find_urls_all(url)[0]
        except IndexError:
            pass

    def find_data(self, url):
        try:
            data = self.find_url(url).data
            return data.copy() if hasattr(data, 'copy') else data
        except AttributeError:
            return {}


class MockLogHandler:

    def __init__(self,  container: list):
        self.target = container
        self.responses = []

    def decorate(self, fn: Callable[[Any], Any]) -> Callable[[Any], Any]:
        def _inner(*args, **kwargs):
            return self.log_request(fn, *args, **kwargs)
        return _inner

    def _format_args(self, args):
        if isinstance(args[0], str):
            url = args[0]
            args = args[1:]
        else:
            url = args[1]
            args = args[2:]

        return url, args

    def add_response(self, url, callback):
        self.responses.append((url, callback))

    def _get_event_response_callback(self, url, method_url):
        for event_url, event_callback in self.responses:
            match = event_url == url or event_url == method_url
            if not match and hasattr(event_url, 'match'):
                match = event_url.match(method_url)
            if match:
                return event_callback

    def log_request(self, real_request_fn, *args, **kwargs):

        url = self._format_args(args)[0]

        method_url = '{} {}'.format(kwargs.get('method'), url)
        event_callback = self._get_event_response_callback(url, method_url)

        if event_callback:
            event_response = event_callback(*args, **kwargs)

            if event_response is not None:
                return event_response

        try:
            response = real_request_fn(*args, **kwargs)
            self._log(response, args, kwargs)
        except Exception as e:
            self._log(e, args, kwargs)
            raise
        return response

    def _log(self, response, args, kwargs):
        url, args = self._format_args(args)
        data = args[0] if args else kwargs.pop('data', None) or kwargs.pop('json', None)
        method = kwargs.pop('method', None)
        cur = LoggedResponse(method, url, args, data, kwargs, response)
        self.target.append(cur)

