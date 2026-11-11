"""Startup verification for final result-import rules."""
from pathlib import Path
import model_data as M


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def main():
    for valid in ('A', 'B', 'C', 'D', 'E', 'a', 'b', 'c', 'd', 'e'):
        require(M._answer(valid, 'Resposta') == valid.upper(), valid + ' must remain a valid isolated alternative.')

    for marker in (
        '', '.', '*', '0', '1', 'x', 'x/x', 'X/X',
        'A/A', 'A|A', 'A | A', 'A/B', 'B|C', 'C - D',
        'AB', 'A B', 'ANULADA', 'ERRO',
    ):
        require(M._answer(marker, 'Resposta') == 0, repr(marker) + ' must be converted to error zero.')

    accounts = [
        {'id': 'student-a', 'name': 'Áluno da Silva', 'username': 'acesso_errado', 'role': 'aluno'},
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
        {'id': 'one', 'name': 'Maria Souza', 'username': 'maria1', 'role': 'aluno'},
        {'id': 'two', 'name': 'Maria Souza', 'username': 'maria2', 'role': 'aluno'},
    ]
    require(M._resolve_student_account(homonyms, {'name': 'Maria Souza', 'login': ''}) == '', 'Homonyms require review.')
    require(M._resolve_student_account(homonyms, {'name': 'Maria Souza', 'login': 'maria2'}) == 'two', 'Login may only disambiguate homonyms.')

    js = (Path(__file__).resolve().parent / 'static' / 'model_data.js').read_text(encoding='utf-8')
    require("result-import-help-results" in js and "result-import-help-map" in js, 'Help buttons are missing.')
    require('Somente uma alternativa isolada A, B, C, D ou E é válida.' in js, 'Strict A-E guidance is missing.')
    require('procura primeiro o nome completo' in js, 'Name-first guidance is missing.')
    print('MEUCRONOGRAMA_STUDENT_IMPORT_RULES_CHECK_OK: name-first binding, strict isolated A-E rule, universal non-A-E error conversion and help buttons passed.', flush=True)


if __name__ == '__main__':
    main()
