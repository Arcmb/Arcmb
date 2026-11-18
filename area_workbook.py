"""Area-separated XLSX templates and imports for Meu Cronograma.

The visible workbook is organised as Geral, one worksheet per selected ENEM area,
and Como preencher.  Before the existing v2.4 transaction is executed, the area
workbook is converted in memory to the canonical Resultados/Questoes/Simulado
format.  Existing storage, permissions, conflict checks and analysis are reused.
"""
from __future__ import annotations

import base64
import csv
import hashlib
import io
import json
import re
import time
import hmac
import zipfile
from xml.sax.saxutils import escape, quoteattr

import exams as E
import performance as F
import planner as P
import selective as S
import templates_v23 as T
import unified as U

MIME = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
FORMAT_VERSION = 'MC-AREAS-1'
GENERAL_SHEET = 'Geral'
GUIDE_SHEET = 'Como preencher'
RESULT_MARKER = 'RESULTADOS DOS ALUNOS'
MAP_MARKER = 'MAPA DE QUESTÕES'

AREA_ORDER = ('LC', 'CH', 'CN', 'MT', 'RED')
AREA_DEFS = {
    'LC': {
        'sheet': 'Linguagens', 'name': 'Linguagens',
        'total': 'Acertos em Linguagens', 'tri': 'Nota TRI Linguagens',
        'disciplines': ['Língua estrangeira', 'Português', 'Literatura', 'Artes',
                        'Educação Física', 'Linguagem corporal', 'TICs'],
    },
    'CH': {
        'sheet': 'Humanas', 'name': 'Humanas',
        'total': 'Acertos em Humanas', 'tri': 'Nota TRI Humanas',
        'disciplines': ['História', 'Geografia', 'Filosofia', 'Sociologia'],
    },
    'CN': {
        'sheet': 'Natureza', 'name': 'Natureza',
        'total': 'Acertos em Natureza', 'tri': 'Nota TRI Natureza',
        'disciplines': ['Biologia', 'Física', 'Química'],
    },
    'MT': {
        'sheet': 'Matemática', 'name': 'Matemática',
        'total': 'Acertos em Matemática', 'tri': 'Nota TRI Matemática',
        'disciplines': ['Matemática'],
    },
    'RED': {
        'sheet': 'Redação', 'name': 'Redação', 'disciplines': ['Redação'],
    },
}
SHEET_TO_AREA = {v['sheet']: k for k, v in AREA_DEFS.items()}
MANDATORY_GENERAL = ('NOME', 'COR DA PROVA', 'TIPO', 'data')
GENERAL_ORDER = ('NOME', 'LOGIN', 'TURMA', 'COR DA PROVA', 'TIPO', 'data', 'L.E',
                 'RANKING', 'TRI', 'BONIFICAÇÃO', 'TRI 10%', 'Acerto')
AREA_GENERAL_KEYS = {
    'Lc', 'Ch', 'Cn', 'Mt', 'TRI LING', 'TRI HUM', 'TRI NAT', 'TRI MAT', 'RED'
}
RED_HEADERS = ['NOME', 'LOGIN', 'TURMA', 'Tema da redação', 'Nota C1', 'Nota C2',
               'Nota C3', 'Nota C4', 'Nota C5', 'Nota de redação']
MAP_HEADERS = E.HEADERS


def _area_payload(data):
    raw = data.get('areas')
    if not isinstance(raw, dict):
        return None
    result = {}
    total_questions = 0
    next_question = 1
    selected_any = False
    for code in AREA_ORDER:
        item = raw.get(code, {})
        if not isinstance(item, dict):
            raise ValueError('Configuração de área inválida.')
        enabled = bool(item.get('enabled', False))
        if not enabled:
            continue
        selected_any = True
        if code == 'RED':
            result[code] = {'enabled': True, 'questions': 0, 'start': None, 'end': None,
                            'skills': False, 'disciplines': ['Redação']}
            continue
        q = F.count_value(item.get('questions'), 'Quantidade de questões de ' + AREA_DEFS[code]['name'])
        if q is None or not 1 <= q <= 180:
            raise ValueError('Informe de 1 a 180 questões para ' + AREA_DEFS[code]['name'] + '.')
        total_questions += q
        if total_questions > 180:
            raise ValueError('A soma das questões das áreas não pode ultrapassar 180.')
        allowed = {F.norm(x): x for x in AREA_DEFS[code]['disciplines']}
        supplied = item.get('disciplines', AREA_DEFS[code]['disciplines'])
        if not isinstance(supplied, list):
            raise ValueError('Seleção de disciplinas inválida em ' + AREA_DEFS[code]['name'] + '.')
        disciplines = []
        for value in supplied:
            name = F.text(value, 140)
            if not name:
                continue
            standard = allowed.get(F.norm(name), name)
            if F.norm(standard) not in {F.norm(x) for x in disciplines}:
                disciplines.append(standard)
        if len(disciplines) > 40:
            raise ValueError('Use no máximo 40 disciplinas por área.')
        start = next_question
        end = start + q - 1
        next_question = end + 1
        result[code] = {
            'enabled': True, 'questions': q, 'start': start, 'end': end,
            'skills': bool(item.get('skills', False)), 'disciplines': disciplines,
        }
    if not selected_any:
        raise ValueError('Selecione ao menos uma área.')
    return result


