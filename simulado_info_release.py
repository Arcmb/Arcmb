"""Add a canonical 'Informações do simulado' worksheet to v2.5 workbooks.

The existing area parser and analytics are preserved. The consolidated worksheet
becomes the preferred source for question classification, while legacy area maps
remain accepted for backwards compatibility.
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parent
MARKER = '# === MEU CRONOGRAMA V2.6: INFORMAÇÕES DO SIMULADO ==='

EXTENSION = r'''

# === MEU CRONOGRAMA V2.6: INFORMAÇÕES DO SIMULADO ===
import io as _v26_io
import re as _v26_re
import zipfile as _v26_zipfile
import xml.etree.ElementTree as _v26_ET
from xml.sax.saxutils import quoteattr as _v26_quoteattr

SIMULADO_INFO_SHEET = 'Informações do simulado'
SIMULADO_INFO_MARKER = 'MAPA COMPLETO DAS QUESTÕES'
_v26_info_cache = {}


def _v26_exam_values(data):
    exam = data.get('exam') if isinstance(data.get('exam'), dict) else {}
    title = F.text(exam.get('title') or data.get('examTitle') or '', 200)
    applied = F.text(exam.get('date') or data.get('examDate') or '', 40)
    color = F.text(exam.get('color') or data.get('examColor') or '', 80)
    return title, applied, color


def _v26_information_xml(data, areas, map_rows=None):
    map_rows = map_rows or {}
    title, applied, color = _v26_exam_values(data)
    total_questions = sum(cfg.get('questions', 0) for code, cfg in areas.items() if code != 'RED')
    rows = [
        (1, ['INFORMAÇÕES DO SIMULADO'], [1] + [0] * 7),
        (2, ['Preencha os dados da avaliação e classifique cada questão uma única vez. As abas das áreas são destinadas aos resultados dos alunos.'], [4] + [0] * 7),
        (4, ['NOME DO SIMULADO', title], [3, 0]),
        (5, ['DATA DE APLICAÇÃO', applied], [3, 0]),
        (6, ['COR DA PROVA', color], [3, 0]),
        (7, ['TOTAL DE QUESTÕES', total_questions], [3, 0]),
        (9, [SIMULADO_INFO_MARKER], [2] + [0] * 7),
        (10, MAP_HEADERS, 3),
    ]
    row_number = 11
    for code in AREA_ORDER:
        if code not in areas or code == 'RED':
            continue
        cfg = areas[code]
        supplied = {int(r.get('QUESTÃO')): r for r in map_rows.get(code, []) if r.get('QUESTÃO') not in (None, '')}
        for question in range(cfg['start'], cfg['end'] + 1):
            record = supplied.get(question, {})
            rows.append((row_number, [
                question,
                AREA_DEFS[code]['name'],
                record.get('DISCIPLINA', ''),
                record.get('TÓPICO', ''),
                record.get('ASSUNTO', ''),
                record.get('HABILIDADE', ''),
                record.get('LÍNGUA ESTRANGEIRA', ''),
                record.get('GABARITO', ''),
            ], 0))
            row_number += 1
    widths = {1: 13, 2: 18, 3: 25, 4: 30, 5: 34, 6: 16, 7: 22, 8: 14}
    return _sheet_xml(
        rows,
        8,
        merges=['A1:H1', 'A2:H2', 'A9:H9'],
        filter_ref=f'A10:H{max(10, row_number - 1)}',
        freeze_row=10,
        widths=widths,
    )


def _v26_relationship_path(target):
    target = str(target or '').lstrip('/')
    return target if target.startswith('xl/') else 'xl/' + target


def _v26_insert_information_sheet(blob, information_xml, areas):
    with _v26_zipfile.ZipFile(_v26_io.BytesIO(blob), 'r') as source:
        files = {item.filename: source.read(item.filename) for item in source.infolist()}

    workbook_text = files['xl/workbook.xml'].decode('utf-8')
    rels_text = files['xl/_rels/workbook.xml.rels'].decode('utf-8')
    types_text = files['[Content_Types].xml'].decode('utf-8')

    main_ns = 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'
    office_rel_ns = 'http://schemas.openxmlformats.org/officeDocument/2006/relationships'
    package_rel_ns = 'http://schemas.openxmlformats.org/package/2006/relationships'
    workbook_root = _v26_ET.fromstring(files['xl/workbook.xml'])
    rel_root = _v26_ET.fromstring(files['xl/_rels/workbook.xml.rels'])
    rel_targets = {
        rel.get('Id'): _v26_relationship_path(rel.get('Target'))
        for rel in rel_root.findall('{' + package_rel_ns + '}Relationship')
    }
    sheet_paths = {}
    sheet_ids = []
    for sheet in workbook_root.find('{' + main_ns + '}sheets'):
        sheet_ids.append(int(sheet.get('sheetId')))
        rid = sheet.get('{' + office_rel_ns + '}id')
        sheet_paths[sheet.get('name')] = rel_targets.get(rid, '')

    sheet_numbers = [int(m.group(1)) for name in files for m in [_v26_re.fullmatch(r'xl/worksheets/sheet(\d+)\.xml', name)] if m]
    new_sheet_number = max(sheet_numbers, default=0) + 1
    new_sheet_path = f'xl/worksheets/sheet{new_sheet_number}.xml'
    new_sheet_id = max(sheet_ids, default=0) + 1
    rid_numbers = [int(x) for x in _v26_re.findall(r'Id="rId(\d+)"', rels_text)]
    new_rid = 'rId' + str(max(rid_numbers, default=0) + 1)

    sheet_tag = f'<sheet name={_v26_quoteattr(SIMULADO_INFO_SHEET)} sheetId="{new_sheet_id}" r:id="{new_rid}"/>'
    workbook_text, count = _v26_re.subn(
        r'(<sheets[^>]*>\s*<sheet\b[^>]*/>)',
        lambda match: match.group(1) + sheet_tag,
        workbook_text,
        count=1,
        flags=_v26_re.S,
    )
    if count != 1:
        raise RuntimeError('Não foi possível inserir a aba Informações do simulado.')

    relation = (
        f'<Relationship Id="{new_rid}" '
        'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" '
        f'Target="worksheets/sheet{new_sheet_number}.xml"/>'
    )
    rels_text = rels_text.replace('</Relationships>', relation + '</Relationships>', 1)
    override = (
        f'<Override PartName="/xl/worksheets/sheet{new_sheet_number}.xml" '
        'ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
    )
    types_text = types_text.replace('</Types>', override + '</Types>', 1)

    # Keep the legacy map rows in the file for backwards compatibility, but hide
    # them in newly generated area tabs. The visible area section is the table in
    # which each participant has one column per question.
    for code, cfg in areas.items():
        if code == 'RED':
            continue
        path = sheet_paths.get(AREA_DEFS[code]['sheet'])
        if not path or path not in files:
            continue
        xml = files[path].decode('utf-8')
        for row_number in range(4, int(cfg['questions']) + 7):
            needle = f'<row r="{row_number}" '
            if needle in xml and f'<row r="{row_number}" hidden="1" ' not in xml:
                xml = xml.replace(needle, f'<row r="{row_number}" hidden="1" ', 1)
        files[path] = xml.encode('utf-8')

    files['xl/workbook.xml'] = workbook_text.encode('utf-8')
    files['xl/_rels/workbook.xml.rels'] = rels_text.encode('utf-8')
    files['[Content_Types].xml'] = types_text.encode('utf-8')
    files[new_sheet_path] = information_xml.encode('utf-8')

    output = _v26_io.BytesIO()
    with _v26_zipfile.ZipFile(output, 'w', _v26_zipfile.ZIP_DEFLATED) as target:
        for name, content in files.items():
            target.writestr(name, content)
    return output.getvalue()


def _v26_area_code(value):
    normalized = F.norm(value)
    for code, definition in AREA_DEFS.items():
        aliases = {F.norm(code), F.norm(definition['name']), F.norm(definition['sheet']), F.norm('Área de ' + definition['name'])}
        if normalized in aliases:
            return code
    return ''


def _v26_parse_information(data):
    cache_key = (str(data.get('filename', '')), hash(str(data.get('file', ''))))
    if cache_key in _v26_info_cache:
        return _v26_info_cache[cache_key]
    try:
        _, _, sheets, _, _ = _matrix(data)
    except ValueError:
        raise
    if SIMULADO_INFO_SHEET not in sheets:
        _v26_info_cache[cache_key] = None
        return None
    rows, epoch, _, _, _ = _matrix(data, SIMULADO_INFO_SHEET)
    header_index = _find_row(
        rows,
        lambda row: any(F.norm(x) == 'questao' for x in row) and any(F.norm(x) == 'area' for x in row) and any(F.norm(x) == 'disciplina' for x in row),
        'Cabeçalho da aba Informações do simulado',
    )
    metadata = {'title': '', 'date': '', 'color': ''}
    labels = {
        'nome do simulado': 'title',
        'tipo de prova': 'title',
        'data de aplicacao': 'date',
        'cor da prova': 'color',
    }
    for row in rows[:header_index]:
        if not row:
            continue
        key = labels.get(F.norm(row[0]))
        if key and len(row) > 1 and row[1] not in (None, ''):
            if key == 'date':
                metadata[key] = F.date_value(row[1], epoch)
            else:
                metadata[key] = F.text(row[1], 200 if key == 'title' else 80)

    aliases = {
        'questao': 'QUESTÃO', 'area': 'ÁREA', 'disciplina': 'DISCIPLINA',
        'topico': 'TÓPICO', 'assunto': 'ASSUNTO', 'habilidade': 'HABILIDADE',
        'lingua estrangeira': 'LÍNGUA ESTRANGEIRA', 'gabarito': 'GABARITO',
    }
    headers = {i: aliases.get(F.norm(S.fix_header(value)), '') for i, value in enumerate(rows[header_index])}
    question_index = next((i for i, value in headers.items() if value == 'QUESTÃO'), None)
    area_index = next((i for i, value in headers.items() if value == 'ÁREA'), None)
    if question_index is None or area_index is None:
        raise ValueError('Aba Informações do simulado: colunas QUESTÃO e ÁREA são obrigatórias.')

    numbers = {code: [] for code in AREA_ORDER if code != 'RED'}
    maps = {code: [] for code in AREA_ORDER if code != 'RED'}
    seen = set()
    for line, row in enumerate(rows[header_index + 1:], header_index + 2):
        number = F.count_value(_value(row, question_index), 'Aba Informações do simulado · questão')
        if number is None:
            continue
        if not 1 <= number <= 180 or number in seen:
            raise ValueError(f'Aba Informações do simulado · linha {line}: questão inválida ou repetida.')
        seen.add(number)
        code = _v26_area_code(_value(row, area_index))
        if not code or code == 'RED':
            raise ValueError(f'Aba Informações do simulado · linha {line}: informe LC, CH, CN ou MT na área da questão {number:02d}.')
        values = {name: _value(row, i) for i, name in headers.items() if name}
        numbers[code].append(number)
        classification = any(str(values.get(key) or '').strip() for key in ('DISCIPLINA', 'TÓPICO', 'ASSUNTO', 'HABILIDADE', 'LÍNGUA ESTRANGEIRA', 'GABARITO'))
        if classification:
            discipline = F.text(values.get('DISCIPLINA'), 150)
            if not discipline:
                raise ValueError(f'Aba Informações do simulado · linha {line}: informe a disciplina da questão {number:02d}.')
            skill = F.text(values.get('HABILIDADE'), 40).upper().replace(' ', '')
            if skill:
                match = _v26_re.fullmatch(r'(?:C\d+)?H0*([1-9]|[12][0-9]|30)', skill)
                if not match:
                    raise ValueError(f'Aba Informações do simulado · linha {line}: habilidade deve ser H01 a H30.')
                skill = 'H' + str(int(match[1])).zfill(2)
            maps[code].append([
                number, code, discipline,
                F.text(values.get('TÓPICO'), 250),
                F.text(values.get('ASSUNTO'), 250),
                skill,
                E.language(values.get('LÍNGUA ESTRANGEIRA')),
                F.text(values.get('GABARITO'), 30).upper(),
            ])
    result = {**metadata, 'numbers': numbers, 'maps': maps}
    if len(_v26_info_cache) >= 8:
        _v26_info_cache.pop(next(iter(_v26_info_cache)))
    _v26_info_cache[cache_key] = result
    return result


_v25_export_area_workbook = export_area_workbook
_v25_parse_area_sheet = _parse_area_sheet
_v25_parse_general = _parse_general


def export_area_workbook(data, general_rows=None, area_rows=None, map_rows=None):
    blob, mime = _v25_export_area_workbook(data, general_rows, area_rows, map_rows)
    areas = _area_payload(data)
    information_xml = _v26_information_xml(data, areas, map_rows)
    return _v26_insert_information_sheet(blob, information_xml, areas), mime


def _parse_general(data):
    info = _v26_parse_information(data)
    rows, epoch, sheets, _, blob = _matrix(data, GENERAL_SHEET)
    header_index = _find_row(rows, lambda r: 'NOME' in [S.canonical(x) for x in r if str(x or '').strip()] and
                                         'TIPO' in [S.canonical(x) for x in r if str(x or '').strip()] and
                                         'data' in [S.canonical(x) for x in r if str(x or '').strip()],
                             'Cabeçalho da aba Geral')
    raw_headers = [str(x or '').strip() for x in rows[header_index]]
    while raw_headers and not raw_headers[-1]:
        raw_headers.pop()
    headers = [S.canonical(x) for x in raw_headers]
    if len({F.norm(x) for x in headers}) != len(headers):
        raise ValueError('A aba Geral possui cabeçalhos repetidos.')
    for required in MANDATORY_GENERAL:
        if required not in headers:
            raise ValueError('A aba Geral precisa conter ' + _display(required) + '.')
    records = {}
    ordered = []
    titles = set(); dates = set(); colors = set()
    for line, row in enumerate(rows[header_index + 1:], header_index + 2):
        if not any(value not in (None, '') for value in row):
            continue
        values = {header: _value(row, i) for i, header in enumerate(headers)}
        name = F.text(values.get('NOME'), 150)
        if not name:
            raise ValueError(f'Aba Geral · linha {line}: informe o nome.')
        login = F.text(values.get('LOGIN'), 40).lower()
        klass = F.text(values.get('TURMA'), 150)
        activity = F.text(values.get('TIPO'), 200) or (info.get('title', '') if info else '')
        if not activity:
            raise ValueError(f'Aba Geral · linha {line}: informe o tipo de prova na aba Geral ou o nome na aba Informações do simulado.')
        raw_date = values.get('data')
        applied = F.date_value(raw_date, epoch) if raw_date not in (None, '') else (info.get('date', '') if info else '')
        if not applied:
            raise ValueError(f'Aba Geral · linha {line}: informe a data de aplicação na aba Geral ou em Informações do simulado.')
        color = F.text(values.get('COR DA PROVA'), 80) or (info.get('color', '') if info else '')
        if not color:
            raise ValueError(f'Aba Geral · linha {line}: informe a cor da prova ou Única.')
        key = _student_key(name, klass, login)
        if key in records:
            raise ValueError(f'Aba Geral · linha {line}: participante repetido. Use LOGIN para distinguir homônimos.')
        values.update(NOME=name, LOGIN=login, TURMA=klass, TIPO=activity, data=applied, **{'COR DA PROVA': color})
        records[key] = dict(key=key, line=line, name=name, login=login, group=klass, values=values)
        ordered.append(key)
        titles.add(F.norm(activity)); dates.add(applied); colors.add(F.norm(color))
    if not records:
        raise ValueError('Preencha ao menos um participante na aba Geral.')
    if len(titles) != 1 or len(dates) != 1 or len(colors) != 1:
        raise ValueError('A aba Geral deve conter uma única avaliação, data e cor por arquivo.')
    first = records[ordered[0]]['values']
    if info:
        if info.get('title') and F.norm(info['title']) != F.norm(first['TIPO']):
            raise ValueError('O nome do simulado difere entre as abas Geral e Informações do simulado.')
        if info.get('date') and info['date'] != first['data']:
            raise ValueError('A data de aplicação difere entre as abas Geral e Informações do simulado.')
        if info.get('color') and F.norm(info['color']) != F.norm(first['COR DA PROVA']):
            raise ValueError('A cor da prova difere entre as abas Geral e Informações do simulado.')
    return dict(records=records, order=ordered, headers=headers, title=first['TIPO'], date=first['data'],
                color=first['COR DA PROVA'], epoch=epoch, sheets=sheets, blob=blob)


def _parse_area_sheet(data, code, expected_start):
    parsed = _v25_parse_area_sheet(data, code, expected_start)
    info = _v26_parse_information(data)
    if info is None:
        return parsed
    informed_numbers = info['numbers'].get(code, [])
    if informed_numbers != parsed['numbers']:
        expected = ', '.join(f'{number:02d}' for number in parsed['numbers'][:12])
        raise ValueError(f'Aba Informações do simulado: a numeração da área {code} não corresponde à faixa esperada ({expected}).')
    parsed['map_rows'] = info['maps'].get(code, [])
    return parsed
'''


def replace_once(text, old, new, label):
    if text.count(old) != 1:
        raise RuntimeError('Unexpected source while applying v2.6: ' + label)
    return text.replace(old, new, 1)


def prepare():
    area_path = ROOT / 'area_workbook.py'
    text = area_path.read_text(encoding='utf-8')
    if MARKER in text:
        raise RuntimeError('v2.6 extension already present in clean build.')
    area_path.write_text(text + EXTENSION, encoding='utf-8')

    webapp = ROOT / 'webapp.py'
    text = webapp.read_text(encoding='utf-8')
    text = replace_once(text, "ready=True,version='2.5'", "ready=True,version='2.6'", 'readyz version')
    webapp.write_text(text, encoding='utf-8')

    app_html = ROOT / 'static/app.html'
    text = app_html.read_text(encoding='utf-8')
    text = text.replace('v2.5</', 'v2.6</').replace('?v=2.5"', '?v=2.6"')
    app_html.write_text(text, encoding='utf-8')

    # Preserve all old verifiers while aligning their release identity and expected
    # workbook order with the new consolidated sheet.
    for verifier in ROOT.glob('verify_*.py'):
        source = verifier.read_text(encoding='utf-8')
        source = source.replace("=='2.5'", "=='2.6'").replace("'v2.5'in source", "'v2.6'in source")
        source = source.replace("['Geral', 'Linguagens'", "['Geral', 'Informações do simulado', 'Linguagens'")
        source = source.replace("['Geral','Linguagens'", "['Geral','Informações do simulado','Linguagens'")
        verifier.write_text(source, encoding='utf-8')

    print('MEUCRONOGRAMA_V26_PREPARED: consolidated exam information and per-student question columns prepared.')


if __name__ == '__main__':
    prepare()
