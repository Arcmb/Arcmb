"""Verificação estática da v3.7.19. Não grava no banco."""
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def main():
    js = (ROOT / 'static' / 'student_view_mode.js').read_text(encoding='utf-8')
    html = (ROOT / 'static' / 'app.html').read_text(encoding='utf-8')
    webapp = (ROOT / 'webapp.py').read_text(encoding='utf-8')
    require("acts['student-view-return']" in js and 'Voltar ao meu usuário' in js, 'Return control missing.')
    require("['aluno','user','especial'].includes(account.role)" in js, 'Student view must apply only to individual accounts.')
    require(html.index('/static/student_view_mode.js') > html.index('/static/return_to_owner.js'), 'Student view must load after the legacy return control.')
    require("'student_view_mode.js':'application/javascript" in webapp, 'Static allowlist entry missing.')
    print('MEUCRONOGRAMA_V3719_STUDENT_VIEW_CHECK_OK: student interface mode and return control present.', flush=True)


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        print('MEUCRONOGRAMA_V3719_STUDENT_VIEW_CHECK_FAILED:', exc, flush=True)
        sys.exit(1)