def _general_fields(data):
    raw = data.get('fields', [])
    if not isinstance(raw, list):
        raise ValueError('Seleção de campos inválida.')
    found = []
    for value in raw:
        c = S.canonical(F.text(value, 200))
        if c.startswith(('Acertos Hab ', 'Acerto/erro questão ', 'Acertos - ', 'Questões - ')):
            continue
        if c in AREA_GENERAL_KEYS:
            continue
        if c not in found:
            found.append(c)
    for c in MANDATORY_GENERAL:
        if c not in found:
            found.append(c)
    ordered = [c for c in GENERAL_ORDER if c in found]
    ordered.extend(c for c in found if c not in ordered)
    return ordered


def _col(n):
    s = ''
    while n:
        n, r = divmod(n - 1, 26)
        s = chr(65 + r) + s
    return s


def _cell(value, row, column, style=0):
    if value is None or value == '':
        return ''
    ref = f'{_col(column)}{row}'
    attrs = f'r="{ref}" s="{style}"'
    if isinstance(value, bool):
        value = int(value)
    if isinstance(value, (int, float)):
        return f'<c {attrs}><v>{value}</v></c>'
    return f'<c {attrs} t="inlineStr"><is><t xml:space="preserve">{escape(str(value))}</t></is></c>'


def _sheet_xml(rows, max_columns, merges=None, validations=None, filter_ref='', freeze_row=0,
               widths=None):
    ns = 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'
    merges = merges or []
    validations = validations or []
    widths = widths or {}
    cols = ''.join(
        f'<col min="{i}" max="{i}" width="{widths.get(i, 18)}" customWidth="1"/>'
        for i in range(1, max_columns + 1)
    )
    body = []
    for row_number, values, style in rows:
        if isinstance(style, int):
            styles = [style] * len(values)
        else:
            styles = list(style) + [0] * max(0, len(values) - len(style))
        cells = ''.join(_cell(v, row_number, i, styles[i - 1]) for i, v in enumerate(values, 1))
        height = 32 if any(s == 1 for s in styles) else 25 if any(s in (2, 3) for s in styles) else 22
        body.append(f'<row r="{row_number}" ht="{height}" customHeight="1">{cells}</row>')
    pane = ''
    if freeze_row:
        pane = f'<pane ySplit="{freeze_row}" topLeftCell="A{freeze_row + 1}" state="frozen"/>'
    merge_xml = ''
    if merges:
        merge_xml = f'<mergeCells count="{len(merges)}">' + ''.join(f'<mergeCell ref="{x}"/>' for x in merges) + '</mergeCells>'
    dv_xml = ''
    if validations:
        chunks = []
        for v in validations:
            attrs = [f'type="{v.get("type", "whole")}"', f'sqref="{v["sqref"]}"',
                     'allowBlank="1"', 'showErrorMessage="1"', 'showInputMessage="1"',
                     'errorStyle="stop"', f'errorTitle={quoteattr(v.get("errorTitle", "Valor inválido"))}',
                     f'error={quoteattr(v.get("error", "Revise o valor informado."))}',
                     f'promptTitle={quoteattr(v.get("promptTitle", "Preenchimento"))}',
                     f'prompt={quoteattr(v.get("prompt", "Preencha conforme a orientação."))}']
            if v.get('operator'):
                attrs.append(f'operator="{v["operator"]}"')
            formula = ''
            if v.get('formula1') is not None:
                formula += f'<formula1>{escape(str(v["formula1"]))}</formula1>'
            if v.get('formula2') is not None:
                formula += f'<formula2>{escape(str(v["formula2"]))}</formula2>'
            chunks.append('<dataValidation ' + ' '.join(attrs) + '>' + formula + '</dataValidation>')
        dv_xml = f'<dataValidations count="{len(chunks)}">' + ''.join(chunks) + '</dataValidations>'
    auto = f'<autoFilter ref="{filter_ref}"/>' if filter_ref else ''
    return (f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            f'<worksheet xmlns="{ns}"><sheetViews><sheetView workbookViewId="0" showGridLines="0">{pane}</sheetView></sheetViews>'
            f'<sheetFormatPr defaultRowHeight="22"/><cols>{cols}</cols><sheetData>{"".join(body)}</sheetData>'
            f'{auto}{merge_xml}{dv_xml}</worksheet>')


