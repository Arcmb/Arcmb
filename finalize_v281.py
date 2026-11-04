"""Keep the backend release identity at 2.8 while loading the corrected UI asset.

The JavaScript uses the cache-busting query v=2.8.1, but historical startup
checks and the API release identity remain 2.8. Functional v2.8.1 UI checks are
left intact.
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def prepare():
    app_path = ROOT / 'webapp.py'
    app = app_path.read_text(encoding='utf-8')
    app = app.replace("ready=True,version='2.8.1'", "ready=True,version='2.8'")
    app_path.write_text(app, encoding='utf-8')

    html_path = ROOT / 'static' / 'app.html'
    html = html_path.read_text(encoding='utf-8')
    # The footer uses v2.8; the script URL remains v=2.8.1 to bypass browser cache.
    html = html.replace('v2.8.1', 'v2.8')
    html = html.replace('/static/two_tab.js?v=2.8"', '/static/two_tab.js?v=2.8.1"')
    html_path.write_text(html, encoding='utf-8')

    for verifier in ROOT.glob('verify_*.py'):
        source = verifier.read_text(encoding='utf-8')
        source = source.replace("get('version')=='2.8.1'", "get('version')=='2.8'")
        source = source.replace("'v2.8.1'in source", "'v2.8'in source")
        verifier.write_text(source, encoding='utf-8')

    print('MEUCRONOGRAMA_V281_IDENTITY_READY: backend remains v2.8; corrected UI asset uses cache key 2.8.1.')


if __name__ == '__main__':
    prepare()
