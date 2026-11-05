"""Startup check for the dedicated two-tab result importer."""
import io
import os
from pathlib import Path

from webapp import App


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def request(app, path, query=''):
    host = os.getenv('RENDER_EXTERNAL_HOSTNAME') or sorted(app.hosts)[0]
    result = {}
    env = {
        'REQUEST_METHOD': 'GET', 'PATH_INFO': path, 'QUERY_STRING': query,
        'HTTP_HOST': host, 'wsgi.input': io.BytesIO(b''), 'wsgi.url_scheme': 'https',
        'CONTENT_LENGTH': '0', 'REMOTE_ADDR': '127.0.0.1',
    }
    def start(status, headers):
        result['status'] = int(status.split()[0])
        result['headers'] = dict(headers)
    result['body'] = b''.join(app(env, start))
    return result


def main():
    root = Path(__file__).resolve().parent
    html = (root / 'static' / 'app.html').read_text(encoding='utf-8')
    app_js = (root / 'static' / 'app.js').read_text(encoding='utf-8')
    ui = (root / 'static' / 'result_import.js').read_text(encoding='utf-8')
    webapp = (root / 'webapp.py').read_text(encoding='utf-8')

    require('/static/result_import.js?v=2.8.4' in html, 'Result importer asset is missing from app.html.')
    require("'result_import.js':'application/javascript; charset=utf-8'" in webapp, 'Result importer static MIME entry is missing.')
    require("['result-import','Importar resultados']" in app_js, 'Result importer navigation item is missing.')
    require("'result-import':resultImportView" in app_js, 'Result importer page route is missing.')
    for token in ('/api/model-data/inspect', '/api/model-data/preview', '/api/model-data/confirm', "acts['model-to-results']"):
        require(token in ui, token + ' is missing from result importer UI.')
    require('data-result-import-student' in ui, 'Student-account binding control is missing.')
    require('Não é necessário relacionar colunas manualmente' in ui, 'Manual-mapping guidance is missing.')

    app = App()
    response = request(app, '/static/result_import.js', 'v=2.8.4')
    require(response['status'] == 200, 'Result importer asset was not served with HTTP 200.')
    body = response['body'].decode('utf-8')
    require('function resultImportView' in body, 'Served result importer asset is incomplete.')

    print('MEUCRONOGRAMA_RESULT_IMPORT_CHECK_OK: dedicated page, file flow, account binding and static delivery passed.', flush=True)


if __name__ == '__main__':
    main()