def _xlsx(sheets):
    """sheets: [(name, xml)]"""
    ns = 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'
    rels = 'http://schemas.openxmlformats.org/package/2006/relationships'
    office_rel = 'http://schemas.openxmlformats.org/officeDocument/2006/relationships'
    parts = {
        '_rels/.rels': f'<Relationships xmlns="{rels}"><Relationship Id="rId1" Type="{office_rel}/officeDocument" Target="xl/workbook.xml"/></Relationships>',
        'xl/workbook.xml': f'<workbook xmlns="{ns}" xmlns:r="{office_rel}"><workbookPr/><sheets>' + ''.join(
            f'<sheet name={quoteattr(name)} sheetId="{i}" r:id="rId{i}"/>' for i, (name, _) in enumerate(sheets, 1)
        ) + '</sheets><calcPr calcId="191029" calcMode="auto"/></workbook>',
        'xl/_rels/workbook.xml.rels': f'<Relationships xmlns="{rels}">' + ''.join(
            f'<Relationship Id="rId{i}" Type="{office_rel}/worksheet" Target="worksheets/sheet{i}.xml"/>'
            for i in range(1, len(sheets) + 1)
        ) + f'<Relationship Id="rId{len(sheets) + 1}" Type="{office_rel}/styles" Target="styles.xml"/></Relationships>',
        'xl/styles.xml': f'''<styleSheet xmlns="{ns}">
<fonts count="4"><font><sz val="11"/><name val="Calibri"/></font><font><b/><color rgb="FFFFFFFF"/><sz val="16"/><name val="Calibri"/></font><font><b/><color rgb="FFFFFFFF"/><sz val="11"/><name val="Calibri"/></font><font><i/><color rgb="FF514B67"/><sz val="10"/><name val="Calibri"/></font></fonts>
<fills count="5"><fill><patternFill patternType="none"/></fill><fill><patternFill patternType="gray125"/></fill><fill><patternFill patternType="solid"><fgColor rgb="FF332E5E"/><bgColor indexed="64"/></patternFill></fill><fill><patternFill patternType="solid"><fgColor rgb="FF6652A4"/><bgColor indexed="64"/></patternFill></fill><fill><patternFill patternType="solid"><fgColor rgb="FFECE8F8"/><bgColor indexed="64"/></patternFill></fill></fills>
<borders count="2"><border/><border><left style="thin"><color rgb="FFD8D2E8"/></left><right style="thin"><color rgb="FFD8D2E8"/></right><top style="thin"><color rgb="FFD8D2E8"/></top><bottom style="thin"><color rgb="FFD8D2E8"/></bottom></border></borders>
<cellStyleXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0"/></cellStyleXfs>
<cellXfs count="5"><xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0"><alignment vertical="center" wrapText="1"/></xf><xf numFmtId="0" fontId="1" fillId="2" borderId="0" xfId="0" applyFont="1" applyFill="1"><alignment vertical="center"/></xf><xf numFmtId="0" fontId="2" fillId="3" borderId="1" xfId="0" applyFont="1" applyFill="1" applyBorder="1"><alignment vertical="center" wrapText="1"/></xf><xf numFmtId="0" fontId="2" fillId="2" borderId="1" xfId="0" applyFont="1" applyFill="1" applyBorder="1"><alignment vertical="center" wrapText="1"/></xf><xf numFmtId="0" fontId="3" fillId="4" borderId="0" xfId="0" applyFont="1" applyFill="1"><alignment vertical="center" wrapText="1"/></xf></cellXfs>
<cellStyles count="1"><cellStyle name="Normal" xfId="0" builtinId="0"/></cellStyles></styleSheet>''',
        '[Content_Types].xml': '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/><Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/>' + ''.join(
            f'<Override PartName="/xl/worksheets/sheet{i}.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
            for i in range(1, len(sheets) + 1)
        ) + '</Types>',
    }
    for i, (_, xml) in enumerate(sheets, 1):
        parts[f'xl/worksheets/sheet{i}.xml'] = xml
    out = io.BytesIO()
    with zipfile.ZipFile(out, 'w', zipfile.ZIP_DEFLATED) as z:
        for path, text in parts.items():
            z.writestr(path, text.encode('utf-8'))
    return out.getvalue()


def _display(canonical):
    return S.label(canonical)


