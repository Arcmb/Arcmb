"""Verificação estática da v3.8.2. Não grava no banco."""
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parent


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def main():
    js = (ROOT / 'static' / 'student_view_v2.js').read_text(encoding='utf-8')
    html = (ROOT / 'static' / 'app.html').read_text(encoding='utf-8')
    require("acts['return-owner']=async function(){if(await svLeave())return;if(typeof baseReturn==='function')" in js, 'O botão antigo de voltar precisa continuar funcionando.')
    require('load=async function(){svSync();' in js, 'A visão do aluno deve ser detectada no carregamento da conta.')
    require(html.index('/static/student_view_v2.js') > html.index('/static/return_to_owner.js'), 'Ordem de carregamento incorreta.')
    for name in ('review_history.js', 'review_calendar_table.js', 'student_guidance.js'):
        require(not (ROOT / 'static' / name).read_text(encoding='utf-8').startswith('\\'), name + ' ainda começa com barra invertida.')
    print('MEUCRONOGRAMA_V382_STUDENT_VIEW_CHECK_OK: student view on account load, legacy return kept, review files executable.', flush=True)


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        print('MEUCRONOGRAMA_V382_STUDENT_VIEW_CHECK_FAILED:', exc, flush=True)
        sys.exit(1)
