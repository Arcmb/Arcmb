"""Expose the definitive two-tab JavaScript through the application's static whitelist.

The generated app uses an explicit MIME/allowlist for static assets.  The UI file
must be both present and listed there; otherwise the browser receives a 404 and
the selected menu page cannot render.
"""
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parent
JS_MIME = "'two_tab.js':'application/javascript; charset=utf-8'"
CACHE_URL = '/static/two_tab.js?v=2.8.2'


def prepare():
    asset = ROOT / 'static' / 'two_tab.js'
    if not asset.is_file():
        raise RuntimeError('static/two_tab.js was not generated.')

    app_path = ROOT / 'webapp.py'
    source = app_path.read_text(encoding='utf-8')
    if JS_MIME not in source:
        entries = list(re.finditer(
            r"'[^'\n]+\.js'\s*:\s*'application/javascript; charset=utf-8'",
            source,
        ))
        if not entries:
            raise RuntimeError('JavaScript static MIME allowlist was not found in webapp.py.')
        anchor = entries[-1]
        source = source[:anchor.end()] + ',' + JS_MIME + source[anchor.end():]
        app_path.write_text(source, encoding='utf-8')

    html_path = ROOT / 'static' / 'app.html'
    html = html_path.read_text(encoding='utf-8')
    html, count = re.subn(
        r'/static/two_tab\.js\?v=[^"\s<]+',
        CACHE_URL,
        html,
        count=1,
    )
    if count != 1:
        raise RuntimeError('two_tab.js script reference was not found in app.html.')
    html_path.write_text(html, encoding='utf-8')

    final_source = app_path.read_text(encoding='utf-8')
    if final_source.count(JS_MIME) != 1:
        raise RuntimeError('two_tab.js static allowlist entry is missing or duplicated.')

    print(
        'MEUCRONOGRAMA_V282_STATIC_READY: two_tab.js is whitelisted and cache-busted.',
        flush=True,
    )


if __name__ == '__main__':
    prepare()