def export_area_workbook(data, general_rows=None, area_rows=None, map_rows=None):
    areas = _area_payload(data)
    if areas is None:
        raise ValueError('Informe as áreas e a quantidade de questões por área.')
    fields = _general_fields(data)
    general_rows = general_rows or []
    area_rows = area_rows or {}
    map_rows = map_rows or {}
    sheets = []

    general_headers = [_display(x) for x in fields]
    maxc = max(1, len(general_headers))
    rows = [
        (1, ['DADOS GERAIS DOS PARTICIPANTES'], [1] + [0] * (maxc - 1)),
        (2, [f'Formato {FORMAT_VERSION}. Uma linha por participante; os dados da avaliação devem ser iguais em todas as linhas.'], [4] + [0] * (maxc - 1)),
        (4, general_headers, 3),
    ]
    for idx, record in enumerate(general_rows, 5):
        rows.append((idx, [record.get(h, '') for h in general_headers], 0))
    widths = {1: 36}
    for i, h in enumerate(general_headers, 1):
        if h in ('NOME', 'TURMA'):
            widths[i] = 34
        elif 'data' in F.norm(h):
            widths[i] = 16
        else:
            widths[i] = 21
    sheets.append((GENERAL_SHEET, _sheet_xml(rows, maxc, merges=[f'A1:{_col(maxc)}1', f'A2:{_col(maxc)}2'],
                                                   filter_ref=f'A4:{_col(maxc)}5000', freeze_row=4, widths=widths)))

    for code in AREA_ORDER:
        if code not in areas:
            continue
        cfg = areas[code]
        definition = AREA_DEFS[code]
        if code == 'RED':
            headers = ['NOME']
            if 'LOGIN' in fields:
                headers.append('LOGIN')
            if 'TURMA' in fields:
                headers.append('TURMA')
            headers += RED_HEADERS[3:]
            maxc = len(headers)
            rows = [
                (1, ['ÁREA DE REDAÇÃO'], [1] + [0] * (maxc - 1)),
                (2, ['Preencha o tema e as cinco competências. A nota final é a soma de C1 a C5; o importador confere ou calcula o total.'], [4] + [0] * (maxc - 1)),
                (4, [RESULT_MARKER], [2] + [0] * (maxc - 1)),
                (5, headers, 3),
            ]
            for idx, record in enumerate(area_rows.get(code, []), 6):
                rows.append((idx, [record.get(h, '') for h in headers], 0))
            validations = []
            for h in ('Nota C1', 'Nota C2', 'Nota C3', 'Nota C4', 'Nota C5'):
                c = _col(headers.index(h) + 1)
                validations.append(dict(sqref=f'{c}6:{c}5000', type='whole', operator='between', formula1=0, formula2=200,
                                        errorTitle='Nota inválida', error='Use um valor entre 0 e 200.', prompt='Informe de 0 a 200.'))
            c = _col(headers.index('Nota de redação') + 1)
            validations.append(dict(sqref=f'{c}6:{c}5000', type='whole', operator='between', formula1=0, formula2=1000,
                                    errorTitle='Nota inválida', error='Use um valor entre 0 e 1000.', prompt='Soma de C1 a C5.'))
            widths = {1: 36, 4: 42}
            sheets.append((definition['sheet'], _sheet_xml(rows, maxc, merges=[f'A1:{_col(maxc)}1', f'A2:{_col(maxc)}2', f'A4:{_col(maxc)}4'],
                                                              validations=validations, filter_ref=f'A5:{_col(maxc)}5000', freeze_row=5, widths=widths)))
            continue

        numbers = list(range(cfg['start'], cfg['end'] + 1))
        map_header_row = 5
        map_start = 6
        result_marker_row = map_start + len(numbers) + 1
        result_header_row = result_marker_row + 1
        result_start = result_header_row + 1
        identity = ['NOME']
        if 'LOGIN' in fields:
            identity.append('LOGIN')
        if 'TURMA' in fields:
            identity.append('TURMA')
        result_headers = identity[:]
        # Each selected area always carries its own area total and TRI score.
        # The cells may remain blank, but keeping the columns inside the area tab
        # prevents LC/CH/CN/MT results and skills from being mixed.
        result_headers.append(definition['total'])
        result_headers.append(definition['tri'])
        result_headers.extend('Acertos - ' + d for d in cfg['disciplines'])
        if cfg['skills']:
            result_headers.extend(f'Acertos Hab {i:02d}' for i in range(1, 31))
        result_headers.extend(f'Acerto/erro questão {n:02d}' for n in numbers)
        maxc = max(len(MAP_HEADERS), len(result_headers))
        rows = [
            (1, [f'ÁREA DE {definition["name"].upper()}'], [1] + [0] * (maxc - 1)),
            (2, [f'Questões {numbers[0]:02d} a {numbers[-1]:02d}. Numeração contínua conforme a ordem Linguagens, Humanas, Natureza e Matemática.'], [4] + [0] * (maxc - 1)),
            (4, [MAP_MARKER], [2] + [0] * (maxc - 1)),
            (map_header_row, MAP_HEADERS, 3),
        ]
        supplied_map = {int(r.get('QUESTÃO')): r for r in map_rows.get(code, []) if r.get('QUESTÃO') not in (None, '')}
        for offset, n in enumerate(numbers):
            record = supplied_map.get(n, {})
            values = [n, code, record.get('DISCIPLINA', ''), record.get('TÓPICO', ''), record.get('ASSUNTO', ''),
                      record.get('HABILIDADE', ''), record.get('LÍNGUA ESTRANGEIRA', ''), record.get('GABARITO', '')]
            rows.append((map_start + offset, values, 0))
        rows += [
            (result_marker_row, [RESULT_MARKER], [2] + [0] * (maxc - 1)),
            (result_header_row, result_headers, 3),
        ]
        for idx, record in enumerate(area_rows.get(code, []), result_start):
            rows.append((idx, [record.get(h, '') for h in result_headers], 0))
        validations = []
        for h in result_headers:
            if h.startswith('Acerto/erro questão '):
                c = _col(result_headers.index(h) + 1)
                validations.append(dict(sqref=f'{c}{result_start}:{c}5000', type='whole', operator='between', formula1=0, formula2=1,
                                        errorTitle='Use 1 ou 0', error='1 = acerto; 0 = erro; vazio = não informado.',
                                        promptTitle='Resultado da questão', prompt='Digite 1 para acerto ou 0 para erro.'))
        widths = {1: 36}
        for i, h in enumerate(result_headers, 1):
            if h == 'NOME': widths[i] = 36
            elif h.startswith('Acerto/erro'): widths[i] = 13
            elif h.startswith('Acertos H'): widths[i] = 12
            else: widths[i] = max(widths.get(i, 18), 20)
        for i in (3, 4, 5):
            widths[i] = max(widths.get(i, 18), 28)
        sheets.append((definition['sheet'], _sheet_xml(rows, maxc,
            merges=[f'A1:{_col(maxc)}1', f'A2:{_col(maxc)}2', f'A4:{_col(maxc)}4', f'A{result_marker_row}:{_col(maxc)}{result_marker_row}'],
            validations=validations, filter_ref=f'A{result_header_row}:{_col(len(result_headers))}5000', freeze_row=result_header_row, widths=widths)))

    guide = [
        (1, ['COMO PREENCHER'], [1, 0]),
        (3, ['Regra', 'Orientação'], 3),
    ]
    instructions = [
        ('Ordem das abas', 'Geral; Linguagens; Humanas; Natureza; Matemática; Redação. Apenas áreas selecionadas são geradas.'),
        ('Numeração', 'A primeira área selecionada começa na questão 01. A área seguinte continua após a última questão da área anterior.'),
        ('Resultados por questão', 'Use somente 1 para acerto, 0 para erro e deixe vazio quando não houver informação.'),
        ('Habilidades', 'H01 a H30 pertencem à área da própria aba. H01 de Linguagens não é misturada com H01 de Natureza.'),
        ('Mapa da área', 'Preencha disciplina, tópico, assunto e habilidade uma vez por questão, na mesma aba da área.'),
        ('Participantes', 'Cadastre primeiro os participantes na aba Geral. Repita NOME e, quando usado, LOGIN/TURMA nas abas das áreas.'),
        ('Redação', 'A nota final é a soma de C1, C2, C3, C4 e C5. O sistema calcula quando o total estiver vazio e confere quando informado.'),
        ('Importação parcial', 'Vazios não apagam dados anteriores. Zero é valor válido. Resultados novos complementam a avaliação existente.'),
        ('Percentuais', 'Aproveitamento usa apenas questões com 1/0 informado. Cobertura compara as questões respondidas com o mapa preenchido.'),
    ]
    for i, item in enumerate(instructions, 4):
        guide.append((i, list(item), 0))
    sheets.append((GUIDE_SHEET, _sheet_xml(guide, 2, merges=['A1:B1'], freeze_row=3, widths={1: 28, 2: 95})))
    return _xlsx(sheets), MIME


