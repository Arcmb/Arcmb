"""Startup verification for final result-import rules."""
from pathlib import Path
import model_data as M


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def main():
    for marker in ('.', 'x/x', 'X/X', '*'):
        require(M._answer(marker, 'Resposta') == 0, marker + ' must be converted to error zero.')

    accounts = [
        {'id': 'student-a', 'name': 'Áluno da Silva', 'username': 'acesso_errado', 'role': 'user'},
        {'id': 'master', 'name': 'Áluno da Silva', 'username': 'arcmb', 'role': 'master'},
        {'id': 'technical', 'name': 'Verificação técnica temporária', 'username': 'verificacao_123', 'role': 'user'},
    ]
    allowed = [a for a in accounts if M._is_importable_student_account(a)]
    require([a['id'] for a in allowed] == ['student-a'], 'Only real student accounts may be listed.')
    require(
        M._resolve_student_account(allowed, {'name': 'Aluno da Silva', 'login': 'outro_login'}) == 'student-a',
        'Full normalized name must have priority over login.',
    )

    homonyms = [
        {'id': 'one', 'name': 'Maria Souza', 'username': 'maria1', 'role': 'user'},
        {'id': 'two', 'name': 'Maria Souza', 'username': 'maria2', 'role': 'user'},
    ]
    require(M._resolve_student_account(homonyms, {'name': 'Maria Souza', 'login': ''}) == '', 'Homonyms require review.')
    require(M._resolve_student_account(homonyms, {'name': 'Maria Souza', 'login': 'maria2'}) == 'two', 'Login may only disambiguate homonyms.')

    js = (Path(__file__).resolve().parent / 'static' / 'model_data.js').read_text(encoding='utf-8')
    require("result-import-help-results" in js and "result-import-help-map" in js, 'Help buttons are missing.')
    require('ponto (.), x/x ou asterisco (*)' in js, 'Error-marker guidance is missing.')
    require('procura primeiro o nome completo' in js, 'Name-first guidance is missing.')
    print('MEUCRONOGRAMA_STUDENT_IMPORT_RULES_CHECK_OK: name-first binding, account filtering, error markers and help buttons passed.', flush=True)


if __name__ == '__main__':
    main()
