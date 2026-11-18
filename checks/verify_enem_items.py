"""Verificação da v3.13.0 (banco de itens do ENEM). Não usa o banco."""
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def main():
    import enem_items as E
    require(E.scale(2.0, 1.0) == (2.0, 600.0) and E.scale(0.025, 700) == (2.5, 700), 'Conversão de escala incorreta.')
    require(E.difficulty(650) == 'Média' and E.complexity(2.6, 0.1) == 'Alta', 'Classificação incorreta.')
    require("if path.startswith('/api/enem-items/'):" in (ROOT / 'webapp.py').read_text(encoding='utf-8'), 'Rota do banco ENEM ausente.')
    require('/static/enem_items.js' in (ROOT / 'static' / 'app.html').read_text(encoding='utf-8'), 'Tela do banco ENEM ausente.')
    print('MEUCRONOGRAMA_V3130_ENEM_ITEMS_CHECK_OK', flush=True)


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        print('MEUCRONOGRAMA_V3130_ENEM_ITEMS_CHECK_FAILED:', exc, flush=True)
        sys.exit(1)