def template(data):
    if not isinstance(data.get('areas'), dict):
        return U.template(data)
    return export_area_workbook(data)


def _matrix(data, sheet=''):
    rows, epoch, sheets, selected, blob = S.matrix({**data, 'sheet': sheet})
    return rows, epoch, sheets, selected, blob


def is_area_file(data):
    try:
        _, _, sheets, _, _ = _matrix(data)
    except ValueError:
        return False
    return GENERAL_SHEET in sheets and any(AREA_DEFS[c]['sheet'] in sheets for c in AREA_ORDER)


def _find_row(rows, predicate, label):
    for index, row in enumerate(rows):
        if predicate(row):
            return index
    raise ValueError(label + ' não foi encontrado.')


def _student_key(name, klass, login):
    return hashlib.sha256(json.dumps([F.norm(name), F.norm(klass), login], ensure_ascii=False).encode()).hexdigest()[:24]


def _value(row, index):
    return row[index] if index < len(row) else None


def _parse_general(data):
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
        if not any(v not in (None, '') for v in row):
            continue
        values = {h: _value(row, i) for i, h in enumerate(headers)}
        name = F.text(values.get('NOME'), 150)
        if not name:
            raise ValueError(f'Aba Geral · linha {line}: informe o nome.')
        login = F.text(values.get('LOGIN'), 40).lower()
        klass = F.text(values.get('TURMA'), 150)
        activity = F.text(values.get('TIPO'), 200)
        if not activity:
            raise ValueError(f'Aba Geral · linha {line}: informe o tipo de prova.')
        applied = F.date_value(values.get('data'), epoch)
        color = F.text(values.get('COR DA PROVA'), 80)
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
    return dict(records=records, order=ordered, headers=headers, title=first['TIPO'], date=first['data'],
                color=first['COR DA PROVA'], epoch=epoch, sheets=sheets, blob=blob)


def _header_map(row):
    result = {}
    for i, value in enumerate(row):
        text = str(value or '').strip()
        if not text:
            continue
        result[i] = text
    return result


def _identity_from_row(row, headers, sheet, line):
    indexed = {S.canonical(h): i for i, h in headers.items()}
    if 'NOME' not in indexed:
        raise ValueError(f'Aba {sheet}: o cabeçalho dos resultados precisa conter NOME.')
    name = F.text(_value(row, indexed['NOME']), 150)
    if not name:
        raise ValueError(f'Aba {sheet} · linha {line}: informe o nome.')
    login = F.text(_value(row, indexed.get('LOGIN', -1)), 40).lower() if 'LOGIN' in indexed else ''
    klass = F.text(_value(row, indexed.get('TURMA', -1)), 150) if 'TURMA' in indexed else ''
    return _student_key(name, klass, login), name, login, klass, indexed


def _strict_binary(value, label):
    if value is None or str(value).strip() == '':
        return None
    return S.item_value(value, label)


