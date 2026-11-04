"""Finalize the two-tab batch response model and ENEM language mapping.

This release runs after the v2.7 source is extracted. It preserves the direct
A-E importer and replaces only the model generator, validation refinements,
interface entry point, release identity, and explanatory text.
"""
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parent
PY_MARKER = '# === MEU CRONOGRAMA V2.8: MODELO DEFINITIVO DE DUAS ABAS ==='

PY_EXTENSION = r'''

# === MEU CRONOGRAMA V2.8: MODELO DEFINITIVO DE DUAS ABAS ===
_v27_two_tab_parse = _parse

_V28_DEFAULT_COLORS = ('AZUL', 'AMARELO', 'BRANCO', 'VERDE')
_V28_AREA_NAMES = {
    'LC': 'LINGUAGENS',
    'CH': 'HUMANAS',
    'CN': 'NATUREZA',
    'MT': 'MATEMÁTICA',
}


def _v28_area_for_question(number):
    if number <= 45:
        return 'LC'
    if number <= 90:
        return 'CH'
    if number <= 135:
        return 'CN'
    return 'MT'


def _v28_colors(data):
    raw = data.get('colors', _V28_DEFAULT_COLORS)
    if isinstance(raw, str):
        values = re.split(r'[,;|\n]+', raw)
    elif isinstance(raw, (list, tuple)):
        values = raw
    else:
        raise ValueError('Informe as cores como lista ou texto separado por vírgulas.')
    result = []
    for value in values:
        color = _color(value)
        if color and color not in result:
            result.append(color)
    if not result:
        result = list(_V28_DEFAULT_COLORS)
    if len(result) > 10:
        raise ValueError('Use no máximo 10 cores por arquivo.')
    return result


def template(data):
    count = F.count_value(data.get('questions', 180), 'Quantidade de questões')
    if count is None or not 1 <= count <= 180:
        raise ValueError('Informe de 1 a 180 questões.')
    title = F.text(data.get('title'), 200)
    date = F.text(data.get('date'), 40)
    if date:
        date = F.date_value(date)
    colors = _v28_colors(data)

    student_headers = [
        'NOME', 'LOGIN', 'TURMA', 'NOME DO SIMULADO', 'DATA DE APLICAÇÃO',
        'COR DA PROVA', 'L. ESTRANGEIRA',
    ] + list(range(1, count + 1))
    exam_headers = [
        'NOME DO SIMULADO', 'DATA DE APLICAÇÃO', 'COR DA PROVA', 'QUESTÃO',
        'ÁREA', 'DISCIPLINA', 'TÓPICO', 'ASSUNTO', 'HABILIDADE',
        'LÍNGUA ESTRANGEIRA', 'GABARITO',
    ]
    exam_rows = []
    for color in colors:
        for number in range(1, count + 1):
            code = _v28_area_for_question(number)
            area = _V28_AREA_NAMES[code]
            if code == 'LC' and number <= 5:
                for language, discipline in (('Inglês', 'INGLÊS'), ('Espanhol', 'ESPANHOL')):
                    exam_rows.append([
                        title, date, color, number, area, discipline,
                        '', '', '', language, '',
                    ])
            else:
                exam_rows.append([
                    title, date, color, number, area, '', '', '', '', '', '',
                ])

    # Exactly two worksheets. Instructions are presented in the site instead of
    # creating a third worksheet.
    return T.export(
        student_headers,
        kind='xlsx',
        first_name=STUDENTS_SHEET,
        extra_sheets=[(EXAM_SHEET, exam_headers, exam_rows)],
    )


def _parse(data, require_date=False):
    parsed = _v27_two_tab_parse(data, require_date)
    applicable = set(parsed.get('questions') or [])
    maps_with_languages = set()
    for exam_key, exam in parsed['exams'].items():
        by_number = defaultdict(list)
        for item in exam['items']:
            by_number[item['number']].append(item)
        uses_languages = any(item.get('language') for item in exam['items'])
        if not uses_languages:
            continue
        maps_with_languages.add(exam_key)
        for number in sorted(q for q in applicable if 1 <= q <= 5):
            items = by_number.get(number, [])
            languages = {item.get('language') for item in items if item.get('language')}
            if languages != {'Inglês', 'Espanhol'}:
                raise ValueError(
                    f'DADOS DO SIMULADO: a questão {number:02d} deve possuir uma linha de Inglês e outra de Espanhol para cada cor.'
                )
            if any(not item.get('answer') for item in items if item.get('language')):
                parsed['warnings'].append(
                    f'{exam["color"]}: questão {number:02d} possui versão de língua sem gabarito e não será calculada nessa versão.'
                )
        invalid = [item['number'] for item in exam['items'] if item.get('language') and item['number'] > 5]
        if invalid:
            raise ValueError('DADOS DO SIMULADO: língua estrangeira só deve ser informada nas questões 01 a 05.')

    for student in parsed['students']:
        exam_key = (F.norm(student['title']), student['date'], F.norm(student['color']))
        if exam_key in maps_with_languages and not student.get('language'):
            raise ValueError(
                f'DADOS DOS ALUNOS · linha {student["line"]}: informe Inglês ou Espanhol para selecionar o gabarito das questões 01 a 05.'
            )
    return parsed
'''


def prepare():
    model_path = ROOT / 'model_data.py'
    text = model_path.read_text(encoding='utf-8')
    if PY_MARKER not in text:
        model_path.write_text(text.rstrip() + PY_EXTENSION + '\n', encoding='utf-8')

    unified_path = ROOT / 'unified.py'
    unified = unified_path.read_text(encoding='utf-8')
    unified = unified.replace(
        'Vazios não são erros; totais importados são exibidos separadamente.',
        'No modelo DADOS, resposta vazia é erro quando existe gabarito válido; questões anuladas ou sem gabarito ficam fora do cálculo. Totais importados são exibidos separadamente.',
    )
    unified_path.write_text(unified, encoding='utf-8')

    app_path = ROOT / 'webapp.py'
    app = app_path.read_text(encoding='utf-8')
    app, count = re.subn(r"ready=True,version='2\.7'", "ready=True,version='2.8'", app, count=1)
    if count != 1 and "ready=True,version='2.8'" not in app:
        raise RuntimeError('Identificação da versão 2.7 não encontrada.')
    app_path.write_text(app, encoding='utf-8')

    html_path = ROOT / 'static' / 'app.html'
    html = html_path.read_text(encoding='utf-8')
    script = '<script src="/static/two_tab.js?v=2.8" defer></script>'
    if script not in html:
        match = re.search(r'<script src="/static/model_data\.js\?v=[^"]+" defer></script>', html)
        if not match:
            raise RuntimeError('Script model_data.js não encontrado.')
        html = html[:match.end()] + script + html[match.end():]
    html = re.sub(r'v2\.7', 'v2.8', html)
    html_path.write_text(html, encoding='utf-8')

    # Keep legacy startup checks aligned without disabling any functional test.
    for verifier in ROOT.glob('verify_*.py'):
        source = verifier.read_text(encoding='utf-8')
        source = source.replace("get('version')=='2.7'", "get('version')=='2.8'")
        source = source.replace("'v2.7'in source", "'v2.8'in source")
        verifier.write_text(source, encoding='utf-8')

    print('MEUCRONOGRAMA_V28_PREPARED: two tabs, 45 LC responses, 50 LC map records per color and language-specific scoring prepared.')


if __name__ == '__main__':
    prepare()
