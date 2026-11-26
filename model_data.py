"""Importação direta do modelo simples com respostas A–E e mapa do simulado.

O arquivo possui duas abas:
- DADOS DOS ALUNOS: uma linha por participante e uma coluna por questão;
- DADOS DO SIMULADO: mapa por questão/cor/língua com gabarito e classificação.

As alternativas são comparadas ao gabarito no servidor. Internamente, o sistema
armazena 1 para acerto, 0 para erro e vazio para resultado não informado.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import io
import json
import import_fixes as _IF
import re
import time
from collections import defaultdict

import exams as E
import performance as F
import planner as P
import selective as S
import templates_v23 as T
import unified as U

STUDENTS_SHEET = 'DADOS DOS ALUNOS'
EXAM_SHEET = 'DADOS DO SIMULADO'
MIME = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'

STUDENT_ALIASES = {
    'nome do aluno': 'name', 'nome': 'name', 'aluno': 'name',
    'login': 'login', 'usuario': 'login',
    'turma': 'class',
    'nome do simulado': 'title', 'nome do simualdo': 'title', 'simulado': 'title',
    'tipo de prova': 'title',
    'data de aplicacao': 'date', 'data': 'date',
    'cor da prova': 'color', 'cor': 'color',
    'l estrangeira': 'language', 'l. estrangeira': 'language',
    'lingua estrangeira': 'language', 'idioma': 'language',
}
EXAM_ALIASES = {
    'nome do simulado': 'title', 'nome do simualdo': 'title', 'simulado': 'title',
    'tipo de prova': 'title',
    'data de aplicacao': 'date', 'data': 'date',
    'cor da prova': 'color', 'cor': 'color',
    'questao': 'number', 'numero da questao': 'number', 'numero': 'number',
    'area': 'area', 'disciplina': 'discipline', 'topico': 'topic',
    'assunto': 'subject', 'habilidade': 'skill', 'gabarito': 'answer',
    'lingua estrangeira': 'language', 'l estrangeira': 'language',
    'l. estrangeira': 'language', 'idioma': 'language',
    '% acertos': 'reported_percent', 'percentual de acertos': 'reported_percent',
}

_COLOR_ALIASES = {
    'azul': 'AZUL', 'verde': 'VERDE', 'amarelo': 'AMARELO', 'amarela': 'AMARELO',
    'branco': 'BRANCO', 'branca': 'BRANCO', 'rosa': 'ROSA', 'cinza': 'CINZA',
    'unica': 'ÚNICA', 'sem cor': 'ÚNICA',
}


def _color(value):
    text = F.text(value, 80)
    if not text:
        return ''
    return _COLOR_ALIASES.get(F.norm(text), text.upper())


def _answer(value, label):
    if value is None or str(value).strip() == '':
        return None
    if isinstance(value, bool):
        raise ValueError(label + ': use A–E, 1, 0 ou vazio.')
    text = str(value).strip().upper()
    # === STRICT A-E IMPORT V3.7.9 ===
    # Only one isolated alternative is valid. Everything else is error = 0.
    if text in ('A', 'B', 'C', 'D', 'E'):
        return text
    return 0
    # Marcadores usados nas planilhas para ausência/erro também valem zero.
    if text in ('.', 'X/X', '*'):
        return 0
    if text in ('0', '0.0'):
        return 0
    if text in ('1', '1.0'):
        return 1
    if text in ('A', 'B', 'C', 'D', 'E'):
        return text
    raise ValueError(label + ': somente A, B, C, D ou E são alternativas válidas; qualquer outro conteúdo é considerado erro (0).')


def _map_answer(value, label):
    text = F.text(value, 30).upper()
    if not text:
        return ''
    if text not in ('A', 'B', 'C', 'D', 'E', 'ANULADA'):
        raise ValueError(label + ': gabarito deve ser A–E, ANULADA ou vazio.')
    return text


def _question_header(value):
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)) and int(value) == value and 1 <= int(value) <= 180:
        return int(value)
    text = F.norm(value)
    match = re.fullmatch(r'(?:questao|q)?\s*0*([1-9]|[1-9][0-9]|1[0-7][0-9]|180)', text)
    return int(match.group(1)) if match else None


def _header_row(rows, aliases, required, label):
    for index, row in enumerate(rows):
        keys = {aliases.get(F.norm(S.fix_header(value)), '') for value in row if str(value or '').strip()}
        if all(key in keys for key in required):
            return index
    raise ValueError(label + ' não foi encontrado.')


def _matrix(data, sheet=''):
    return S.matrix({**data, 'sheet': sheet})


def _student_key(name, klass, login):
    return hashlib.sha256(json.dumps([F.norm(name), F.norm(klass), login], ensure_ascii=False).encode()).hexdigest()[:24]


def _infer_language(discipline, explicit=''):
    lang = E.language(explicit)
    if lang:
        return lang
    n = F.norm(discipline)
    if n in ('ingles', 'lingua inglesa'):
        return 'Inglês'
    if n in ('espanhol', 'lingua espanhola'):
        return 'Espanhol'
    return ''


def _skill(value, label):
    text = F.text(value, 40).upper().replace(' ', '')
    if not text:
        return ''
    match = re.fullmatch(r'(?:C\d+)?H0*([1-9]|[12][0-9]|30)', text)
    if not match:
        raise ValueError(label + ': habilidade deve ser H01 a H30.')
    return 'H' + str(int(match.group(1))).zfill(2)


def _parse(data, require_date=False):
    if not str(data.get('filename', '')).lower().endswith('.xlsx'):
        raise ValueError('Use um arquivo Excel .xlsx com as abas DADOS DOS ALUNOS e DADOS DO SIMULADO.')
    _, _, sheets, _, blob = _matrix(data)
    if STUDENTS_SHEET not in sheets or EXAM_SHEET not in sheets:
        raise ValueError('O arquivo precisa conter as abas DADOS DOS ALUNOS e DADOS DO SIMULADO.')

    student_rows, student_epoch, _, _, _ = _matrix(data, STUDENTS_SHEET)
    exam_rows, exam_epoch, _, _, _ = _matrix(data, EXAM_SHEET)
    sh = _header_row(student_rows, STUDENT_ALIASES, ('name', 'title', 'color'), 'Cabeçalho de DADOS DOS ALUNOS')
    eh = _header_row(exam_rows, EXAM_ALIASES, ('title', 'color', 'number', 'discipline', 'answer'), 'Cabeçalho de DADOS DO SIMULADO')

    student_columns = {}
    question_columns = {}
    for index, value in enumerate(student_rows[sh]):
        q = _question_header(value)
        if q:
            if q in question_columns.values():
                raise ValueError('DADOS DOS ALUNOS possui questão repetida no cabeçalho: ' + str(q))
            question_columns[index] = q
            continue
        key = STUDENT_ALIASES.get(F.norm(S.fix_header(value)), '')
        if key:
            if key in student_columns:
                raise ValueError('DADOS DOS ALUNOS possui coluna repetida: ' + key)
            student_columns[key] = index
    if not question_columns:
        raise ValueError('DADOS DOS ALUNOS precisa ter ao menos uma coluna de questão entre 1 e 180.')

    exam_columns = {}
    for index, value in enumerate(exam_rows[eh]):
        key = EXAM_ALIASES.get(F.norm(S.fix_header(value)), '')
        if key:
            if key in exam_columns:
                raise ValueError('DADOS DO SIMULADO possui coluna repetida: ' + key)
            exam_columns[key] = index

    fallback_date = F.text(data.get('date'), 40)
    if fallback_date:
        fallback_date = F.date_value(fallback_date)
    map_by_exam = defaultdict(list)
    map_keys = set()
    map_dates = set()
    map_titles = set()
    map_colors = set()
    map_warnings = []
    reported_percent_present = False

    # === CORREÇÃO NA INTERFACE V3.17.0 ===
    # Em vez de parar no primeiro erro, cada linha com problema vira uma divergência com
    # aba, linha, coluna e (quando cabe) as opções válidas; a interface corrige e reenvia.
    issues = []
    title_cells = []
    date_cells = []

    def take(field, fn, *args):
        try:
            return fn(*args)
        except _IF.CellIssue:
            raise
        except ValueError as exc:
            raise _IF.CellIssue(str(exc), field)

    def report(sheet, header_row, columns, line, row, exc):
        field = exc.field
        col = field if type(field) is int else columns.get(field)
        if col is None:
            issues.append(_IF.issue(sheet, line, None, field or '', '', str(exc) + ' (a coluna não existe no arquivo; ajuste o arquivo ou ignore a linha)'))
            return
        value = row[col] if col < len(row) else None
        header = header_row[col] if col < len(header_row) else ''
        issues.append(_IF.issue(sheet, line, col, header, value, str(exc), exc.options, suggest=exc.suggest))

    for line, row in enumerate(exam_rows[eh + 1:], eh + 2):
        if not any(v not in (None, '') for v in row):
            continue
        at = lambda key: row[exam_columns[key]] if key in exam_columns and exam_columns[key] < len(row) else None
        where = f'DADOS DO SIMULADO · linha {line}'
        try:
            title = take('title', F.text, at('title'), 200)
            color = take('color', _color, at('color'))
            number = take('number', F.count_value, at('number'), f'{where} · questão')
            if not title:
                raise _IF.CellIssue(f'{where}: informe o nome do simulado.', 'title')
            if not color:
                raise _IF.CellIssue(f'{where}: informe a cor da prova.', 'color')
            if number is None:
                raise _IF.CellIssue(f'{where}: informe o número da questão.', 'number')
            if not 1 <= number <= 180:
                raise _IF.CellIssue(f'{where}: questão deve estar entre 1 e 180.', 'number')
            date = take('date', F.date_value, at('date'), exam_epoch) if at('date') not in (None, '') else fallback_date
            discipline = take('discipline', F.text, at('discipline'), 150)
            if not discipline:
                raise _IF.CellIssue(f'{where}: informe a disciplina da questão {number:02d}.', 'discipline')
            area = E.area(at('area')) or E.DISC_AREAS.get(F.norm(discipline), '')
            if area not in S.AREAS:
                raise _IF.CellIssue(f'{where}: informe LC, CH, CN ou MT na área.', 'area', ['LC', 'CH', 'CN', 'MT'])
            language = take('language', _infer_language, discipline, at('language'))
            if language not in ('', 'Inglês', 'Espanhol'):
                raise _IF.CellIssue(f'{where}: língua estrangeira inválida.', 'language', ['', 'Inglês', 'Espanhol'])
            answer = take('answer', _map_answer, at('answer'), where)
            key = (F.norm(title), date or '', F.norm(color), number, language)
            if key in map_keys:
                raise _IF.CellIssue(f'{where}: questão {number:02d}, cor e língua repetidas.', 'number')
            topic = take('topic', F.text, at('topic'), 250)
            subject = take('subject', F.text, at('subject'), 250)
            skill = take('skill', _skill, at('skill'), where)
        except _IF.CellIssue as exc:
            report(EXAM_SHEET, exam_rows[eh], exam_columns, line, row, exc)
            continue
        map_keys.add(key)
        item = dict(number=number, area=area, discipline=discipline, topic=topic, subject=subject,
                    skill=skill, language=language, answer=answer)
        map_by_exam[(F.norm(title), date or '', F.norm(color))].append((title, date, color, item))
        map_titles.add(F.norm(title)); map_colors.add(F.norm(color))
        title_cells.append((EXAM_SHEET, exam_rows[eh], exam_columns, line, row, title))
        if date:
            map_dates.add(date)
            if at('date') not in (None, ''):
                date_cells.append((EXAM_SHEET, exam_rows[eh], exam_columns, line, row, date))
        if at('reported_percent') not in (None, ''):
            reported_percent_present = True

    map_color_names = {}
    for rows in map_by_exam.values():
        map_color_names.setdefault(F.norm(rows[0][2]), rows[0][2])

    students = []
    titles = set(); dates = set(); colors = set(); seen_students = set()
    for line, row in enumerate(student_rows[sh + 1:], sh + 2):
        if not any(v not in (None, '') for v in row):
            continue
        at = lambda key: row[student_columns[key]] if key in student_columns and student_columns[key] < len(row) else None
        where = f'DADOS DOS ALUNOS · linha {line}'
        try:
            name = take('name', F.text, at('name'), 150)
            title = take('title', F.text, at('title'), 200)
            color = take('color', _color, at('color'))
            if not name:
                raise _IF.CellIssue(f'{where}: informe o nome do aluno.', 'name')
            if not title:
                raise _IF.CellIssue(f'{where}: informe o nome do simulado.', 'title')
            if not color:
                raise _IF.CellIssue(f'{where}: informe a cor da prova.', 'color', sorted(map_color_names.values()))
            if map_color_names and F.norm(color) not in map_color_names:
                raise _IF.CellIssue(f'{where}: não existe gabarito da cor {color} em DADOS DO SIMULADO.', 'color',
                                    sorted(map_color_names.values()))
            login = take('login', F.text, at('login'), 40).lower()
            klass = take('class', F.text, at('class'), 150)
            language = E.language(at('language'))
            if language not in ('', 'Inglês', 'Espanhol'):
                raise _IF.CellIssue(f'{where}: língua deve ser Inglês, Espanhol ou vazia.', 'language', ['', 'Inglês', 'Espanhol'])
            date = take('date', F.date_value, at('date'), student_epoch) if at('date') not in (None, '') else fallback_date
            if require_date and not date:
                raise _IF.CellIssue(f'{where}: informe a data de aplicação.', 'date')
            key = _student_key(name, klass, login)
            if key in seen_students:
                raise _IF.CellIssue(f'{where}: participante repetido. Use LOGIN para distinguir homônimos, ou ignore a linha repetida.', 'name')
            responses = {}
            for index, number in question_columns.items():
                value = row[index] if index < len(row) else None
                responses[number] = take(index, _answer, value, f'{where} · questão {number:02d}')
        except _IF.CellIssue as exc:
            report(STUDENTS_SHEET, student_rows[sh], student_columns, line, row, exc)
            continue
        seen_students.add(key)
        students.append(dict(key=key, name=name, login=login, group=klass, title=title,
                             date=date, color=color, language=language, responses=responses, line=line))
        titles.add(F.norm(title)); colors.add(F.norm(color))
        title_cells.append((STUDENTS_SHEET, student_rows[sh], student_columns, line, row, title))
        if date:
            dates.add(date)
            if at('date') not in (None, ''):
                date_cells.append((STUDENTS_SHEET, student_rows[sh], student_columns, line, row, date))

    # Nome e data do simulado: aponta só as linhas que divergem do restante do arquivo.
    def odd_ones(cells, field, label, shown):
        counts = defaultdict(int)
        first = {}
        for cell in cells:
            counts[F.norm(cell[5])] += 1
            first.setdefault(F.norm(cell[5]), cell[5])
        if len(counts) <= 1:
            return
        main = max(counts, key=lambda k: counts[k])
        for sheet, header_row, columns, line, row, value in cells:
            if F.norm(value) != main:
                report(sheet, header_row, columns, line, row, _IF.CellIssue(
                    f'{sheet} · linha {line}: {label} diferente do restante do arquivo ({shown(first[main])}).',
                    field, [shown(first[main])], suggest=shown(first[main])))

    odd_ones(title_cells, 'title', 'nome do simulado', lambda v: v)
    if require_date:
        odd_ones(date_cells, 'date', 'data de aplicação', lambda v: '/'.join(reversed(str(v).split('-'))))
    if issues:
        raise _IF.ImportIssues(issues)

    if not map_by_exam:
        raise ValueError('DADOS DO SIMULADO não possui questões preenchidas.')
    if len(map_titles) != 1:
        raise ValueError('Use um arquivo por simulado. DADOS DO SIMULADO contém mais de um nome de avaliação.')
    if require_date and not map_dates and not fallback_date:
        raise ValueError('Informe a data de aplicação na planilha ou na conferência do site.')
    if not students:
        raise ValueError('DADOS DOS ALUNOS não possui participantes.')
    if len(titles) != 1:
        raise ValueError('Use um arquivo por simulado. DADOS DOS ALUNOS contém mais de um nome de avaliação.')
    if titles != map_titles:
        raise ValueError('O nome do simulado diverge entre as duas abas.')
    if require_date and len(dates | map_dates) != 1:
        raise ValueError('O arquivo deve representar uma única data de aplicação.')
    date = next(iter(dates or map_dates), fallback_date)

    # Reindex maps using the final date supplied during inspection/preview.
    exams = {}
    for rows in map_by_exam.values():
        title, row_date, color, _ = rows[0]
        final_date = row_date or date
        items = [entry[3] for entry in rows]
        exams[(F.norm(title), final_date, F.norm(color))] = dict(title=title, date=final_date, color=color, items=items)
    for student in students:
        student['date'] = student['date'] or date

    warnings = []
    if reported_percent_present:
        warnings.append('A coluna % ACERTOS do arquivo é informativa e será recalculada a partir das respostas importadas.')
    for exam in exams.values():
        answered = {item['number'] for item in exam['items'] if item['answer']}
        supplied = set(question_columns.values())
        missing = sorted(supplied - answered)
        if missing:
            warnings.append(f'{exam["color"]}: {len(missing)} questão(ões) sem gabarito; respostas dessas questões ficarão como não calculadas.')
    return dict(blob=blob, hash=hashlib.sha256(blob + _IF.digest(data.get('fixes')).encode()).hexdigest(), sheets=sheets,
                students=students, exams=exams, title=students[0]['title'], date=date,
                colors=sorted({x['color'] for x in students}), questions=sorted(question_columns.values()),
                mapRows=sum(len(x['items']) for x in exams.values()), warnings=warnings,
                columns=dict(students=student_columns, studentHeader=list(student_rows[sh]), studentHeaderLine=sh + 1))


def inspect(data):
    parsed = _parse(data, require_date=False)
    return dict(sheets=parsed['sheets'], rows=len(parsed['students']), mapRows=parsed['mapRows'],
                title=parsed['title'], date=parsed['date'] or '', colors=parsed['colors'],
                firstQuestion=min(parsed['questions']), lastQuestion=max(parsed['questions']),
                warnings=parsed['warnings'], format='modelo-dados')


def _identity(title, date, color):
    return hashlib.sha256(E.enc([F.norm(title), date, F.norm(color)]).encode()).hexdigest()


def _exam_prepare(app, c, user, spec, replace_map):
    identity = _identity(spec['title'], spec['date'], spec['color'])
    found = _exam_metadata.find_import_map(app, c, spec['title'], spec['date'], spec['color'])
    old = E.get_exam(app, c, found['id']) if found else None
    supplied = sorted(spec['items'], key=lambda x: (x['number'], x['language']))
    if old and not _exam_metadata.can_edit(user):
        existing = {(x['number'], x['language']): x for x in old['items']}
        for item in supplied:
            current = existing.get((item['number'], item['language']))
            if current is None or any(v not in ('', None) and current.get(k) != v for k, v in item.items()):
                raise ValueError('A edição dos mapas é exclusiva do Master e da coordenação.')
        return old, old, False, dict(new=0, updated=0, conflicts=0, total=len(old['items']))
    bykey = {(x['number'], x['language']): dict(x) for x in (old['items'] if old else [])}
    added = updated = conflicts = 0
    for item in supplied:
        key = (item['number'], item['language'])
        if key not in bykey:
            bykey[key] = dict(item); added += 1; continue
        current = bykey[key]; before = dict(current)
        for field, value in item.items():
            if value in ('', None):
                continue
            if current.get(field) not in ('', None) and current[field] != value:
                conflicts += 1
                if not replace_map:
                    continue
            current[field] = value
        updated += current != before
    items = sorted(bykey.values(), key=lambda x: (x['number'], x['language']))
    result = dict(id=old['id'] if old else _exam_metadata.available_import_id(app, c, 'md_' + identity[:32]), identity_key=identity,
                  owner_id=old['owner_id'] if old else user['id'], title=spec['title'],
                  applied_on=spec['date'], color=spec['color'], area=old['area'] if old else '', items=items,
                  version=(old['version'] if old else 0) + (1 if (not old or items != old['items']) else 0))
    changed = not old or items != old['items']
    return result, old, changed, dict(new=added, updated=updated, conflicts=conflicts, total=len(items))


def _answer_result(answer, item):
    # Só é possível avaliar quando a questão existe no mapa e possui gabarito.
    # Questões anuladas são identificadas, mas não geram acerto nem erro e ficam
    # fora do denominador do aproveitamento.
    if not item:
        return None
    gabarito = item.get('answer', '')
    if not gabarito or gabarito == 'ANULADA':
        return None
    # Arquivos antigos com 1/0 continuam aceitos.
    if answer in (0, 1):
        return answer
    # Em questão válida e com gabarito, resposta em branco é erro.
    if answer is None:
        return 0
    return int(answer == gabarito)



# === MEU CRONOGRAMA: REGRAS FINAIS DE IMPORTAÇÃO DE ALUNOS ===
def _student_account_value(account, key):
    try:
        return account[key]
    except (KeyError, IndexError, TypeError):
        return ''


def _is_importable_student_account(account):
    name = F.norm(_student_account_value(account, 'name'))
    technical_name = F.norm('Verificação técnica temporária')
    return (
        _student_account_value(account, 'role') in ('user', 'aluno')
        and not name.startswith(technical_name)
    )


def _resolve_student_account(accounts, student):
    """Resolve by full name; login only disambiguates exact-name homonyms."""
    normalized_name = F.norm(student.get('name', ''))
    same_name = [
        account for account in accounts
        if F.norm(_student_account_value(account, 'name')) == normalized_name
    ]
    if len(same_name) == 1:
        return _student_account_value(same_name[0], 'id')
    if len(same_name) > 1 and student.get('login'):
        login = F.text(student.get('login'), 100).lower()
        same_login = [
            account for account in same_name
            if F.text(_student_account_value(account, 'username'), 100).lower() == login
        ]
        if len(same_login) == 1:
            return _student_account_value(same_login[0], 'id')
    return ''


def prepare(app, c, user, data):
    parsed = _parse(data, require_date=True)
    if type(data.get('replace', False)) is not bool or type(data.get('replaceMap', False)) is not bool:
        raise ValueError('Opções de substituição inválidas.')
    allowed_student_accounts = [
        account for account in F.allowed_accounts(app, c, user)
        if _student_account_value(account, 'role') in ('user', 'aluno')
    ]
    accounts = [
        account for account in allowed_student_accounts
        if _is_importable_student_account(account)
    ]
    byid = {_student_account_value(a, 'id'): a for a in allowed_student_accounts}
    mapping = data.get('mapping', {})
    if not isinstance(mapping, dict):
        raise ValueError('Vínculos inválidos.')
    known = {s['key'] for s in parsed['students']}
    if any(k not in known for k in mapping):
        raise ValueError('Há vínculos que não pertencem a este arquivo.')
    resolved = {}; unresolved = 0
    for student in parsed['students']:
        selected = mapping.get(student['key'])
        if selected is None:
            selected = _resolve_student_account(accounts, student)
        if selected and selected not in byid:
            raise ValueError('Vínculo não autorizado ou conta desativada.')
        resolved[student['key']] = selected; student['selected'] = selected
        if not selected: unresolved += 1

    exams = {}; exam_snapshots = []; map_summary = dict(new=0, updated=0, conflicts=0, total=0)
    for key, spec in parsed['exams'].items():
        result, old, changed, summary = _exam_prepare(app, c, user, spec, bool(data.get('replaceMap', False)))
        exams[key] = dict(result=result, old=old, changed=changed)
        exam_snapshots.append((result['id'], old['version'] if old else 0, changed))
        for name in map_summary: map_summary[name] += summary[name]

    targets = sorted({x for x in resolved.values() if x})
    existing = {}
    if targets:
        for offset in range(0, len(targets), 800):
            group = targets[offset:offset + 800]
            placeholders = ','.join('?' for _ in group)
            rows = app.db.execute(c, 'SELECT * FROM hmay_performance WHERE user_id IN (' + placeholders + ') AND applied_on=?', (*group, parsed['date'])).fetchall()
            for row in rows:
                existing[(row['user_id'], row['activity_key'], row['applied_on'])] = row

    prepared = []; conflicts = 0; seen = set(); warnings = list(parsed['warnings'])
    for student in parsed['students']:
        target = resolved[student['key']]
        if not target:
            continue
        activity_key = F.norm(student['title'])
        key = (target, activity_key, student['date'])
        if key in seen:
            raise ValueError('Dois participantes foram vinculados à mesma conta, avaliação e data.')
        seen.add(key)
        exam_key = (F.norm(student['title']), student['date'], F.norm(student['color']))
        exam_pack = exams.get(exam_key)
        if not exam_pack:
            raise ValueError(f'Não existe mapa para a cor {student["color"]}.')
        exam = exam_pack['result']
        item_by_number = defaultdict(list)
        for item in exam['items']:
            item_by_number[item['number']].append(item)
        metrics = {}; missing_language = 0; missing_map = 0
        for number, answer in student['responses'].items():
            candidates = item_by_number.get(number, [])
            item = None
            language_items = [x for x in candidates if x['language']]
            if language_items:
                if student['language']:
                    item = next((x for x in language_items if x['language'] == student['language']), None)
                else:
                    missing_language += int(answer is not None)
            else:
                item = next((x for x in candidates if not x['language']), None)
            result = _answer_result(answer, item) if item else None
            if answer is not None and not item:
                missing_map += 1
            metrics[f'questao:{number:03d}'] = dict(name=f'Questão {number:02d}', correct=result, total=1 if result is not None else None, response=(str(answer).strip().upper() if answer is not None and str(answer).strip().upper() in ('A', 'B', 'C', 'D', 'E') else ''))  # === SCHOOL REPORTS V3.10.0 ===
        metadata = {'COR DA PROVA': student['color'], 'L.E': student['language'], 'TURMA': student['group'],
                    '_exam_id': exam['id'], '_exam_version': exam['version'],
                    'Respostas convertidas automaticamente': 'A–E comparadas ao gabarito'}
        if missing_language:
            metadata['Questões sem língua definida'] = missing_language
        if missing_map:
            metadata['Respostas sem questão/gabarito aplicável'] = missing_map
        row = existing.get(key)
        old_metrics = json.loads(row['metrics']) if row else {}
        merged, n = F.merged_metrics(old_metrics, metrics, bool(data.get('replace', False))); conflicts += n
        old_metadata = json.loads(row['metadata']) if row else {}
        S.guard_merge(old_metadata, metadata)
        merged_metadata = dict(old_metadata)
        for field, value in metadata.items():
            if value in (None, ''):
                continue
            if field in merged_metadata and merged_metadata[field] != value:
                conflicts += 1
                if not data.get('replace', False):
                    continue
            merged_metadata[field] = value
        changed = not row or merged != old_metrics or merged_metadata != old_metadata
        record = dict(student=student['key'], name=student['name'], activity=student['title'],
                      activityKey=activity_key, date=student['date'], line=student['line'])
        prepared.append(dict(target=target, record=record, metrics=merged,
                             metadata=merged_metadata, existing=dict(row) if row else None,
                             changed=changed, exam=exam))

    summary = dict(rows=len(parsed['students']), linked=len(prepared), skipped=len(parsed['students']) - len(prepared),
                   new=sum(x['existing'] is None for x in prepared),
                   updated=sum(x['existing'] is not None and x['changed'] for x in prepared),
                   unchanged=sum(not x['changed'] for x in prepared), conflicts=conflicts,
                   unresolved=unresolved, map=map_summary, title=parsed['title'], date=parsed['date'],
                   colors=parsed['colors'], warnings=warnings)
    signed = json.dumps([user['id'], parsed['hash'], resolved, bool(data.get('replace', False)),
                         bool(data.get('replaceMap', False)), exam_snapshots,
                         [(x['target'], x['record']['activityKey'], x['record']['date'], x['existing']['version'] if x['existing'] else 0) for x in prepared]],
                        ensure_ascii=False, sort_keys=True, separators=(',', ':'))
    return dict(parsed=parsed, accounts=accounts, mapping=resolved, prepared=prepared,
                exams=exams, summary=summary, signed=signed)


def confirm(app, c, user, package, HTTPError):
    at = P.now().isoformat()
    for pack in package['exams'].values():
        exam, old = pack['result'], pack['old']
        import disciplines_catalog as _DC;_DC.canon_items(app,c,exam['items'])  # === DISCIPLINES CATALOG V3.12.0 ===
        if not pack['changed']:
            continue
        if old:
            cur = app.db.execute(c, 'UPDATE hmay_exams SET items=?,area=?,version=version+1,updated_at=? WHERE id=? AND version=?',
                                 (E.enc(exam['items']), exam['area'], at, exam['id'], old['version']))
        else:
            _exam_metadata.release_obsolete_key(app, c, exam['identity_key'])
            cur = app.db.execute(c, 'INSERT INTO hmay_exams(id,identity_key,owner_id,title,applied_on,color,area,items,version,updated_at) VALUES (?,?,?,?,?,?,?,?,?,?) ON CONFLICT(identity_key) DO NOTHING',
                                 (exam['id'], exam['identity_key'], exam['owner_id'], exam['title'], exam['applied_on'], exam['color'], exam['area'], E.enc(exam['items']), 1, at))
        if cur.rowcount != 1:
            raise HTTPError(409, 'Um mapa do simulado mudou durante a importação. Nada deste lote foi salvo; refaça a conferência.')
    for item in sorted(package['prepared'], key=lambda x: (x['target'], x['record']['activityKey'], x['record']['date'])):
        if not item['changed']:
            continue
        record, old = item['record'], item['existing']
        encoded_metrics = json.dumps(item['metrics'], ensure_ascii=False, separators=(',', ':'), allow_nan=False)
        encoded_metadata = json.dumps(item['metadata'], ensure_ascii=False, separators=(',', ':'), allow_nan=False)
        if old:
            cur = app.db.execute(c, 'UPDATE hmay_performance SET metrics=?,metadata=?,version=version+1,updated_at=? WHERE id=? AND version=?',
                                 (encoded_metrics, encoded_metadata, at, old['id'], old['version']))
        else:
            cur = app.db.execute(c, 'INSERT INTO hmay_performance(id,user_id,activity_key,activity,applied_on,metrics,metadata,version,updated_at) VALUES (?,?,?,?,?,?,?,?,?) ON CONFLICT(user_id,activity_key,applied_on) DO NOTHING',
                                 (P.uid(), item['target'], record['activityKey'], record['activity'], record['date'], encoded_metrics, encoded_metadata, 1, at))
        if cur.rowcount != 1:
            raise HTTPError(409, 'Os resultados mudaram durante a importação. Nada deste lote foi salvo; refaça a conferência.')
    for pack in package['exams'].values():
        if pack['changed']:
            app.event(c, user, user['id'], 'model_data_exam_import')
    for target in {x['target'] for x in package['prepared'] if x['changed']}:
        app.event(c, user, target, 'model_data_results_import')


def template(data):
    count = F.count_value(data.get('questions', 180), 'Quantidade de questões')
    if count is None or not 1 <= count <= 180:
        raise ValueError('Informe de 1 a 180 questões.')
    include_login = bool(data.get('login', True))
    include_date = bool(data.get('dateField', True))
    student_headers = ['Nome do aluno'] + (['LOGIN'] if include_login else []) + ['Turma', 'nome do simulado']
    if include_date:
        student_headers.append('data de aplicação')
    student_headers += ['Cor da prova', 'L. Estrangeira'] + list(range(1, count + 1))
    exam_headers = ['nome do simulado'] + (['data de aplicação'] if include_date else []) + ['Cor da prova', 'QUESTÃO', 'ÁREA', 'DISCIPLINA', 'TÓPICO', 'ASSUNTO', 'HABILIDADE', 'LÍNGUA ESTRANGEIRA', 'GABARITO']
    guide = [
        ['Respostas dos alunos', 'Preencha A, B, C, D ou E. O sistema compara com o gabarito e converte internamente para 1/0.'],
        ['Resposta em branco', 'Quando a questão possui gabarito válido, célula vazia é considerada erro (0).'],
        ['Questão anulada', 'Não gera acerto automático nem erro; fica fora do denominador do aproveitamento.'],
        ['Língua estrangeira', 'Informe Inglês ou Espanhol. Nas questões com duas versões, cadastre uma linha por língua em DADOS DO SIMULADO.'],
        ['Cores', 'AMARELO/AMARELA e BRANCO/BRANCA são normalizados automaticamente.'],
        ['Detalhamento', 'Após importar, o sistema calcula acertos e percentuais por área, disciplina, tópico, assunto, habilidade e questão.'],
    ]
    return T.export(student_headers, kind='xlsx', first_name=STUDENTS_SHEET,
                    extra_sheets=[(EXAM_SHEET, exam_headers, [])], guide=guide)


def _detail_xlsx(record, exam, analysis):
    meta = record['metadata']
    summary_headers = ['Campo', 'Valor']
    summary_rows = [
        ['Aluno', record.get('name', '')], ['Avaliação', record['activity']],
        ['Data', record['applied_on']], ['Cor', meta.get('COR DA PROVA', '')],
        ['Língua estrangeira', meta.get('L.E', '')],
        ['Acertos conhecidos', analysis['overall']['correct']],
        ['Erros conhecidos', analysis['overall']['errors']],
        ['Questões informadas', analysis['overall']['marked']],
        ['Questões aplicáveis no mapa', analysis['overall']['total']],
        ['Aproveitamento', '' if analysis['overall']['accuracy'] is None else analysis['overall']['accuracy'] / 100],
        ['Cobertura', '' if analysis['overall']['coverage'] is None else analysis['overall']['coverage'] / 100],
    ]
    extras = []
    for kind in ('Área', 'Disciplina', 'Tópico', 'Assunto', 'Habilidade'):
        rows = []
        for item in analysis['groups'].get(kind, []):
            rows.append([item['name'], item['correct'], item['errors'], item['marked'], item['total'],
                         '' if item['accuracy'] is None else item['accuracy'] / 100,
                         '' if item['coverage'] is None else item['coverage'] / 100,
                         ', '.join(str(x) for x in item.get('correctQuestions', [])),
                         ', '.join(str(x) for x in item.get('errorQuestions', [])),
                         ', '.join(str(x) for x in item.get('pendingQuestions', []))])
        extras.append((kind, [kind, 'Acertos', 'Erros', 'Informadas', 'No mapa', 'Aproveitamento', 'Cobertura', 'Questões acertadas', 'Questões erradas', 'Sem resultado'], rows))
    qrows = [[x['number'], x['area'], x['discipline'], x['topic'], x['subject'], x['skill'], x['language'], x['answer'], x['status']] for x in analysis['questions']]
    extras.append(('Questões', ['Questão', 'Área', 'Disciplina', 'Tópico', 'Assunto', 'Habilidade', 'Língua', 'Gabarito', 'Resultado'], qrows))
    return T.export(summary_headers, summary_rows, first_name='Resumo', extra_sheets=extras)


def handle(app, c, user, path, method, data, query, start, HTTPError):
    if path == '/api/model-data/detail' and method == 'GET':
        target = query.get('user', [user['id']])[0]; app.require_target(user, target, c)
        record_id = query.get('record', [''])[0]
        row = app.db.execute(c, 'SELECT p.*,u.name FROM hmay_performance p JOIN hmay_users u ON u.id=p.user_id WHERE p.id=? AND p.user_id=?', (record_id, target)).fetchone()
        if not row:
            raise HTTPError(404, 'Resultado não encontrado.')
        metadata = json.loads(row['metadata']); exam_id = metadata.get('_exam_id')
        if not exam_id:
            raise ValueError('Este resultado ainda não possui mapa de questões vinculado.')
        exam = E.get_exam(app, c, exam_id)
        record = {**dict(row), 'metadata': metadata, 'metrics': json.loads(row['metrics'])}
        analysis = U.analyse(exam, record['metrics'], metadata)
        blob, mime = _detail_xlsx(record, exam, analysis)
        filename = re.sub(r'[^A-Za-z0-9_-]+', '_', record['activity']).strip('_') or 'resultado'
        return app.reply(start, 200, blob, mime, [('Content-Disposition', f'attachment; filename="Detalhamento_{filename}.xlsx"')])

    if user['role'] not in ('master', 'coordenador'):
        raise HTTPError(403, 'Importação e geração de modelos são exclusivas do Master e da coordenação.')
    if path == '/api/model-data/template' and method == 'POST':
        blob, mime = template(data)
        return app.reply(start, 200, blob, mime, [('Content-Disposition', 'attachment; filename="MODELO_DADOS.xlsx"')])
    if path == '/api/model-data/inspect' and method == 'POST':
        return app.reply(start, 200, inspect(data))
    if path not in ('/api/model-data/preview', '/api/model-data/confirm') or method != 'POST':
        raise HTTPError(404, 'Página não encontrada.')
    package = prepare(app, c, user, data)
    if path.endswith('/preview'):
        stamp = int(time.time())
        sample = [dict(name=x['record']['name'], analysis=U.analyse(x['exam'], x['metrics'], x['metadata'])) for x in package['prepared'][:3]]
        token = str(stamp) + '.' + F.sign(app, package['signed'], stamp)
        return app.reply(start, 200, dict(summary=package['summary'], students=package['parsed']['students'],
                                          accounts=package['accounts'], mapping=package['mapping'], sample=sample,
                                          token=token, format='modelo-dados'))
    try:
        raw, signature = data.get('token', '').split('.'); stamp = int(raw)
    except (ValueError, AttributeError):
        raise ValueError('Confira o arquivo novamente antes de confirmar.')
    if not 0 <= time.time() - stamp <= 1800 or not hmac.compare_digest(signature, F.sign(app, package['signed'], stamp)):
        raise HTTPError(409, 'Arquivo, vínculos ou mapas mudaram. Refaça a conferência.')
    if not package['prepared']:
        raise ValueError('Vincule ao menos um aluno a uma conta existente.')
    if package['summary']['unresolved'] and data.get('skipUnmapped') is not True:
        raise ValueError('Confirme que os alunos sem vínculo serão ignorados.')
    confirm(app, c, user, package, HTTPError)
    return app.reply(start, 200, dict(ok=True, summary=package['summary']))

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
    issues = []
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
                issues.append(_IF.general(
                    f'DADOS DO SIMULADO · {exam["color"]}: a questão {number:02d} deve possuir uma linha de Inglês e outra de Espanhol.'))
            elif any(not item.get('answer') for item in items if item.get('language')):
                parsed['warnings'].append(
                    f'{exam["color"]}: questão {number:02d} possui versão de língua sem gabarito e não será calculada nessa versão.'
                )
        invalid = sorted({item['number'] for item in exam['items'] if item.get('language') and item['number'] > 5})
        if invalid:
            issues.append(_IF.general(
                f'DADOS DO SIMULADO · {exam["color"]}: língua estrangeira só deve ser informada nas questões 01 a 05 '
                f'(informada na(s) questão(ões) {", ".join(f"{n:02d}" for n in invalid[:10])}). Apague a língua dessas linhas.'))

    columns = parsed.get('columns') or {}
    lang_col = (columns.get('students') or {}).get('language')
    header = columns.get('studentHeader') or []
    for student in parsed['students']:
        exam_key = (F.norm(student['title']), student['date'], F.norm(student['color']))
        if exam_key in maps_with_languages and not student.get('language'):
            message = (f'DADOS DOS ALUNOS · linha {student["line"]}: informe Inglês ou Espanhol para selecionar '
                       'o gabarito das questões 01 a 05.')
            if lang_col is None:
                issues.append(_IF.issue(STUDENTS_SHEET, student['line'], None, 'L. ESTRANGEIRA', '',
                                        message + ' (a coluna não existe no arquivo)'))
            else:
                issues.append(_IF.issue(STUDENTS_SHEET, student['line'], lang_col,
                                        header[lang_col] if lang_col < len(header) else 'L. ESTRANGEIRA', '',
                                        message, ['Inglês', 'Espanhol']))
    if issues:
        raise _IF.ImportIssues(issues)
    return parsed

# === MEU CRONOGRAMA: EXPORTAÇÃO COLETIVA POR SIMULADO ===
_RX_AREA_LABELS = {
    'LC': 'Linguagens',
    'CH': 'Humanas',
    'CN': 'Natureza',
    'MT': 'Matemática',
}
_RX_GROUP_KINDS = ('Área', 'Disciplina', 'Tópico', 'Assunto', 'Habilidade')


def _rx_json(value):
    try:
        loaded = json.loads(value or '{}')
    except (TypeError, ValueError):
        return {}
    return loaded if isinstance(loaded, dict) else {}


def _rx_role_guard(user, HTTPError):
    if user.get('role') not in ('master', 'coordenador'):
        raise HTTPError(403, 'A exportação coletiva é exclusiva do Master e da coordenação.')


def _rx_rows(app, c, activity_key='', applied_on=''):
    sql = (
        'SELECT p.*,u.name AS student_name,u.username AS student_login,'
        'u.role AS student_role FROM hmay_performance p '
        'JOIN hmay_users u ON u.id=p.user_id'
    )
    args = []
    conditions = []
    if activity_key:
        conditions.append('p.activity_key=?'); args.append(activity_key)
    if applied_on:
        conditions.append('p.applied_on=?'); args.append(applied_on)
    if conditions:
        sql += ' WHERE ' + ' AND '.join(conditions)
    sql += ' ORDER BY p.applied_on DESC,p.activity,u.name,u.username'
    rows = []
    for source in app.db.execute(c, sql, tuple(args)).fetchall():
        row = dict(source)
        # A exportação coletiva é de alunos. Perfis especiais nunca aparecem,
        # inclusive quando o solicitante é Master.
        if row.get('student_role') not in ('user', 'aluno'):
            continue
        metadata = _rx_json(row.get('metadata'))
        if not metadata.get('_exam_id'):
            continue
        row['_metadata'] = metadata
        rows.append(row)
    return rows


def result_export_simulations(app, c, user):
    grouped = {}
    for row in _rx_rows(app, c):
        key = (row['activity_key'], row['applied_on'])
        group = grouped.setdefault(key, {
            'activityKey': row['activity_key'],
            'activity': row['activity'],
            'date': row['applied_on'],
            'students': set(),
            'colors': set(),
            'updatedAt': row.get('updated_at', ''),
        })
        group['students'].add(row['user_id'])
        color = F.text(row['_metadata'].get('COR DA PROVA'), 80)
        if color:
            group['colors'].add(color)
        if row.get('updated_at', '') > group['updatedAt']:
            group['updatedAt'] = row['updated_at']
    result = []
    for index, group in enumerate(sorted(
            grouped.values(), key=lambda x: (x['date'], F.norm(x['activity'])), reverse=True)):
        result.append({
            'id': 'sim_' + hashlib.sha256(
                (group['activityKey'] + '\x1f' + group['date']).encode('utf-8')
            ).hexdigest()[:20],
            'activityKey': group['activityKey'],
            'activity': group['activity'],
            'date': group['date'],
            'participants': len(group['students']),
            'colors': sorted(group['colors']),
            'updatedAt': group['updatedAt'],
        })
    return result


def _rx_percent(numerator, denominator):
    return None if not denominator else round(100 * numerator / denominator, 2)


def _rx_add_group(groups, kind, name, number, result):
    label = F.text(name, 250) or 'Não informado'
    bucket = groups[kind].setdefault(label, {
        'name': label, 'correct': 0, 'errors': 0, 'marked': 0, 'total': 0,
        'correctQuestions': [], 'errorQuestions': [], 'pendingQuestions': [],
    })
    bucket['total'] += 1
    if result in (0, 1):
        bucket['marked'] += 1
        if result == 1:
            bucket['correct'] += 1
            bucket['correctQuestions'].append(number)
        else:
            bucket['errors'] += 1
            bucket['errorQuestions'].append(number)
    else:
        bucket['pendingQuestions'].append(number)


def _rx_analyse(exam, metrics, metadata):
    language = F.text(metadata.get('L.E'), 40)
    groups = {kind: {} for kind in _RX_GROUP_KINDS}
    overall = {'correct': 0, 'errors': 0, 'marked': 0, 'total': 0}
    for item in exam.get('items', []):
        item_language = F.text(item.get('language'), 40)
        if item_language and item_language != language:
            continue
        answer = F.text(item.get('answer'), 30).upper()
        if not answer or answer == 'ANULADA':
            continue
        number = int(item.get('number') or 0)
        if not 1 <= number <= 180:
            continue
        metric = metrics.get(f'questao:{number:03d}', {})
        result = metric.get('correct') if isinstance(metric, dict) else None
        if result not in (0, 1):
            result = None
        overall['total'] += 1
        if result in (0, 1):
            overall['marked'] += 1
            if result == 1:
                overall['correct'] += 1
            else:
                overall['errors'] += 1
        area_code = F.text(item.get('area'), 10).upper()
        area_name = _RX_AREA_LABELS.get(area_code, area_code or 'Não informado')
        skill = F.text(item.get('skill'), 40)
        labels = {
            'Área': area_name,
            'Disciplina': item.get('discipline'),
            'Tópico': item.get('topic'),
            'Assunto': item.get('subject'),
            # H01 de áreas diferentes continua sendo uma métrica diferente.
            'Habilidade': f'{area_name} · {skill}' if skill else f'{area_name} · Não informada',
        }
        for kind, label in labels.items():
            _rx_add_group(groups, kind, label, number, result)
    overall['accuracy'] = _rx_percent(overall['correct'], overall['marked'])
    overall['coverage'] = _rx_percent(overall['marked'], overall['total'])
    normalized = {}
    for kind, values in groups.items():
        rows = []
        for item in values.values():
            item['accuracy'] = _rx_percent(item['correct'], item['marked'])
            item['coverage'] = _rx_percent(item['marked'], item['total'])
            rows.append(item)
        normalized[kind] = sorted(rows, key=lambda x: F.norm(x['name']))
    return {'overall': overall, 'groups': normalized}


def result_export_workbook(app, c, user, activity_key, applied_on):
    rows = _rx_rows(app, c, activity_key, applied_on)
    if not rows:
        raise ValueError('Nenhum resultado de aluno foi encontrado para esse simulado.')
    exam_cache = {}
    summary_rows = []
    detail_rows = {kind: [] for kind in _RX_GROUP_KINDS}
    for row in rows:
        metadata = row['_metadata']
        exam_id = metadata.get('_exam_id')
        if exam_id not in exam_cache:
            exam_cache[exam_id] = E.get_exam(app, c, exam_id)
        exam = exam_cache[exam_id]
        if not exam:
            raise ValueError('Um resultado possui mapa de questões inexistente. Corrija o mapa antes de exportar.')
        metrics = _rx_json(row.get('metrics'))
        analysis = _rx_analyse(exam, metrics, metadata)
        overall = analysis['overall']
        common = [
            row.get('student_name', ''), row.get('student_login', ''),
            F.text(metadata.get('TURMA'), 150), row['activity'], row['applied_on'],
            F.text(metadata.get('COR DA PROVA'), 80), F.text(metadata.get('L.E'), 40),
        ]
        summary_rows.append(common + [
            overall['correct'], overall['errors'], overall['marked'], overall['total'],
            '' if overall['accuracy'] is None else overall['accuracy'],
            '' if overall['coverage'] is None else overall['coverage'],
        ])
        for kind in _RX_GROUP_KINDS:
            for item in analysis['groups'][kind]:
                detail_rows[kind].append(common[:3] + [
                    item['name'], item['correct'], item['errors'], item['marked'], item['total'],
                    '' if item['accuracy'] is None else item['accuracy'],
                    '' if item['coverage'] is None else item['coverage'],
                    ', '.join(str(x) for x in item['correctQuestions']),
                    ', '.join(str(x) for x in item['errorQuestions']),
                    ', '.join(str(x) for x in item['pendingQuestions']),
                ])
    summary_rows.sort(key=lambda x: (F.norm(x[0]), F.norm(x[1])))
    summary_headers = [
        'Aluno', 'Login', 'Turma', 'Simulado', 'Data', 'Cor da prova',
        'Língua estrangeira', 'Acertos', 'Erros', 'Questões calculadas',
        'Questões válidas', 'Aproveitamento (%)', 'Cobertura (%)',
    ]
    extra_sheets = []
    sheet_names = {
        'Área': 'Por área', 'Disciplina': 'Por disciplina', 'Tópico': 'Por tópico',
        'Assunto': 'Por assunto', 'Habilidade': 'Por habilidade',
    }
    group_headers = [
        'Aluno', 'Login', 'Turma', 'Classificação', 'Acertos', 'Erros',
        'Questões calculadas', 'Questões válidas', 'Aproveitamento (%)',
        'Cobertura (%)', 'Questões acertadas', 'Questões erradas', 'Sem resultado',
    ]
    for kind in _RX_GROUP_KINDS:
        values = detail_rows[kind]
        values.sort(key=lambda x: (F.norm(x[0]), F.norm(x[3])))
        extra_sheets.append((sheet_names[kind], group_headers, values))
    return T.export(
        summary_headers, summary_rows, first_name='Resumo dos alunos',
        extra_sheets=extra_sheets,
    )


_rx_original_handle = handle


def handle(app, c, user, path, method, data, query, start, HTTPError):
    if path == '/api/model-data/simulations' and method == 'GET':
        _rx_role_guard(user, HTTPError)
        return app.reply(start, 200, {'simulations': result_export_simulations(app, c, user)})
    if path == '/api/model-data/export-results-json' and method == 'POST':
        _rx_role_guard(user, HTTPError)
        activity_key = F.text(data.get('activityKey'), 250)
        applied_on = F.text(data.get('date'), 40)
        if not activity_key or not applied_on:
            raise ValueError('Selecione um simulado para exportar.')
        blob, mime = result_export_workbook(app, c, user, activity_key, applied_on)
        title_row = app.db.execute(
            c, 'SELECT activity FROM hmay_performance WHERE activity_key=? AND applied_on=? ORDER BY activity LIMIT 1',
            (activity_key, applied_on),
        ).fetchone()
        title = title_row['activity'] if title_row else 'simulado'
        filename = re.sub(r'[^A-Za-z0-9_-]+', '_', title).strip('_') or 'simulado'
        import base64 as _result_export_base64
        app.event(c, user, user['id'], 'model_data_results_export')
        return app.reply(start, 200, {
            'filename': f'Resultados_convertidos_{filename}_{applied_on}.xlsx',
            'mime': mime,
            'content': _result_export_base64.b64encode(blob).decode('ascii'),
        })
    if path == '/api/model-data/export-results' and method == 'POST':
        _rx_role_guard(user, HTTPError)
        activity_key = F.text(data.get('activityKey'), 250)
        applied_on = F.text(data.get('date'), 40)
        if not activity_key or not applied_on:
            raise ValueError('Selecione um simulado para exportar.')
        blob, mime = result_export_workbook(app, c, user, activity_key, applied_on)
        title_row = app.db.execute(
            c, 'SELECT activity FROM hmay_performance WHERE activity_key=? AND applied_on=? ORDER BY activity LIMIT 1',
            (activity_key, applied_on),
        ).fetchone()
        title = title_row['activity'] if title_row else 'simulado'
        filename = re.sub(r'[^A-Za-z0-9_-]+', '_', title).strip('_') or 'simulado'
        app.event(c, user, user['id'], 'model_data_results_export')
        return app.reply(
            start, 200, blob, mime,
            [('Content-Disposition', f'attachment; filename="Resultados_convertidos_{filename}_{applied_on}.xlsx"')],
        )
    return _rx_original_handle(app, c, user, path, method, data, query, start, HTTPError)



# === MEU CRONOGRAMA: RESUMO INDIVIDUAL DO ALUNO ===
def _ss_num(value):
    try:
        return int(float(value or 0))
    except (TypeError, ValueError):
        return 0


def _ss_target(app, c, user, query, HTTPError):
    raw = query.get('user', ['']) if isinstance(query, dict) else ['']
    target_id = F.text(raw[0] if raw else '', 100) or user['id']
    row = app.db.execute(
        c, 'SELECT id,username,name,role,active FROM hmay_users WHERE id=?', (target_id,)
    ).fetchone()
    if not row:
        raise HTTPError(404, 'Aluno não encontrado.')
    account = dict(row)
    if target_id != user['id']:
        if user.get('role') == 'master':
            pass
        elif user.get('role') == 'coordenador' and account.get('role') in ('user', 'aluno') and account.get('active'):
            pass
        else:
            raise HTTPError(403, 'Você não pode consultar esse perfil.')
    return account


def _ss_profile_summary(profile):
    subjects = profile.get('subjects') if isinstance(profile.get('subjects'), list) else []
    contents = profile.get('contents') if isinstance(profile.get('contents'), list) else []
    feedback = profile.get('feedback') if isinstance(profile.get('feedback'), list) else []
    by_subject = {}
    subject_names = {}
    for subject in subjects:
        if not isinstance(subject, dict):
            continue
        sid = F.text(subject.get('id'), 100)
        name = F.text(subject.get('name'), 150) or 'Sem disciplina'
        if sid:
            subject_names[sid] = name
        by_subject.setdefault(name, {
            'name': name, 'contents': 0, 'studied': 0, 'plannedMinutes': 0,
            'actualMinutes': 0, 'paused': 0,
        })
    content_subject = {}
    recent = []
    for content in contents:
        if not isinstance(content, dict):
            continue
        sid = F.text(content.get('subjectId'), 100)
        name = subject_names.get(sid, 'Sem disciplina')
        bucket = by_subject.setdefault(name, {
            'name': name, 'contents': 0, 'studied': 0, 'plannedMinutes': 0,
            'actualMinutes': 0, 'paused': 0,
        })
        bucket['contents'] += 1
        if F.text(content.get('status'), 40).lower() == 'studied':
            bucket['studied'] += 1
        if content.get('paused'):
            bucket['paused'] += 1
        bucket['plannedMinutes'] += max(0, _ss_num(content.get('studyMinutes')))
        cid = F.text(content.get('id'), 100)
        if cid:
            content_subject[cid] = name
        recent.append({
            'title': F.text(content.get('title'), 250) or 'Conteúdo sem título',
            'topic': F.text(content.get('topic'), 250),
            'subject': name,
            'status': F.text(content.get('status'), 40) or 'planned',
            'studiedOn': F.text(content.get('studiedOn'), 40),
            'nextDue': F.text(content.get('nextDue'), 40),
            'difficulty': _ss_num(content.get('difficulty')),
        })
    actual_total = 0
    for item in feedback:
        if not isinstance(item, dict):
            continue
        minutes = max(0, _ss_num(item.get('actualMin')))
        actual_total += minutes
        name = content_subject.get(F.text(item.get('contentId'), 100), 'Sem disciplina')
        bucket = by_subject.setdefault(name, {
            'name': name, 'contents': 0, 'studied': 0, 'plannedMinutes': 0,
            'actualMinutes': 0, 'paused': 0,
        })
        bucket['actualMinutes'] += minutes
    recent.sort(key=lambda x: (x.get('studiedOn') or x.get('nextDue') or '', F.norm(x.get('title'))), reverse=True)
    rows = sorted(by_subject.values(), key=lambda x: F.norm(x['name']))
    return {
        'subjects': len([x for x in subjects if isinstance(x, dict) and x.get('active', True)]),
        'contents': len([x for x in contents if isinstance(x, dict)]),
        'studied': sum(x['studied'] for x in rows),
        'paused': sum(x['paused'] for x in rows),
        'plannedMinutes': sum(x['plannedMinutes'] for x in rows),
        'actualMinutes': actual_total,
        'bySubject': rows,
        'recentContents': recent[:12],
    }


def _ss_rollup_add(target, source):
    for item in source:
        name = F.text(item.get('name'), 300) or 'Não informado'
        bucket = target.setdefault(name, {
            'name': name, 'correct': 0, 'errors': 0, 'marked': 0, 'total': 0,
        })
        for key in ('correct', 'errors', 'marked', 'total'):
            bucket[key] += max(0, _ss_num(item.get(key)))


def _ss_rollup_rows(values):
    rows = []
    for item in values.values():
        marked = item['marked']
        total = item['total']
        item['accuracy'] = None if not marked else round(100 * item['correct'] / marked, 2)
        item['coverage'] = None if not total else round(100 * marked / total, 2)
        rows.append(item)
    return sorted(rows, key=lambda x: (-x['marked'], F.norm(x['name'])))


def student_summary(app, c, user, target, history_year=None):
    state_row = app.db.execute(c, 'SELECT profile FROM hmay_state WHERE user_id=?', (target['id'],)).fetchone()
    profile = _rx_json(state_row['profile']) if state_row else {}
    study = _ss_profile_summary(profile)
    condition='p.user_id=?'
    args=[target['id']]
    if history_year is not None:
        condition+=""" OR (p.applied_on LIKE ? AND EXISTS (
            SELECT 1 FROM hmay_history_links h WHERE h.target_id=? AND h.year=?
            AND h.source_id=p.user_id AND (h.result_id='' OR h.result_id=p.id)))"""
        args.extend([str(history_year)+'-%',target['id'],history_year])
    performance_rows=app.db.execute(c,'SELECT p.* FROM hmay_performance p WHERE '+condition+
                                    ' ORDER BY p.applied_on DESC,p.activity',tuple(args)).fetchall()
    exam_cache = {}
    simulations = []
    aggregate = {kind: {} for kind in _RX_GROUP_KINDS}
    total_correct = total_errors = total_marked = total_valid = 0
    for raw in performance_rows:
        row = dict(raw)
        metadata = _rx_json(row.get('metadata'))
        exam_id = metadata.get('_exam_id')
        if not exam_id:
            continue
        if exam_id not in exam_cache:
            exam_cache[exam_id] = E.get_exam(app, c, exam_id)
        exam = exam_cache.get(exam_id)
        if not exam:
            continue
        analysis = _rx_analyse(exam, _rx_json(row.get('metrics')), metadata)
        overall = analysis['overall']
        total_correct += overall['correct']
        total_errors += overall['errors']
        total_marked += overall['marked']
        total_valid += overall['total']
        for kind in _RX_GROUP_KINDS:
            _ss_rollup_add(aggregate[kind], analysis['groups'][kind])
        simulations.append({
            'activity': row.get('activity', ''),
            'date': row.get('applied_on', ''),
            'color': F.text(metadata.get('COR DA PROVA'), 80),
            'language': F.text(metadata.get('L.E'), 40),
            'correct': overall['correct'],
            'errors': overall['errors'],
            'marked': overall['marked'],
            'valid': overall['total'],
            'accuracy': overall['accuracy'],
            'coverage': overall['coverage'],
            'areas': analysis['groups']['Área'],
            'disciplines': analysis['groups']['Disciplina'],
        })
    simulations.sort(key=lambda x: (x['date'], F.norm(x['activity'])), reverse=True)
    return {
        'student': {
            'id': target['id'], 'name': target['name'], 'username': target['username'],
        },
        'study': study,
        'performance': {
            'simulations': len(simulations),
            'correct': total_correct,
            'errors': total_errors,
            'marked': total_marked,
            'valid': total_valid,
            'accuracy': None if not total_marked else round(100 * total_correct / total_marked, 2),
            'coverage': None if not total_valid else round(100 * total_marked / total_valid, 2),
        },
        'simulations': simulations,
        'aggregates': {
            'area': _ss_rollup_rows(aggregate['Área']),
            'discipline': _ss_rollup_rows(aggregate['Disciplina']),
            'topic': _ss_rollup_rows(aggregate['Tópico']),
            'subject': _ss_rollup_rows(aggregate['Assunto']),
            'skill': _ss_rollup_rows(aggregate['Habilidade']),
        },
    }


_ss_original_handle = handle


def handle(app, c, user, path, method, data, query, start, HTTPError):
    if path == '/api/model-data/student-summary' and method == 'GET':
        target = _ss_target(app, c, user, query, HTTPError)
        return app.reply(start, 200, student_summary(app, c, user, target))
    return _ss_original_handle(app, c, user, path, method, data, query, start, HTTPError)

# === MEU CRONOGRAMA: TRAJETÓRIA ACADÊMICA NA VISÃO GERAL ===
_ss_home_original_student_summary = student_summary


def _ss_home_profile_engagement(profile):
    from datetime import date as _ss_home_date_type, timedelta as _ss_home_timedelta

    sessions = profile.get('sessions') if isinstance(profile.get('sessions'), list) else []
    contents = profile.get('contents') if isinstance(profile.get('contents'), list) else []
    feedback = profile.get('feedback') if isinstance(profile.get('feedback'), list) else []

    activity = {'planned': 0, 'done': 0, 'partial': 0, 'missed': 0, 'totalClosed': 0}
    reviews = {'planned': 0, 'done': 0, 'partial': 0, 'missed': 0, 'overdue': 0, 'dueSoon': 0}
    by_kind = {
        'study': {'planned': 0, 'done': 0, 'partial': 0, 'missed': 0},
        'review': {'planned': 0, 'done': 0, 'partial': 0, 'missed': 0},
        'action': {'planned': 0, 'done': 0, 'partial': 0, 'missed': 0},
    }
    for session in sessions:
        if not isinstance(session, dict):
            continue
        status = F.text(session.get('status'), 30).lower()
        kind = F.text(session.get('kind'), 30).lower()
        if status in activity:
            activity[status] += 1
        if kind in by_kind and status in by_kind[kind]:
            by_kind[kind][status] += 1
        if kind == 'review' and status in reviews:
            reviews[status] += 1

    activity['totalClosed'] = activity['done'] + activity['partial'] + activity['missed']
    activity['completionRate'] = (
        None if not activity['totalClosed']
        else round(100 * (activity['done'] + .5 * activity['partial']) / activity['totalClosed'], 2)
    )

    today = _ss_home_date_type.today()
    soon = today + _ss_home_timedelta(days=7)
    for content in contents:
        if not isinstance(content, dict):
            continue
        if F.text(content.get('status'), 30).lower() != 'studied' or content.get('paused'):
            continue
        raw_due = F.text(content.get('nextDue'), 40)
        if not raw_due:
            continue
        try:
            due = _ss_home_date_type.fromisoformat(raw_due[:10])
        except (TypeError, ValueError):
            continue
        if due < today:
            reviews['overdue'] += 1
        elif due <= soon:
            reviews['dueSoon'] += 1

    actual_minutes = 0
    questions = correct = 0
    for item in feedback:
        if not isinstance(item, dict):
            continue
        actual_minutes += max(0, _ss_num(item.get('actualMin')))
        questions += max(0, _ss_num(item.get('total')))
        correct += max(0, _ss_num(item.get('correct')))

    return {
        'activities': activity,
        'reviews': reviews,
        'byKind': by_kind,
        'feedback': {
            'records': len([x for x in feedback if isinstance(x, dict)]),
            'minutes': actual_minutes,
            'questions': questions,
            'correct': correct,
            'accuracy': None if not questions else round(100 * correct / questions, 2),
        },
    }


def student_summary(app, c, user, target):
    result = _ss_home_original_student_summary(app, c, user, target)
    state_row = app.db.execute(c, 'SELECT profile FROM hmay_state WHERE user_id=?', (target['id'],)).fetchone()
    profile = _rx_json(state_row['profile']) if state_row else {}
    result['engagement'] = _ss_home_profile_engagement(profile)
    return result

# === MEU CRONOGRAMA: NOTAS TRI VINCULADAS AO SIMULADO ===
_TRI_META_KEYS = {
    'ranking': ('_ranking', 'RANKING', 'Ranking'),
    'tri': ('_tri_general', 'TRI', 'NOTA TRI', 'Nota TRI', 'NOTA ENEM'),
    'triBonus': ('_tri_bonus', 'TRI 10%', 'TRI 10', 'NOTA COM BONIFICAÇÃO'),
    'lc': ('_tri_lc', 'TRI LING', 'TRI LINGUAGENS', 'NOTA TRI LINGUAGENS', 'NU_NOTA_LC'),
    'ch': ('_tri_ch', 'TRI HUM', 'TRI HUMANAS', 'NOTA TRI HUMANAS', 'NU_NOTA_CH'),
    'cn': ('_tri_cn', 'TRI NAT', 'TRI NATUREZA', 'NOTA TRI NATUREZA', 'NU_NOTA_CN'),
    'mt': ('_tri_mt', 'TRI MAT', 'TRI MATEMÁTICA', 'NOTA TRI MATEMÁTICA', 'NU_NOTA_MT'),
    'redaction': ('_tri_redaction', 'RED', 'REDAÇÃO', 'NOTA DE REDAÇÃO', 'NU_NOTA_REDACAO'),
}


def _tri_norm(value):
    import unicodedata as _tri_ud
    text = _tri_ud.normalize('NFKD', str(value or ''))
    text = ''.join(ch for ch in text if not _tri_ud.combining(ch)).casefold()
    return ' '.join(re.findall(r'[a-z0-9]+', text))


def _tri_number(value):
    import math as _tri_math
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        number = float(value)
        return number if _tri_math.isfinite(number) else None
    text = str(value).strip().replace('\u00a0', '').replace(' ', '')
    if not text or text.casefold() in ('-', '—', 'n/a', 'na', 'nan', 'null'):
        return None
    text = text.replace('%', '')
    if ',' in text and '.' in text:
        if text.rfind(',') > text.rfind('.'):
            text = text.replace('.', '').replace(',', '.')
        else:
            text = text.replace(',', '')
    elif ',' in text:
        text = text.replace(',', '.')
    try:
        number = float(text)
    except (TypeError, ValueError):
        return None
    return number if _tri_math.isfinite(number) else None


def _tri_iso_date(value):
    from datetime import datetime as _tri_dt, timedelta as _tri_delta
    number = _tri_number(value)
    if number is not None and 1 <= number <= 100000:
        try:
            return (_tri_dt(1899, 12, 30) + _tri_delta(days=number)).date().isoformat()
        except (OverflowError, ValueError):
            pass
    text = str(value or '').strip()
    if not text:
        return ''
    for fmt in ('%Y-%m-%d', '%d/%m/%Y', '%d-%m-%Y', '%Y/%m/%d'):
        try:
            return _tri_dt.strptime(text[:10], fmt).date().isoformat()
        except ValueError:
            continue
    return ''


def _tri_excel_col(reference):
    match = re.match(r'([A-Z]+)', str(reference or '').upper())
    if not match:
        return None
    result = 0
    for char in match.group(1):
        result = result * 26 + ord(char) - 64
    return result - 1


def _tri_xlsx_rows(data):
    import base64 as _tri_base64
    import io as _tri_io
    import zipfile as _tri_zip
    import xml.etree.ElementTree as _tri_xml

    encoded = data.get('file')
    if not isinstance(encoded, str) or not encoded:
        raise ValueError('Selecione o arquivo Excel com a aba Ranking ou Ranking Geral.')
    if len(encoded) > 16_000_000:
        raise ValueError('O arquivo de ranking excede o limite permitido.')
    try:
        blob = _tri_base64.b64decode(encoded, validate=True)
    except Exception as exc:
        raise ValueError('O arquivo de ranking não pôde ser decodificado.') from exc
    if len(blob) > 8_000_000:
        raise ValueError('O arquivo de ranking deve ter no máximo 8 MB.')
    try:
        archive = _tri_zip.ZipFile(_tri_io.BytesIO(blob))
    except Exception as exc:
        raise ValueError('O arquivo não é um XLSX válido.') from exc
    names = set(archive.namelist())
    if '[Content_Types].xml' not in names or 'xl/workbook.xml' not in names:
        raise ValueError('Estrutura XLSX inválida.')
    content_types = archive.read('[Content_Types].xml').decode('utf-8', 'ignore').casefold()
    if 'vbaproject' in content_types or 'macroenabled' in content_types:
        raise ValueError('Use um arquivo .xlsx sem macros.')

    ns = {'m': 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
    rel_ns = {'r': 'http://schemas.openxmlformats.org/package/2006/relationships'}
    office_rel = '{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id'
    workbook = _tri_xml.fromstring(archive.read('xl/workbook.xml'))
    relationships = {}
    if 'xl/_rels/workbook.xml.rels' in names:
        rel_root = _tri_xml.fromstring(archive.read('xl/_rels/workbook.xml.rels'))
        for rel in rel_root.findall('r:Relationship', rel_ns):
            relationships[rel.attrib.get('Id')] = rel.attrib.get('Target', '')

    shared = []
    if 'xl/sharedStrings.xml' in names:
        shared_root = _tri_xml.fromstring(archive.read('xl/sharedStrings.xml'))
        for item in shared_root.findall('m:si', ns):
            shared.append(''.join(node.text or '' for node in item.iter() if node.tag.endswith('}t')))

    def sheet_path(target):
        target = str(target or '').replace('\\', '/')
        if target.startswith('/'):
            target = target[1:]
        elif not target.startswith('xl/'):
            target = 'xl/' + target
        parts = []
        for part in target.split('/'):
            if part == '..':
                if parts:
                    parts.pop()
            elif part and part != '.':
                parts.append(part)
        return '/'.join(parts)

    def cell_value(cell):
        kind = cell.attrib.get('t', '')
        if kind == 'inlineStr':
            return ''.join(node.text or '' for node in cell.iter() if node.tag.endswith('}t'))
        value_node = cell.find('m:v', ns)
        raw = value_node.text if value_node is not None else ''
        if kind == 's':
            try:
                return shared[int(raw)]
            except (ValueError, IndexError):
                return ''
        if kind in ('str', 'e'):
            return raw if kind == 'str' else ''
        if kind == 'b':
            return raw == '1'
        if raw == '':
            return ''
        try:
            number = float(raw)
            return int(number) if number.is_integer() else number
        except ValueError:
            return raw

    sheets = []
    sheets_node = workbook.find('m:sheets', ns)
    for sheet in list(sheets_node or []):
        title = sheet.attrib.get('name', '')
        relationship_id = sheet.attrib.get(office_rel)
        path = sheet_path(relationships.get(relationship_id, ''))
        if not path or path not in names:
            continue
        root = _tri_xml.fromstring(archive.read(path))
        output = []
        for row_node in root.findall('.//m:sheetData/m:row', ns):
            row_values = {}
            max_col = -1
            for cell in row_node.findall('m:c', ns):
                col = _tri_excel_col(cell.attrib.get('r'))
                if col is None or col > 250:
                    continue
                row_values[col] = cell_value(cell)
                max_col = max(max_col, col)
            if max_col >= 0:
                output.append([row_values.get(index, '') for index in range(max_col + 1)])
            else:
                output.append([])
            if len(output) >= 10000:
                break
        sheets.append({'name': title, 'rows': output})
    if not sheets:
        raise ValueError('Nenhuma planilha legível foi encontrada no arquivo.')
    return sheets


_TRI_ALIASES = {
    'name': {'nome', 'nome do aluno', 'aluno', 'nome aluno'},
    'group': {'turma', 'grupo'},
    'activity': {'tipo', 'tipo de prova', 'simulado', 'nome do simulado', 'atividade', 'avaliacao'},
    'date': {'data', 'data de aplicacao', 'aplicacao'},
    'language': {'l e', 'lingua estrangeira', 'l estrangeira selecionada'},
    'ranking': {'ranking', 'rank', 'classificacao', 'posicao', 'colocacao'},
    'triBonus': {'tri 10', 'tri 10 0', 'tri 10 percentual', 'nota com bonificacao', 'nota bonus'},
    'tri': {'tri', 'nota tri', 'nota enem', 'nota enem geral', 'sua nota enem'},
    'lc': {'tri ling', 'tri linguagens', 'tri linguagem', 'nota tri linguagens', 'nota enem linguagens', 'nu nota lc'},
    'ch': {'tri hum', 'tri humanas', 'nota tri humanas', 'nota enem humanas', 'nu nota ch'},
    'cn': {'tri nat', 'tri natureza', 'nota tri natureza', 'nota enem natureza', 'nu nota cn'},
    'mt': {'tri mat', 'tri matematica', 'nota tri matematica', 'nota enem matematica', 'nu nota mt'},
    'redaction': {'red', 'redacao', 'nota redacao', 'nota de redacao', 'nu nota redacao'},
    'lcCorrect': {'lc', 'acertos linguagens', 'acertos em linguagens'},
    'chCorrect': {'ch', 'acertos humanas', 'acertos em humanas'},
    'cnCorrect': {'cn', 'acertos natureza', 'acertos em natureza'},
    'mtCorrect': {'mt', 'acertos matematica', 'acertos em matematica'},
}


def _tri_header_columns(values):
    columns = {}
    for index, value in enumerate(values):
        normalized = _tri_norm(value)
        if not normalized:
            continue
        for key, aliases in _TRI_ALIASES.items():
            if normalized in aliases and key not in columns:
                columns[key] = index
                break
        if 'tri' in normalized or 'nota enem' in normalized:
            if 'ling' in normalized and 'lc' not in columns:
                columns['lc'] = index
            elif ('hum' in normalized or normalized.endswith(' ch')) and 'ch' not in columns:
                columns['ch'] = index
            elif ('nat' in normalized or normalized.endswith(' cn')) and 'cn' not in columns:
                columns['cn'] = index
            elif ('mat' in normalized or normalized.endswith(' mt')) and 'mt' not in columns:
                columns['mt'] = index
    return columns


def _tri_detect_table(sheets):
    candidates = []
    for sheet_order, sheet in enumerate(sheets):
        rows = sheet['rows']
        for row_index in range(min(40, len(rows))):
            current = rows[row_index]
            next_row = rows[row_index + 1] if row_index + 1 < len(rows) else []
            width = max(len(current), len(next_row))
            combined = []
            for col in range(width):
                one = current[col] if col < len(current) else ''
                two = next_row[col] if col < len(next_row) else ''
                combined.append((str(one or '') + ' ' + str(two or '')).strip())
            for span, header in ((1, current), (2, combined)):
                columns = _tri_header_columns(header)
                score = (8 if 'name' in columns else 0)
                score += 2 * sum(key in columns for key in ('tri', 'lc', 'ch', 'cn', 'mt', 'redaction'))
                score += int('ranking' in columns)
                preferred = _tri_norm(sheet['name']) in ('ranking', 'ranking geral', 'ranking geral alunos')
                score += 4 if preferred else 0
                if 'name' in columns and any(key in columns for key in ('tri', 'lc', 'ch', 'cn', 'mt', 'redaction')):
                    candidates.append((score, -sheet_order, -row_index, sheet, row_index, span, columns, header))
    if not candidates:
        raise ValueError('Não encontrei NOME e colunas de nota TRI em uma aba Ranking/Ranking Geral.')
    candidates.sort(reverse=True, key=lambda item: item[:3])
    _, _, _, sheet, row_index, span, columns, header = candidates[0]
    return sheet, row_index, span, columns, header


def _tri_parse_ranking(data):
    sheets = _tri_xlsx_rows(data)
    sheet, header_row, header_span, columns, header = _tri_detect_table(sheets)
    records = []
    for source_index, row in enumerate(sheet['rows'][header_row + header_span:], start=header_row + header_span + 1):
        def value(key):
            index = columns.get(key)
            return row[index] if index is not None and index < len(row) else ''
        name = F.text(value('name'), 250)
        if not name:
            continue
        scores = {key: _tri_number(value(key)) for key in ('ranking', 'tri', 'triBonus', 'lc', 'ch', 'cn', 'mt', 'redaction')}
        if all(item is None for item in scores.values()):
            continue
        if scores['tri'] is None and all(scores[key] is not None for key in ('lc', 'ch', 'cn', 'mt', 'redaction')):
            scores['tri'] = round(sum(scores[key] for key in ('lc', 'ch', 'cn', 'mt', 'redaction')) / 5, 3)
        records.append({
            'name': name,
            'nameKey': F.norm(name),
            'group': F.text(value('group'), 150),
            'activity': F.text(value('activity'), 200),
            'date': _tri_iso_date(value('date')),
            'language': F.text(value('language'), 40),
            'scores': scores,
            'line': source_index,
        })
    if not records:
        raise ValueError('A aba de ranking foi encontrada, mas não contém notas TRI preenchidas.')
    detected = {}
    for key, index in columns.items():
        detected[key] = F.text(header[index] if index < len(header) else '', 120)
    return {
        'sheet': sheet['name'], 'headerRow': header_row + 1,
        'columns': detected, 'records': records,
    }


def _tri_meta_number(metadata, key):
    for name in _TRI_META_KEYS[key]:
        number = _tri_number(metadata.get(name))
        if number is not None:
            return number
    return None


def _tri_scores_from_metadata(metadata):
    result = {key: _tri_meta_number(metadata, key) for key in _TRI_META_KEYS}
    if result['tri'] is None and all(result[key] is not None for key in ('lc', 'ch', 'cn', 'mt', 'redaction')):
        result['tri'] = round(sum(result[key] for key in ('lc', 'ch', 'cn', 'mt', 'redaction')) / 5, 3)
    return result


def _tri_target_results(app, c, activity_key, applied_on):
    rows = app.db.execute(
        c,
        'SELECT p.id,p.user_id,p.activity,p.activity_key,p.applied_on,p.metadata,'
        'u.name AS student_name,u.username AS student_login,u.role AS student_role '
        'FROM hmay_performance p JOIN hmay_users u ON u.id=p.user_id '
        'WHERE p.activity_key=? AND p.applied_on=? ORDER BY u.name,u.username',
        (activity_key, applied_on),
    ).fetchall()
    return [dict(row) for row in rows if row['student_role'] in ('user', 'aluno')]


def _tri_choose_record(records, activity, applied_on):
    if len(records) == 1:
        return records[0], ''
    dated = [row for row in records if row.get('date') == applied_on]
    if len(dated) == 1:
        return dated[0], ''
    if dated:
        records = dated
    activity_key = F.norm(activity)
    titled = [row for row in records if row.get('activity') and F.norm(row['activity']) == activity_key]
    if len(titled) == 1:
        return titled[0], ''
    if titled:
        records = titled
    signatures = {
        tuple(records[index]['scores'].get(key) for key in ('ranking', 'tri', 'triBonus', 'lc', 'ch', 'cn', 'mt', 'redaction'))
        for index in range(len(records))
    }
    if len(signatures) == 1:
        return records[0], ''
    return None, 'Há mais de uma linha de ranking para o mesmo nome e não foi possível escolher o simulado correto.'


def _tri_match(app, c, parsed, activity_key, applied_on):
    targets = _tri_target_results(app, c, activity_key, applied_on)
    if not targets:
        raise ValueError('O simulado selecionado não possui resultados de alunos.')
    target_groups = {}
    for row in targets:
        target_groups.setdefault(F.norm(row['student_name']), []).append(row)
    source_groups = {}
    for record in parsed['records']:
        source_groups.setdefault(record['nameKey'], []).append(record)
    matched = []
    unmatched = []
    conflicts = []
    for name_key, records in source_groups.items():
        target_rows = target_groups.get(name_key, [])
        if not target_rows:
            unmatched.append(records[0]['name'])
            continue
        if len(target_rows) != 1:
            conflicts.append({'name': records[0]['name'], 'reason': 'Existem contas duplicadas com esse nome no simulado.'})
            continue
        chosen, reason = _tri_choose_record(records, target_rows[0]['activity'], applied_on)
        if not chosen:
            conflicts.append({'name': records[0]['name'], 'reason': reason})
            continue
        matched.append({'target': target_rows[0], 'source': chosen})
    return {
        'targets': targets, 'matched': matched, 'unmatched': unmatched,
        'conflicts': conflicts,
        'withoutScore': [row['student_name'] for key, rows in target_groups.items() if key not in source_groups for row in rows],
    }


def _tri_preview(app, c, data):
    parsed = _tri_parse_ranking(data)
    activity_key = F.text(data.get('activityKey'), 250)
    applied_on = F.date_value(data.get('date'))
    match = _tri_match(app, c, parsed, activity_key, applied_on)
    sample = []
    changed = unchanged = 0
    for pair in match['matched']:
        metadata = _rx_json(pair['target'].get('metadata'))
        old = _tri_scores_from_metadata(metadata)
        new = pair['source']['scores']
        has_change = any(new.get(key) is not None and old.get(key) != new.get(key) for key in new)
        changed += int(has_change); unchanged += int(not has_change)
        if len(sample) < 20:
            sample.append({
                'name': pair['target']['student_name'], 'login': pair['target']['student_login'],
                'ranking': new.get('ranking'), 'tri': new.get('tri'), 'lc': new.get('lc'),
                'ch': new.get('ch'), 'cn': new.get('cn'), 'mt': new.get('mt'),
                'redaction': new.get('redaction'), 'changed': has_change,
            })
    return parsed, match, {
        'sheet': parsed['sheet'], 'sourceRows': len(parsed['records']),
        'students': len(match['targets']), 'matched': len(match['matched']),
        'changed': changed, 'unchanged': unchanged,
        'unmatched': len(match['unmatched']), 'conflicts': len(match['conflicts']),
        'withoutScore': len(match['withoutScore']), 'sample': sample,
    }


def _tri_apply_metadata(metadata, scores, source_sheet, user):
    changed = False
    mapping = {
        'ranking': '_ranking', 'tri': '_tri_general', 'triBonus': '_tri_bonus',
        'lc': '_tri_lc', 'ch': '_tri_ch', 'cn': '_tri_cn', 'mt': '_tri_mt',
        'redaction': '_tri_redaction',
    }
    for key, destination in mapping.items():
        value = scores.get(key)
        if value is None:
            continue
        stored = int(value) if key == 'ranking' and float(value).is_integer() else round(float(value), 4)
        if metadata.get(destination) != stored:
            metadata[destination] = stored
            changed = True
    if changed:
        metadata['_tri_source_sheet'] = source_sheet
        metadata['_tri_imported_at'] = P.now().isoformat()
        metadata['_tri_imported_by'] = user['id']
    return changed


def _tri_simulation_metadata(app, c, target_id):
    rows = app.db.execute(
        c, 'SELECT activity,applied_on,metadata,updated_at FROM hmay_performance '
        'WHERE user_id=? ORDER BY applied_on DESC,updated_at DESC', (target_id,),
    ).fetchall()
    result = {}
    for row in rows:
        key = (F.norm(row['activity']), row['applied_on'])
        result.setdefault(key, _rx_json(row['metadata']))
    return result


_tri_original_student_summary = student_summary


def student_summary(app, c, user, target):
    result = _tri_original_student_summary(app, c, user, target)
    metadata_by_simulation = _tri_simulation_metadata(app, c, target['id'])
    tri_rows = []
    for simulation in result.get('simulations', []):
        metadata = metadata_by_simulation.get((F.norm(simulation.get('activity')), simulation.get('date')), {})
        scores = _tri_scores_from_metadata(metadata)
        simulation['tri'] = scores['tri']
        simulation['triBonus'] = scores['triBonus']
        simulation['ranking'] = scores['ranking']
        simulation['redactionScore'] = scores['redaction']
        simulation['triByArea'] = [
            {'code': 'LC', 'name': 'Linguagens', 'score': scores['lc']},
            {'code': 'CH', 'name': 'Humanas', 'score': scores['ch']},
            {'code': 'CN', 'name': 'Natureza', 'score': scores['cn']},
            {'code': 'MT', 'name': 'Matemática', 'score': scores['mt']},
            {'code': 'RED', 'name': 'Redação', 'score': scores['redaction']},
        ]
        area_scores = {item['name']: item['score'] for item in simulation['triByArea']}
        for area in simulation.get('areas', []):
            area['tri'] = area_scores.get(_RX_AREA_LABELS.get(str(area.get('name') or '').upper(), area.get('name')))
        if scores['tri'] is not None:
            tri_rows.append({'activity': simulation.get('activity'), 'date': simulation.get('date'), 'score': scores['tri']})
    result['tri'] = {
        'simulations': len(tri_rows),
        'latest': tri_rows[0]['score'] if tri_rows else None,
        'average': None if not tri_rows else round(sum(row['score'] for row in tri_rows) / len(tri_rows), 2),
        'highest': None if not tri_rows else max(row['score'] for row in tri_rows),
        'evolution': list(reversed(tri_rows[-10:])),
    }
    return result


_tri_original_result_export_workbook = result_export_workbook


def result_export_workbook(app, c, user, activity_key, applied_on):
    rows = _rx_rows(app, c, activity_key, applied_on)
    if not rows:
        raise ValueError('Nenhum resultado de aluno foi encontrado para esse simulado.')
    exam_cache = {}
    summary_rows = []
    detail_rows = {kind: [] for kind in _RX_GROUP_KINDS}
    for row in rows:
        metadata = row['_metadata']
        exam_id = metadata.get('_exam_id')
        if exam_id not in exam_cache:
            exam_cache[exam_id] = E.get_exam(app, c, exam_id)
        exam = exam_cache[exam_id]
        if not exam:
            raise ValueError('Um resultado possui mapa de questões inexistente. Corrija o mapa antes de exportar.')
        analysis = _rx_analyse(exam, _rx_json(row.get('metrics')), metadata)
        overall = analysis['overall']
        scores = _tri_scores_from_metadata(metadata)
        common = [
            row.get('student_name', ''), row.get('student_login', ''),
            F.text(metadata.get('TURMA'), 150), row['activity'], row['applied_on'],
            F.text(metadata.get('COR DA PROVA'), 80), F.text(metadata.get('L.E'), 40),
        ]
        summary_rows.append(common + [
            '' if scores['ranking'] is None else int(scores['ranking']),
            '' if scores['tri'] is None else scores['tri'],
            '' if scores['triBonus'] is None else scores['triBonus'],
            '' if scores['lc'] is None else scores['lc'],
            '' if scores['ch'] is None else scores['ch'],
            '' if scores['cn'] is None else scores['cn'],
            '' if scores['mt'] is None else scores['mt'],
            '' if scores['redaction'] is None else scores['redaction'],
            overall['correct'], overall['errors'], overall['marked'], overall['total'],
            '' if overall['accuracy'] is None else overall['accuracy'],
            '' if overall['coverage'] is None else overall['coverage'],
        ])
        for kind in _RX_GROUP_KINDS:
            for item in analysis['groups'][kind]:
                detail_rows[kind].append(common[:3] + [
                    item['name'], item['correct'], item['errors'], item['marked'], item['total'],
                    '' if item['accuracy'] is None else item['accuracy'],
                    '' if item['coverage'] is None else item['coverage'],
                    ', '.join(str(x) for x in item['correctQuestions']),
                    ', '.join(str(x) for x in item['errorQuestions']),
                    ', '.join(str(x) for x in item['pendingQuestions']),
                ])
    summary_rows.sort(key=lambda row: (F.norm(row[0]), F.norm(row[1])))
    summary_headers = [
        'Aluno', 'Login', 'Turma', 'Simulado', 'Data', 'Cor da prova',
        'Língua estrangeira', 'Ranking', 'Nota TRI geral', 'TRI com bônus',
        'TRI Linguagens', 'TRI Humanas', 'TRI Natureza', 'TRI Matemática',
        'Nota de redação', 'Acertos', 'Erros', 'Questões calculadas',
        'Questões válidas', 'Aproveitamento (%)', 'Cobertura (%)',
    ]
    sheet_names = {
        'Área': 'Por área', 'Disciplina': 'Por disciplina', 'Tópico': 'Por tópico',
        'Assunto': 'Por assunto', 'Habilidade': 'Por habilidade',
    }
    group_headers = [
        'Aluno', 'Login', 'Turma', 'Classificação', 'Acertos', 'Erros',
        'Questões calculadas', 'Questões válidas', 'Aproveitamento (%)',
        'Cobertura (%)', 'Questões acertadas', 'Questões erradas', 'Sem resultado',
    ]
    extra_sheets = []
    for kind in _RX_GROUP_KINDS:
        values = detail_rows[kind]
        values.sort(key=lambda row: (F.norm(row[0]), F.norm(row[3])))
        extra_sheets.append((sheet_names[kind], group_headers, values))
    return T.export(summary_headers, summary_rows, first_name='Resumo dos alunos', extra_sheets=extra_sheets)


_tri_original_handle = handle


def handle(app, c, user, path, method, data, query, start, HTTPError):
    if path in ('/api/model-data/tri-inspect', '/api/model-data/tri-preview', '/api/model-data/tri-confirm'):
        _rx_role_guard(user, HTTPError)
        parsed = _tri_parse_ranking(data)
        if path == '/api/model-data/tri-inspect':
            return app.reply(start, 200, {
                'sheet': parsed['sheet'], 'headerRow': parsed['headerRow'],
                'columns': parsed['columns'], 'rows': len(parsed['records']),
                'sample': parsed['records'][:12],
                'simulations': result_export_simulations(app, c, user),
                'notice': 'Fórmulas não são executadas. O sistema lê somente os valores armazenados no XLSX.',
            })
        activity_key = F.text(data.get('activityKey'), 250)
        applied_on = F.date_value(data.get('date'))
        if path == '/api/model-data/tri-preview':
            parsed, match, preview = _tri_preview(app, c, data)
            preview['unmatchedNames'] = match['unmatched'][:50]
            preview['conflictRows'] = match['conflicts'][:50]
            preview['withoutScoreNames'] = match['withoutScore'][:50]
            return app.reply(start, 200, preview)

        # === TRI IMPORT STABILITY V2 ===
        # The workbook was parsed above. Reuse it and persist changed rows in
        # small SQL batches instead of one network round-trip per student.
        match = _tri_match(app, c, parsed, activity_key, applied_on)
        pending_updates = []
        unchanged = 0
        for pair in match['matched']:
            metadata = _rx_json(pair['target'].get('metadata'))
            if _tri_apply_metadata(metadata, pair['source']['scores'], parsed['sheet'], user):
                pending_updates.append((
                    pair['target']['id'],
                    json.dumps(metadata, ensure_ascii=False, separators=(',', ':')),
                ))
            else:
                unchanged += 1

        TRI_IMPORT_BATCH_SIZE = 80
        updated = 0
        total_pending = len(pending_updates)
        print(
            f'MEUCRONOGRAMA_TRI_IMPORT_START matched={len(match["matched"])} pending={total_pending} unchanged={unchanged}',
            flush=True,
        )
        stamp = P.now().isoformat()
        for offset in range(0, total_pending, TRI_IMPORT_BATCH_SIZE):
            chunk = pending_updates[offset:offset + TRI_IMPORT_BATCH_SIZE]
            cases = ' '.join('WHEN ? THEN ?' for _ in chunk)
            placeholders = ','.join('?' for _ in chunk)
            params = []
            for row_id, metadata_json in chunk:
                params.extend((row_id, metadata_json))
            params.append(stamp)
            params.extend(row_id for row_id, _ in chunk)
            sql = (
                'UPDATE hmay_performance SET metadata=CASE id ' + cases +
                ' ELSE metadata END,updated_at=? WHERE id IN (' + placeholders + ')'
            )
            app.db.execute(c, sql, tuple(params))
            updated += len(chunk)
            print(
                f'MEUCRONOGRAMA_TRI_IMPORT_BATCH_DONE updated={updated}/{total_pending}',
                flush=True,
            )

        app.event(c, user, user['id'], 'tri_scores_import')
        print(
            f'MEUCRONOGRAMA_TRI_IMPORT_DONE updated={updated} unchanged={unchanged} matched={len(match["matched"])}',
            flush=True,
        )
        return app.reply(start, 200, {
            'summary': {
                'updated': updated, 'unchanged': unchanged,
                'matched': len(match['matched']), 'unmatched': len(match['unmatched']),
                'conflicts': len(match['conflicts']), 'withoutScore': len(match['withoutScore']),
            },
            'issues': {
                'unmatchedNames': match['unmatched'][:100],
                'conflictRows': match['conflicts'][:100],
                'withoutScoreNames': match['withoutScore'][:100],
            }
        })
    return _tri_original_handle(app, c, user, path, method, data, query, start, HTTPError)


# === EXAM ERROR REVIEW SYNC V1 ===
import json as _er_json
import hashlib as _er_hash
import unicodedata as _er_ud
from datetime import date as _er_date

def _er_load(value, fallback):
    try:
        out=_er_json.loads(value or '')
    except Exception:
        return fallback
    return out if isinstance(out,type(fallback)) else fallback

def _er_norm(value):
    raw=str(value or '').strip().lower()
    raw=''.join(ch for ch in _er_ud.normalize('NFD',raw) if _er_ud.category(ch)!='Mn')
    return ' '.join(raw.split())

def _er_lang(value):
    n=_er_norm(value)
    if n in ('ingles','english','en','ing'): return 'ingles'
    if n in ('espanhol','espanol','spanish','es','esp'): return 'espanhol'
    return n

def _er_target(app,c,user,target_id,HTTPError=None):
    target_id=str(target_id or user.get('id') or '')
    row=app.db.execute(c,'SELECT id,username,name,role,active FROM hmay_users WHERE id=?',(target_id,)).fetchone()
    if not row:
        raise ValueError('Conta do aluno não encontrada.')
    target=dict(row)
    actor=str(user.get('id') or '')
    role=str(user.get('role') or '')
    target_role=str(target.get('role') or '')
    allowed=(target_id==actor or role=='master' or (role=='coordenador' and target_role in ('user','aluno')))
    if not allowed:
        if HTTPError: raise HTTPError(403,'Sem permissão para atualizar revisões desta conta.')
        raise PermissionError('Sem permissão para atualizar revisões desta conta.')
    return target

def _er_exam_errors(app,c,target_id):
    rows=app.db.execute(c,'SELECT * FROM hmay_performance WHERE user_id=? ORDER BY applied_on,activity,id',(target_id,)).fetchall()
    cache={}
    groups={}
    for src in rows:
        row=dict(src)
        metadata=_er_load(row.get('metadata'),{})
        metrics=_er_load(row.get('metrics'),{})
        exam_id=str(metadata.get('_exam_id') or '')
        if not exam_id: continue
        if exam_id not in cache:
            ex=app.db.execute(c,'SELECT * FROM hmay_exams WHERE id=?',(exam_id,)).fetchone()
            cache[exam_id]=dict(ex) if ex else None
        exam=cache.get(exam_id)
        if not exam: continue
        items=_er_load(exam.get('items'),[])
        student_lang=_er_lang(metadata.get('L.E') or metadata.get('LINGUA ESTRANGEIRA') or '')
        for item in items:
            if not isinstance(item,dict): continue
            try: number=int(item.get('number') or 0)
            except Exception: continue
            if not 1<=number<=180: continue
            item_lang=_er_lang(item.get('language') or '')
            if item_lang and student_lang and item_lang!=student_lang: continue
            answer=str(item.get('answer') or '').strip().upper()
            if not answer or answer=='ANULADA': continue
            metric=metrics.get('questao:%03d'%number,{})
            if not isinstance(metric,dict): continue
            try: result=int(metric.get('correct'))
            except Exception: continue
            if result!=0: continue
            area=str(item.get('area') or '').strip().upper()
            discipline=str(item.get('discipline') or 'Não informado').strip()
            topic=str(item.get('topic') or '').strip()
            subject=str(item.get('subject') or '').strip()
            skill=str(item.get('skill') or '').strip()
            title=subject or topic or skill or ('Erros de '+discipline)
            key='|'.join([_er_norm(area),_er_norm(discipline),_er_norm(topic),_er_norm(title)])
            bucket=groups.setdefault(key,dict(area=area,discipline=discipline,topic=topic,title=title,errors=[]))
            activity=str(row.get('activity') or exam.get('title') or 'Avaliação')
            applied=str(row.get('applied_on') or exam.get('applied_on') or '')
            raw_key=str(row.get('activity_key') or activity)
            err_hash=_er_hash.sha1((raw_key+'|'+applied+'|'+str(number)+'|'+area).encode('utf-8')).hexdigest()[:5].upper()
            error_id='ERR-%s-%s-Q%03d-%s'%((applied.replace('-','') or 'SEM_DATA'),(area or 'GERAL'),number,err_hash)
            response=str(metric.get('response') or metric.get('selected') or metric.get('answer') or '').strip().upper()
            bucket['errors'].append(dict(
                id=error_id,simulation=activity,date=applied,question=number,area=area,
                discipline=discipline,topic=topic,subject=subject,skill=skill,
                answer=answer,response=response,color=str(metadata.get('COR DA PROVA') or ''),
                language=str(metadata.get('L.E') or '')
            ))
    for bucket in groups.values():
        unique={}
        for err in bucket['errors']: unique[err['id']]=err
        bucket['errors']=sorted(unique.values(),key=lambda x:(x.get('date',''),x.get('simulation',''),x.get('question',0)))
    return groups

def _er_sync_target(app,c,user,target_id,HTTPError=None):
    target=_er_target(app,c,user,target_id,HTTPError)
    state=app.db.execute(c,'SELECT profile,version FROM hmay_state WHERE user_id=?',(target['id'],)).fetchone()
    if not state: raise ValueError('Planejamento do aluno não encontrado.')
    profile=_er_load(state['profile'],{})
    contents=profile.get('contents') if isinstance(profile.get('contents'),list) else []
    subjects=profile.get('subjects') if isinstance(profile.get('subjects'),list) else []
    subject_map={_er_norm(x.get('name')):x.get('id') for x in subjects if isinstance(x,dict) and x.get('id')}
    existing={x.get('sourceKey'):x for x in contents if isinstance(x,dict) and x.get('sourceType')=='exam_error' and x.get('sourceKey')}
    groups=_er_exam_errors(app,c,target['id'])
    auto_subjects=0
    for bucket in groups.values():
        discipline=str(bucket.get('discipline') or '').strip()
        discipline_key=_er_norm(discipline)
        if not discipline_key or discipline_key in subject_map:continue
        subject_id='sub_exam_'+_er_hash.sha1(discipline_key.encode('utf-8')).hexdigest()[:16]
        subjects.append(dict(id=subject_id,name=discipline,kind='study',action='Estudar e praticar',weeklyMin=90,difficulty=3,importance=3,priority=2,examDate='',active=True,reviewPlan='both',theoryReviewMin=10,exerciseReviewMin=20,preferredReviewDay=-1))
        subject_map[discipline_key]=subject_id;auto_subjects+=1
    profile['subjects']=subjects
    created=updated=0
    today=str(P.today())
    default_review=20
    try: default_review=max(10,min(180,int(profile.get('settings',{}).get('reviewMin',20))))
    except Exception: pass
    for key,bucket in groups.items():
        stable='examerr_'+_er_hash.sha1(key.encode('utf-8')).hexdigest()[:16]
        errors=bucket['errors']
        latest=max((x.get('date') or '' for x in errors),default='')
        first=min((x.get('date') or '' for x in errors),default='')
        subject_id=subject_map.get(_er_norm(bucket['discipline']),'')
        source_sims=sorted(set(x.get('simulation') for x in errors if x.get('simulation')))
        source_skills=sorted(set(x.get('skill') for x in errors if x.get('skill')))
        source_questions=sorted(set(int(x.get('question') or 0) for x in errors if x.get('question')))
        row=existing.get(stable) or existing.get(key)
        if row is None:
            row=dict(
                id=stable,subjectId=subject_id,title=bucket['title'],topic=bucket['topic'],
                status='studied',paused=False,studyMinutes=0,reviewMinutes=default_review,
                difficulty=3,studiedOn=latest or today,studiedTime='12:00',
                nextDue=today,stage=0,material='',notes='Gerado automaticamente a partir de erros de avaliações importadas.',
                sourceType='exam_error',sourceKey=stable,sourceDiscipline=bucket['discipline'],
                sourceArea=bucket['area'],examErrors=errors,errorCount=len(errors),
                firstErrorDate=first,lastErrorDate=latest,sourceSimulations=source_sims,
                sourceSkills=source_skills,sourceQuestions=source_questions
            )
            contents.append(row);existing[stable]=row;created+=1
        else:
            old_ids={x.get('id') for x in row.get('examErrors',[]) if isinstance(x,dict)}
            new_ids={x.get('id') for x in errors}
            added=bool(new_ids-old_ids)
            before=(row.get('errorCount'),row.get('lastErrorDate'),row.get('subjectId'),row.get('title'),old_ids)
            row.update(sourceKey=stable,sourceDiscipline=bucket['discipline'],sourceArea=bucket['area'],
                       examErrors=errors,errorCount=len(errors),firstErrorDate=first,lastErrorDate=latest,
                       sourceSimulations=source_sims,sourceSkills=source_skills,sourceQuestions=source_questions,
                       title=bucket['title'],topic=bucket['topic'])
            if subject_id: row['subjectId']=subject_id
            if added and not row.get('paused'):
                row['nextDue']=today
                try: row['stage']=max(0,min(1,int(row.get('stage',0))))
                except Exception: row['stage']=0
            after=(row.get('errorCount'),row.get('lastErrorDate'),row.get('subjectId'),row.get('title'),new_ids)
            if added or before!=after: updated+=1
    changed=bool(created or updated or auto_subjects)
    if changed:
        profile['contents']=contents
        app.db.execute(c,'UPDATE hmay_state SET profile=?,version=version+1,updated_at=? WHERE user_id=?',
                       (_er_json.dumps(profile,ensure_ascii=False,separators=(',',':')),P.now().isoformat(),target['id']))
        try: app.event(c,user,target['id'],'exam_error_reviews_sync')
        except Exception: pass
    return dict(changed=changed,created=created,updated=updated,groups=len(groups),
                errors=sum(len(x['errors']) for x in groups.values()),subjectsCreated=auto_subjects,targetId=target['id'])

_er_original_handle=handle
def handle(app,c,user,path,method,data,query,start,HTTPError):
    if path=='/api/model-data/review-errors-sync' and method=='POST':
        result=_er_sync_target(app,c,user,data.get('targetId') or user.get('id'),HTTPError)
        return app.reply(start,200,result)
    if path=='/api/model-data/review-errors-sync-batch' and method=='POST':
        ids=data.get('targetIds') if isinstance(data.get('targetIds'),list) else []
        results=[]
        seen=set()
        for target_id in ids[:500]:
            key=str(target_id or '')
            if not key or key in seen: continue
            seen.add(key)
            results.append(_er_sync_target(app,c,user,key,HTTPError))
        return app.reply(start,200,dict(results=results,changed=sum(1 for x in results if x.get('changed'))))
    return _er_original_handle(app,c,user,path,method,data,query,start,HTTPError)


# === QI TRI E REDACAO V1 ===
import base64 as _qi_b64

_TRI_ALIASES.update({
    'redactionTheme': {'tema', 'tema da redacao', 'tema redacao', 'proposta de redacao'},
    'c1': {'c1', 'nota c1', 'competencia 1', 'competencia i'},
    'c2': {'c2', 'nota c2', 'competencia 2', 'competencia ii'},
    'c3': {'c3', 'nota c3', 'competencia 3', 'competencia iii'},
    'c4': {'c4', 'nota c4', 'competencia 4', 'competencia iv'},
    'c5': {'c5', 'nota c5', 'competencia 5', 'competencia v'},
})
_TRI_META_KEYS.update({
    'c1': ('_redaction_c1', 'C1', 'NOTA C1', 'COMPETÊNCIA 1', 'COMPETENCIA 1'),
    'c2': ('_redaction_c2', 'C2', 'NOTA C2', 'COMPETÊNCIA 2', 'COMPETENCIA 2'),
    'c3': ('_redaction_c3', 'C3', 'NOTA C3', 'COMPETÊNCIA 3', 'COMPETENCIA 3'),
    'c4': ('_redaction_c4', 'C4', 'NOTA C4', 'COMPETÊNCIA 4', 'COMPETENCIA 4'),
    'c5': ('_redaction_c5', 'C5', 'NOTA C5', 'COMPETÊNCIA 5', 'COMPETENCIA 5'),
})
_QI_TRI_NUMERIC_KEYS = ('ranking', 'tri', 'triBonus', 'lc', 'ch', 'cn', 'mt', 'redaction', 'c1', 'c2', 'c3', 'c4', 'c5')
_QI_TRI_SIGNATURE_KEYS = _QI_TRI_NUMERIC_KEYS + ('redactionTheme',)


def _tri_detect_table(sheets):
    candidates = []
    accepted = ('tri', 'lc', 'ch', 'cn', 'mt', 'redaction', 'c1', 'c2', 'c3', 'c4', 'c5')
    for sheet_order, sheet in enumerate(sheets):
        rows = sheet['rows']
        for row_index in range(min(40, len(rows))):
            current = rows[row_index]
            next_row = rows[row_index + 1] if row_index + 1 < len(rows) else []
            width = max(len(current), len(next_row))
            combined = []
            for col in range(width):
                one = current[col] if col < len(current) else ''
                two = next_row[col] if col < len(next_row) else ''
                combined.append((str(one or '') + ' ' + str(two or '')).strip())
            for span, header in ((1, current), (2, combined)):
                columns = _tri_header_columns(header)
                score = 8 if 'name' in columns else 0
                score += 2 * sum(key in columns for key in accepted)
                score += int('ranking' in columns)
                preferred = _tri_norm(sheet['name']) in ('ranking', 'ranking geral', 'ranking geral alunos', 'tri e redacao', 'tri redacao')
                score += 4 if preferred else 0
                if 'name' in columns and any(key in columns for key in accepted):
                    candidates.append((score, -sheet_order, -row_index, sheet, row_index, span, columns, header))
    if not candidates:
        raise ValueError('Não encontrei NOME e colunas de TRI ou redação no arquivo.')
    candidates.sort(reverse=True, key=lambda item: item[:3])
    _, _, _, sheet, row_index, span, columns, header = candidates[0]
    return sheet, row_index, span, columns, header


def _tri_parse_ranking(data):
    sheets = _tri_xlsx_rows(data)
    sheet, header_row, header_span, columns, header = _tri_detect_table(sheets)
    records = []
    for source_index, row in enumerate(sheet['rows'][header_row + header_span:], start=header_row + header_span + 1):
        def value(key):
            index = columns.get(key)
            return row[index] if index is not None and index < len(row) else ''
        name = F.text(value('name'), 250)
        if not name:
            continue
        scores = {key: _tri_number(value(key)) for key in _QI_TRI_NUMERIC_KEYS}
        scores['redactionTheme'] = F.text(value('redactionTheme'), 500) or None
        competencies = [scores[key] for key in ('c1', 'c2', 'c3', 'c4', 'c5')]
        for index, number in enumerate(competencies, start=1):
            if number is not None and not 0 <= number <= 200:
                raise ValueError(f'Linha {source_index}: C{index} deve estar entre 0 e 200.')
        if scores['redaction'] is not None and not 0 <= scores['redaction'] <= 1000:
            raise ValueError(f'Linha {source_index}: a nota de redação deve estar entre 0 e 1000.')
        if all(number is not None for number in competencies):
            total = round(sum(competencies), 4)
            if scores['redaction'] is None:
                scores['redaction'] = total
            elif abs(scores['redaction'] - total) > .01:
                raise ValueError(f'Linha {source_index}: a nota de redação ({scores["redaction"]}) difere da soma C1–C5 ({total}).')
        if all(scores.get(key) is None for key in _QI_TRI_SIGNATURE_KEYS):
            continue
        if scores['tri'] is None and all(scores[key] is not None for key in ('lc', 'ch', 'cn', 'mt', 'redaction')):
            scores['tri'] = round(sum(scores[key] for key in ('lc', 'ch', 'cn', 'mt', 'redaction')) / 5, 3)
        records.append({
            'name': name,
            'nameKey': F.norm(name),
            'group': F.text(value('group'), 150),
            'activity': F.text(value('activity'), 200),
            'date': _tri_iso_date(value('date')),
            'language': F.text(value('language'), 40),
            'scores': scores,
            'line': source_index,
        })
    if not records:
        raise ValueError('A planilha foi encontrada, mas não contém notas TRI ou de redação preenchidas.')
    detected = {}
    for key, index in columns.items():
        detected[key] = F.text(header[index] if index < len(header) else '', 120)
    return {'sheet': sheet['name'], 'headerRow': header_row + 1, 'columns': detected, 'records': records}


def _tri_scores_from_metadata(metadata):
    result = {key: _tri_meta_number(metadata, key) for key in _TRI_META_KEYS}
    result['redactionTheme'] = F.text(
        metadata.get('_redaction_theme') or metadata.get('TEMA DA REDAÇÃO') or metadata.get('TEMA REDAÇÃO'), 500
    ) or None
    if result['tri'] is None and all(result[key] is not None for key in ('lc', 'ch', 'cn', 'mt', 'redaction')):
        result['tri'] = round(sum(result[key] for key in ('lc', 'ch', 'cn', 'mt', 'redaction')) / 5, 3)
    return result


def _tri_choose_record(records, activity, applied_on):
    if len(records) == 1:
        return records[0], ''
    dated = [row for row in records if row.get('date') == applied_on]
    if len(dated) == 1:
        return dated[0], ''
    if dated:
        records = dated
    activity_key = F.norm(activity)
    titled = [row for row in records if row.get('activity') and F.norm(row['activity']) == activity_key]
    if len(titled) == 1:
        return titled[0], ''
    if titled:
        records = titled
    signatures = {tuple(row['scores'].get(key) for key in _QI_TRI_SIGNATURE_KEYS) for row in records}
    if len(signatures) == 1:
        return records[0], ''
    return None, 'Há mais de uma linha para o mesmo nome e não foi possível escolher o simulado correto.'


def _tri_preview(app, c, data):
    parsed = _tri_parse_ranking(data)
    activity_key = F.text(data.get('activityKey'), 250)
    applied_on = F.date_value(data.get('date'))
    match = _tri_match(app, c, parsed, activity_key, applied_on)
    sample = []
    changed = unchanged = 0
    for pair in match['matched']:
        metadata = _rx_json(pair['target'].get('metadata'))
        old = _tri_scores_from_metadata(metadata)
        new = pair['source']['scores']
        has_change = any(new.get(key) is not None and old.get(key) != new.get(key) for key in new)
        changed += int(has_change); unchanged += int(not has_change)
        if len(sample) < 20:
            sample.append({
                'name': pair['target']['student_name'], 'login': pair['target']['student_login'],
                **{key: new.get(key) for key in _QI_TRI_SIGNATURE_KEYS}, 'changed': has_change,
            })
    return parsed, match, {
        'sheet': parsed['sheet'], 'sourceRows': len(parsed['records']),
        'students': len(match['targets']), 'matched': len(match['matched']),
        'changed': changed, 'unchanged': unchanged,
        'unmatched': len(match['unmatched']), 'conflicts': len(match['conflicts']),
        'withoutScore': len(match['withoutScore']), 'sample': sample,
    }


def _tri_apply_metadata(metadata, scores, source_sheet, user):
    changed = False
    numeric_mapping = {
        'ranking': '_ranking', 'tri': '_tri_general', 'triBonus': '_tri_bonus',
        'lc': '_tri_lc', 'ch': '_tri_ch', 'cn': '_tri_cn', 'mt': '_tri_mt',
        'redaction': '_tri_redaction', 'c1': '_redaction_c1', 'c2': '_redaction_c2',
        'c3': '_redaction_c3', 'c4': '_redaction_c4', 'c5': '_redaction_c5',
    }
    for key, destination in numeric_mapping.items():
        value = scores.get(key)
        if value is None:
            continue
        stored = int(value) if key == 'ranking' and float(value).is_integer() else round(float(value), 4)
        if metadata.get(destination) != stored:
            metadata[destination] = stored
            changed = True
    theme = F.text(scores.get('redactionTheme'), 500)
    if theme and metadata.get('_redaction_theme') != theme:
        metadata['_redaction_theme'] = theme
        changed = True
    if changed:
        metadata['_tri_source_sheet'] = source_sheet
        metadata['_tri_imported_at'] = P.now().isoformat()
        metadata['_tri_imported_by'] = user['id']
    return changed


def _qi_tri_template_workbook():
    headers = [
        'NOME', 'LOGIN (opcional)', 'NOME DO SIMULADO', 'DATA DE APLICAÇÃO', 'TURMA',
        'RANKING', 'NOTA TRI GERAL', 'TRI LINGUAGENS', 'TRI HUMANAS',
        'TRI NATUREZA', 'TRI MATEMÁTICA', 'NOTA COM BONIFICAÇÃO',
        'TEMA DA REDAÇÃO', 'C1', 'C2', 'C3', 'C4', 'C5', 'NOTA DA REDAÇÃO',
    ]
    rows = [['' for _ in headers] for _ in range(200)]
    help_headers = ['Campo', 'Orientação']
    help_rows = [
        ['NOME', 'Obrigatório. Deve corresponder ao nome usado no resultado já importado.'],
        ['LOGIN', 'Opcional. Serve apenas como apoio; o vínculo principal continua pelo nome.'],
        ['NOME DO SIMULADO', 'Informe o mesmo nome da avaliação já importada.'],
        ['DATA DE APLICAÇÃO', 'Use dd/mm/aaaa ou aaaa-mm-dd.'],
        ['RANKING', 'Posição do aluno no simulado, quando disponível.'],
        ['NOTA TRI GERAL', 'Nota oficial geral. Não é recalculada a partir dos acertos.'],
        ['TRI POR ÁREA', 'Linguagens, Humanas, Natureza e Matemática. Deixe vazio quando a área não foi aplicada.'],
        ['TEMA DA REDAÇÃO', 'Opcional. Texto do tema/proposta da redação.'],
        ['C1–C5', 'Cada competência deve estar entre 0 e 200.'],
        ['NOTA DA REDAÇÃO', 'De 0 a 1000. Se ficar vazia e C1–C5 estiverem completos, o sistema calcula a soma.'],
        ['REGRA DE ATUALIZAÇÃO', 'Campos vazios não apagam notas existentes. Respostas A–E, acertos, mapa de questões e cronograma são preservados.'],
        ['ARQUIVO', 'Use XLSX sem fórmulas, macros, proteção ou vínculos externos.'],
    ]
    output = T.export(headers, rows, first_name='TRI e Redação', extra_sheets=[('Como preencher', help_headers, help_rows)])
    if isinstance(output, tuple):
        output = next((item for item in output if isinstance(item, (bytes, bytearray))), None)
    if not isinstance(output, (bytes, bytearray)):
        raise ValueError('Não foi possível gerar o arquivo-modelo TRI e Redação.')
    return bytes(output)


_qi_tri_original_summary = student_summary

def student_summary(app, c, user, target):
    result = _qi_tri_original_summary(app, c, user, target)
    metadata_by_simulation = _tri_simulation_metadata(app, c, target['id'])
    for simulation in result.get('simulations', []):
        metadata = metadata_by_simulation.get((F.norm(simulation.get('activity')), simulation.get('date')), {})
        scores = _tri_scores_from_metadata(metadata)
        simulation['redaction'] = {
            'score': scores.get('redaction'), 'theme': scores.get('redactionTheme'),
            'c1': scores.get('c1'), 'c2': scores.get('c2'), 'c3': scores.get('c3'),
            'c4': scores.get('c4'), 'c5': scores.get('c5'),
        }
    return result


_qi_tri_original_handle = handle

def handle(app, c, user, path, method, data, query, start, HTTPError):
    if path == '/api/model-data/tri-template':
        _rx_role_guard(user, HTTPError)
        if method != 'POST':
            raise HTTPError(405, 'Use o botão Gerar modelo TRI + Redação.')
        workbook = _qi_tri_template_workbook()
        return app.reply(start, 200, {
            'filename': 'MODELO_TRI_E_REDACAO.xlsx',
            'mime': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            'file': _qi_b64.b64encode(workbook).decode('ascii'),
        })
    return _qi_tri_original_handle(app, c, user, path, method, data, query, start, HTTPError)

# === MEU CRONOGRAMA: DISCIPLINAS AUTOMATICAS DOS SIMULADOS V1 ===

# === TRI IMPORT TOKEN V1 ===
import os as _tri_tok_os
import time as _tri_tok_time
import hmac as _tri_tok_hmac
import hashlib as _tri_tok_hashlib
import base64 as _tri_tok_base64

_TRI_TOKEN_TTL_SECONDS = 1800
_TRI_TOKEN_BATCH_SIZE = 80
_TRI_TOKEN_SCORE_TO_META = {
    'ranking': '_ranking',
    'tri': '_tri_general',
    'triBonus': '_tri_bonus',
    'lc': '_tri_lc',
    'ch': '_tri_ch',
    'cn': '_tri_cn',
    'mt': '_tri_mt',
    'redaction': '_tri_redaction',
    'c1': '_redaction_c1',
    'c2': '_redaction_c2',
    'c3': '_redaction_c3',
    'c4': '_redaction_c4',
    'c5': '_redaction_c5',
    'redactionTheme': '_redaction_theme',
}

def _tri_token_b64e(raw):
    return _tri_tok_base64.urlsafe_b64encode(raw).decode('ascii').rstrip('=')

def _tri_token_b64d(value):
    value = str(value or '')
    value += '=' * (-len(value) % 4)
    return _tri_tok_base64.urlsafe_b64decode(value.encode('ascii'))

def _tri_token_secret():
    secret = _tri_tok_os.environ.get('SECRET_KEY', '')
    if not secret:
        raise RuntimeError('SECRET_KEY ausente; não é possível assinar a importação.')
    return secret.encode('utf-8')

def _tri_make_import_token(pairs, parsed, activity_key, applied_on, user, final=True):
    now = int(_tri_tok_time.time())
    records = []
    for pair in pairs:
        records.append({
            'id': str(pair['target']['id']),
            'scores': pair['source'].get('scores') or {},
        })
    payload = {
        'v': 1,
        'final': final,
        'actor': str(user.get('id') or ''),
        'activityKey': str(activity_key or ''),
        'date': str(applied_on or ''),
        'sheet': str(parsed.get('sheet') or ''),
        'iat': now,
        'exp': now + _TRI_TOKEN_TTL_SECONDS,
        'records': records,
    }
    raw = json.dumps(payload, ensure_ascii=False, separators=(',', ':'), sort_keys=True).encode('utf-8')
    signature = _tri_tok_hmac.new(_tri_token_secret(), raw, _tri_tok_hashlib.sha256).digest()
    return _tri_token_b64e(raw) + '.' + _tri_token_b64e(signature)

def _tri_read_import_token(token, user):
    token = str(token or '')
    if len(token) < 20 or len(token) > 1000000 or '.' not in token:
        raise ValueError('Pacote de importação inválido ou ausente.')
    encoded, signed = token.split('.', 1)
    raw = _tri_token_b64d(encoded)
    supplied = _tri_token_b64d(signed)
    expected = _tri_tok_hmac.new(_tri_token_secret(), raw, _tri_tok_hashlib.sha256).digest()
    if not _tri_tok_hmac.compare_digest(supplied, expected):
        raise ValueError('A assinatura da importação é inválida. Gere uma nova conferência.')
    try:
        payload = json.loads(raw.decode('utf-8'))
    except Exception as exc:
        raise ValueError('O pacote de importação está corrompido.') from exc
    if not isinstance(payload, dict) or payload.get('v') != 1:
        raise ValueError('Versão do pacote de importação não suportada.')
    if str(payload.get('actor') or '') != str(user.get('id') or ''):
        raise ValueError('Este pacote pertence a outra sessão de usuário.')
    if int(payload.get('exp') or 0) < int(_tri_tok_time.time()):
        raise ValueError('A conferência expirou. Confira os vínculos novamente antes de salvar.')
    records = payload.get('records')
    if not isinstance(records, list) or not records:
        raise ValueError('O pacote não possui registros para salvar.')
    if len(records) > 5000:
        raise ValueError('Quantidade de registros acima do limite de segurança.')
    return payload

def _tri_token_fetch_targets(app, c, ids, lock=False):
    rows = {}
    for offset in range(0, len(ids), 500):
        chunk = ids[offset:offset + 500]
        placeholders = ','.join('?' for _ in chunk)
        query = (
            'SELECT id,activity_key,applied_on,metadata FROM hmay_performance '
            'WHERE id IN (' + placeholders + ')'
        )
        if lock and not app.db.local_path:
            query += ' ORDER BY id FOR UPDATE'
        for row in app.db.execute(c, query, tuple(chunk)).fetchall():
            item = dict(row)
            rows[str(item['id'])] = item
    return rows

def _tri_token_verify_metadata(app, c, ids, records):
    targets = _tri_token_fetch_targets(app, c, ids)
    expected = {key: 0 for key in _TRI_TOKEN_SCORE_TO_META}
    actual = {key: 0 for key in _TRI_TOKEN_SCORE_TO_META}
    source_by_id = {str(item['id']): item.get('scores') or {} for item in records}
    for record_id, scores in source_by_id.items():
        if record_id not in targets:
            raise ValueError('Um resultado deixou de existir durante a gravação.')
        metadata = _rx_json(targets[record_id].get('metadata'))
        if _tri_apply_metadata(dict(metadata), scores, '', {'id': ''}):
            raise ValueError('As notas lidas no banco diferem das notas enviadas.')
        for score_key, meta_key in _TRI_TOKEN_SCORE_TO_META.items():
            source_value = scores.get(score_key)
            if source_value is None or source_value == '':
                continue
            expected[score_key] += 1
            stored = metadata.get(meta_key)
            if stored is not None and stored != '':
                actual[score_key] += 1
    return {
        key: {'expected': expected[key], 'stored': actual[key]}
        for key in expected
        if expected[key]
    }

_tri_token_original_handle = handle

def handle(app, c, user, path, method, data, query, start, HTTPError):
    if path == '/api/model-data/tri-coverage' and method == 'GET':
        _rx_role_guard(user, HTTPError)
        json_field = ("json_extract(p.metadata, '$.%s')" if app.db.local_path
                      else "(p.metadata::jsonb ->> '%s')")
        stamp = json_field % '_tri_imported_at'
        exam = json_field % '_exam_id'
        rows = app.db.execute(c, (
            "SELECT MIN(p.activity) AS activity, p.applied_on AS date, "
            "COUNT(DISTINCT p.user_id) AS total, "
            f"COUNT(DISTINCT CASE WHEN NULLIF({stamp}, '') IS NOT NULL THEN p.user_id END) AS saved "
            "FROM hmay_performance p JOIN hmay_users u ON u.id=p.user_id "
            f"WHERE u.role IN ('user','aluno') AND NULLIF({exam}, '') IS NOT NULL "
            "GROUP BY p.activity_key, p.applied_on ORDER BY p.applied_on DESC, MIN(p.activity)"
        )).fetchall()
        return app.reply(start, 200, {'simulations': [dict(row) for row in rows]})

    if path == '/api/model-data/tri-preview':
        _rx_role_guard(user, HTTPError)
        parsed, match, preview = _tri_preview(app, c, data)
        activity_key = F.text(data.get('activityKey'), 250)
        applied_on = F.date_value(data.get('date'))
        preview['unmatchedNames'] = match['unmatched'][:50]
        preview['conflictRows'] = match['conflicts'][:50]
        preview['withoutScoreNames'] = match['withoutScore'][:50]
        pairs = match['matched']
        if len(pairs) > 5000:
            raise ValueError('A conferência excede o limite de 5.000 registros.')
        if data.get('batchMode') is True:
            preview['batches'] = []
            for offset in range(0, len(pairs), _TRI_TOKEN_BATCH_SIZE):
                batch = pairs[offset:offset + _TRI_TOKEN_BATCH_SIZE]
                token = _tri_make_import_token(batch, parsed, activity_key, applied_on, user,
                                               final=(offset + len(batch) == len(pairs)))
                preview['batches'].append({'count': len(batch), 'importToken': token})
        else:
            preview['importToken'] = _tri_make_import_token(pairs, parsed, activity_key, applied_on, user)
        preview['tokenExpiresMinutes'] = _TRI_TOKEN_TTL_SECONDS // 60
        print(
            f'MEUCRONOGRAMA_TRI_TOKEN_PREVIEW matched={len(match["matched"])} token_records={len(match["matched"])}',
            flush=True,
        )
        return app.reply(start, 200, preview)


    if path == '/api/model-data/tri-confirm-prepare':
        _rx_role_guard(user, HTTPError)
        payload = _tri_read_import_token(data.get('importToken'), user)
        records = payload['records']
        ids = [str(item.get('id') or '') for item in records]
        if any(not item for item in ids) or len(set(ids)) != len(ids):
            raise ValueError('O pacote contém identificadores inválidos ou duplicados.')

        targets = _tri_token_fetch_targets(app, c, ids)
        if len(targets) != len(ids):
            raise ValueError('Um ou mais resultados vinculados não existem mais no banco.')

        activity_key = str(payload.get('activityKey') or '')
        applied_on = str(payload.get('date') or '')
        for record_id in ids:
            target = targets[record_id]
            if str(target.get('activity_key') or '') != activity_key or str(target.get('applied_on') or '') != applied_on:
                raise ValueError('O pacote não corresponde mais ao simulado selecionado.')

        print(
            f'MEUCRONOGRAMA_TRI_TOKEN_RECEIVED records={len(records)} activity={activity_key} date={applied_on}',
            flush=True,
        )
        return app.reply(start, 200, {
            'ready': True,
            'receivedRecords': len(records),
            'activityKey': activity_key,
            'date': applied_on,
        })

    if path == '/api/model-data/tri-confirm':
        _rx_role_guard(user, HTTPError)
        payload = _tri_read_import_token(data.get('importToken'), user)
        records = payload['records']
        ids = [str(item.get('id') or '') for item in records]
        if any(not item for item in ids) or len(set(ids)) != len(ids):
            raise ValueError('O pacote contém identificadores inválidos ou duplicados.')

        targets = _tri_token_fetch_targets(app, c, sorted(ids), lock=True)
        if len(targets) != len(ids):
            raise ValueError('Um ou mais resultados vinculados não existem mais no banco.')

        activity_key = str(payload.get('activityKey') or '')
        applied_on = str(payload.get('date') or '')
        for record_id in ids:
            target = targets[record_id]
            if str(target.get('activity_key') or '') != activity_key or str(target.get('applied_on') or '') != applied_on:
                raise ValueError('O pacote não corresponde mais ao simulado selecionado.')

        pending = []
        unchanged = 0
        for item in records:
            record_id = str(item['id'])
            metadata = _rx_json(targets[record_id].get('metadata'))
            if _tri_apply_metadata(
                metadata,
                item.get('scores') or {},
                str(payload.get('sheet') or ''),
                user,
            ):
                pending.append((
                    record_id,
                    json.dumps(metadata, ensure_ascii=False, separators=(',', ':')),
                ))
            else:
                unchanged += 1

        print(
            f'MEUCRONOGRAMA_TRI_TOKEN_CONFIRM_RECEIVED records={len(records)} pending={len(pending)} unchanged={unchanged}',
            flush=True,
        )

        updated = 0
        stamp = P.now().isoformat()
        for offset in range(0, len(pending), _TRI_TOKEN_BATCH_SIZE):
            chunk = pending[offset:offset + _TRI_TOKEN_BATCH_SIZE]
            cases = ' '.join('WHEN ? THEN ?' for _ in chunk)
            placeholders = ','.join('?' for _ in chunk)
            params = []
            for row_id, metadata_json in chunk:
                params.extend((row_id, metadata_json))
            params.append(stamp)
            params.extend(row_id for row_id, _ in chunk)
            sql = (
                'UPDATE hmay_performance SET metadata=CASE id ' + cases +
                ' ELSE metadata END,updated_at=? WHERE id IN (' + placeholders + ')'
            )
            app.db.execute(c, sql, tuple(params))
            updated += len(chunk)
            print(
                f'MEUCRONOGRAMA_TRI_TOKEN_BATCH_DONE updated={updated}/{len(pending)}',
                flush=True,
            )

        verification = _tri_token_verify_metadata(app, c, ids, records)
        mismatches = {
            key: value for key, value in verification.items()
            if value['expected'] != value['stored']
        }
        if mismatches:
            raise RuntimeError('A verificação final das notas no banco não coincidiu com o pacote enviado.')

        if payload.get('final', True):
            app.event(c, user, user['id'], 'tri_scores_import')
        print(
            f'MEUCRONOGRAMA_TRI_TOKEN_DONE updated={updated} unchanged={unchanged} verified={len(records)}',
            flush=True,
        )
        return app.reply(start, 200, {
            'summary': {
                'updated': updated,
                'unchanged': unchanged,
                'matched': len(records),
                'unmatched': 0,
                'conflicts': 0,
                'withoutScore': 0,
            },
            'verification': verification,
            'verifiedRecords': len(records),
            'tokenMode': True,
        })

    return _tri_token_original_handle(app, c, user, path, method, data, query, start, HTTPError)

# === TRI DASHBOARD V3.3 ===
_tri_dashboard_original_summary = student_summary

def student_summary(app, c, user, target):
    result = _tri_dashboard_original_summary(app, c, user, target)
    metadata_by_simulation = _tri_simulation_metadata(app, c, target['id'])
    for simulation in result.get('simulations', []):
        metadata = metadata_by_simulation.get(
            (F.norm(simulation.get('activity')), simulation.get('date')),
            {},
        )
        scores = _tri_scores_from_metadata(metadata)
        simulation['triScores'] = {
            'ranking': scores.get('ranking'),
            'general': scores.get('tri'),
            'bonus': scores.get('triBonus'),
            'lc': scores.get('lc'),
            'ch': scores.get('ch'),
            'cn': scores.get('cn'),
            'mt': scores.get('mt'),
            'redaction': scores.get('redaction'),
        }
    return result

# === PERFORMANCE REFINEMENT V3.4 ===
_performance_refinement_original_handle = handle

import exam_metadata as _exam_metadata

def handle(app, c, user, path, method, data, query, start, HTTPError):
    if path == '/api/model-data/exam-edit-list':
        if not _exam_metadata.can_edit(user):
            raise HTTPError(403, 'O cadastro de mapas é exclusivo do Master e da coordenação.')
        if method != 'GET':
            raise HTTPError(405, 'Use GET para listar os mapas.')
        return app.reply(start, 200, {'exams': _exam_metadata.catalogue(app, c, user)})

    if path in ('/api/model-data/exam-date-update', '/api/model-data/exam-metadata-update'):
        if method != 'POST':
            raise HTTPError(405, 'Use POST para editar o caderno.')
        result = _exam_metadata.update(app, c, user, data, HTTPError,
                                       date_only=path.endswith('/exam-date-update'))
        return app.reply(start, 200, result)

    return _performance_refinement_original_handle(app, c, user, path, method, data, query, start, HTTPError)

# === MANAGEMENT DASHBOARD V3.5 ===
_management_dashboard_original_handle = handle

def _mgmt_mean(values):
    vals=[]
    for value in values:
        try:
            if value is not None and value != '':
                vals.append(float(value))
        except Exception:
            pass
    return None if not vals else round(sum(vals)/len(vals),3)

def _mgmt_area_key(name):
    raw=F.norm(name or '')
    if raw in ('lc','linguagens') or 'lingu' in raw:
        return 'LC'
    if raw in ('ch','humanas') or 'human' in raw:
        return 'CH'
    if raw in ('cn','natureza') or 'nature' in raw:
        return 'CN'
    if raw in ('mt','matematica') or 'matem' in raw:
        return 'MT'
    return None

def _mgmt_dashboard_data(app,c,user,query):
    if user.get('role') not in ('master','coordenador'):
        raise ValueError('Painel gerencial exclusivo do Master e da coordenação.')

    requested_year=F.text((query or {}).get('year'),4)
    requested_turma=F.text((query or {}).get('turma'),160)
    requested_activity=F.text((query or {}).get('activityKey'),250)
    requested_date=F.text((query or {}).get('date'),40)

    active_students=app.db.execute(
        c,"SELECT COUNT(*) AS n FROM hmay_users WHERE role IN ('user','aluno') AND active=1"
    ).fetchone()['n']

    raw_rows=app.db.execute(
        c,
        """SELECT p.id,p.user_id,p.activity_key,p.activity,p.applied_on,p.metrics,p.metadata
           FROM hmay_performance p
           JOIN hmay_users u ON u.id=p.user_id
           WHERE u.role IN ('user','aluno') AND u.active=1
           ORDER BY p.applied_on,p.activity,u.name,u.username"""
    ).fetchall()

    turmas=set()
    years=set()
    sim_options={}
    prepared=[]
    for raw in raw_rows:
        row=dict(raw)
        metadata=_rx_json(row.get('metadata'))
        turma=F.text(metadata.get('TURMA'),160) or 'Sem turma'
        turmas.add(turma)
        date=F.text(row.get('applied_on'),40)
        if len(date)>=4:
            years.add(date[:4])
        sim_options[(row.get('activity_key',''),date)]={
            'activityKey':row.get('activity_key',''),
            'activity':row.get('activity',''),
            'date':date,
        }
        prepared.append((row,metadata,turma))

    exam_rows=app.db.execute(
        c,'SELECT id,title,applied_on,color FROM hmay_exams ORDER BY applied_on,title,color'
    ).fetchall()
    maps_count=0
    catalog_sims=set()
    for exam in exam_rows:
        date=F.text(exam['applied_on'],40)
        if requested_year and not date.startswith(requested_year):
            continue
        maps_count+=1
        catalog_sims.add((F.norm(exam['title']),date))

    filtered=[]
    for row,metadata,turma in prepared:
        date=F.text(row.get('applied_on'),40)
        if requested_year and not date.startswith(requested_year):
            continue
        if requested_turma and turma != requested_turma:
            continue
        if requested_activity and row.get('activity_key') != requested_activity:
            continue
        if requested_date and date != requested_date:
            continue
        filtered.append((row,metadata,turma))

    exam_cache={}
    participants=set()
    total_correct=total_marked=total_valid=0
    tri_general=[]
    redactions=[]
    areas={key:{'correct':0,'marked':0,'valid':0,'tri':[]} for key in ('LC','CH','CN','MT')}
    simulations={}
    classes={}

    for row,metadata,turma in filtered:
        exam_id=F.text(metadata.get('_exam_id'),160)
        if not exam_id:
            continue
        if exam_id not in exam_cache:
            exam_cache[exam_id]=E.get_exam(app,c,exam_id)
        exam=exam_cache.get(exam_id)
        if not exam:
            continue

        analysis=_rx_analyse(exam,_rx_json(row.get('metrics')),metadata)
        overall=analysis['overall']
        participants.add(row['user_id'])
        correct=max(0,int(overall.get('correct') or 0))
        marked=max(0,int(overall.get('marked') or 0))
        valid=max(0,int(overall.get('total') or 0))
        total_correct+=correct
        total_marked+=marked
        total_valid+=valid

        scores=_tri_scores_from_metadata(metadata)
        if scores.get('tri') is not None:
            tri_general.append(scores['tri'])
        if scores.get('redaction') is not None:
            redactions.append(scores['redaction'])

        skey=(row['activity_key'],row['applied_on'])
        sim=simulations.setdefault(skey,{
            'activityKey':row['activity_key'],'activity':row['activity'],'date':row['applied_on'],
            'participants':set(),'correct':0,'marked':0,'valid':0,
            'triGeneral':[],'lc':[],'ch':[],'cn':[],'mt':[],'redaction':[],
        })
        sim['participants'].add(row['user_id'])
        sim['correct']+=correct;sim['marked']+=marked;sim['valid']+=valid

        cls=classes.setdefault(turma,{
            'turma':turma,'participants':set(),'correct':0,'marked':0,'valid':0,
            'triGeneral':[],'redaction':[],
        })
        cls['participants'].add(row['user_id'])
        cls['correct']+=correct;cls['marked']+=marked;cls['valid']+=valid

        for key,value in (
            ('triGeneral',scores.get('tri')),('lc',scores.get('lc')),('ch',scores.get('ch')),
            ('cn',scores.get('cn')),('mt',scores.get('mt')),('redaction',scores.get('redaction'))
        ):
            if value is not None:
                sim[key].append(value)
        if scores.get('tri') is not None:
            cls['triGeneral'].append(scores['tri'])
        if scores.get('redaction') is not None:
            cls['redaction'].append(scores['redaction'])

        for item in analysis['groups'].get('Área',[]):
            key=_mgmt_area_key(item.get('name'))
            if not key:
                continue
            bucket=areas[key]
            bucket['correct']+=max(0,int(item.get('correct') or 0))
            bucket['marked']+=max(0,int(item.get('marked') or 0))
            bucket['valid']+=max(0,int(item.get('total') or 0))
        for area_key,score_key in (('LC','lc'),('CH','ch'),('CN','cn'),('MT','mt')):
            value=scores.get(score_key)
            if value is not None:
                areas[area_key]['tri'].append(value)

    sim_rows=[]
    for sim in simulations.values():
        sim_rows.append({
            'activityKey':sim['activityKey'],'activity':sim['activity'],'date':sim['date'],
            'participants':len(sim['participants']),'correct':sim['correct'],'valid':sim['valid'],
            'accuracy':None if not sim['marked'] else round(100*sim['correct']/sim['marked'],2),
            'triGeneral':_mgmt_mean(sim['triGeneral']),'lc':_mgmt_mean(sim['lc']),
            'ch':_mgmt_mean(sim['ch']),'cn':_mgmt_mean(sim['cn']),'mt':_mgmt_mean(sim['mt']),
            'redaction':_mgmt_mean(sim['redaction']),
        })
    sim_rows.sort(key=lambda x:(x['date'],F.norm(x['activity'])),reverse=True)

    class_rows=[]
    for cls in classes.values():
        class_rows.append({
            'turma':cls['turma'],'participants':len(cls['participants']),
            'correct':cls['correct'],'valid':cls['valid'],
            'accuracy':None if not cls['marked'] else round(100*cls['correct']/cls['marked'],2),
            'triGeneral':_mgmt_mean(cls['triGeneral']),'redaction':_mgmt_mean(cls['redaction']),
        })
    class_rows.sort(key=lambda x:(-(x['participants'] or 0),F.norm(x['turma'])))

    area_rows=[]
    for key,label in (('LC','Linguagens'),('CH','Humanas'),('CN','Natureza'),('MT','Matemática')):
        bucket=areas[key]
        area_rows.append({
            'key':key,'name':label,'correct':bucket['correct'],'valid':bucket['valid'],
            'accuracy':None if not bucket['marked'] else round(100*bucket['correct']/bucket['marked'],2),
            'tri':_mgmt_mean(bucket['tri']),
        })

    options=sorted(sim_options.values(),key=lambda x:(x['date'],F.norm(x['activity'])),reverse=True)
    return {
        'filters':{
            'years':sorted(years,reverse=True),
            'turmas':sorted(turmas,key=F.norm),
            'simulations':options,
            'selected':{
                'year':requested_year,'turma':requested_turma,
                'activityKey':requested_activity,'date':requested_date,
            },
        },
        'kpis':{
            'activeStudents':active_students,'participants':len(participants),
            'catalogSimulations':len(catalog_sims),'maps':maps_count,
            'simulationsWithResults':len(sim_rows),'participations':len(filtered),
            'correct':total_correct,'valid':total_valid,
            'accuracy':None if not total_marked else round(100*total_correct/total_marked,2),
            'triGeneral':_mgmt_mean(tri_general),'redaction':_mgmt_mean(redactions),
        },
        'areas':area_rows,'simulations':sim_rows,'classes':class_rows,
    }

def handle(app,c,user,path,method,data,query,start,HTTPError):
    if path == '/api/model-data/management-dashboard':
        if user.get('role') not in ('master','coordenador'):
            raise HTTPError(403,'Painel gerencial exclusivo do Master e da coordenação.')
        if method != 'GET':
            raise HTTPError(405,'Use GET para consultar o painel gerencial.')
        return app.reply(start,200,_mgmt_dashboard_data(app,c,user,query))
    return _management_dashboard_original_handle(app,c,user,path,method,data,query,start,HTTPError)

# === MANAGEMENT REFINEMENT V3.6 ===
import json as _v36_json
import re as _v36_re
import time as _v36_time
import uuid as _v36_uuid

_v36_classes_ready=False
_v36_dashboard_cache={}

def _v36_classes_ensure(app,c):
    global _v36_classes_ready
    # Lembra por banco (e não por processo): nos testes, cada caso usa um banco novo.
    database=str(getattr(app.db,'local_path',None) or getattr(app.db,'url','') or id(app.db))
    if _v36_classes_ready==database:
        return
    app.db.execute(c, """CREATE TABLE IF NOT EXISTS hmay_classes(
        id text PRIMARY KEY,
        name text NOT NULL UNIQUE,
        norm text NOT NULL UNIQUE,
        aliases text NOT NULL DEFAULT '[]',
        active integer NOT NULL DEFAULT 1,
        created_at text NOT NULL,
        updated_at text NOT NULL
    )""")
    _v36_classes_ready=database

def _v36_class_rows(app,c,active_only=False):
    _v36_classes_ensure(app,c)
    sql='SELECT id,name,norm,aliases,active,created_at,updated_at FROM hmay_classes'
    if active_only:
        sql+=' WHERE active=1'
    sql+=' ORDER BY lower(name)'
    rows=[]
    for raw in app.db.execute(c,sql).fetchall():
        row=dict(raw)
        try:
            aliases=_v36_json.loads(row.get('aliases') or '[]')
        except Exception:
            aliases=[]
        if not isinstance(aliases,list):
            aliases=[]
        row['aliases']=[F.text(x,160) for x in aliases if F.text(x,160)]
        rows.append(row)
    return rows

def _v36_class_lookup(app,c):
    lookup={}
    for row in _v36_class_rows(app,c,True):
        lookup[F.norm(row['name'])]=row['name']
        for alias in row['aliases']:
            lookup[F.norm(alias)]=row['name']
    return lookup

def _v36_validate_class_names(app,c,names,source_label):
    lookup=_v36_class_lookup(app,c)
    invalid=[]
    for value in names:
        raw=F.text(value,160)
        if not raw:
            invalid.append('(sem turma)')
        elif F.norm(raw) not in lookup:
            invalid.append(raw)
    invalid=sorted(set(invalid),key=F.norm)
    if invalid:
        shown=', '.join(invalid[:20])
        extra='' if len(invalid)<=20 else f' e mais {len(invalid)-20}'
        raise ValueError(
            f'{source_label}: turma(s) não cadastrada(s): {shown}{extra}. '
            'Cadastre a turma ou ajuste o nome/alias no Painel de bordo antes de importar.'
        )

def _v317_class_issues(app,c,parsed):
    """Turmas não cadastradas viram divergências corrigíveis (v3.17.0).

    Um nome desconhecido aparece uma vez só, com a lista de turmas cadastradas: a escolha
    troca o nome em todas as linhas da coluna TURMA. Linhas sem turma aparecem uma a uma.
    """
    lookup=_v36_class_lookup(app,c)
    names=[row['name'] for row in _v36_class_rows(app,c,True)]
    columns=parsed.get('columns') or {}
    col=(columns.get('students') or {}).get('class')
    header=columns.get('studentHeader') or []
    label=header[col] if col is not None and col<len(header) else 'TURMA'
    issues=[];unknown={}
    for student in parsed.get('students',[]):
        raw=F.text(student.get('group'),160)
        if not raw:
            if col is not None:
                issues.append(_IF.issue(STUDENTS_SHEET,student['line'],col,label,'',
                                        f'DADOS DOS ALUNOS · linha {student["line"]}: informe a turma do aluno {student["name"]}.',names))
            continue
        if F.norm(raw) not in lookup:
            unknown.setdefault(F.norm(raw),[raw,0])[1]+=1
    if col is None and parsed.get('students'):
        issues=[_IF.general('DADOS DOS ALUNOS não tem a coluna TURMA. Inclua a coluna no arquivo e envie de novo.')]
    for raw,count in sorted(unknown.values(),key=lambda x:F.norm(x[0])):
        issues.append(_IF.issue(STUDENTS_SHEET,None,col,label,raw,
                                f'Turma "{raw}" não está cadastrada ({count} aluno(s)). Escolha a turma cadastrada correspondente '
                                '(a troca vale para todas as linhas com esse nome) ou cadastre a turma no Painel de bordo.',
                                names,kind='replace'))
    if issues:
        raise _IF.ImportIssues(issues)

def _v36_class_payload(app,c):
    rows=_v36_class_rows(app,c,False)
    lookup=_v36_class_lookup(app,c)
    detected=[]
    for raw in app.db.execute(c,'SELECT metadata FROM hmay_performance').fetchall():
        meta=_rx_json(raw['metadata'])
        name=F.text(meta.get('TURMA'),160) or '(sem turma)'
        detected.append(name)
    counts={}
    for name in detected:
        counts[name]=counts.get(name,0)+1
    unregistered=[
        {'name':name,'records':count}
        for name,count in sorted(counts.items(),key=lambda x:F.norm(x[0]))
        if name=='(sem turma)' or F.norm(name) not in lookup
    ]
    return {'classes':rows,'unregistered':unregistered}

def _v36_save_class(app,c,user,data):
    rows=_v36_class_rows(app,c,False)
    class_id=F.text(data.get('id'),160)
    name=F.text(data.get('name'),160)
    if not name:
        raise ValueError('Informe o nome oficial da turma.')
    aliases_raw=data.get('aliases')
    if isinstance(aliases_raw,str):
        aliases=[F.text(x,160) for x in _v36_re.split(r'[,;\n]+',aliases_raw) if F.text(x,160)]
    elif isinstance(aliases_raw,list):
        aliases=[F.text(x,160) for x in aliases_raw if F.text(x,160)]
    else:
        aliases=[]
    aliases=sorted({x for x in aliases if F.norm(x)!=F.norm(name)},key=F.norm)
    active=1 if data.get('active',True) else 0
    claimed={}
    for row in rows:
        if class_id and row['id']==class_id:
            continue
        if row['active']:
            claimed[F.norm(row['name'])]=row['name']
            for alias in row['aliases']:
                claimed[F.norm(alias)]=row['name']
    for candidate in [name]+aliases:
        owner=claimed.get(F.norm(candidate))
        if owner:
            raise ValueError(f'O nome/alias "{candidate}" já pertence à turma "{owner}".')
    stamp=P.now().isoformat()
    if class_id:
        exists=app.db.execute(c,'SELECT id FROM hmay_classes WHERE id=?',(class_id,)).fetchone()
        if not exists:
            raise ValueError('Turma não encontrada.')
        app.db.execute(
            c,'UPDATE hmay_classes SET name=?,norm=?,aliases=?,active=?,updated_at=? WHERE id=?',
            (name,F.norm(name),_v36_json.dumps(aliases,ensure_ascii=False),active,stamp,class_id),
        )
    else:
        class_id='cls_'+_v36_uuid.uuid4().hex
        app.db.execute(
            c,'INSERT INTO hmay_classes(id,name,norm,aliases,active,created_at,updated_at) VALUES (?,?,?,?,?,?,?)',
            (class_id,name,F.norm(name),_v36_json.dumps(aliases,ensure_ascii=False),active,stamp,stamp),
        )
    _v36_dashboard_cache.clear()
    app.event(c,user,user['id'],'class_registry_update')
    return {'id':class_id,'name':name,'aliases':aliases,'active':bool(active)}

def _v36_metric_number(key):
    try:
        return int(str(key).split(':')[-1])
    except Exception:
        return None

def _v36_exam_area_maps(app,c):
    result={}
    for raw in app.db.execute(c,'SELECT id,items FROM hmay_exams').fetchall():
        items=_rx_json(raw['items'])
        qmap={}
        if isinstance(items,list):
            for item in items:
                if not isinstance(item,dict):
                    continue
                try:
                    number=int(item.get('number'))
                except Exception:
                    continue
                area=_mgmt_area_key(item.get('area'))
                if area:
                    qmap[number]=area
        result[raw['id']]=qmap
    return result

def _v36_data_stamp(app,c):
    perf=app.db.execute(c,"SELECT COUNT(*) AS n,COALESCE(MAX(updated_at),'') AS stamp FROM hmay_performance").fetchone()
    exams=app.db.execute(c,"SELECT COUNT(*) AS n,COALESCE(MAX(updated_at),'') AS stamp FROM hmay_exams").fetchone()
    _v36_classes_ensure(app,c)
    classes=app.db.execute(c,"SELECT COUNT(*) AS n,COALESCE(MAX(updated_at),'') AS stamp FROM hmay_classes").fetchone()
    return f"{perf['n']}:{perf['stamp']}|{exams['n']}:{exams['stamp']}|{classes['n']}:{classes['stamp']}"

_mgmt_dashboard_data_v35=_mgmt_dashboard_data

def _mgmt_dashboard_data(app,c,user,query):
    if user.get('role') not in ('master','coordenador'):
        raise ValueError('Painel gerencial exclusivo do Master e da coordenação.')
    selected={
        'year':F.text((query or {}).get('year'),4),
        'turma':F.text((query or {}).get('turma'),160),
        'activityKey':F.text((query or {}).get('activityKey'),250),
        'date':F.text((query or {}).get('date'),40),
    }
    stamp=_v36_data_stamp(app,c)
    cache_key=(stamp,selected['year'],selected['turma'],selected['activityKey'],selected['date'])
    cached=_v36_dashboard_cache.get(cache_key)
    if cached and _v36_time.time()-cached[0] < 180:
        return cached[1]

    class_rows=_v36_class_rows(app,c,True)
    class_lookup=_v36_class_lookup(app,c)
    active_students=app.db.execute(
        c,"SELECT COUNT(*) AS n FROM hmay_users WHERE role IN ('user','aluno') AND active=1"
    ).fetchone()['n']
    conditions=["u.role IN ('user','aluno')","u.active=1"]
    args=[]
    if selected['year']:
        conditions.append('p.applied_on LIKE ?');args.append(selected['year']+'%')
    if selected['activityKey']:
        conditions.append('p.activity_key=?');args.append(selected['activityKey'])
    if selected['date']:
        conditions.append('p.applied_on=?');args.append(selected['date'])
    raw_rows=app.db.execute(
        c,
        """SELECT p.id,p.user_id,p.activity_key,p.activity,p.applied_on,p.metrics,p.metadata
           FROM hmay_performance p JOIN hmay_users u ON u.id=p.user_id
           WHERE """+' AND '.join(conditions)+' ORDER BY p.applied_on,p.activity',
        tuple(args),
    ).fetchall()

    area_maps=_v36_exam_area_maps(app,c)
    participants=set();total_correct=0;total_valid=0
    tri_general=[];redactions=[]
    areas={key:{'correct':0,'valid':0,'tri':[]} for key in ('LC','CH','CN','MT')}
    simulations={};classes={};years=set();sim_options={};participations=0

    for raw in raw_rows:
        row=dict(raw);metadata=_rx_json(row.get('metadata'))
        raw_class=F.text(metadata.get('TURMA'),160) or 'Sem turma'
        canonical=class_lookup.get(F.norm(raw_class),raw_class)
        if selected['turma'] and canonical!=selected['turma']:
            continue
        date=F.text(row.get('applied_on'),40)
        if len(date)>=4:
            years.add(date[:4])
        sim_options[(row['activity_key'],date)]={'activityKey':row['activity_key'],'activity':row['activity'],'date':date}
        participants.add(row['user_id']);participations+=1

        metrics=_rx_json(row.get('metrics'))
        if not isinstance(metrics,dict):
            metrics={}
        qmap=area_maps.get(F.text(metadata.get('_exam_id'),160),{})
        row_correct=0;row_valid=0
        row_area={key:{'correct':0,'valid':0} for key in ('LC','CH','CN','MT')}
        for mkey,mval in metrics.items():
            if not isinstance(mval,dict):
                continue
            try:
                correct=max(0,int(mval.get('correct') or 0))
                valid=max(0,int(mval.get('total') or 0))
            except Exception:
                continue
            row_correct+=correct;row_valid+=valid
            number=_v36_metric_number(mkey)
            area=qmap.get(number)
            if not area and number:
                area='LC' if number<=45 else 'CH' if number<=90 else 'CN' if number<=135 else 'MT' if number<=180 else None
            if area in row_area:
                row_area[area]['correct']+=correct;row_area[area]['valid']+=valid
        total_correct+=row_correct;total_valid+=row_valid

        scores=_tri_scores_from_metadata(metadata)
        if scores.get('tri') is not None: tri_general.append(scores['tri'])
        if scores.get('redaction') is not None: redactions.append(scores['redaction'])

        skey=(row['activity_key'],date)
        sim=simulations.setdefault(skey,{'activityKey':row['activity_key'],'activity':row['activity'],'date':date,'participants':set(),'correct':0,'valid':0,'triGeneral':[],'lc':[],'ch':[],'cn':[],'mt':[],'redaction':[]})
        sim['participants'].add(row['user_id']);sim['correct']+=row_correct;sim['valid']+=row_valid
        cls=classes.setdefault(canonical,{'turma':canonical,'participants':set(),'correct':0,'valid':0,'triGeneral':[],'redaction':[]})
        cls['participants'].add(row['user_id']);cls['correct']+=row_correct;cls['valid']+=row_valid

        for area_key in ('LC','CH','CN','MT'):
            areas[area_key]['correct']+=row_area[area_key]['correct']
            areas[area_key]['valid']+=row_area[area_key]['valid']
        for key,value in (('triGeneral',scores.get('tri')),('lc',scores.get('lc')),('ch',scores.get('ch')),('cn',scores.get('cn')),('mt',scores.get('mt')),('redaction',scores.get('redaction'))):
            if value is not None: sim[key].append(value)
        if scores.get('tri') is not None: cls['triGeneral'].append(scores['tri'])
        if scores.get('redaction') is not None: cls['redaction'].append(scores['redaction'])
        for area_key,score_key in (('LC','lc'),('CH','ch'),('CN','cn'),('MT','mt')):
            value=scores.get(score_key)
            if value is not None: areas[area_key]['tri'].append(value)

    sim_rows=[]
    for sim in simulations.values():
        sim_rows.append({
            'activityKey':sim['activityKey'],'activity':sim['activity'],'date':sim['date'],
            'participants':len(sim['participants']),'correct':sim['correct'],'valid':sim['valid'],
            'accuracy':None if not sim['valid'] else round(100*sim['correct']/sim['valid'],2),
            'triGeneral':_mgmt_mean(sim['triGeneral']),'lc':_mgmt_mean(sim['lc']),'ch':_mgmt_mean(sim['ch']),
            'cn':_mgmt_mean(sim['cn']),'mt':_mgmt_mean(sim['mt']),'redaction':_mgmt_mean(sim['redaction']),
        })
    sim_rows.sort(key=lambda x:(x['date'],F.norm(x['activity'])),reverse=True)

    class_summary=[]
    for cls in classes.values():
        class_summary.append({
            'turma':cls['turma'],'participants':len(cls['participants']),'correct':cls['correct'],'valid':cls['valid'],
            'accuracy':None if not cls['valid'] else round(100*cls['correct']/cls['valid'],2),
            'triGeneral':_mgmt_mean(cls['triGeneral']),'redaction':_mgmt_mean(cls['redaction']),
        })
    class_summary.sort(key=lambda x:(-(x['participants'] or 0),F.norm(x['turma'])))

    area_rows=[]
    for key,label in (('LC','Linguagens'),('CH','Humanas'),('CN','Natureza'),('MT','Matemática')):
        bucket=areas[key]
        area_rows.append({
            'key':key,'name':label,'correct':bucket['correct'],'valid':bucket['valid'],
            'accuracy':None if not bucket['valid'] else round(100*bucket['correct']/bucket['valid'],2),
            'tri':_mgmt_mean(bucket['tri']),
        })
    area_rows.append({'key':'RED','name':'Redação','correct':0,'valid':0,'accuracy':None,'tri':_mgmt_mean(redactions)})

    exam_rows=app.db.execute(c,'SELECT title,applied_on FROM hmay_exams ORDER BY applied_on,title').fetchall()
    catalog={(F.norm(x['title']),F.text(x['applied_on'],40)) for x in exam_rows}
    all_years=sorted({F.text(x['applied_on'],40)[:4] for x in exam_rows if len(F.text(x['applied_on'],40))>=4} | years,reverse=True)
    options=sorted(sim_options.values(),key=lambda x:(x['date'],F.norm(x['activity'])),reverse=True)
    result={
        'filters':{'years':all_years,'turmas':[x['name'] for x in class_rows],'simulations':options,'selected':selected},
        'kpis':{
            'activeStudents':active_students,'participants':len(participants),'catalogSimulations':len(catalog),'maps':len(exam_rows),
            'simulationsWithResults':len(sim_rows),'participations':participations,'correct':total_correct,'valid':total_valid,
            'accuracy':None if not total_valid else round(100*total_correct/total_valid,2),
            'triGeneral':_mgmt_mean(tri_general),'redaction':_mgmt_mean(redactions),
        },
        'areas':area_rows,'simulations':sim_rows,'classes':class_summary,'scaleMax':1000,
    }
    _v36_dashboard_cache[cache_key]=(_v36_time.time(),result)
    if len(_v36_dashboard_cache)>12:
        for key in list(_v36_dashboard_cache.keys())[:-8]:
            _v36_dashboard_cache.pop(key,None)
    return result

_v36_original_tri_preview=_tri_preview

def _tri_preview(app,c,data):
    parsed,match,preview=_v36_original_tri_preview(app,c,data)
    _v36_validate_class_names(app,c,[row.get('group') for row in parsed.get('records',[])],'TRI e Redação')
    return parsed,match,preview

_v36_original_handle=handle

def handle(app,c,user,path,method,data,query,start,HTTPError):
    if path == '/api/model-data/classes':
        if user.get('role') not in ('master','coordenador'):
            raise HTTPError(403,'Cadastro de turmas exclusivo do Master e da coordenação.')
        if method=='GET':
            return app.reply(start,200,_v36_class_payload(app,c))
        if method=='POST':
            saved=_v36_save_class(app,c,user,data)
            return app.reply(start,200,{'saved':saved,**_v36_class_payload(app,c)})
        raise HTTPError(405,'Use GET ou POST para o cadastro de turmas.')

    if path in ('/api/model-data/preview','/api/model-data/confirm') and method=='POST' and user.get('role') in ('master','coordenador'):
        parsed=_parse(data,False)
        _v317_class_issues(app,c,parsed)

    return _v36_original_handle(app,c,user,path,method,data,query,start,HTTPError)

# === TRI MODEL WITHOUT BONUS V3.6 ===
def _qi_tri_template_workbook():
    headers = [
        'NOME', 'LOGIN (opcional)', 'NOME DO SIMULADO', 'DATA DE APLICAÇÃO', 'TURMA',
        'RANKING', 'NOTA TRI GERAL', 'TRI LINGUAGENS', 'TRI HUMANAS',
        'TRI NATUREZA', 'TRI MATEMÁTICA',
        'TEMA DA REDAÇÃO', 'C1', 'C2', 'C3', 'C4', 'C5', 'NOTA DA REDAÇÃO',
    ]
    rows = [['' for _ in headers] for _ in range(200)]
    help_headers = ['Campo', 'Orientação']
    help_rows = [
        ['NOME', 'Obrigatório. Deve corresponder ao nome usado no resultado já importado.'],
        ['LOGIN', 'Opcional. Serve apenas como apoio; o vínculo principal continua pelo nome.'],
        ['NOME DO SIMULADO', 'Informe o mesmo nome da avaliação já importada.'],
        ['DATA DE APLICAÇÃO', 'Use dd/mm/aaaa ou aaaa-mm-dd.'],
        ['TURMA', 'Use o nome oficial cadastrado no Painel de bordo ou um alias autorizado.'],
        ['RANKING', 'Posição do aluno no simulado, quando disponível.'],
        ['NOTA TRI GERAL', 'Nota oficial geral.'],
        ['TRI POR ÁREA', 'Linguagens, Humanas, Natureza e Matemática. Deixe vazio quando a área não foi aplicada.'],
        ['TEMA DA REDAÇÃO', 'Opcional. Texto do tema/proposta da redação.'],
        ['C1–C5', 'Cada competência deve estar entre 0 e 200.'],
        ['NOTA DA REDAÇÃO', 'De 0 a 1000. Se ficar vazia e C1–C5 estiverem completos, o sistema calcula a soma.'],
        ['REGRA DE ATUALIZAÇÃO', 'Campos vazios não apagam notas existentes. Respostas A–E, acertos, mapa de questões e cronograma são preservados.'],
        ['ARQUIVO', 'Use XLSX sem fórmulas, macros, proteção ou vínculos externos.'],
    ]
    return T.export(headers, rows, first_name='TRI e Redação', extra_sheets=[('Como preencher', help_headers, help_rows)])

# === MANAGEMENT REFINEMENT V3.7 ===
_v37_dashboard_base=_mgmt_dashboard_data
_v37_handle_base=handle

def _v37_filtered_metadata(app,c,query):
    conditions=["u.role IN ('user','aluno')","u.active=1"]
    args=[]
    year=F.text((query or {}).get('year'),4)
    activity=F.text((query or {}).get('activityKey'),250)
    date=F.text((query or {}).get('date'),40)
    turma=F.text((query or {}).get('turma'),160)
    if year:
        conditions.append('p.applied_on LIKE ?');args.append(year+'%')
    if activity:
        conditions.append('p.activity_key=?');args.append(activity)
    if date:
        conditions.append('p.applied_on=?');args.append(date)
    rows=app.db.execute(
        c,
        """SELECT p.metadata
           FROM hmay_performance p
           JOIN hmay_users u ON u.id=p.user_id
           WHERE """+' AND '.join(conditions),
        tuple(args),
    ).fetchall()
    lookup=_v36_class_lookup(app,c)
    result=[]
    for raw in rows:
        meta=_rx_json(raw['metadata'])
        raw_class=F.text(meta.get('TURMA'),160) or 'Sem turma'
        canonical=lookup.get(F.norm(raw_class),raw_class)
        if turma and canonical!=turma:
            continue
        result.append(meta)
    return result

def _mgmt_dashboard_data(app,c,user,query):
    result=_v37_dashboard_base(app,c,user,query)
    maxima={'LC':None,'CH':None,'CN':None,'MT':None,'RED':None}
    for meta in _v37_filtered_metadata(app,c,query):
        scores=_tri_scores_from_metadata(meta)
        for key,score_key in (('LC','lc'),('CH','ch'),('CN','cn'),('MT','mt'),('RED','redaction')):
            value=scores.get(score_key)
            if value is None:
                continue
            try:
                number=float(value)
            except Exception:
                continue
            if maxima[key] is None or number>maxima[key]:
                maxima[key]=number
    for area in result.get('areas',[]):
        area['maxTri']=maxima.get(area.get('key'))
    return result

def _v37_correct_class(app,c,user,source,target):
    source=F.text(source,160) or '(sem turma)'
    target=F.text(target,160)
    if not target:
        raise ValueError('Selecione a turma oficial de destino.')
    active={row['name'] for row in _v36_class_rows(app,c,True)}
    if target not in active:
        raise ValueError('A turma de destino não está ativa no cadastro.')
    rows=app.db.execute(c,'SELECT id,metadata FROM hmay_performance').fetchall()
    updates=[]
    for raw in rows:
        meta=_rx_json(raw['metadata'])
        current=F.text(meta.get('TURMA'),160) or '(sem turma)'
        if current!=source:
            continue
        meta['TURMA']=target
        updates.append((raw['id'],_v36_json.dumps(meta,ensure_ascii=False,separators=(',',':'))))
    if not updates:
        return {'source':source,'target':target,'updated':0}
    stamp=P.now().isoformat()
    for offset in range(0,len(updates),200):
        chunk=updates[offset:offset+200]
        cases=' '.join('WHEN ? THEN ?' for _ in chunk)
        placeholders=','.join('?' for _ in chunk)
        params=[]
        for row_id,meta_json in chunk:
            params.extend((row_id,meta_json))
        params.append(stamp)
        params.extend(row_id for row_id,_ in chunk)
        app.db.execute(
            c,
            'UPDATE hmay_performance SET metadata=CASE id '+cases+
            ' ELSE metadata END,version=version+1,updated_at=? WHERE id IN ('+placeholders+')',
            tuple(params),
        )
    _v36_dashboard_cache.clear()
    app.event(c,user,user['id'],'class_name_correction')
    return {'source':source,'target':target,'updated':len(updates)}

def handle(app,c,user,path,method,data,query,start,HTTPError):
    if path=='/api/model-data/class-correction':
        if user.get('role') not in ('master','coordenador'):
            raise HTTPError(403,'Correção de turmas exclusiva do Master e da coordenação.')
        if method!='POST':
            raise HTTPError(405,'Use POST para corrigir a turma.')
        result=_v37_correct_class(app,c,user,data.get('source'),data.get('target'))
        return app.reply(start,200,{**result,**_v36_class_payload(app,c)})
    return _v37_handle_base(app,c,user,path,method,data,query,start,HTTPError)

# === STUDENT REPORTS MODULE V1 ===
import base64 as _reports_b64
import json as _reports_json
import uuid as _reports_uuid
import re as _reports_re

_reports_handle_base=handle

def _reports_ensure(app,c):
    app.db.execute(c, """CREATE TABLE IF NOT EXISTS hmay_report_types(
        id text PRIMARY KEY,name text NOT NULL UNIQUE,sort_order integer NOT NULL DEFAULT 0,
        active integer NOT NULL DEFAULT 1,created_at text NOT NULL,updated_at text NOT NULL)""")
    app.db.execute(c, """CREATE TABLE IF NOT EXISTS hmay_report_models(
        id text PRIMARY KEY,type_id text NOT NULL,activity text NOT NULL,applied_on text NOT NULL DEFAULT '',
        title text NOT NULL,description text NOT NULL DEFAULT '',cover text NOT NULL DEFAULT '',
        active integer NOT NULL DEFAULT 1,created_at text NOT NULL,updated_at text NOT NULL,
        UNIQUE(type_id,activity,applied_on))""")
    app.db.execute(c, """CREATE TABLE IF NOT EXISTS hmay_student_reports(
        id text PRIMARY KEY,model_id text NOT NULL,user_id text NOT NULL REFERENCES hmay_users(id),
        report_name text NOT NULL DEFAULT '',report_url text NOT NULL,created_at text NOT NULL,updated_at text NOT NULL,
        UNIQUE(model_id,user_id))""")

def _reports_types(app,c,active_only=False):
    _reports_ensure(app,c)
    sql='SELECT id,name,sort_order,active,created_at,updated_at FROM hmay_report_types'
    if active_only: sql+=' WHERE active=1'
    sql+=' ORDER BY sort_order,lower(name)'
    return [dict(x) for x in app.db.execute(c,sql).fetchall()]

def _reports_models(app,c):
    _reports_ensure(app,c)
    rows=app.db.execute(c, """SELECT m.id,m.type_id,m.activity,m.applied_on,m.title,m.description,m.cover,m.active,
        m.created_at,m.updated_at,t.name AS type_name,t.sort_order,
        COUNT(r.id) AS assignments
        FROM hmay_report_models m
        JOIN hmay_report_types t ON t.id=m.type_id
        LEFT JOIN hmay_student_reports r ON r.model_id=m.id
        GROUP BY m.id,m.type_id,m.activity,m.applied_on,m.title,m.description,m.cover,m.active,m.created_at,m.updated_at,t.name,t.sort_order
        ORDER BY t.sort_order,lower(t.name),m.applied_on DESC,lower(m.activity)""").fetchall()
    return [dict(x) for x in rows]

def _reports_target(app,c,user,target_id):
    if user.get('role') in ('master','coordenador'):
        target_id=F.text(target_id,160)
        if not target_id or target_id==user.get('id'):
            return None
        row=app.db.execute(c,"SELECT id,name,username,role,active FROM hmay_users WHERE id=?",(target_id,)).fetchone()
        if not row or row['role'] not in ('user','aluno') or not row['active']:
            raise ValueError('Aluno não encontrado para consulta de relatórios.')
        return dict(row)
    if user.get('role') in ('user','aluno'):
        return user
    raise ValueError('Perfil sem acesso aos relatórios do aluno.')

def _reports_student_data(app,c,user,target_id):
    _reports_ensure(app,c)
    target=_reports_target(app,c,user,target_id)
    if not target:
        return {'student':None,'groups':[]}
    rows=app.db.execute(c, """SELECT r.id,r.report_name,r.report_url,m.id AS model_id,m.activity,m.applied_on,
        m.title,m.description,m.cover,t.id AS type_id,t.name AS type_name,t.sort_order
        FROM hmay_student_reports r
        JOIN hmay_report_models m ON m.id=r.model_id
        JOIN hmay_report_types t ON t.id=m.type_id
        WHERE r.user_id=? AND m.active=1 AND t.active=1
        ORDER BY t.sort_order,lower(t.name),m.applied_on DESC,lower(m.activity)""",(target['id'],)).fetchall()
    groups={}
    for raw in rows:
        row=dict(raw)
        bucket=groups.setdefault(row['type_id'],{'id':row['type_id'],'name':row['type_name'],'sortOrder':row['sort_order'],'reports':[]})
        bucket['reports'].append({
            'id':row['id'],'modelId':row['model_id'],'name':row['report_name'] or row['title'],
            'title':row['title'],'activity':row['activity'],'date':row['applied_on'],
            'description':row['description'],'cover':row['cover'],'url':row['report_url'],
        })
    return {'student':{'id':target['id'],'name':target['name'],'username':target['username']},'groups':list(groups.values())}

_REPORT_HEADER_ALIASES={
    'name':{'nome','aluno','nome do aluno','nome aluno'},
    'activity':{'atividade','simulado','atividade simulado','nome do simulado','simulado atividade'},
    'type':{'tipo','tipo de relatorio','tipo relatorio','categoria'},
    'url':{'link','url','link de acesso','link acesso','link do relatorio','url do relatorio'},
    'reportName':{'nome do relatorio','nome relatorio','titulo','titulo do relatorio'},
    'date':{'data','data de aplicacao','data aplicacao'},
}

def _reports_header_map(row):
    result={}
    for i,value in enumerate(row):
        key=F.norm(value)
        for field,aliases in _REPORT_HEADER_ALIASES.items():
            if key in {F.norm(x) for x in aliases}:
                result.setdefault(field,i)
    return result

def _reports_parse(data):
    sheets=_tri_xlsx_rows(data)
    candidate=None
    for sheet_order,sheet in enumerate(sheets):
        for row_index,row in enumerate(sheet.get('rows',[])[:25]):
            columns=_reports_header_map(row)
            score=sum(1 for key in ('name','activity','type','url') if key in columns)
            if score>=4:
                item=(score,-sheet_order,-row_index,sheet,row_index,columns)
                if candidate is None or item[:3]>candidate[:3]:
                    candidate=item
    if not candidate:
        raise ValueError('Não encontrei as colunas NOME DO ALUNO, ATIVIDADE/SIMULADO, TIPO DE RELATÓRIO e LINK.')
    _,_,_,sheet,header_row,columns=candidate
    records=[]
    for line,row in enumerate(sheet.get('rows',[])[header_row+1:],start=header_row+2):
        def value(key):
            idx=columns.get(key)
            return row[idx] if idx is not None and idx<len(row) else ''
        name=F.text(value('name'),250)
        activity=F.text(value('activity'),250)
        type_name=F.text(value('type'),160)
        url=F.text(value('url'),2000)
        report_name=F.text(value('reportName'),250)
        date_raw=F.text(value('date'),60)
        if not any((name,activity,type_name,url,report_name,date_raw)):
            continue
        if not name:
            raise ValueError(f'Linha {line}: informe o nome do aluno.')
        if not activity:
            raise ValueError(f'Linha {line}: informe a atividade ou simulado.')
        if not type_name:
            raise ValueError(f'Linha {line}: informe o tipo de relatório.')
        if not url:
            raise ValueError(f'Linha {line}: informe o link do relatório.')
        if not (url.startswith('https://') or url.startswith('http://')):
            raise ValueError(f'Linha {line}: o link deve começar com http:// ou https://.')
        date=''
        if date_raw:
            date=_tri_iso_date(date_raw)
        records.append({'line':line,'name':name,'activity':activity,'type':type_name,'url':url,'reportName':report_name,'date':date})
    if not records:
        raise ValueError('O arquivo não possui relatórios preenchidos.')
    if len(records)>5000:
        raise ValueError('O arquivo possui mais de 5.000 linhas de relatórios.')
    return {'sheet':sheet.get('name',''),'records':records}

def _reports_match(app,c,parsed):
    users=app.db.execute(c,"SELECT id,name,username FROM hmay_users WHERE role IN ('user','aluno') AND active=1 ORDER BY name").fetchall()
    by_name={}
    for raw in users:
        row=dict(raw);by_name.setdefault(F.norm(row['name']),[]).append(row)
    types=_reports_types(app,c,True)
    by_type={F.norm(x['name']):x for x in types}
    matched=[];unmatched=[];ambiguous=[];unknown_types=[]
    for record in parsed['records']:
        candidates=by_name.get(F.norm(record['name']),[])
        type_row=by_type.get(F.norm(record['type']))
        if not type_row:
            unknown_types.append(record['type']);continue
        if len(candidates)==0:
            unmatched.append(record['name']);continue
        if len(candidates)>1:
            ambiguous.append(record['name']);continue
        matched.append({'record':record,'user':candidates[0],'type':type_row})
    return {
        'matched':matched,
        'unmatched':sorted(set(unmatched),key=F.norm),
        'ambiguous':sorted(set(ambiguous),key=F.norm),
        'unknownTypes':sorted(set(unknown_types),key=F.norm),
    }

def _reports_preview(app,c,data):
    parsed=_reports_parse(data)
    match=_reports_match(app,c,parsed)
    return {
        'sheet':parsed['sheet'],'rows':len(parsed['records']),'matched':len(match['matched']),
        'unmatched':match['unmatched'],'ambiguous':match['ambiguous'],'unknownTypes':match['unknownTypes'],
        'sample':[{
            'name':x['record']['name'],'activity':x['record']['activity'],'type':x['type']['name'],
            'date':x['record']['date'],'reportName':x['record']['reportName'],'url':x['record']['url']
        } for x in match['matched'][:40]],
    },parsed,match

def _reports_confirm(app,c,user,data):
    preview,parsed,match=_reports_preview(app,c,data)
    issues=[]
    if match['unmatched']: issues.append('alunos não encontrados: '+', '.join(match['unmatched'][:20]))
    if match['ambiguous']: issues.append('nomes de alunos duplicados: '+', '.join(match['ambiguous'][:20]))
    if match['unknownTypes']: issues.append('tipos não cadastrados: '+', '.join(match['unknownTypes'][:20]))
    if issues:
        raise ValueError('Não foi possível confirmar: '+'; '.join(issues)+'.')
    stamp=P.now().isoformat()
    new_models=0;new_reports=0;updated_reports=0
    model_cache={}
    for item in match['matched']:
        record=item['record'];type_row=item['type'];user_row=item['user']
        mkey=(type_row['id'],F.norm(record['activity']),record['date'])
        model=model_cache.get(mkey)
        if not model:
            row=app.db.execute(c,
                'SELECT id,title FROM hmay_report_models WHERE type_id=? AND activity=? AND applied_on=?',
                (type_row['id'],record['activity'],record['date'])).fetchone()
            if row:
                model=dict(row)
            else:
                model={'id':'rmdl_'+_reports_uuid.uuid4().hex,'title':record['activity']}
                app.db.execute(c,
                    'INSERT INTO hmay_report_models(id,type_id,activity,applied_on,title,description,cover,active,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?,?,?)',
                    (model['id'],type_row['id'],record['activity'],record['date'],record['activity'],'','',1,stamp,stamp))
                new_models+=1
            model_cache[mkey]=model
        existing=app.db.execute(c,'SELECT id,report_url,report_name FROM hmay_student_reports WHERE model_id=? AND user_id=?',(model['id'],user_row['id'])).fetchone()
        report_name=record['reportName'] or model.get('title') or record['activity']
        if existing:
            app.db.execute(c,'UPDATE hmay_student_reports SET report_name=?,report_url=?,updated_at=? WHERE id=?',
                (report_name,record['url'],stamp,existing['id']))
            updated_reports+=1
        else:
            app.db.execute(c,'INSERT INTO hmay_student_reports(id,model_id,user_id,report_name,report_url,created_at,updated_at) VALUES (?,?,?,?,?,?,?)',
                ('rptlink_'+_reports_uuid.uuid4().hex,model['id'],user_row['id'],report_name,record['url'],stamp,stamp))
            new_reports+=1
    app.event(c,user,user['id'],'student_reports_batch_import')
    return {'summary':{'rows':len(parsed['records']),'matched':len(match['matched']),'newModels':new_models,'newReports':new_reports,'updatedReports':updated_reports}}

def _reports_template():
    headers=['NOME DO ALUNO','ATIVIDADE/SIMULADO','TIPO DE RELATÓRIO','NOME DO RELATÓRIO (opcional)','DATA (opcional)','LINK DE ACESSO']
    rows=[['' for _ in headers] for _ in range(200)]
    help_headers=['Campo','Orientação']
    help_rows=[
        ['NOME DO ALUNO','Deve corresponder ao nome cadastrado no sistema.'],
        ['ATIVIDADE/SIMULADO','Nome do simulado, treino, teste ou atividade.'],
        ['TIPO DE RELATÓRIO','Use um tipo previamente criado pelo Master, como Simulado, Treino ou Mapa de Metas.'],
        ['NOME DO RELATÓRIO','Opcional. Se vazio, usa o nome geral do modelo.'],
        ['DATA','Opcional. Use dd/mm/aaaa ou aaaa-mm-dd.'],
        ['LINK DE ACESSO','URL individual do PDF/relatório online. Deve começar com http:// ou https://.'],
    ]
    return T.export(headers,rows,first_name='RELATORIOS',extra_sheets=[('Como preencher',help_headers,help_rows)])

def _reports_admin_data(app,c):
    return {'types':_reports_types(app,c,False),'models':_reports_models(app,c)}

def _reports_save_type(app,c,user,data):
    _reports_ensure(app,c)
    type_id=F.text(data.get('id'),160)
    name=F.text(data.get('name'),160)
    if not name: raise ValueError('Informe o nome do tipo.')
    try: sort_order=int(data.get('sortOrder') or 0)
    except Exception: sort_order=0
    active=1 if data.get('active',True) else 0
    stamp=P.now().isoformat()
    duplicate=app.db.execute(c,'SELECT id FROM hmay_report_types WHERE lower(name)=lower(?) AND id<>?',(name,type_id or '')).fetchone()
    if duplicate: raise ValueError('Já existe um tipo com esse nome.')
    if type_id:
        app.db.execute(c,'UPDATE hmay_report_types SET name=?,sort_order=?,active=?,updated_at=? WHERE id=?',(name,sort_order,active,stamp,type_id))
    else:
        type_id='rtype_'+_reports_uuid.uuid4().hex
        app.db.execute(c,'INSERT INTO hmay_report_types(id,name,sort_order,active,created_at,updated_at) VALUES (?,?,?,?,?,?)',(type_id,name,sort_order,active,stamp,stamp))
    app.event(c,user,user['id'],'report_type_update')
    return _reports_admin_data(app,c)

def _reports_save_model(app,c,user,data):
    _reports_ensure(app,c)
    model_id=F.text(data.get('id'),160)
    if not model_id: raise ValueError('Modelo de relatório não informado.')
    row=app.db.execute(c,'SELECT id FROM hmay_report_models WHERE id=?',(model_id,)).fetchone()
    if not row: raise ValueError('Modelo não encontrado.')
    title=F.text(data.get('title'),250)
    description=F.text(data.get('description'),1000)
    cover=F.text(data.get('cover'),800000)
    active=1 if data.get('active',True) else 0
    if cover and not (cover.startswith('http://') or cover.startswith('https://') or cover.startswith('data:image/')):
        raise ValueError('A capa deve ser uma URL http(s) ou uma imagem enviada pelo formulário.')
    stamp=P.now().isoformat()
    app.db.execute(c,'UPDATE hmay_report_models SET title=?,description=?,cover=?,active=?,updated_at=? WHERE id=?',
        (title or 'Relatório',description,cover,active,stamp,model_id))
    app.event(c,user,user['id'],'report_model_update')
    return _reports_admin_data(app,c)

def handle(app,c,user,path,method,data,query,start,HTTPError):
    if path=='/api/model-data/student-reports':
        if method!='GET': raise HTTPError(405,'Use GET para consultar relatórios.')
        return app.reply(start,200,_reports_student_data(app,c,user,(query or {}).get('userId')))

    if path=='/api/model-data/report-admin-data':
        if user.get('role') not in ('master','coordenador'): raise HTTPError(403,'Acesso reservado.')
        if method!='GET': raise HTTPError(405,'Use GET.')
        return app.reply(start,200,_reports_admin_data(app,c))

    if path=='/api/model-data/report-type-save':
        if user.get('role') not in ('master','coordenador'): raise HTTPError(403,'Acesso reservado.')
        if method!='POST': raise HTTPError(405,'Use POST.')
        return app.reply(start,200,_reports_save_type(app,c,user,data))

    if path=='/api/model-data/report-model-save':
        if user.get('role') not in ('master','coordenador'): raise HTTPError(403,'Acesso reservado.')
        if method!='POST': raise HTTPError(405,'Use POST.')
        return app.reply(start,200,_reports_save_model(app,c,user,data))

    if path=='/api/model-data/report-batch-template':
        if user.get('role') not in ('master','coordenador'): raise HTTPError(403,'Acesso reservado.')
        blob=_reports_template()
        if not isinstance(blob,(bytes,bytearray)): raise RuntimeError('Falha ao gerar o modelo XLSX.')
        return app.reply(start,200,{'filename':'MODELO_CADASTRO_RELATORIOS.xlsx','mime':'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet','file':_reports_b64.b64encode(blob).decode('ascii')})

    if path=='/api/model-data/report-batch-preview':
        if user.get('role') not in ('master','coordenador'): raise HTTPError(403,'Acesso reservado.')
        preview,_,_=_reports_preview(app,c,data)
        return app.reply(start,200,preview)

    if path=='/api/model-data/report-batch-confirm':
        if user.get('role') not in ('master','coordenador'): raise HTTPError(403,'Acesso reservado.')
        return app.reply(start,200,_reports_confirm(app,c,user,data))

    return _reports_handle_base(app,c,user,path,method,data,query,start,HTTPError)

# === HOTFIX V3.7.1 ===
_v371_handle_base=handle

def _reports_template():
    headers=['NOME DO ALUNO','ATIVIDADE/SIMULADO','TIPO DE RELATÓRIO','NOME DO RELATÓRIO (opcional)','DATA (opcional)','LINK DE ACESSO']
    rows=[['' for _ in headers] for _ in range(200)]
    help_headers=['Campo','Orientação']
    help_rows=[
        ['NOME DO ALUNO','Deve corresponder ao nome cadastrado no sistema.'],
        ['ATIVIDADE/SIMULADO','Nome do simulado, treino, teste ou atividade.'],
        ['TIPO DE RELATÓRIO','Use um tipo previamente criado pelo Master, como Simulado, Treino ou Mapa de Metas.'],
        ['NOME DO RELATÓRIO','Opcional. Se vazio, usa o nome geral do modelo.'],
        ['DATA','Opcional. Use dd/mm/aaaa ou aaaa-mm-dd.'],
        ['LINK DE ACESSO','URL individual do PDF/relatório online. Deve começar com http:// ou https://.'],
    ]
    output=T.export(headers,rows,first_name='RELATORIOS',extra_sheets=[('Como preencher',help_headers,help_rows)])
    if isinstance(output,tuple):
        output=next((item for item in output if isinstance(item,(bytes,bytearray))),None)
    if not isinstance(output,(bytes,bytearray)):
        raise ValueError('Não foi possível gerar o arquivo-modelo de relatórios.')
    return bytes(output)

def _reports_delete_type(app,c,user,type_id):
    type_id=F.text(type_id,160)
    if not type_id:
        raise ValueError('Tipo de relatório não informado.')
    row=app.db.execute(c,'SELECT id,name FROM hmay_report_types WHERE id=?',(type_id,)).fetchone()
    if not row:
        raise ValueError('Tipo de relatório não encontrado.')
    models=app.db.execute(c,'SELECT id FROM hmay_report_models WHERE type_id=?',(type_id,)).fetchall()
    model_ids=[x['id'] for x in models]
    links=0
    if model_ids:
        placeholders=','.join('?' for _ in model_ids)
        count=app.db.execute(c,'SELECT COUNT(*) AS n FROM hmay_student_reports WHERE model_id IN ('+placeholders+')',tuple(model_ids)).fetchone()
        links=int(count['n'] or 0)
        app.db.execute(c,'DELETE FROM hmay_student_reports WHERE model_id IN ('+placeholders+')',tuple(model_ids))
        app.db.execute(c,'DELETE FROM hmay_report_models WHERE id IN ('+placeholders+')',tuple(model_ids))
    app.db.execute(c,'DELETE FROM hmay_report_types WHERE id=?',(type_id,))
    app.event(c,user,user['id'],'report_type_delete')
    return {'deletedType':row['name'],'deletedModels':len(model_ids),'deletedReports':links,**_reports_admin_data(app,c)}

def handle(app,c,user,path,method,data,query,start,HTTPError):
    if path=='/api/model-data/report-type-delete':
        if user.get('role') not in ('master','coordenador'):
            raise HTTPError(403,'Acesso reservado ao Master e à coordenação.')
        if method!='POST':
            raise HTTPError(405,'Use POST para excluir o tipo.')
        return app.reply(start,200,_reports_delete_type(app,c,user,data.get('id')))
    return _v371_handle_base(app,c,user,path,method,data,query,start,HTTPError)

# === HOTFIX V3.7.2 ===
import unicodedata as _v372_unicode

def _reports_header_key(value):
    text=str(value or '').strip().lower()
    text=_v372_unicode.normalize('NFKD',text)
    text=''.join(ch for ch in text if not _v372_unicode.combining(ch))
    text=_reports_re.sub(r'[^a-z0-9]+',' ',text).strip()
    return text

_REPORT_HEADER_ALIASES={
    'name':{'nome','aluno','nome do aluno','nome aluno'},
    'activity':{'atividade','simulado','atividade simulado','nome do simulado','simulado atividade'},
    'type':{'tipo','tipo de relatorio','tipo relatorio','categoria'},
    'url':{'link','url','link de acesso','link acesso','link do relatorio','url do relatorio'},
    'reportName':{'nome do relatorio','nome relatorio','nome do relatorio opcional','titulo','titulo do relatorio'},
    'date':{'data','data opcional','data de aplicacao','data aplicacao'},
}
_REPORT_HEADER_NORMALIZED={
    field:{_reports_header_key(alias) for alias in aliases}
    for field,aliases in _REPORT_HEADER_ALIASES.items()
}

def _reports_header_map(row):
    result={}
    for i,value in enumerate(row):
        key=_reports_header_key(value)
        for field,aliases in _REPORT_HEADER_NORMALIZED.items():
            if key in aliases:
                result.setdefault(field,i)
    return result

def _reports_normalize_url(value,line):
    url=F.text(value,2000)
    if not url:
        raise ValueError(f'Linha {line}: informe o link do relatório.')
    if url.startswith('www.'):
        url='https://'+url
    elif not (url.startswith('https://') or url.startswith('http://')):
        if _reports_re.match(r'^[A-Za-z0-9.-]+\.[A-Za-z]{2,}(?:/.*)?$',url):
            url='https://'+url
        else:
            raise ValueError(f'Linha {line}: informe um link válido, como https://exemplo.com/relatorio.')
    return url

def _reports_parse(data):
    sheets=_tri_xlsx_rows(data)
    candidate=None
    for sheet_order,sheet in enumerate(sheets):
        for row_index,row in enumerate(sheet.get('rows',[])[:25]):
            columns=_reports_header_map(row)
            score=sum(1 for key in ('name','activity','type','url') if key in columns)
            if score>=4:
                item=(score,-sheet_order,-row_index,sheet,row_index,columns)
                if candidate is None or item[:3]>candidate[:3]:
                    candidate=item
    if not candidate:
        raise ValueError(
            'Não encontrei as colunas obrigatórias do modelo. '
            'Use NOME DO ALUNO, ATIVIDADE/SIMULADO, TIPO DE RELATÓRIO e LINK DE ACESSO.'
        )
    _,_,_,sheet,header_row,columns=candidate
    records=[]
    for line,row in enumerate(sheet.get('rows',[])[header_row+1:],start=header_row+2):
        def value(key):
            idx=columns.get(key)
            return row[idx] if idx is not None and idx<len(row) else ''
        name=F.text(value('name'),250)
        activity=F.text(value('activity'),250)
        type_name=F.text(value('type'),160)
        report_name=F.text(value('reportName'),250)
        date_raw=value('date')
        url_raw=value('url')
        if not any((name,activity,type_name,report_name,F.text(date_raw,80),F.text(url_raw,2000))):
            continue
        if not name:
            raise ValueError(f'Linha {line}: informe o nome do aluno.')
        if not activity:
            raise ValueError(f'Linha {line}: informe a atividade ou simulado.')
        if not type_name:
            raise ValueError(f'Linha {line}: informe o tipo de relatório.')
        url=_reports_normalize_url(url_raw,line)
        date=''
        if date_raw not in (None,''):
            date=_tri_iso_date(date_raw)
        records.append({
            'line':line,'name':name,'activity':activity,'type':type_name,
            'url':url,'reportName':report_name,'date':date
        })
    if not records:
        raise ValueError('O arquivo não possui relatórios preenchidos.')
    if len(records)>5000:
        raise ValueError('O arquivo possui mais de 5.000 linhas de relatórios.')
    return {'sheet':sheet.get('name',''),'records':records}

def _v372_class_variants(app,c):
    counts={}
    for raw in app.db.execute(c,'SELECT metadata FROM hmay_performance').fetchall():
        meta=_rx_json(raw['metadata'])
        name=F.text(meta.get('TURMA'),160) or '(sem turma)'
        counts[name]=counts.get(name,0)+1
    return counts

def _v36_class_payload(app,c):
    rows=_v36_class_rows(app,c,False)
    lookup=_v36_class_lookup(app,c)
    counts=_v372_class_variants(app,c)
    divergents={row['id']:[] for row in rows}
    by_norm={}
    for row in rows:
        by_norm[F.norm(row['name'])]=row
        for alias in row['aliases']:
            by_norm[F.norm(alias)]=row
    unregistered=[]
    for raw_name,count in sorted(counts.items(),key=lambda x:F.norm(x[0])):
        mapped=by_norm.get(F.norm(raw_name))
        if mapped:
            if F.norm(raw_name)!=F.norm(mapped['name']):
                divergents[mapped['id']].append({'name':raw_name,'records':count})
        else:
            unregistered.append({'name':raw_name,'records':count})
    for row in rows:
        row['divergents']=divergents.get(row['id'],[])
    return {'classes':rows,'unregistered':unregistered}

def _v372_update_performance_class(app,c,accepted_names,new_name):
    accepted={F.norm(x) for x in accepted_names if F.text(x,160)}
    rows=app.db.execute(c,'SELECT id,metadata FROM hmay_performance').fetchall()
    updates=[]
    for raw in rows:
        meta=_rx_json(raw['metadata'])
        current=F.text(meta.get('TURMA'),160)
        if not current or F.norm(current) not in accepted:
            continue
        if current==new_name:
            continue
        meta['TURMA']=new_name
        updates.append((raw['id'],_v36_json.dumps(meta,ensure_ascii=False,separators=(',',':'))))
    if not updates:
        return 0
    stamp=P.now().isoformat()
    for offset in range(0,len(updates),200):
        chunk=updates[offset:offset+200]
        cases=' '.join('WHEN ? THEN ?' for _ in chunk)
        placeholders=','.join('?' for _ in chunk)
        params=[]
        for row_id,meta_json in chunk:
            params.extend((row_id,meta_json))
        params.append(stamp)
        params.extend(row_id for row_id,_ in chunk)
        app.db.execute(
            c,
            'UPDATE hmay_performance SET metadata=CASE id '+cases+
            ' ELSE metadata END,version=version+1,updated_at=? WHERE id IN ('+placeholders+')',
            tuple(params),
        )
    return len(updates)

def _v36_save_class(app,c,user,data):
    rows=_v36_class_rows(app,c,False)
    class_id=F.text(data.get('id'),160)
    name=F.text(data.get('name'),160)
    if not name:
        raise ValueError('Informe o nome oficial da turma.')
    aliases_raw=data.get('aliases')
    if isinstance(aliases_raw,str):
        aliases=[F.text(x,160) for x in _v36_re.split(r'[,;\n]+',aliases_raw) if F.text(x,160)]
    elif isinstance(aliases_raw,list):
        aliases=[F.text(x,160) for x in aliases_raw if F.text(x,160)]
    else:
        aliases=[]
    active=1 if data.get('active',True) else 0

    current=None
    if class_id:
        current=next((row for row in rows if row['id']==class_id),None)
        if not current:
            raise ValueError('Turma não encontrada.')

    old_name=current['name'] if current else ''
    old_aliases=list(current['aliases']) if current else []
    if old_name and F.norm(old_name)!=F.norm(name):
        aliases.append(old_name)
    aliases=sorted({x for x in aliases+old_aliases if F.norm(x)!=F.norm(name)},key=F.norm)

    claimed={}
    for row in rows:
        if class_id and row['id']==class_id:
            continue
        if row['active']:
            claimed[F.norm(row['name'])]=row['name']
            for alias in row['aliases']:
                claimed[F.norm(alias)]=row['name']
    for candidate in [name]+aliases:
        owner=claimed.get(F.norm(candidate))
        if owner:
            raise ValueError(f'O nome/alias "{candidate}" já pertence à turma "{owner}".')

    stamp=P.now().isoformat()
    if class_id:
        app.db.execute(
            c,'UPDATE hmay_classes SET name=?,norm=?,aliases=?,active=?,updated_at=? WHERE id=?',
            (name,F.norm(name),_v36_json.dumps(aliases,ensure_ascii=False),active,stamp,class_id),
        )
        accepted=[old_name]+old_aliases+aliases
        updated_results=_v372_update_performance_class(app,c,accepted,name)
    else:
        class_id='cls_'+_v36_uuid.uuid4().hex
        app.db.execute(
            c,'INSERT INTO hmay_classes(id,name,norm,aliases,active,created_at,updated_at) VALUES (?,?,?,?,?,?,?)',
            (class_id,name,F.norm(name),_v36_json.dumps(aliases,ensure_ascii=False),active,stamp,stamp),
        )
        updated_results=0
    _v36_dashboard_cache.clear()
    app.event(c,user,user['id'],'class_registry_update')
    return {
        'id':class_id,'name':name,'aliases':aliases,'active':bool(active),
        'updatedResults':updated_results,'oldName':old_name
    }

# === HOTFIX V3.7.3 ===
_v373_save_class_base=_v36_save_class

def _v373_merge_classes(app,c,user,current,target,requested_aliases):
    rows=_v36_class_rows(app,c,False)
    merged_aliases=[]
    for value in (
        list(target.get('aliases') or [])
        + [current.get('name')]
        + list(current.get('aliases') or [])
        + list(requested_aliases or [])
    ):
        value=F.text(value,160)
        if value and F.norm(value)!=F.norm(target['name']):
            merged_aliases.append(value)
    merged_aliases=sorted(set(merged_aliases),key=F.norm)

    claimed={}
    for row in rows:
        if row['id'] in (current['id'],target['id']):
            continue
        claimed[F.norm(row['name'])]=row['name']
        for alias in row.get('aliases') or []:
            claimed[F.norm(alias)]=row['name']
    for alias in merged_aliases:
        owner=claimed.get(F.norm(alias))
        if owner:
            raise ValueError(
                f'Não é possível mesclar: o nome/alias "{alias}" já pertence à turma "{owner}".'
            )

    accepted=[current['name']]+list(current.get('aliases') or [])+list(requested_aliases or [])
    updated_results=_v372_update_performance_class(app,c,accepted,target['name'])
    stamp=P.now().isoformat()
    app.db.execute(
        c,
        'UPDATE hmay_classes SET aliases=?,active=1,updated_at=? WHERE id=?',
        (_v36_json.dumps(merged_aliases,ensure_ascii=False),stamp,target['id']),
    )
    app.db.execute(c,'DELETE FROM hmay_classes WHERE id=?',(current['id'],))
    _v36_dashboard_cache.clear()
    app.event(c,user,user['id'],'class_registry_merge')
    return {
        'id':target['id'],
        'name':target['name'],
        'aliases':merged_aliases,
        'active':True,
        'updatedResults':updated_results,
        'oldName':current['name'],
        'merged':True,
        'mergedFrom':current['name'],
        'mergedInto':target['name'],
    }

def _v36_save_class(app,c,user,data):
    rows=_v36_class_rows(app,c,False)
    class_id=F.text(data.get('id'),160)
    name=F.text(data.get('name'),160)
    if not name:
        raise ValueError('Informe o nome oficial da turma.')

    if class_id:
        current=next((row for row in rows if row['id']==class_id),None)
        if not current:
            raise ValueError('Turma não encontrada.')
        target=next(
            (row for row in rows if row['id']!=class_id and F.norm(row['name'])==F.norm(name)),
            None,
        )
        if target:
            aliases_raw=data.get('aliases')
            if isinstance(aliases_raw,str):
                requested_aliases=[
                    F.text(x,160) for x in _v36_re.split(r'[,;\n]+',aliases_raw)
                    if F.text(x,160)
                ]
            elif isinstance(aliases_raw,list):
                requested_aliases=[F.text(x,160) for x in aliases_raw if F.text(x,160)]
            else:
                requested_aliases=[]
            return _v373_merge_classes(app,c,user,current,target,requested_aliases)

    return _v373_save_class_base(app,c,user,data)

# === HOTFIX V3.7.4 ===
def _reports_target(app,c,user,target_id):
    if user.get('role') in ('master','coordenador'):
        if isinstance(target_id,(list,tuple)):
            target_id=target_id[0] if target_id else ''
        target_id=F.text(target_id,160)
        if not target_id or target_id==user.get('id'):
            return None
        row=app.db.execute(
            c,
            'SELECT id,name,username,role,active FROM hmay_users WHERE id=?',
            (target_id,),
        ).fetchone()
        if not row:
            raise ValueError('Aluno não encontrado para consulta de relatórios.')
        account=dict(row)
        if user.get('role')=='master':
            if account.get('role') not in ('user','aluno') or not account.get('active'):
                raise ValueError('A conta selecionada não é um aluno ativo.')
            return account
        if account.get('role') in ('user','aluno') and account.get('active'):
            return account
        raise ValueError('Você não pode consultar os relatórios deste perfil.')

    if user.get('role') in ('user','aluno'):
        return user
    raise ValueError('Perfil sem acesso aos relatórios do aluno.')

_reports_handle_v374_base=handle

def handle(app,c,user,path,method,data,query,start,HTTPError):
    if path=='/api/model-data/student-reports':
        if method!='GET':
            raise HTTPError(405,'Use GET para consultar relatórios.')
        raw=query.get('userId',['']) if isinstance(query,dict) else ['']
        return app.reply(start,200,_reports_student_data(app,c,user,raw))
    return _reports_handle_v374_base(app,c,user,path,method,data,query,start,HTTPError)

# === REPORT SCOPED DELETE V3.7.6 ===
_reports_handle_v376_base=handle

def _reports_latest_class_by_user(app,c,user_ids):
    if not user_ids:
        return {}
    lookup=_v36_class_lookup(app,c)
    placeholders=','.join('?' for _ in user_ids)
    rows=app.db.execute(
        c,
        'SELECT user_id,metadata,applied_on,updated_at FROM hmay_performance '
        'WHERE user_id IN ('+placeholders+') '
        'ORDER BY user_id,applied_on DESC,updated_at DESC',
        tuple(user_ids),
    ).fetchall()
    result={}
    for raw in rows:
        user_id=raw['user_id']
        if user_id in result:
            continue
        meta=_rx_json(raw['metadata'])
        raw_class=F.text(meta.get('TURMA'),160) or 'Sem turma'
        result[user_id]=lookup.get(F.norm(raw_class),raw_class)
    for user_id in user_ids:
        result.setdefault(user_id,'Sem turma')
    return result

def _reports_delete_options(app,c,model_id):
    _reports_ensure(app,c)
    model_id=F.text(model_id,160)
    model=app.db.execute(
        c,
        'SELECT m.id,m.title,m.activity,m.applied_on,t.name AS type_name '
        'FROM hmay_report_models m JOIN hmay_report_types t ON t.id=m.type_id '
        'WHERE m.id=?',
        (model_id,),
    ).fetchone()
    if not model:
        raise ValueError('Modelo de relatório não encontrado.')

    rows=app.db.execute(
        c,
        'SELECT r.user_id,u.name,u.username '
        'FROM hmay_student_reports r JOIN hmay_users u ON u.id=r.user_id '
        'WHERE r.model_id=? ORDER BY lower(u.name),lower(u.username)',
        (model_id,),
    ).fetchall()
    user_ids=[row['user_id'] for row in rows]
    class_by_user=_reports_latest_class_by_user(app,c,user_ids)

    groups={}
    for raw in rows:
        turma=class_by_user.get(raw['user_id'],'Sem turma')
        bucket=groups.setdefault(turma,[])
        bucket.append({
            'id':raw['user_id'],
            'name':raw['name'],
            'username':raw['username'],
        })

    classes=[
        {'name':name,'count':len(students),'students':students}
        for name,students in sorted(groups.items(),key=lambda item:F.norm(item[0]))
    ]
    return {
        'model':{
            'id':model['id'],'title':model['title'],'activity':model['activity'],
            'date':model['applied_on'],'type':model['type_name'],
        },
        'totalAssignments':len(rows),
        'classes':classes,
    }

def _reports_delete_scope(app,c,user,data):
    _reports_ensure(app,c)
    model_id=F.text(data.get('modelId'),160)
    if not model_id:
        raise ValueError('Modelo de relatório não informado.')
    model=app.db.execute(
        c,'SELECT id,title FROM hmay_report_models WHERE id=?',(model_id,)
    ).fetchone()
    if not model:
        raise ValueError('Modelo de relatório não encontrado.')

    options=_reports_delete_options(app,c,model_id)
    assignments={}
    for group in options['classes']:
        for student in group['students']:
            assignments[student['id']]=group['name']

    selections=data.get('selections')
    if not isinstance(selections,list):
        selections=[]

    deleted_users=set()
    delete_model=False

    if not selections:
        deleted_users=set(assignments.keys())
        delete_model=True
    else:
        for selection in selections:
            if not isinstance(selection,dict):
                continue
            turma=F.text(selection.get('turma'),160)
            if not turma:
                continue
            group_users={uid for uid,current_class in assignments.items() if current_class==turma}
            if not group_users:
                continue
            raw_ids=selection.get('userIds')
            selected_ids=[]
            if isinstance(raw_ids,list):
                selected_ids=[F.text(uid,160) for uid in raw_ids if F.text(uid,160)]
            if selected_ids:
                valid={uid for uid in selected_ids if uid in group_users}
                deleted_users.update(valid)
            else:
                deleted_users.update(group_users)

    deleted_count=0
    if deleted_users:
        ids=sorted(deleted_users)
        for offset in range(0,len(ids),300):
            chunk=ids[offset:offset+300]
            placeholders=','.join('?' for _ in chunk)
            params=[model_id]+chunk
            before=app.db.execute(
                c,
                'SELECT COUNT(*) AS n FROM hmay_student_reports '
                'WHERE model_id=? AND user_id IN ('+placeholders+')',
                tuple(params),
            ).fetchone()
            deleted_count+=int(before['n'] or 0)
            app.db.execute(
                c,
                'DELETE FROM hmay_student_reports WHERE model_id=? '
                'AND user_id IN ('+placeholders+')',
                tuple(params),
            )

    if delete_model:
        app.db.execute(c,'DELETE FROM hmay_report_models WHERE id=?',(model_id,))

    remaining=app.db.execute(
        c,'SELECT COUNT(*) AS n FROM hmay_student_reports WHERE model_id=?',(model_id,)
    ).fetchone()
    remaining_count=0 if delete_model else int(remaining['n'] or 0)

    app.event(c,user,user['id'],'student_report_scope_delete')
    return {
        'deletedAssignments':deleted_count,
        'remainingAssignments':remaining_count,
        'modelDeleted':delete_model,
        'modelTitle':model['title'],
        **_reports_admin_data(app,c),
    }

def handle(app,c,user,path,method,data,query,start,HTTPError):
    if path=='/api/model-data/report-delete-options':
        if user.get('role') not in ('master','coordenador'):
            raise HTTPError(403,'Acesso reservado ao Master e à coordenação.')
        if method!='POST':
            raise HTTPError(405,'Use POST para consultar o escopo de exclusão.')
        return app.reply(start,200,_reports_delete_options(app,c,data.get('modelId')))

    if path=='/api/model-data/report-delete-scope':
        if user.get('role') not in ('master','coordenador'):
            raise HTTPError(403,'Acesso reservado ao Master e à coordenação.')
        if method!='POST':
            raise HTTPError(405,'Use POST para excluir relatórios.')
        return app.reply(start,200,_reports_delete_scope(app,c,user,data))

    return _reports_handle_v376_base(app,c,user,path,method,data,query,start,HTTPError)

# === REPORT REGISTRY VIEW V3.7.7 ===
_reports_handle_v377_base=handle

def _v377_query_value(query,key):
    if not isinstance(query,dict):
        return ''
    raw=query.get(key,[''])
    if isinstance(raw,(list,tuple)):
        raw=raw[0] if raw else ''
    return F.text(raw,250)

def _reports_registry_assignments(app,c):
    rows=app.db.execute(
        c,
        """SELECT r.model_id,r.user_id,r.report_name,r.report_url,
                  u.name,u.username
           FROM hmay_student_reports r
           JOIN hmay_users u ON u.id=r.user_id
           WHERE u.role IN ('user','aluno') AND u.active=1
           ORDER BY lower(u.name),lower(u.username)"""
    ).fetchall()
    user_ids=sorted({row['user_id'] for row in rows})
    class_by_user=_reports_latest_class_by_user(app,c,user_ids)
    result=[]
    for raw in rows:
        row=dict(raw)
        row['turma']=class_by_user.get(row['user_id'],'Sem turma')
        result.append(row)
    return result

def _reports_registry(app,c,query):
    _reports_ensure(app,c)
    q=F.norm(_v377_query_value(query,'q'))
    type_q=F.norm(_v377_query_value(query,'type'))
    student_q=F.norm(_v377_query_value(query,'student'))
    class_q=F.norm(_v377_query_value(query,'turma'))

    models=_reports_models(app,c)
    assignments=_reports_registry_assignments(app,c)
    by_model={}
    for row in assignments:
        by_model.setdefault(row['model_id'],[]).append(row)

    type_suggestions=sorted({m['type_name'] for m in models if m.get('type_name')},key=F.norm)
    report_suggestions=sorted(
        {value for m in models for value in (m.get('title'),m.get('activity')) if value},
        key=F.norm,
    )
    student_suggestions=sorted({row['name'] for row in assignments if row.get('name')},key=F.norm)
    class_suggestions=sorted({row['turma'] for row in assignments if row.get('turma')},key=F.norm)

    result=[]
    for model in models:
        linked=by_model.get(model['id'],[])
        if q:
            hay=' '.join([
                F.norm(model.get('title')),
                F.norm(model.get('activity')),
                F.norm(model.get('type_name')),
            ])
            if q not in hay:
                continue
        if type_q and type_q not in F.norm(model.get('type_name')):
            continue
        if student_q and not any(student_q in F.norm(row.get('name')) for row in linked):
            continue
        if class_q and not any(class_q in F.norm(row.get('turma')) for row in linked):
            continue

        class_counts={}
        for row in linked:
            turma=row.get('turma') or 'Sem turma'
            class_counts[turma]=class_counts.get(turma,0)+1

        result.append({
            'id':model['id'],
            'type':model['type_name'],
            'title':model['title'],
            'activity':model['activity'],
            'date':model['applied_on'],
            'createdAt':model['created_at'],
            'updatedAt':model['updated_at'],
            'active':bool(model['active']),
            'assignments':len(linked),
            'classCount':len(class_counts),
            'classes':[
                {'name':name,'count':count}
                for name,count in sorted(class_counts.items(),key=lambda item:F.norm(item[0]))
            ],
        })

    result.sort(
        key=lambda item:(item.get('createdAt') or '',item.get('title') or ''),
        reverse=True,
    )

    return {
        'models':result,
        'total':len(result),
        'suggestions':{
            'types':type_suggestions,
            'reports':report_suggestions,
            'students':student_suggestions,
            'classes':class_suggestions,
        },
        'filters':{
            'q':_v377_query_value(query,'q'),
            'type':_v377_query_value(query,'type'),
            'student':_v377_query_value(query,'student'),
            'turma':_v377_query_value(query,'turma'),
        },
    }

def _reports_registry_detail(app,c,model_id):
    _reports_ensure(app,c)
    model_id=F.text(model_id,160)
    model=app.db.execute(
        c,
        """SELECT m.id,m.title,m.activity,m.applied_on,m.created_at,
                  t.name AS type_name
           FROM hmay_report_models m
           JOIN hmay_report_types t ON t.id=m.type_id
           WHERE m.id=?""",
        (model_id,),
    ).fetchone()
    if not model:
        raise ValueError('Relatório não encontrado.')

    rows=app.db.execute(
        c,
        """SELECT r.id,r.user_id,r.report_name,r.report_url,
                  u.name,u.username
           FROM hmay_student_reports r
           JOIN hmay_users u ON u.id=r.user_id
           WHERE r.model_id=? AND u.role IN ('user','aluno') AND u.active=1
           ORDER BY lower(u.name),lower(u.username)""",
        (model_id,),
    ).fetchall()
    user_ids=[row['user_id'] for row in rows]
    class_by_user=_reports_latest_class_by_user(app,c,user_ids)

    groups={}
    for raw in rows:
        row=dict(raw)
        turma=class_by_user.get(row['user_id'],'Sem turma')
        bucket=groups.setdefault(turma,[])
        bucket.append({
            'id':row['user_id'],
            'name':row['name'],
            'username':row['username'],
            'reportName':row['report_name'] or model['title'],
            'url':row['report_url'],
        })

    classes=[
        {'name':name,'count':len(students),'students':students}
        for name,students in sorted(groups.items(),key=lambda item:F.norm(item[0]))
    ]
    return {
        'model':{
            'id':model['id'],
            'type':model['type_name'],
            'title':model['title'],
            'activity':model['activity'],
            'date':model['applied_on'],
            'createdAt':model['created_at'],
        },
        'classes':classes,
        'assignments':len(rows),
    }

def handle(app,c,user,path,method,data,query,start,HTTPError):
    if path=='/api/model-data/report-registry':
        if user.get('role') not in ('master','coordenador'):
            raise HTTPError(403,'Acesso reservado ao Master e à coordenação.')
        if method!='GET':
            raise HTTPError(405,'Use GET para consultar os relatórios cadastrados.')
        return app.reply(start,200,_reports_registry(app,c,query))

    if path=='/api/model-data/report-registry-detail':
        if user.get('role') not in ('master','coordenador'):
            raise HTTPError(403,'Acesso reservado ao Master e à coordenação.')
        if method!='GET':
            raise HTTPError(405,'Use GET para consultar os vínculos do relatório.')
        model_id=_v377_query_value(query,'modelId')
        return app.reply(start,200,_reports_registry_detail(app,c,model_id))

    return _reports_handle_v377_base(app,c,user,path,method,data,query,start,HTTPError)

# === TRI TEMPLATE FINAL BYTES V3.7.8 ===
def _qi_tri_template_workbook():
    headers = [
        'NOME', 'LOGIN (opcional)', 'NOME DO SIMULADO', 'DATA DE APLICAÇÃO', 'TURMA',
        'RANKING', 'NOTA TRI GERAL', 'TRI LINGUAGENS', 'TRI HUMANAS',
        'TRI NATUREZA', 'TRI MATEMÁTICA',
        'TEMA DA REDAÇÃO', 'C1', 'C2', 'C3', 'C4', 'C5', 'NOTA DA REDAÇÃO',
    ]
    rows = [['' for _ in headers] for _ in range(200)]
    help_headers = ['Campo', 'Orientação']
    help_rows = [
        ['NOME', 'Obrigatório. Deve corresponder ao nome usado no resultado já importado.'],
        ['LOGIN', 'Opcional. Serve apenas como apoio; o vínculo principal continua pelo nome.'],
        ['NOME DO SIMULADO', 'Informe o mesmo nome da avaliação já importada.'],
        ['DATA DE APLICAÇÃO', 'Use dd/mm/aaaa ou aaaa-mm-dd.'],
        ['TURMA', 'Use o nome oficial cadastrado no Painel de bordo ou um alias autorizado.'],
        ['RANKING', 'Posição do aluno no simulado, quando disponível.'],
        ['NOTA TRI GERAL', 'Nota oficial geral.'],
        ['TRI POR ÁREA', 'Linguagens, Humanas, Natureza e Matemática. Deixe vazio quando a área não foi aplicada.'],
        ['TEMA DA REDAÇÃO', 'Opcional. Texto do tema/proposta da redação.'],
        ['C1–C5', 'Cada competência deve estar entre 0 e 200.'],
        ['NOTA DA REDAÇÃO', 'De 0 a 1000. Se ficar vazia e C1–C5 estiverem completos, o sistema calcula a soma.'],
        ['REGRA DE ATUALIZAÇÃO', 'Campos vazios não apagam notas existentes. Respostas A–E, acertos, mapa de questões e cronograma são preservados.'],
        ['ARQUIVO', 'Use XLSX sem fórmulas, macros, proteção ou vínculos externos.'],
    ]
    output = T.export(
        headers,
        rows,
        first_name='TRI e Redação',
        extra_sheets=[('Como preencher', help_headers, help_rows)],
    )
    if isinstance(output, tuple):
        output = next(
            (item for item in output if isinstance(item, (bytes, bytearray))),
            None,
        )
    if not isinstance(output, (bytes, bytearray)):
        raise ValueError('Não foi possível gerar o arquivo-modelo TRI e Redação.')
    return bytes(output)

# === STRICT A-E FINAL OVERRIDE V3.7.9 ===
_v379_answer_legacy = _answer

def _answer(value, label='Resposta', *args, **kwargs):
    text = '' if value is None else str(value).strip().upper()
    if text in ('A', 'B', 'C', 'D', 'E'):
        return text
    return 0

# === MANAGEMENT FILTER FIX V3.7.11 ===
_mgmt_dashboard_data_v3711_base = _mgmt_dashboard_data

def _v3711_query_scalar(query, key, limit):
    if not isinstance(query, dict):
        return ''
    raw = query.get(key, '')
    if isinstance(raw, (list, tuple)):
        raw = raw[0] if raw else ''
    return F.text(raw, limit)

def _mgmt_dashboard_data(app, c, user, query):
    normalized = {
        'year': _v3711_query_scalar(query, 'year', 4),
        'turma': _v3711_query_scalar(query, 'turma', 160),
        'activityKey': _v3711_query_scalar(query, 'activityKey', 250),
        'date': _v3711_query_scalar(query, 'date', 40),
    }
    data = _mgmt_dashboard_data_v3711_base(app, c, user, normalized)

    # Guarantee a complete dashboard payload even when a filter yields no rows.
    if not isinstance(data, dict):
        data = {}
    filters = data.get('filters')
    if not isinstance(filters, dict):
        filters = {}
        data['filters'] = filters
    filters.setdefault('years', [])
    filters.setdefault('turmas', [])
    filters.setdefault('simulations', [])
    filters['selected'] = normalized

    data.setdefault('kpis', {})
    data.setdefault('areas', [])
    data.setdefault('simulations', [])
    data.setdefault('classes', [])
    return data

# === CLASS ENEM ANALYTICS V3.7.12 ===
_v3712_handle_base=handle

def _v3712_num(value):
    try:
        if value in (None,''):
            return None
        return float(value)
    except Exception:
        return None

def _v3712_query_scalar(query,key,limit=500):
    if not isinstance(query,dict):
        return ''
    raw=query.get(key,'')
    if isinstance(raw,(list,tuple)):
        raw=raw[0] if raw else ''
    return F.text(raw,limit)

def _v3712_selected_sims(query):
    raw=_v3712_query_scalar(query,'sims',5000)
    return {x for x in raw.split('||') if x} if raw else set()

def _v3712_sim_token(activity_key,date):
    return F.text(activity_key,250)+'@@'+F.text(date,40)

def _v3712_scores(metadata):
    vals={
        'lc':_v3712_num(metadata.get('_tri_lc')),
        'ch':_v3712_num(metadata.get('_tri_ch')),
        'cn':_v3712_num(metadata.get('_tri_cn')),
        'mt':_v3712_num(metadata.get('_tri_mt')),
        'red':_v3712_num(metadata.get('_tri_redaction')),
        'c1':_v3712_num(metadata.get('_redaction_c1')),
        'c2':_v3712_num(metadata.get('_redaction_c2')),
        'c3':_v3712_num(metadata.get('_redaction_c3')),
        'c4':_v3712_num(metadata.get('_redaction_c4')),
        'c5':_v3712_num(metadata.get('_redaction_c5')),
    }
    has_any=any(vals[k] is not None for k in ('lc','ch','cn','mt','red'))
    if has_any:
        enem=sum(vals[k] or 0.0 for k in ('lc','ch','cn','mt','red'))/5.0
        bonus=enem*1.10
    else:
        enem=bonus=None
    vals['enem']=enem
    vals['bonus']=bonus
    return vals

def _v3712_row_accuracy(row,metadata,area_maps):
    metrics=_rx_json(row.get('metrics'))
    if not isinstance(metrics,dict):
        metrics={}
    exam_id=F.text(metadata.get('_exam_id'),160)
    qmap=area_maps.get(exam_id,{})
    result={key:{'correct':0,'valid':0} for key in ('ALL','LC','CH','CN','MT')}
    for mkey,mval in metrics.items():
        if not isinstance(mval,dict):
            continue
        try:
            correct=max(0,int(mval.get('correct') or 0))
            valid=max(0,int(mval.get('total') or 0))
        except Exception:
            continue
        result['ALL']['correct']+=correct
        result['ALL']['valid']+=valid
        number=_v36_metric_number(mkey)
        area=qmap.get(number)
        if not area and number:
            area='LC' if number<=45 else 'CH' if number<=90 else 'CN' if number<=135 else 'MT' if number<=180 else None
        if area in result:
            result[area]['correct']+=correct
            result[area]['valid']+=valid
    return result

def _v3712_bucket():
    return {
        'records':0,'students':set(),'simulations':set(),
        'correct':{key:0 for key in ('ALL','LC','CH','CN','MT')},
        'valid':{key:0 for key in ('ALL','LC','CH','CN','MT')},
        'enem':[],'bonus':[],
        'c1':[],'c2':[],'c3':[],'c4':[],'c5':[],
    }

def _v3712_add(bucket,row,metadata,area_maps):
    bucket['records']+=1
    bucket['students'].add(row['user_id'])
    bucket['simulations'].add(_v3712_sim_token(row['activity_key'],row['applied_on']))
    acc=_v3712_row_accuracy(row,metadata,area_maps)
    for key in ('ALL','LC','CH','CN','MT'):
        bucket['correct'][key]+=acc[key]['correct']
        bucket['valid'][key]+=acc[key]['valid']
    scores=_v3712_scores(metadata)
    for key in ('enem','bonus','c1','c2','c3','c4','c5'):
        value=scores.get(key)
        if value is not None:
            bucket[key].append(value)

def _v3712_pct(bucket,key):
    valid=bucket['valid'][key]
    return None if not valid else round(100.0*bucket['correct'][key]/valid,2)

def _v3712_summary(bucket):
    means={key:_mgmt_mean(bucket[key]) for key in ('enem','bonus','c1','c2','c3','c4','c5')}
    red_parts=[means[k] for k in ('c1','c2','c3','c4','c5')]
    redaction=None if all(v is None for v in red_parts) else round(sum(v or 0 for v in red_parts),2)
    return {
        'participants':len(bucket['students']),
        'simulations':len(bucket['simulations']),
        'records':bucket['records'],
        'enem':means['enem'],'bonus':means['bonus'],
        'accuracy':_v3712_pct(bucket,'ALL'),
        'lcAccuracy':_v3712_pct(bucket,'LC'),
        'chAccuracy':_v3712_pct(bucket,'CH'),
        'cnAccuracy':_v3712_pct(bucket,'CN'),
        'mtAccuracy':_v3712_pct(bucket,'MT'),
        'c1':means['c1'],'c2':means['c2'],'c3':means['c3'],'c4':means['c4'],'c5':means['c5'],
        'redaction':redaction,
    }

def _v3712_rows(app,c,year=''):
    class_lookup=_v36_class_lookup(app,c)
    sql="""SELECT p.user_id,p.activity_key,p.activity,p.applied_on,p.metrics,p.metadata,
                  u.name AS student_name,u.username
           FROM hmay_performance p
           JOIN hmay_users u ON u.id=p.user_id
           WHERE u.role IN ('user','aluno') AND u.active=1"""
    args=[]
    if year:
        sql+=' AND p.applied_on LIKE ?'
        args.append(year+'%')
    sql+=' ORDER BY p.applied_on,p.activity,u.name'
    rows=[]
    for raw in app.db.execute(c,sql,tuple(args)).fetchall():
        row=dict(raw)
        meta=_rx_json(row.get('metadata'))
        raw_class=F.text(meta.get('TURMA'),160) or 'Sem turma'
        row['_meta']=meta
        row['_turma']=class_lookup.get(F.norm(raw_class),raw_class)
        row['_token']=_v3712_sim_token(row['activity_key'],row['applied_on'])
        rows.append(row)
    return rows

def _v3712_options(rows):
    options={}
    for row in rows:
        options[row['_token']]={
            'token':row['_token'],'activityKey':row['activity_key'],
            'activity':row['activity'],'date':row['applied_on'],
        }
    return sorted(options.values(),key=lambda x:(x['date'],F.norm(x['activity'])),reverse=True)

def _v3712_class_analytics(app,c,query):
    year=_v3712_query_scalar(query,'year',4)
    selected=_v3712_selected_sims(query)
    rows=_v3712_rows(app,c,year)
    area_maps=_v36_exam_area_maps(app,c)
    options=_v3712_options(rows)
    buckets={}
    for row in rows:
        if selected and row['_token'] not in selected:
            continue
        bucket=buckets.setdefault(row['_turma'],_v3712_bucket())
        _v3712_add(bucket,row,row['_meta'],area_maps)
    classes=[]
    for turma,bucket in buckets.items():
        classes.append({'turma':turma,**_v3712_summary(bucket)})
    classes.sort(key=lambda x:F.norm(x['turma']))
    return {
        'year':year,'selectedSims':sorted(selected),
        'simulations':options,'classes':classes,
    }

def _v3712_class_detail(app,c,query):
    year=_v3712_query_scalar(query,'year',4)
    turma=_v3712_query_scalar(query,'turma',160)
    selected=_v3712_selected_sims(query)
    if not turma:
        raise ValueError('Turma não informada.')
    rows=_v3712_rows(app,c,year)
    area_maps=_v36_exam_area_maps(app,c)
    buckets={}
    labels={}
    for row in rows:
        if row['_turma']!=turma:
            continue
        if selected and row['_token'] not in selected:
            continue
        bucket=buckets.setdefault(row['_token'],_v3712_bucket())
        labels[row['_token']]={'activityKey':row['activity_key'],'activity':row['activity'],'date':row['applied_on']}
        _v3712_add(bucket,row,row['_meta'],area_maps)
    result=[]
    for token,bucket in buckets.items():
        result.append({'token':token,**labels[token],**_v3712_summary(bucket)})
    result.sort(key=lambda x:(x['date'],F.norm(x['activity'])),reverse=True)
    return {'turma':turma,'simulations':result}

def _v3712_student_detail(app,c,query):
    turma=_v3712_query_scalar(query,'turma',160)
    activity_key=_v3712_query_scalar(query,'activityKey',250)
    date=_v3712_query_scalar(query,'date',40)
    if not turma or not activity_key or not date:
        raise ValueError('Turma, simulado e data são obrigatórios.')
    rows=_v3712_rows(app,c,date[:4] if len(date)>=4 else '')
    area_maps=_v36_exam_area_maps(app,c)
    students=[]
    for row in rows:
        if row['_turma']!=turma or row['activity_key']!=activity_key or row['applied_on']!=date:
            continue
        bucket=_v3712_bucket()
        _v3712_add(bucket,row,row['_meta'],area_maps)
        summary=_v3712_summary(bucket)
        students.append({
            'userId':row['user_id'],'name':row['student_name'],'username':row['username'],
            **summary,
        })
    students.sort(key=lambda x:(-(x['enem'] if x['enem'] is not None else -1e9),F.norm(x['name'])))
    for index,row in enumerate(students,1):
        row['ranking']=index
    return {'turma':turma,'activityKey':activity_key,'date':date,'students':students}

def handle(app,c,user,path,method,data,query,start,HTTPError):
    if path in (
        '/api/model-data/management-class-analytics',
        '/api/model-data/management-class-detail',
        '/api/model-data/management-simulation-students',
    ):
        if user.get('role') not in ('master','coordenador'):
            raise HTTPError(403,'Acesso reservado ao Master e à coordenação.')
        if method!='GET':
            raise HTTPError(405,'Use GET para consultar a análise de turmas.')
        year=app.overview_year(c,user)
        query={**query,'year':year}
        if path.endswith('management-simulation-students') and not _v3712_query_scalar(query,'date',40).startswith(year+'-'):
            raise HTTPError(400,'Selecione um simulado do ano letivo ativo.')
        if path.endswith('management-class-analytics'):
            return app.reply(start,200,_v3712_class_analytics(app,c,query))
        if path.endswith('management-class-detail'):
            return app.reply(start,200,_v3712_class_detail(app,c,query))
        return app.reply(start,200,_v3712_student_detail(app,c,query))
    return _v3712_handle_base(app,c,user,path,method,data,query,start,HTTPError)

# === RESULTS STORE V3.15.0 ===
# O painel da gestão e a análise por turma deixam de reler do banco todos os resultados a
# cada filtro: usam a cópia compacta compartilhada de results_store, refeita só quando os
# dados mudam. A saída é a mesma de antes (v3.6 + máximos da v3.7 + filtros da v3.7.11).
import results_store as _RS

_v315_area_maps_builder=_v36_exam_area_maps

def _v36_exam_area_maps(app,c):
    return _RS.STORE.area_maps(app,c,_v315_area_maps_builder)[0]

def _v315_active_students(app,c):
    rows=app.db.execute(
        c,"SELECT id,name,username FROM hmay_users WHERE role IN ('user','aluno') AND active=1"
    ).fetchall()
    return {row['id']:(row['name'],row['username']) for row in rows}

_v315_row_accuracy_base=_v3712_row_accuracy

def _v3712_row_accuracy(row,metadata,area_maps):
    record=row.get('_rec') if isinstance(row,dict) else None
    if record is None:
        return _v315_row_accuracy_base(row,metadata,area_maps)
    return _RS.STORE.accuracy(record,area_maps)

def _overview_students(app,c,year):
    rows=app.db.execute(c,'''SELECT u.id,u.name,u.username FROM hmay_users u
        LEFT JOIN hmay_academic_year y ON y.user_id=u.id
        WHERE u.role IN ('user','aluno') AND u.active=1 AND
        (COALESCE(y.active_year,CAST(substr(u.created_at,1,4) AS INTEGER))=?
        OR EXISTS (SELECT 1 FROM hmay_academic_cycles cy WHERE cy.user_id=u.id AND cy.academic_year=?))''',
        (int(year),int(year))).fetchall()
    return {row['id']:(row['name'],row['username']) for row in rows}

def _v3712_rows(app,c,year=''):
    class_lookup=_v36_class_lookup(app,c)
    students=_overview_students(app,c,year) if year else _v315_active_students(app,c)
    rows=[]
    for record in _RS.STORE.records(app,c):
        names=students.get(record.user)
        if names is None:
            continue
        if year and not record.date.startswith(year):
            continue
        meta=record.md
        raw_class=F.text(meta.get('TURMA'),160) or 'Sem turma'
        rows.append({
            'user_id':record.user,'activity_key':record.key,'activity':record.activity,
            'applied_on':record.date,'student_name':names[0],'username':names[1],
            '_meta':meta,'_turma':class_lookup.get(F.norm(raw_class),raw_class),
            '_token':_v3712_sim_token(record.key,record.date),'_rec':record,
        })
    rows.sort(key=lambda r:(r['applied_on'],r['activity'],r['student_name'] or ''))
    return rows

def _mgmt_dashboard_data(app,c,user,query):
    if user.get('role') not in ('master','coordenador'):
        raise ValueError('Painel gerencial exclusivo do Master e da coordenação.')
    selected={
        'year':app.overview_year(c,user),
        'turma':_v3711_query_scalar(query,'turma',160),
        'activityKey':_v3711_query_scalar(query,'activityKey',250),
        'date':_v3711_query_scalar(query,'date',40),
    }
    year_classes=set()
    class_lookup=_v36_class_lookup(app,c)
    students=_overview_students(app,c,selected['year'])
    area_maps=_v36_exam_area_maps(app,c)

    participants=set();total_correct=0;total_valid=0
    tri_general=[];redactions=[]
    areas={key:{'correct':0,'valid':0,'tri':[]} for key in ('LC','CH','CN','MT')}
    maxima={'LC':None,'CH':None,'CN':None,'MT':None,'RED':None}
    simulations={};classes={};sim_options={};participations=0

    for record in _RS.STORE.records(app,c):
        if record.user not in students:
            continue
        if selected['year'] and not record.date.startswith(selected['year']):
            continue
        class_name=F.text(record.md.get('TURMA'),160) or 'Sem turma'
        canonical=class_lookup.get(F.norm(class_name),class_name)
        year_classes.add(canonical)
        if selected['activityKey'] and record.key!=selected['activityKey']:
            continue
        if selected['date'] and record.date!=selected['date']:
            continue
        metadata=record.md
        if selected['turma'] and canonical!=selected['turma']:
            continue
        date=F.text(record.date,40)
        sim_options[(record.key,date)]={'activityKey':record.key,'activity':record.activity,'date':date}
        participants.add(record.user);participations+=1

        accuracy=_RS.STORE.accuracy(record,area_maps)
        row_correct=accuracy['ALL']['correct'];row_valid=accuracy['ALL']['valid']
        total_correct+=row_correct;total_valid+=row_valid

        scores=_tri_scores_from_metadata(metadata)
        if scores.get('tri') is not None: tri_general.append(scores['tri'])
        if scores.get('redaction') is not None: redactions.append(scores['redaction'])
        for key,score_key in (('LC','lc'),('CH','ch'),('CN','cn'),('MT','mt'),('RED','redaction')):
            value=scores.get(score_key)
            if value is None:
                continue
            try:
                number=float(value)
            except Exception:
                continue
            if maxima[key] is None or number>maxima[key]:
                maxima[key]=number

        skey=(record.key,date)
        sim=simulations.setdefault(skey,{'activityKey':record.key,'activity':record.activity,'date':date,'participants':set(),'correct':0,'valid':0,'triGeneral':[],'lc':[],'ch':[],'cn':[],'mt':[],'redaction':[]})
        sim['participants'].add(record.user);sim['correct']+=row_correct;sim['valid']+=row_valid
        cls=classes.setdefault(canonical,{'turma':canonical,'participants':set(),'correct':0,'valid':0,'triGeneral':[],'redaction':[]})
        cls['participants'].add(record.user);cls['correct']+=row_correct;cls['valid']+=row_valid

        for area_key in ('LC','CH','CN','MT'):
            areas[area_key]['correct']+=accuracy[area_key]['correct']
            areas[area_key]['valid']+=accuracy[area_key]['valid']
        for key,value in (('triGeneral',scores.get('tri')),('lc',scores.get('lc')),('ch',scores.get('ch')),('cn',scores.get('cn')),('mt',scores.get('mt')),('redaction',scores.get('redaction'))):
            if value is not None: sim[key].append(value)
        if scores.get('tri') is not None: cls['triGeneral'].append(scores['tri'])
        if scores.get('redaction') is not None: cls['redaction'].append(scores['redaction'])
        for area_key,score_key in (('LC','lc'),('CH','ch'),('CN','cn'),('MT','mt')):
            value=scores.get(score_key)
            if value is not None: areas[area_key]['tri'].append(value)

    sim_rows=[]
    for sim in simulations.values():
        sim_rows.append({
            'activityKey':sim['activityKey'],'activity':sim['activity'],'date':sim['date'],
            'participants':len(sim['participants']),'correct':sim['correct'],'valid':sim['valid'],
            'accuracy':None if not sim['valid'] else round(100*sim['correct']/sim['valid'],2),
            'triGeneral':_mgmt_mean(sim['triGeneral']),'lc':_mgmt_mean(sim['lc']),'ch':_mgmt_mean(sim['ch']),
            'cn':_mgmt_mean(sim['cn']),'mt':_mgmt_mean(sim['mt']),'redaction':_mgmt_mean(sim['redaction']),
        })
    sim_rows.sort(key=lambda x:(x['date'],F.norm(x['activity'])),reverse=True)

    class_summary=[]
    for cls in classes.values():
        class_summary.append({
            'turma':cls['turma'],'participants':len(cls['participants']),'correct':cls['correct'],'valid':cls['valid'],
            'accuracy':None if not cls['valid'] else round(100*cls['correct']/cls['valid'],2),
            'triGeneral':_mgmt_mean(cls['triGeneral']),'redaction':_mgmt_mean(cls['redaction']),
        })
    class_summary.sort(key=lambda x:(-(x['participants'] or 0),F.norm(x['turma'])))

    area_rows=[]
    for key,label in (('LC','Linguagens'),('CH','Humanas'),('CN','Natureza'),('MT','Matemática')):
        bucket=areas[key]
        area_rows.append({
            'key':key,'name':label,'correct':bucket['correct'],'valid':bucket['valid'],
            'accuracy':None if not bucket['valid'] else round(100*bucket['correct']/bucket['valid'],2),
            'tri':_mgmt_mean(bucket['tri']),'maxTri':maxima[key],
        })
    area_rows.append({'key':'RED','name':'Redação','correct':0,'valid':0,'accuracy':None,'tri':_mgmt_mean(redactions),'maxTri':maxima['RED']})

    exam_rows=app.db.execute(c,'SELECT title,applied_on FROM hmay_exams WHERE applied_on LIKE ? ORDER BY applied_on,title',(selected['year']+'%',)).fetchall()
    catalog={(F.norm(x['title']),F.text(x['applied_on'],40)) for x in exam_rows}
    options=sorted(sim_options.values(),key=lambda x:(x['date'],F.norm(x['activity'])),reverse=True)
    return {
        'filters':{'years':[selected['year']],'turmas':sorted(year_classes),'simulations':options,'selected':selected},
        'kpis':{
            'activeStudents':len(students),'participants':len(participants),'catalogSimulations':len(catalog),'maps':len(exam_rows),
            'simulationsWithResults':len(sim_rows),'participations':participations,'correct':total_correct,'valid':total_valid,
            'accuracy':None if not total_valid else round(100*total_correct/total_valid,2),
            'triGeneral':_mgmt_mean(tri_general),'redaction':_mgmt_mean(redactions),
        },
        'areas':area_rows,'simulations':sim_rows,'classes':class_summary,'scaleMax':1000,
    }

# === EXAM DELETE V3.15.0 ===
_v315_delete_handle_base=handle

def handle(app,c,user,path,method,data,query,start,HTTPError):
    if path in ('/api/model-data/exam-delete-preview','/api/model-data/exam-delete'):
        if method!='POST':
            raise HTTPError(405,'Use POST para excluir dados do simulado.')
        if path.endswith('/exam-delete-preview'):
            return app.reply(start,200,_exam_metadata.delete_preview(app,c,user,data,HTTPError))
        return app.reply(start,200,_exam_metadata.delete(app,c,user,data,HTTPError))
    return _v315_delete_handle_base(app,c,user,path,method,data,query,start,HTTPError)

# === EXAM DETAIL V3.16.0 ===
# Ao clicar num caderno do Mapa de questões: o gabarito, as notas e as respostas vinculadas.

def _v316_number(value):
    try:
        return int(value)
    except Exception:
        return None

def _v316_exam_detail(app,c,user,query,HTTPError):
    if not _exam_metadata.can_edit(user):
        raise HTTPError(403,'A consulta dos cadernos é exclusiva do Master e da coordenação.')
    exam_id=_v3711_query_scalar(query,'examId',160)
    row=app.db.execute(c,'SELECT id,title,applied_on,color,area,items,version,updated_at FROM hmay_exams WHERE id=?',(exam_id,)).fetchone()
    if not row:
        raise HTTPError(404,'Este caderno não foi encontrado. Atualize a lista.')
    try:
        raw_items=json.loads(row['items'] or '[]')
    except Exception:
        raw_items=[]
    items=[]
    qmap={}
    for it in raw_items if isinstance(raw_items,list) else []:
        if not isinstance(it,dict):
            continue
        number=_v316_number(it.get('number'))
        area=str(it.get('area') or '')
        if number and area and number not in qmap:
            qmap[number]=area
        items.append({key:it.get(key) for key in ('number','area','discipline','subject','topic','skill','language','answer')})
    items.sort(key=lambda x:(_v316_number(x.get('number')) or 0,str(x.get('language') or '')))

    class_lookup=_v36_class_lookup(app,c)
    link=_exam_metadata.exam_link(app,'p.metadata')
    rows=app.db.execute(
        c,f'SELECT p.id,p.user_id,p.activity,p.applied_on,p.metrics,p.metadata,p.updated_at,u.name,u.username,u.active '
          f'FROM hmay_performance p LEFT JOIN hmay_users u ON u.id=p.user_id WHERE {link}=?',(exam_id,)).fetchall()
    students=[]
    with_scores=0
    imported=set()
    for r in rows:
        metadata=_rx_json(r['metadata']);metrics=_rx_json(r['metrics'])
        areas={key:{'correct':0,'valid':0} for key in ('LC','CH','CN','MT')}
        correct=valid=0;wrong=[];blank=[]
        for key,value in metrics.items():
            if not isinstance(value,dict):
                continue
            number=_v36_metric_number(key)
            c_=value.get('correct');t_=value.get('total')
            if c_ is None or t_ is None or not t_:
                if number: blank.append(number)
                continue
            try:
                c_=max(0,int(c_));t_=max(0,int(t_))
            except Exception:
                continue
            correct+=c_;valid+=t_
            if number and c_<t_: wrong.append(number)
            area=qmap.get(number) or ('LC' if number and number<=45 else 'CH' if number and number<=90 else 'CN' if number and number<=135 else 'MT' if number and number<=180 else None)
            if area in areas:
                areas[area]['correct']+=c_;areas[area]['valid']+=t_
        scores=_tri_scores_from_metadata(metadata)
        has_scores=any(k=='_ranking' or k.startswith('_tri_') or k.startswith('_redaction_') for k in metadata)
        with_scores+=1 if has_scores else 0
        if metadata.get('_tri_imported_at'): imported.add(str(metadata.get('_tri_imported_at'))[:16])
        raw_class=F.text(metadata.get('TURMA'),160) or 'Sem turma'
        students.append({
            'resultId':r['id'],'userId':r['user_id'],'activity':str(r['activity'] or ''),'date':str(r['applied_on'] or ''),'name':r['name'] or '(conta excluída)','username':r['username'] or '',
            'active':bool(r['active']),'turma':class_lookup.get(F.norm(raw_class),raw_class),
            'language':str(metadata.get('L.E') or ''),'updatedAt':str(r['updated_at'] or ''),
            'correct':correct,'valid':valid,'areas':areas,'wrong':sorted(wrong),'blank':sorted(blank),
            'hasScores':has_scores,'ranking':metadata.get('_ranking'),
            'scores':{key:scores.get(key) for key in ('lc','ch','cn','mt','tri','redaction')},
            'competencies':[metadata.get('_redaction_c%d'%n) for n in range(1,6)],
        })
    students.sort(key=lambda s:(F.norm(s['name']),s['username']))
    return {
        'exam':{'id':row['id'],'title':row['title'],'date':row['applied_on'],'color':row['color'],'area':row['area'] or '',
                'version':row['version'],'updatedAt':str(row['updated_at'] or ''),'questions':len(qmap) or len({x.get('number') for x in items})},
        'items':items,'students':students,
        'summary':{'results':len(students),'withScores':with_scores,'scoresImportedAt':sorted(imported)},
    }

_v316_detail_handle_base=handle

def handle(app,c,user,path,method,data,query,start,HTTPError):
    if path=='/api/model-data/exam-detail':
        if method!='GET':
            raise HTTPError(405,'Use GET para consultar o caderno.')
        return app.reply(start,200,_v316_exam_detail(app,c,user,query,HTTPError))
    return _v316_detail_handle_base(app,c,user,path,method,data,query,start,HTTPError)

# === CORREÇÃO NA INTERFACE · NOTAS TRI V3.17.0 ===
# Valores fora da faixa e turmas não cadastradas viram divergências corrigíveis; nomes que
# não batem com os alunos do simulado aparecem na conferência com sugestões de vínculo.
import difflib as _v317_difflib

_v317_tri_xlsx_rows_base=_tri_xlsx_rows

def _tri_xlsx_rows(data):
    sheets=_v317_tri_xlsx_rows_base(data)
    if data.get('fixes'):
        for sheet in sheets:
            sheet['rows']=_IF.apply(sheet['rows'],sheet['name'],data.get('fixes'))
    return sheets

def _v317_tri_parse(data):
    """Mesmas regras da leitura de notas, mas devolve todas as divergências de uma vez."""
    sheets=_tri_xlsx_rows(data)
    sheet,header_row,header_span,columns,header=_tri_detect_table(sheets)
    label=lambda key:(header[columns[key]] if columns.get(key) is not None and columns[key]<len(header) else key)
    records=[];issues=[]

    def problem(line,row,key,message,options=None,suggest=None):
        col=columns.get(key)
        value=row[col] if col is not None and col<len(row) else ''
        issues.append(_IF.issue(sheet['name'],line,col,label(key),value,message,options,suggest=suggest))

    for source_index,row in enumerate(sheet['rows'][header_row+header_span:],start=header_row+header_span+1):
        def value(key):
            index=columns.get(key)
            return row[index] if index is not None and index<len(row) else ''
        name=F.text(value('name'),250)
        if not name:
            continue
        scores={key:_tri_number(value(key)) for key in _QI_TRI_NUMERIC_KEYS}
        scores['redactionTheme']=F.text(value('redactionTheme'),500) or None
        competencies=[scores[key] for key in ('c1','c2','c3','c4','c5')]
        bad=False
        for index,number in enumerate(competencies,start=1):
            if number is not None and not 0<=number<=200:
                problem(source_index,row,f'c{index}',f'Linha {source_index} ({name}): C{index} deve estar entre 0 e 200.');bad=True
        if scores['redaction'] is not None and not 0<=scores['redaction']<=1000:
            problem(source_index,row,'redaction',f'Linha {source_index} ({name}): a nota de redação deve estar entre 0 e 1000.');bad=True
        if bad:
            continue
        if all(number is not None for number in competencies):
            total=round(sum(competencies),4)
            if scores['redaction'] is None:
                scores['redaction']=total
            elif abs(scores['redaction']-total)>.01:
                shown=int(total) if float(total).is_integer() else total
                problem(source_index,row,'redaction',
                        f'Linha {source_index} ({name}): a nota de redação ({scores["redaction"]:g}) difere da soma C1–C5 ({shown}). '
                        'Corrija a nota ou a competência errada.',[str(shown)],suggest=str(shown))
                continue
        if all(scores.get(key) is None for key in _QI_TRI_SIGNATURE_KEYS):
            continue
        if scores['tri'] is None and all(scores[key] is not None for key in ('lc','ch','cn','mt','redaction')):
            scores['tri']=round(sum(scores[key] for key in ('lc','ch','cn','mt','redaction'))/5,3)
        records.append({
            'name':name,'nameKey':F.norm(name),'group':F.text(value('group'),150),
            'activity':F.text(value('activity'),200),'date':_tri_iso_date(value('date')),
            'language':F.text(value('language'),40),'scores':scores,'line':source_index,
        })
    detected={key:F.text(header[index] if index<len(header) else '',120) for key,index in columns.items()}
    parsed={'sheet':sheet['name'],'headerRow':header_row+1,'columns':detected,'records':records,
            '_columnIndex':dict(columns),'_header':list(header)}
    return parsed,issues

def _tri_parse_ranking(data):
    parsed,issues=_v317_tri_parse(data)
    if issues:
        raise _IF.ImportIssues(issues)
    if not parsed['records']:
        raise ValueError('A planilha foi encontrada, mas não contém notas TRI ou de redação preenchidas.')
    return parsed

def _v317_tri_class_issues(app,c,parsed):
    lookup=_v36_class_lookup(app,c)
    names=[row['name'] for row in _v36_class_rows(app,c,True)]
    col=parsed['_columnIndex'].get('group')
    header=parsed['_header']
    label=header[col] if col is not None and col<len(header) else 'TURMA'
    issues=[];unknown={}
    for record in parsed['records']:
        raw=F.text(record.get('group'),160)
        if not raw:
            if col is not None:
                issues.append(_IF.issue(parsed['sheet'],record['line'],col,label,'',
                                        f'Linha {record["line"]} ({record["name"]}): informe a turma.',names))
            continue
        if F.norm(raw) not in lookup:
            unknown.setdefault(F.norm(raw),[raw,0])[1]+=1
    if col is None and parsed['records']:
        return [_IF.general('A planilha de notas não tem a coluna TURMA. Inclua a coluna no arquivo e envie de novo.')]
    for raw,count in sorted(unknown.values(),key=lambda x:F.norm(x[0])):
        issues.append(_IF.issue(parsed['sheet'],None,col,label,raw,
                                f'Turma "{raw}" não está cadastrada ({count} aluno(s)). Escolha a turma cadastrada correspondente '
                                '(a troca vale para todas as linhas com esse nome) ou cadastre a turma no Painel de bordo.',
                                names,kind='replace'))
    return issues

def _v317_tri_match_issues(parsed,match):
    """Divergências que não impedem a importação: nomes sem aluno no simulado e nomes repetidos."""
    col=parsed['_columnIndex'].get('name')
    header=parsed['_header']
    label=header[col] if col is not None and col<len(header) else 'NOME'
    free=sorted(set(match['withoutScore']),key=F.norm)  # alunos do simulado ainda sem nota nesta planilha
    unmatched={F.norm(n) for n in match['unmatched']}
    conflicted={F.norm(item['name']):item['reason'] for item in match['conflicts']}
    issues=[]
    for record in parsed['records']:
        key=record['nameKey']
        if key in unmatched:
            ranked=sorted(free,key=lambda n:(-_v317_difflib.SequenceMatcher(None,key,F.norm(n)).ratio(),F.norm(n)))
            issues.append(_IF.issue(parsed['sheet'],record['line'],col,label,record['name'],
                                    f'Linha {record["line"]}: "{record["name"]}" não corresponde a nenhum aluno deste simulado. '
                                    'Escolha o aluno correto (os nomes mais parecidos aparecem primeiro) ou ignore a linha.',ranked))
        elif key in conflicted:
            issues.append(_IF.issue(parsed['sheet'],record['line'],col,label,record['name'],
                                    f'Linha {record["line"]}: {conflicted[key]} Ignore as linhas que não são deste simulado.'))
    return issues

def _tri_preview(app,c,data):
    parsed,issues=_v317_tri_parse(data)
    issues+=_v317_tri_class_issues(app,c,parsed)
    if issues:
        raise _IF.ImportIssues(issues)
    if not parsed['records']:
        raise ValueError('A planilha foi encontrada, mas não contém notas TRI ou de redação preenchidas.')
    activity_key=F.text(data.get('activityKey'),250)
    applied_on=F.date_value(data.get('date'))
    match=_tri_match(app,c,parsed,activity_key,applied_on)
    sample=[];changed=unchanged=0
    for pair in match['matched']:
        metadata=_rx_json(pair['target'].get('metadata'))
        old=_tri_scores_from_metadata(metadata)
        new=pair['source']['scores']
        has_change=any(new.get(key) is not None and old.get(key)!=new.get(key) for key in new)
        changed+=int(has_change);unchanged+=int(not has_change)
        if len(sample)<20:
            sample.append({'name':pair['target']['student_name'],'login':pair['target']['student_login'],
                           **{key:new.get(key) for key in _QI_TRI_SIGNATURE_KEYS},'changed':has_change})
    preview={
        'sheet':parsed['sheet'],'sourceRows':len(parsed['records']),'students':len(match['targets']),
        'matched':len(match['matched']),'changed':changed,'unchanged':unchanged,
        'unmatched':len(match['unmatched']),'conflicts':len(match['conflicts']),
        'withoutScore':len(match['withoutScore']),'sample':sample,
        'issues':_v317_tri_match_issues(parsed,match)[:_IF.MAX_ISSUES],
    }
    public={k:v for k,v in parsed.items() if not k.startswith('_')}
    return public,match,preview

# O modelo oficial de TRI (gerado pelo próprio site) usa "NOTA TRI GERAL" e "NOTA DA REDAÇÃO";
# esses nomes não eram reconhecidos: a nota geral era recalculada e a de redação vinha da soma C1–C5.
_TRI_ALIASES['tri']=set(_TRI_ALIASES['tri'])|{'nota tri geral','tri geral','nota geral tri'}
_TRI_ALIASES['redaction']=set(_TRI_ALIASES['redaction'])|{'nota da redacao','redacao nota','nota final da redacao'}