def _parse_area_sheet(data, code, expected_start):
    name = AREA_DEFS[code]['sheet']
    rows, epoch, sheets, _, _ = _matrix(data, name)
    marker_index = _find_row(rows, lambda r: any(F.norm(x) == F.norm(RESULT_MARKER) for x in r),
                             f'Marcador {RESULT_MARKER} na aba {name}')
    map_header_index = _find_row(rows[:marker_index], lambda r: any(F.norm(x) == 'questao' for x in r) and
                                                             any(F.norm(x) == 'disciplina' for x in r),
                                 f'Cabeçalho do mapa na aba {name}')
    map_headers = {i: E.ALIASES.get(F.norm(S.fix_header(h)), '') for i, h in enumerate(rows[map_header_index])}
    question_index = next((i for i, h in map_headers.items() if h == 'QUESTÃO'), None)
    if question_index is None:
        raise ValueError('Aba ' + name + ': coluna QUESTÃO ausente.')
    numbers = []
    map_rows = []
    for line, row in enumerate(rows[map_header_index + 1:marker_index], map_header_index + 2):
        number = F.count_value(_value(row, question_index), f'Aba {name} · questão')
        if number is None:
            continue
        if not 1 <= number <= 180:
            raise ValueError(f'Aba {name} · linha {line}: questão fora de 01 a 180.')
        numbers.append(number)
        values = {h: _value(row, i) for i, h in map_headers.items() if h}
        classification = any(str(values.get(k) or '').strip() for k in ('DISCIPLINA', 'TÓPICO', 'ASSUNTO', 'HABILIDADE', 'LÍNGUA ESTRANGEIRA', 'GABARITO'))
        if classification:
            discipline = F.text(values.get('DISCIPLINA'), 150)
            if not discipline:
                raise ValueError(f'Aba {name} · linha {line}: informe a disciplina da questão {number}.')
            skill = F.text(values.get('HABILIDADE'), 40).upper().replace(' ', '')
            if skill:
                m = re.fullmatch(r'(?:C\d+)?H0*([1-9]|[12][0-9]|30)', skill)
                if not m:
                    raise ValueError(f'Aba {name} · linha {line}: habilidade deve ser H01 a H30.')
                skill = 'H' + str(int(m[1])).zfill(2)
            language = E.language(values.get('LÍNGUA ESTRANGEIRA'))
            answer = F.text(values.get('GABARITO'), 30).upper()
            map_rows.append([number, code, discipline, F.text(values.get('TÓPICO'), 250),
                             F.text(values.get('ASSUNTO'), 250), skill, language, answer])
    if not numbers:
        raise ValueError('Aba ' + name + ': mantenha a numeração das questões.')
    if numbers != list(range(expected_start, expected_start + len(numbers))):
        raise ValueError(f'Aba {name}: a numeração deve ser contínua a partir da questão {expected_start:02d}.')
    result_header_index = next((i for i in range(marker_index + 1, len(rows)) if any(str(x or '').strip() for x in rows[i])), None)
    if result_header_index is None:
        raise ValueError('Aba ' + name + ': cabeçalho de resultados ausente.')
    result_headers = _header_map(rows[result_header_index])
    canonical_headers = {i: S.canonical(h) for i, h in result_headers.items()}
    question_headers = {}
    skill_headers = {}
    for i, h in canonical_headers.items():
        if h.startswith('Acerto/erro questão '):
            question_headers[i] = int(h.rsplit(' ', 1)[-1])
        elif re.fullmatch(r'Acertos Hab \d{2}', h):
            skill_headers[i] = int(h.rsplit(' ', 1)[-1])
    expected_numbers = set(numbers)
    if set(question_headers.values()) != expected_numbers:
        missing = sorted(expected_numbers - set(question_headers.values()))
        extra = sorted(set(question_headers.values()) - expected_numbers)
        msg = []
        if missing: msg.append('faltam ' + ', '.join(f'{n:02d}' for n in missing[:12]))
        if extra: msg.append('sobram ' + ', '.join(f'{n:02d}' for n in extra[:12]))
        raise ValueError('Aba ' + name + ': colunas de resultado não correspondem ao intervalo do mapa (' + '; '.join(msg) + ').')
    records = {}
    for line, row in enumerate(rows[result_header_index + 1:], result_header_index + 2):
        if not any(v not in (None, '') for v in row):
            continue
        key, student_name, login, klass, indexed = _identity_from_row(row, result_headers, name, line)
        if key in records:
            raise ValueError(f'Aba {name} · linha {line}: participante repetido.')
        ordinary = {}
        metrics = {}
        metadata = {}
        for i, header in canonical_headers.items():
            value = _value(row, i)
            if i in question_headers:
                n = question_headers[i]
                v = _strict_binary(value, f'Aba {name} · linha {line} · questão {n:02d}')
                metrics[f'questao:{n:03d}'] = dict(name=f'Questão {n:02d}', correct=v, total=1 if v is not None else None)
            elif i in skill_headers:
                n = skill_headers[i]
                v = F.count_value(value, f'Aba {name} · H{n:02d}')
                metrics[f'habilidade:{code}:h{n:02d}'] = dict(name=f'{code} · H{n:02d}', correct=v, total=None)
            elif header.startswith('Acertos - '):
                ordinary[header] = F.count_value(value, f'Aba {name} · {header}')
            elif header in (S.canonical(AREA_DEFS[code]['total']), S.canonical(AREA_DEFS[code]['tri'])):
                ordinary[header] = value
        records[key] = dict(key=key, name=student_name, login=login, group=klass,
                            ordinary=ordinary, metrics=metrics, metadata=metadata, line=line)
    return dict(code=code, name=name, numbers=numbers, map_rows=map_rows, records=records,
                next_question=numbers[-1] + 1)


