"""Verify that the corrected two-tab UI is actually served over the WSGI app."""
import io
import os
import sys

from webapp import App


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def main():
    app = App()
    host = os.getenv('RENDER_EXTERNAL_HOSTNAME') or sorted(app.hosts)[0]
    server_name = host.split(':', 1)[0]
    response = {}

    environ = {
        'REQUEST_METHOD': 'GET',
        'PATH_INFO': '/static/two_tab.js',
        'QUERY_STRING': 'v=2.8.2',
        'HTTP_HOST': host,
        'SERVER_NAME': server_name,
        'SERVER_PORT': '443',
        'SERVER_PROTOCOL': 'HTTP/1.1',
        'REMOTE_ADDR': '127.0.0.1',
        'CONTENT_LENGTH': '0',
        'wsgi.version': (1, 0),
        'wsgi.url_scheme': 'https',
        'wsgi.input': io.BytesIO(b''),
        'wsgi.errors': sys.stderr,
        'wsgi.multithread': False,
        'wsgi.multiprocess': False,
        'wsgi.run_once': False,
    }

    def start_response(status, headers, exc_info=None):
        response['status'] = int(status.split()[0])
        response['headers'] = {key.lower(): value for key, value in headers}

    body = b''.join(app(environ, start_response))
    require(response.get('status') == 200, 'two_tab.js must be served with HTTP 200.')
    require(
        response.get('headers', {}).get('content-type', '').startswith('application/javascript'),
        'two_tab.js must use the JavaScript content type.',
    )
    require(b'v281ResultModelView' in body, 'Served two-tab UI implementation is incomplete.')
    require(b'Gerar arquivo com 2 abas' in body, 'Served two-tab generator button is missing.')

    print(
        'MEUCRONOGRAMA_V282_STATIC_CHECK_OK: two-tab UI asset returned HTTP 200.',
        flush=True,
    )


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        print(
            'MEUCRONOGRAMA_V282_STATIC_CHECK_FAILED: '
            + type(exc).__name__
            + '. Credentials omitted.',
            flush=True,
        )
        raise SystemExit(18)
