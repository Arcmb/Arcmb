"""Verificação estática da v3.12.0. Não grava no banco."""
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def main():
    import disciplines_catalog as D
    mark = '_DC.canon_items(app,c,'
    for name in ('exams.py', 'unified.py', 'model_data.py'):
        require(mark in (ROOT / name).read_text(encoding='utf-8'), name + ': importação sem conversão para o nome oficial.')
    require("if path.startswith('/api/disciplines/'):" in (ROOT / 'webapp.py').read_text(encoding='utf-8'), 'Rota do cadastro ausente.')
    require('/static/disciplines_catalog.js' in (ROOT / 'static' / 'app.html').read_text(encoding='utf-8'), 'Script da tela ausente.')
    idx = D.index(D.validate(D.DEFAULT_CATALOG))
    require(D.canonical('ESPANHOL', idx) == 'Espanhol' and D.canonical('L. corporal', idx) == 'Linguagem Corporal'
            and D.canonical('INGLÊS', idx) == 'Inglês' and D.canonical('Astronomia', idx) == 'Astronomia', 'Conversão de nomes incorreta.')
    try:
        D.validate({'disciplines': [{'name': 'Artes', 'area': 'LC', 'aliases': ['Física']}, {'name': 'Física', 'area': 'CN', 'aliases': []}]})
        raise RuntimeError('Variação repetida deveria ser recusada.')
    except ValueError:
        pass
    print('MEUCRONOGRAMA_V3120_DISCIPLINES_CHECK_OK: catalog, import conversion and routes present.', flush=True)


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        print('MEUCRONOGRAMA_V3120_DISCIPLINES_CHECK_FAILED:', exc, flush=True)
        sys.exit(1)
