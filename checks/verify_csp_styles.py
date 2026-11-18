"""v3.14.1: os estilos inline das telas (tamanho das barras dos gráficos) precisam ser reaplicados pelo csp_style_shim.js."""
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]


def main():
    html = (ROOT / 'static' / 'app.html').read_text(encoding='utf-8')
    scripts = re.findall(r'<script[^>]+src="([^"]+)"', html)
    if not scripts or not scripts[0].startswith('/static/csp_style_shim.js'):
        raise RuntimeError('csp_style_shim.js precisa ser o primeiro script de app.html.')
    print('MEUCRONOGRAMA_V3141_CSP_STYLES_CHECK_OK', flush=True)


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        print('MEUCRONOGRAMA_V3141_CSP_STYLES_CHECK_FAILED:', exc, flush=True)
        sys.exit(1)
