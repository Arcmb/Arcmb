"""Muda a versão pública exibida no rodapé.

Uso: python tools/set_version.py 3.13.0

Atualiza site_version.py e o rótulo "vX.Y.Z" e as chaves &map= de app.html.
As chaves ?v= de cada script ficam a cargo de quem altera o script: ao mudar um
arquivo em static/, troque o ?v= dele em static/app.html para o navegador baixar a versão nova.
"""
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]


def main(new):
    if not re.fullmatch(r'\d+\.\d+\.\d+', new):
        raise SystemExit('Informe a versão no formato 3.13.0')
    sv = ROOT / 'site_version.py'
    text = sv.read_text(encoding='utf-8')
    old = re.search(r'PUBLIC_VERSION = "([^"]+)"', text).group(1)
    sv.write_text(text.replace(f'PUBLIC_VERSION = "{old}"', f'PUBLIC_VERSION = "{new}"'), encoding='utf-8')
    html_path = ROOT / 'static' / 'app.html'
    html = html_path.read_text(encoding='utf-8')
    html = html.replace(f'v{old}</small>', f'v{new}</small>')
    html = re.sub(r'(&amp;map=)' + re.escape(old), r'\g<1>' + new, html)
    html_path.write_text(html, encoding='utf-8')
    print(f'Versão {old} → {new}')


if __name__ == '__main__':
    main(sys.argv[1] if len(sys.argv) > 1 else '')