def _parse_redaction(data):
    name = AREA_DEFS['RED']['sheet']
    rows, epoch, sheets, _, _ = _matrix(data, name)
    header_index = _find_row(rows, lambda r: any(F.norm(x) == 'nome' for x in r) and
                                         any(F.norm(x) == 'nota c1' for x in r),
                             'Cabeçalho da aba Redação')
    raw_headers = _header_map(rows[header_index])
    canonical = {i: S.canonical(h) for i, h in raw_headers.items()}
    by_norm = {F.norm(h): i for i, h in raw_headers.items()}
    records = {}
    for line, row in enumerate(rows[header_index + 1:], header_index + 2):
        if not any(v not in (None, '') for v in row):
            continue
        key, student_name, login, klass, indexed = _identity_from_row(row, raw_headers, name, line)
        if key in records:
            raise ValueError(f'Aba Redação · linha {line}: participante repetido.')
        criteria = []
        metadata = {}
        theme_i = by_norm.get('tema da redacao')
        if theme_i is not None and _value(row, theme_i) not in (None, ''):
            metadata['Redação - Tema'] = F.text(_value(row, theme_i), 500)
        for n in range(1, 6):
            idx = by_norm.get(f'nota c{n}')
            value = F.count_value(_value(row, idx), f'Aba Redação · linha {line} · C{n}') if idx is not None else None
            if value is not None and not 0 <= value <= 200:
                raise ValueError(f'Aba Redação · linha {line}: C{n} deve ficar entre 0 e 200.')
            criteria.append(value)
            if value is not None:
                metadata[f'Redação - C{n}'] = value
        total_i = by_norm.get('nota de redacao')
        total = F.count_value(_value(row, total_i), f'Aba Redação · linha {line} · nota total') if total_i is not None else None
        calculated = sum(criteria) if all(x is not None for x in criteria) else None
        if total is not None and not 0 <= total <= 1000:
            raise ValueError(f'Aba Redação · linha {line}: nota total deve ficar entre 0 e 1000.')
        if total is not None and calculated is not None and total != calculated:
            raise ValueError(f'Aba Redação · linha {line}: a nota total ({total}) difere da soma C1–C5 ({calculated}).')
        if total is None and calculated is not None:
            total = calculated
        if total is not None:
            metadata['Redação - Nota calculada'] = total
        metrics = {f'redacao:c{n}': dict(name=f'Redação · C{n}', correct=v, total=200)
                   for n, v in enumerate(criteria, 1) if v is not None}
        records[key] = dict(key=key, name=student_name, login=login, group=klass,
                            ordinary={'RED': total} if total is not None else {}, metrics=metrics,
                            metadata=metadata, line=line)
    return records


def _canonicalize(data):
    general = _parse_general(data)
    sheets = general['sheets']
    extras = {key: {'metrics': {}, 'metadata': {}} for key in general['records']}
    rows = {key: dict(general['records'][key]['values']) for key in general['records']}
    question_rows = []
    areas_info = []
    expected = 1
    for code in AREA_ORDER:
        sheet = AREA_DEFS[code]['sheet']
        if sheet not in sheets:
            continue
        if code == 'RED':
            red = _parse_redaction(data)
            for key, rec in red.items():
                if key not in rows:
                    raise ValueError(f'Aba Redação: {rec["name"]} não está cadastrado na aba Geral com a mesma turma/login.')
                rows[key].update({k: v for k, v in rec['ordinary'].items() if v is not None})
                extras[key]['metrics'].update(rec['metrics']); extras[key]['metadata'].update(rec['metadata'])
            areas_info.append(dict(code='RED', name='Redação', questions=0, start=None, end=None))
            continue
        parsed = _parse_area_sheet(data, code, expected)
        expected = parsed['next_question']
        question_rows.extend(parsed['map_rows'])
        areas_info.append(dict(code=code, name=AREA_DEFS[code]['name'], questions=len(parsed['numbers']),
                               start=parsed['numbers'][0], end=parsed['numbers'][-1]))
        for key, rec in parsed['records'].items():
            if key not in rows:
                raise ValueError(f'Aba {parsed["name"]}: {rec["name"]} não está cadastrado na aba Geral com a mesma turma/login.')
            for field, value in rec['ordinary'].items():
                if value not in (None, ''):
                    rows[key][field] = value
            extras[key]['metrics'].update(rec['metrics']); extras[key]['metadata'].update(rec['metadata'])
    if expected - 1 > 180:
        raise ValueError('A soma das questões ultrapassa 180.')

    ordinary_keys = set()
    for row in rows.values():
        ordinary_keys.update(row)
    headers = [h for h in GENERAL_ORDER if h in ordinary_keys]
    headers += sorted((h for h in ordinary_keys if h not in headers and not h.startswith('_')),
                      key=lambda x: (0 if x.startswith('Acertos - ') else 1, F.norm(x)))
    output_headers = [_display(h) for h in headers]
    output_rows = [[rows[key].get(h, '') for h in headers] for key in general['order']]
    config = [[general['title'], general['date'], general['color'], '']]
    blob, _ = T.export(output_headers, output_rows, first_name=U.RESULTS,
                       extra_sheets=[(U.QUESTIONS, E.HEADERS, question_rows),
                                     (U.CONFIG, U.CONFIG_HEADERS, config)])
    canonical = dict(filename='areas_convertido.xlsx', file=base64.b64encode(blob).decode(), mapping=data.get('mapping', {}),
                     replace=bool(data.get('replace', False)), replaceMap=bool(data.get('replaceMap', False)))
    extras_keyed = {}
    for key, extra in extras.items():
        g = general['records'][key]
        record_key = (key, F.norm(g['values']['TIPO']), g['values']['data'])
        extras_keyed[record_key] = extra
    original_hash = hashlib.sha256(general['blob']).hexdigest()
    signature = U.encode([areas_info, [[list(key), value] for key, value in sorted(extras_keyed.items())]])
    return dict(payload=canonical, extras=extras_keyed, hash=original_hash, signature=signature,
                areas=areas_info, sheets=sheets, rows=len(general['records']), map_rows=len(question_rows))


