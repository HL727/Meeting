import asyncio
import re

from django.utils.functional import curry

try:
    import gevent  # noqa
    import gevent.monkey

    gevent.monkey.patch_all()
except ImportError:
    gevent = None

import os
import sys
from random import randint, random

import gunicorn.app.base

BASE_URL = os.environ.get('SIMULATE_ENDPOINT_TARGET_HOST') or ''
COUNT = int(os.environ.get('SIMULATE_ENDPOINT_COUNT') or '5000')


class LoadTestApplication(gunicorn.app.base.BaseApplication):
    def __init__(self, manager, options=None, is_async=False):
        self.manager = manager
        self.options = options or {}
        self.is_async = is_async
        super().__init__()

    def load_config(self):
        config = {
            key: value
            for key, value in self.options.items()
            if key in self.cfg.settings and value is not None
        }
        for key, value in config.items():
            self.cfg.set(key.lower(), value)

    def load(self, is_async=None):
        if is_async is None:
            is_async = self.is_async
        if self.manager.base_url:
            self.manager.start_event_thread()

        def asgi2(scope):
            return curry(self.handler_app_async, scope)

        return asgi2 if is_async else self.handler_app

    _valuespace_data = None

    def get_valuespace_data(self):
        if self._valuespace_data is None:
            root = (
                os.path.join(os.path.abspath(os.path.dirname(__file__)), '..', '..', 'data') + '/'
            )

            with open(root + 'valuespace.xml') as fd:
                self._valuespace_data = fd.read().encode('utf-8')
        return self._valuespace_data

    def get_putxml_response(self, body: bytes):

        result = []
        for cmd in re.findall(rb'<([A-z0-9]+) command="[Tt]rue">', body):
            result.append(b'<%sResult status="OK" />' % cmd)

        if result:  # command
            return [b'<?xml version="1.0" ?><Command>'] + result + [b'</Command>']

        if re.search(rb'> *[A-z0-9]', body):
            result.append(b'<Config status="OK" />')

        if result:  # configuration
            return [b'<?xml version="1.0" ?><Configuration>'] + result + [b'</Configuration>']

        return [b'<Empty />']

    def handler_app(self, environ, start_response):

        needs_body = ('/putxml',)
        url = self._get_url(environ)
        if url in needs_body:
            body = self._read_body(environ)
            if self._get_url(environ).startswith('/putxml'):
                self._accept(start_response)
                return self.get_putxml_response(body)

        response = self.get_response(url, environ.get('HTTP_HOST', ''))
        if response is not None:
            self._accept(start_response)
            return response

        start_response(
            '404 Not Found',
            [
                ('Content-Type', 'text/xml'),
            ],
        )
        return [b'']

    async def handler_app_async(self, scope, receive, send):
        needs_body = ('/putxml',)
        url = self._get_url(scope)
        if url in needs_body:
            body = await self._read_body_async(receive)
            if self._get_url(scope).startswith('/putxml'):
                await self._accept_async(send)
                await send(self.get_putxml_response(body))

        response = self.get_response(url, dict(scope['headers']).get(b'host', b'').decode())
        if response is not None:
            await self._accept_async(send)
            await send(
                {
                    'type': 'http.response.body',
                    'body': b''.join(response),
                }
            )
            return

        await send(
            {
                'type': 'http.response.start',
                'status': 404,
                'headers': [
                    [b'content-type', b'text/xml'],
                ],
            }
        )

    def _accept(self, start_response):
        if randint(0, 3) == 2 and gevent:
            gevent.sleep(random() * 3)

        def _start_response():

            response_headers = [
                ('Content-Type', 'text/xml'),
            ]

            start_response('200 OK', response_headers)

            if randint(0, 3) == 2 and gevent:
                gevent.sleep(random() * 7)

        return _start_response()

    async def _accept_async(self, send):
        if randint(0, 3) == 2 and gevent:
            await asyncio.sleep(random() * 3)

        await send(
            {
                'type': 'http.response.start',
                'status': 200,
                'headers': [
                    [b'content-type', b'text/xml'],
                ],
            }
        )
        if randint(0, 3) == 2 and gevent:
            await asyncio.sleep(random() * 7)

    def _get_url(self, environ):
        url = environ.get('PATH_INFO', environ.get('path', '')).lower()
        query = environ.get('QUERY_STRING', '').lower()
        if '?' in url:
            url, query = url.split('?', 1)

        if url.startswith('/getxml'):
            from urllib.parse import parse_qsl

            qs = dict(parse_qsl(query))
            new_url = qs.get('location', '').strip('/')
            if new_url:
                url = '/{}.xml'.format(new_url)

        return url

    def _read_body(self, environ):
        try:
            request_body_size = int(environ.get('CONTENT_LENGTH', 0))
        except (ValueError):
            request_body_size = 0

        return environ['wsgi.input'].read(max(0, min(1024 * 1024, request_body_size)))

    async def _read_body_async(self, receive):
        body = b''
        more_body = True

        while more_body:
            message = await receive()
            body += message.get('body', b'')
            more_body = message.get('more_body', False)

        return body

    def get_response(
        self,
        url,
        http_host,
    ):
        if url.startswith('/status.xml'):
            return [self.manager.get_endpoint(http_host).get_status().encode()]
        elif url.startswith('/configuration.xml'):
            return [self.manager.get_endpoint(http_host).get_configuration().encode()]
        elif url.startswith('/valuespace.xml'):
            return [
                self.get_valuespace_data(),
            ]
        elif url.startswith('/putxml.xml'):
            return [b'<Status status="OK" />']


def get_app(base_url=BASE_URL, is_async=False):
    from .load_test import Manager

    manager = Manager(COUNT, base_url)

    default_options = {
        'bind': '%s:%s' % ('0.0.0.0', os.environ.get('PORT') or '8087'),
        'workers': 2,
        'log_level': 'info',
        'accesslog': '-',
    }

    if is_async:
        options = {
            **default_options,
            'worker_class': 'uvicorn.workers.UvicornWorker',
            'interface': 'asgi3',
        }
    else:
        options = {
            **default_options,
            'worker_class': 'gevent',
            'worker_connections': 100,
        }

    return LoadTestApplication(manager, options, is_async=is_async)


is_async = os.environ.get('ASYNC_WORKER', '') in ('', '1', 'true')

app = get_app(sys.argv[1] if len(sys.argv) > 1 else BASE_URL, is_async)
app_async = app.handler_app_async


def run():

    try:
        app.run()
    finally:
        app.manager.done = True


if __name__ == '__main__':
    run()
