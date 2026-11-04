"""Deployment check for the definitive two-tab workbook and language variants."""
import base64
import re
from collections import Counter
from pathlib import Path

import model_data as M
import selective as S
import templates_v23 as T


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def encoded(blob):
    return base64.b64encode(blob).decode('ascii')


def main():
    root = Path(__file__).resolve().parent
    html = (root / 'static' / 'app.html').read_text(encoding='utf-8')
    scripts = re.findall(r'<script[^>]+src="([^"]+)"[^>]*></script>', html)
    require(scripts, 'Application scripts missing.')
    require(
        '/static/two_tab.js?v=2.8.1' in scripts,
        'Two-tab interface with cache-busting version is missing from app.html.',
    )
    ui_source = (root / 'static' / 'two_tab.js').read_text(encoding='utf-8')
    require('v281ResultModelView' in ui_source, 'Two-tab view implementation missing.')
    require('DOMContentLoaded' in ui_source and 'v281Install' in ui_source, 'Late UI activation missing.')
    require('MutationObserver' in ui_source and 'v281ReplaceLegacyScreen' in ui_source, 'Legacy-screen replacement missing.')
    require('Gerar arquivo com 2 abas' in ui_source, 'Definitive two-tab button missing.')
    require('Gerar Excel separado por áreas' not in ui_source, 'Legacy area button leaked into two-tab UI.')

    blob, _ = M.template({'questions': 180, 'colors': ['AZUL', 'AMARELO', 'BRANCO', 'VERDE']})
    data = {'filename': 'MODELO_DADOS_2_ABAS.xlsx', 'file': encoded(blob)}
    _, _, sheets, _, _ = S.matrix(data)
    require(sheets == [M.STUDENTS_SHEET, M.EXAM_SHEET], 'Template must contain exactly two worksheets.')

    students, _, _, _, _ = S.matrix({**data, 'sheet': M.STUDENTS_SHEET})
    exam, _, _, _, _ = S.matrix({**data, 'sheet': M.EXAM_SHEET})
    require(len(students[0]) == 187, 'Student sheet must contain seven identification fields plus 180 questions.')
    require(len(exam) == 741, 'Four colors must generate 740 map rows plus header.')
    headers = {str(value).strip(): index for index, value in enumerate(exam[0])}
    by_color = {}
    for row in exam[1:]:
        color = row[headers['COR DA PROVA']]
        by_color.setdefault(color, []).append(row)
    require(set(by_color) == {'AZUL', 'AMARELO', 'BRANCO', 'VERDE'}, 'Default colors missing.')
    for color, rows in by_color.items():
        require(len(rows) == 185, color + ' must have 185 map records.')
        numbers = Counter(int(row[headers['QUESTÃO']]) for row in rows)
        require(all(numbers[q] == 2 for q in range(1, 6)), color + ' must duplicate questions 01-05 by language.')
        require(all(numbers[q] == 1 for q in range(6, 181)), color + ' must contain one map row for questions 06-180.')
        q1 = [row for row in rows if int(row[headers['QUESTÃO']]) == 1]
        require({row[headers['LÍNGUA ESTRANGEIRA']] for row in q1} == {'Inglês', 'Espanhol'}, 'Question 01 language versions missing.')
        require({row[headers['DISCIPLINA']] for row in q1} == {'INGLÊS', 'ESPANHOL'}, 'Question 01 disciplines missing.')

    student_headers = ['NOME', 'LOGIN', 'TURMA', 'NOME DO SIMULADO', 'DATA DE APLICAÇÃO', 'COR DA PROVA', 'L. ESTRANGEIRA', 1, 2, 3, 4, 5]
    student_rows = [
        ['Aluno Inglês', 'aluno_en', 'T1', 'Simulado teste', '04/11/2026', 'AZUL', 'Inglês', 'A', '', 'C', 'D', 'E'],
        ['Aluno Espanhol', 'aluno_es', 'T1', 'Simulado teste', '04/11/2026', 'AZUL', 'Espanhol', 'A', 'B', 'C', 'D', 'E'],
    ]
    map_headers = ['NOME DO SIMULADO', 'DATA DE APLICAÇÃO', 'COR DA PROVA', 'QUESTÃO', 'ÁREA', 'DISCIPLINA', 'TÓPICO', 'ASSUNTO', 'HABILIDADE', 'LÍNGUA ESTRANGEIRA', 'GABARITO']
    map_rows = []
    english_keys = ['A', 'B', 'C', 'D', 'E']
    spanish_keys = ['E', 'D', 'C', 'B', 'A']
    for q in range(1, 6):
        map_rows.append(['Simulado teste', '04/11/2026', 'AZUL', q, 'LINGUAGENS', 'INGLÊS', 'T', 'A', 'H01', 'Inglês', 'ANULADA' if q == 3 else english_keys[q-1]])
        map_rows.append(['Simulado teste', '04/11/2026', 'AZUL', q, 'LINGUAGENS', 'ESPANHOL', 'T', 'A', 'H02', 'Espanhol', 'ANULADA' if q == 3 else spanish_keys[q-1]])
    sample, _ = T.export(student_headers, student_rows, first_name=M.STUDENTS_SHEET, extra_sheets=[(M.EXAM_SHEET, map_headers, map_rows)])
    parsed = M._parse({'filename': 'sample.xlsx', 'file': encoded(sample)}, require_date=True)
    exam_spec = next(iter(parsed['exams'].values()))
    items = {(item['number'], item['language']): item for item in exam_spec['items']}
    require(M._answer_result('A', items[(1, 'Inglês')]) == 1, 'Correct answer must be 1.')
    require(M._answer_result('A', items[(1, 'Espanhol')]) == 0, 'Different answer must be 0.')
    require(M._answer_result(None, items[(2, 'Inglês')]) == 0, 'Blank answer must be 0 with valid key.')
    require(M._answer_result('C', items[(3, 'Inglês')]) is None, 'Annulled question must be excluded.')

    missing_language_rows = [student_rows[0][:6] + [''] + student_rows[0][7:]]
    missing_blob, _ = T.export(student_headers, missing_language_rows, first_name=M.STUDENTS_SHEET, extra_sheets=[(M.EXAM_SHEET, map_headers, map_rows)])
    try:
        M._parse({'filename': 'missing.xlsx', 'file': encoded(missing_blob)}, require_date=True)
    except ValueError as exc:
        require('Inglês ou Espanhol' in str(exc), 'Missing-language error must be explicit.')
    else:
        raise RuntimeError('Student language must be required when questions 01-05 have two versions.')

    print('MEUCRONOGRAMA_V281_CHECK_OK: UI override, exactly two tabs, 180 student answers, 185 map rows per color and English/Spanish selection passed.', flush=True)


if __name__ == '__main__':
    main()