def inspect(data):
    if not is_area_file(data):
        return U.inspect(data)
    converted = _canonicalize(data)
    info = U.inspect(converted['payload'])
    info.update(areaFormat=True, areas=converted['areas'], sourceSheets=converted['sheets'])
    return info


def _merge_extras(prepared, extras, replace):
    conflicts = 0
    for item in prepared:
        r = item['record']
        extra = extras.get((r['student'], r['activityKey'], r['date']))
        if not extra:
            continue
        item['metrics'], n = F.merged_metrics(item['metrics'], extra['metrics'], replace)
        conflicts += n
        for key, value in extra['metadata'].items():
            if value in (None, ''):
                continue
            if key in item['metadata'] and item['metadata'][key] != value:
                conflicts += 1
                if not replace:
                    continue
            item['metadata'][key] = value
        old_metrics = json.loads(item['existing']['metrics']) if item['existing'] else {}
        old_metadata = json.loads(item['existing']['metadata']) if item['existing'] else {}
        item['changed'] = not item['existing'] or item['metrics'] != old_metrics or item['metadata'] != old_metadata
    return conflicts


def prepare(app, c, user, data):
    converted = _canonicalize(data)
    payload = {**converted['payload'], 'mapping': data.get('mapping', {}),
               'replace': bool(data.get('replace', False)), 'replaceMap': bool(data.get('replaceMap', False))}
    p = U.prepare(app, c, user, payload)
    added_conflicts = _merge_extras(p['prepared'], converted['extras'], bool(data.get('replace', False)))
    p['summary']['conflicts'] += added_conflicts
    p['summary']['updated'] = sum(x['existing'] is not None and x['changed'] for x in p['prepared'])
    p['summary']['unchanged'] = sum(not x['changed'] for x in p['prepared'])
    p['summary']['areas'] = converted['areas']
    p['signed'] = U.encode([p['signed'], converted['hash'], converted['signature']])
    p['areaFormat'] = True
    return p


def analyse(exam, metrics, metadata):
    return U.analyse(exam, metrics, metadata)


def handle(app, c, user, path, method, data, query, start, HTTPError):
    if user['role'] not in ('master', 'coordenador'):
        raise HTTPError(403, 'Área exclusiva do Master e da coordenação.')
    if method != 'POST':
        raise HTTPError(405, 'Método não permitido.')
    if path == '/api/workbook/template':
        blob, mime = template(data)
        filename = 'Modelo_resultados_por_areas.xlsx' if isinstance(data.get('areas'), dict) else 'Modelo_unico_resultados_questoes.xlsx'
        return app.reply(start, 200, blob, mime, [('Content-Disposition', f'attachment; filename="{filename}"')])
    if path == '/api/workbook/inspect':
        info = inspect(data)
        return app.reply(start, 200, {k: v for k, v in info.items() if not k.startswith('_') and k != 'hash'})
    if path not in ('/api/workbook/preview', '/api/workbook/confirm'):
        raise HTTPError(404, 'Página não encontrada.')
    if not is_area_file(data):
        return U.handle(app, c, user, path, method, data, query, start, HTTPError)
    p = prepare(app, c, user, data)
    if path.endswith('/preview'):
        stamp = int(time.time())
        sample = [dict(name=x['record']['name'], activity=x['record']['activity'], date=x['record']['date'],
                       analysis=analyse(p['exam'], x['metrics'], x['metadata']) if p['exam'] else None)
                  for x in p['prepared'][:3]]
        return app.reply(start, 200, dict(summary=p['summary'], students=p['parsed']['students'], accounts=p['accounts'],
                                          mapping=p['mapping'], sample=sample,
                                          token=str(stamp) + '.' + F.sign(app, p['signed'], stamp), areaFormat=True))
    try:
        raw, sig = data.get('token', '').split('.')
        stamp = int(raw)
    except (ValueError, AttributeError):
        raise ValueError('Confira o arquivo antes de confirmar.')
    if not 0 <= time.time() - stamp <= 1800 or not hmac.compare_digest(sig, F.sign(app, p['signed'], stamp)):
        raise HTTPError(409, 'Arquivo, vínculos, mapa ou resultados mudaram. Refaça a conferência.')
    if p['summary']['rows'] and not p['prepared']:
        raise ValueError('Vincule ao menos um aluno a uma conta existente.')
    if p['summary']['unresolved'] and data.get('skipUnmapped') is not True:
        raise ValueError('Confirme que os alunos sem vínculo não serão importados.')
    U.confirm(app, c, user, p, HTTPError)
    return app.reply(start, 200, dict(ok=True, summary=p['summary'], examId=p['exam']['id'] if p['exam'] else None))


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
