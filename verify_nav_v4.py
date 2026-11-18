"""Verificação estática da v3.8.0: toda tela do menu antigo continua alcançável."""
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parent


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def main():
    js = (ROOT / 'static' / 'nav_v4.js').read_text(encoding='utf-8')
    app = (ROOT / 'static' / 'app.js').read_text(encoding='utf-8')
    html = (ROOT / 'static' / 'app.html').read_text(encoding='utf-8')
    legacy = set(re.findall(r"\['([a-z-]+)','[^']+'\]", app[app.index('const navItems='):app.index('function renderNav')]))
    legacy |= {'review-table', 'accounts'}
    grouped = set(re.findall(r"\['([a-z-]+)','[^']+'\]", js))
    missing = sorted(legacy - grouped)
    require(not missing, 'Telas sem lugar no menu novo: ' + ', '.join(missing))
    require(html.index('/static/nav_v4.js') > html.index('/static/student_view_mode.js'), 'Menu novo deve carregar por último.')
    for name in ('review_history.js', 'review_calendar_table.js', 'student_guidance.js'):
        require(not (ROOT / 'static' / name).read_text(encoding='utf-8').startswith('\\'), name + ' ainda começa com barra invertida.')
    print(f'MEUCRONOGRAMA_V380_NAV_CHECK_OK: {len(legacy)} telas antigas alcançáveis pelo menu agrupado.', flush=True)


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        print('MEUCRONOGRAMA_V380_NAV_CHECK_FAILED:', exc, flush=True)
        sys.exit(1)
