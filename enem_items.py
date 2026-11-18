"""Banco de itens do ENEM com parâmetros da TRI (v3.13.0).

A coordenação importa uma planilha com disciplina, tópico, conteúdo, habilidade e os parâmetros a, b e c
de cada item. O sistema calcula:

- Dificuldade cobrada (parâmetro b na escala do ENEM, média 500 e desvio 100 dos concluintes de 2009):
  Fácil < 600 · Média 600–699 · Difícil 700–799 · Muito difícil ≥ 800.
  O b dos microdados do Inep vem na escala (0,1); valores entre -10 e 10 são convertidos por 500 + 100·b.
- Complexidade de resolução (parâmetros a e c): o quanto o item exige domínio do conteúdo para ser resolvido.
  Alta: a ≥ 2,5 e c ≤ 0,20 (discrimina bem e quase não dá para acertar no chute).
  Baixa: a < 1,5 ou c ≥ 0,30 (pouco seletivo ou com muito acerto ao acaso).
  Média: os demais. O a na escala do ENEM (valores abaixo de 0,2) é convertido para a escala (0,1) multiplicando por 100.
- Recorrência: quantos itens de cada disciplina, tópico, conteúdo ou habilidade aparecem no banco.
"""
import base64
import json
import re
import unicodedata

import planner as P
import performance as F
import templates_v23 as T
import disciplines_catalog as DC

AREAS = ('LC', 'CH', 'CN', 'MT')
LEVELS = {'discipline': 'Disciplina', 'topic': 'Tópico', 'subject': 'Conteúdo', 'skill': 'Habilidade'}
DIFFICULTY = ('Fácil', 'Média', 'Difícil', 'Muito difícil')
COMPLEXITY = ('Baixa', 'Média', 'Alta')
HEADERS = ['Ano', 'Área', 'Disciplina', 'Tópico', 'Conteúdo', 'Habilidade', 'Parâmetro a', 'Parâmetro b', 'Parâmetro c']
ALIASES = {
    'ano': 'year', 'ano enem': 'year', 'edicao': 'year',
    'area': 'area', 'area do conhecimento': 'area',
    'disciplina': 'discipline',
    'topico': 'topic', 'tema': 'topic',
    'conteudo': 'subject', 'assunto': 'subject',
    'habilidade': 'skill', 'co habilidade': 'skill',
    'parametro a': 'a', 'a': 'a', 'param a': 'a', 'nu param a': 'a', 'discriminacao': 'a',
    'parametro b': 'b', 'b': 'b', 'param b': 'b', 'nu param b': 'b', 'dificuldade': 'b',
    'parametro c': 'c', 'c': 'c', 'param c': 'c', 'nu param c': 'c', 'acerto ao acaso': 'c',
}
GUIDE = [
    ['Uma linha por item', 'Cada linha é uma questão do ENEM. Pode juntar vários anos na mesma planilha.'],
    ['Ano', 'Opcional. Ano da prova (ex.: 2023).'],
    ['Área', 'Opcional. LC, CH, CN ou MT. Se ficar vazia, vem do cadastro de disciplinas.'],
    ['Disciplina', 'Obrigatória. O nome é convertido para o nome oficial do cadastro de disciplinas.'],
    ['Tópico / Conteúdo', 'Conteúdo é obrigatório; tópico é o agrupamento maior (opcional).'],
    ['Habilidade', 'Opcional. Código da Matriz de Referência (ex.: H17).'],
    ['Parâmetro a', 'Discriminação. Aceita a escala dos microdados do Inep (ex.: 2,35) ou a escala do ENEM (ex.: 0,0235).'],
    ['Parâmetro b', 'Dificuldade. Aceita a escala dos microdados (ex.: 1,42) ou a escala do ENEM (ex.: 642).'],
    ['Parâmetro c', 'Acerto ao acaso, de 0 a 0,6 (ex.: 0,18).'],
    ['Dificuldade calculada', 'Fácil abaixo de 600 · Média 600–699 · Difícil 700–799 · Muito difícil a partir de 800 (escala do ENEM).'],
    ['Complexidade calculada', 'Alta: a ≥ 2,5 e c ≤ 0,20. Baixa: a < 1,5 ou c ≥ 0,30. Média: os demais.'],
]


def _key(value):
    text = unicodedata.normalize('NFKD', str(value or '')).encode('ascii', 'ignore').decode('ascii').lower()
    return re.sub(r'\s+', ' ', re.sub(r'[^a-z0-9]+', ' ', text)).strip()


def _num(value):
    if value is None or str(value).strip() == '':
        return None
    try:
        return float(str(value).strip().replace(',', '.'))
    except ValueError:
        return 'erro'


def _row(row, name, default=None):
    try:
        return row[name]
    except (KeyError, IndexError, TypeError):
        return default


def schema(app, c):
    app.db.execute(c, 'CREATE TABLE IF NOT EXISTS hmay_enem_items (id TEXT PRIMARY KEY, year INTEGER, area TEXT NOT NULL, '
                      'discipline TEXT NOT NULL, topic TEXT NOT NULL, subject TEXT NOT NULL, skill TEXT NOT NULL, '
                      'a REAL NOT NULL, b REAL NOT NULL, c REAL NOT NULL, b_enem REAL NOT NULL, a_theta REAL NOT NULL, '
                      'difficulty TEXT NOT NULL, complexity TEXT NOT NULL, created_by TEXT NOT NULL, created_at TEXT NOT NULL)')


def difficulty(b_enem):
    if b_enem < 600:
        return 'Fácil'
    if b_enem < 700:
        return 'Média'
    if b_enem < 800:
        return 'Difícil'
    return 'Muito difícil'


def complexity(a_theta, c):
    if a_theta >= 2.5 and c <= 0.20:
        return 'Alta'
    if a_theta < 1.5 or c >= 0.30:
        return 'Baixa'
    return 'Média'


def scale(a, b):
    b_enem = 500 + 100 * b if -10 <= b <= 10 else b
    a_theta = a * 100 if a < 0.2 else a
    return round(a_theta, 4), round(b_enem, 1)


def template():
    sample = [[2023, 'MT', 'Matemática', 'Geometria', 'Áreas e volumes', 'H08', 2.41, 1.37, 0.17],
              [2023, 'CN', 'Química', 'Estequiometria', 'Cálculo estequiométrico', 'H24', 0.0312, 712, 0.21]]
    return T.export(HEADERS, sample, guide=GUIDE, first_name='Itens ENEM')


def parse(app, c, data):
    filename = str(data.get('filename') or '')
    try:
        blob = base64.b64decode(str(data.get('file') or ''), validate=True)
    except (ValueError, TypeError):
        raise ValueError('Arquivo inválido.')
    rows = F.load_matrix(filename, blob)[0]
    head_i = next((i for i, r in enumerate(rows[:10]) if sum(1 for v in r if ALIASES.get(_key(v))) >= 4), None)
    if head_i is None:
        raise ValueError('Cabeçalho não encontrado. Use a planilha modelo (Disciplina, Conteúdo, Parâmetro a, b e c).')
    cols = {}
    for j, v in enumerate(rows[head_i]):
        k = ALIASES.get(_key(v))
        if k and k not in cols:
            cols[k] = j
    missing = [n for k, n in (('discipline', 'Disciplina'), ('subject', 'Conteúdo'), ('a', 'Parâmetro a'), ('b', 'Parâmetro b'), ('c', 'Parâmetro c')) if k not in cols]
    if missing:
        raise ValueError('Faltam as colunas: ' + ', '.join(missing) + '.')
    catalog, _ = DC.load(app, c)
    idx = DC.index(catalog)
    areas = {DC.key(d['name']): d['area'] for d in catalog['disciplines']}
    items, errors = [], []
    for i, r in enumerate(rows[head_i + 1:], head_i + 2):
        at = lambda k: r[cols[k]] if k in cols and cols[k] < len(r) else None
        if all(str(v or '').strip() == '' for v in r):
            continue
        line = f'Linha {i}'
        disc = DC.canonical(F.text(at('discipline'), 120), idx)
        subject = F.text(at('subject'), 200)
        if not disc or not subject:
            errors.append(f'{line}: informe disciplina e conteúdo.')
            continue
        a, b, cc = _num(at('a')), _num(at('b')), _num(at('c'))
        if 'erro' in (a, b, cc) or None in (a, b, cc):
            errors.append(f'{line}: parâmetros a, b e c devem ser números.')
            continue
        a_theta, b_enem = scale(a, b)
        if not 0 < a_theta <= 10 or not 0 <= cc <= 0.6 or not 0 <= b_enem <= 1500:
            errors.append(f'{line}: parâmetros fora do esperado (a entre 0 e 10, c entre 0 e 0,6, b até 1.500 na escala do ENEM).')
            continue
        area = str(at('area') or '').strip().upper() or areas.get(DC.key(disc), '')
        if area not in AREAS:
            errors.append(f'{line}: informe a área (LC, CH, CN ou MT) ou cadastre a disciplina {disc}.')
            continue
        year = _num(at('year'))
        if year == 'erro' or (year is not None and not 1998 <= year <= 2100):
            errors.append(f'{line}: ano inválido.')
            continue
        items.append({'year': int(year) if year else None, 'area': area, 'discipline': disc, 'topic': F.text(at('topic'), 200) or '',
                      'subject': subject, 'skill': (F.text(at('skill'), 20) or '').upper(), 'a': a, 'b': b, 'c': cc,
                      'b_enem': b_enem, 'a_theta': a_theta, 'difficulty': difficulty(b_enem), 'complexity': complexity(a_theta, cc)})
    if len(items) > 20000:
        raise ValueError('Limite de 20.000 itens por planilha.')
    return items, errors


def _fingerprint(x):
    return (x['year'], DC.key(x['discipline']), DC.key(x['subject']), x['skill'], round(float(x['a']), 5), round(float(x['b']), 5), round(float(x['c']), 5))


def preview(app, c, data):
    items, errors = parse(app, c, data)
    dist = {k: sum(1 for x in items if x['difficulty'] == k) for k in DIFFICULTY}
    comp = {k: sum(1 for x in items if x['complexity'] == k) for k in COMPLEXITY}
    years = sorted({x['year'] for x in items if x['year']})
    return {'valid': len(items), 'errors': errors[:50], 'errorCount': len(errors), 'difficulty': dist, 'complexity': comp,
            'years': years, 'disciplines': sorted({x['discipline'] for x in items}), 'sample': items[:8]}


def confirm(app, c, user, data):
    items, errors = parse(app, c, data)
    if errors and not data.get('ignoreErrors'):
        raise ValueError(f'A planilha tem {len(errors)} linha(s) com erro. Corrija ou confirme importar só as linhas válidas.')
    if not items:
        raise ValueError('Nenhum item válido na planilha.')
    mode = data.get('mode')
    if mode not in ('add', 'replace'):
        raise ValueError('Escolha adicionar ou substituir.')
    if mode == 'replace':
        app.db.execute(c, 'DELETE FROM hmay_enem_items')
        existing = set()
    else:
        existing = {_fingerprint(dict(r)) for r in app.db.execute(c, 'SELECT year,discipline,subject,skill,a,b,c FROM hmay_enem_items').fetchall()}
    stamp, added, skipped = P.now().isoformat(), 0, 0
    for x in items:
        fp = _fingerprint(x)
        if fp in existing:
            skipped += 1
            continue
        existing.add(fp)
        app.db.execute(c, 'INSERT INTO hmay_enem_items(id,year,area,discipline,topic,subject,skill,a,b,c,b_enem,a_theta,difficulty,complexity,created_by,created_at) '
                          'VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',
                       (P.uid(), x['year'], x['area'], x['discipline'], x['topic'], x['subject'], x['skill'], x['a'], x['b'], x['c'],
                        x['b_enem'], x['a_theta'], x['difficulty'], x['complexity'], user['id'], stamp))
        added += 1
    app.event(c, user, user['id'], 'enem_items_import_' + mode)
    return {'added': added, 'skipped': skipped, 'ignored': len(errors), 'mode': mode}


def load_items(app, c, area='', discipline='', year=''):
    schema(app, c)
    sql, args = 'SELECT year,area,discipline,topic,subject,skill,a,b,c,b_enem,a_theta,difficulty,complexity FROM hmay_enem_items WHERE 1=1', []
    if area:
        sql += ' AND area=?'; args.append(area)
    if discipline:
        sql += ' AND discipline=?'; args.append(discipline)
    if year:
        sql += ' AND year=?'; args.append(int(year))
    return [dict(r) for r in app.db.execute(c, sql, tuple(args)).fetchall()]


def summary(items, level):
    if level not in LEVELS:
        level = 'subject'
    groups, totals = {}, {}
    for x in items:
        totals[x['discipline']] = totals.get(x['discipline'], 0) + 1
        label = x[level] or ('Sem ' + LEVELS[level].lower())
        k = (x['discipline'] if level != 'discipline' else '', label)
        g = groups.setdefault(k, {'discipline': x['discipline'], 'area': x['area'], 'label': label, 'items': 0, 'b': 0.0,
                                  'difficulty': {d: 0 for d in DIFFICULTY}, 'complexity': {d: 0 for d in COMPLEXITY}, 'years': set(),
                                  'related': {}})
        g['items'] += 1
        g['b'] += float(x['b_enem'])
        g['difficulty'][x['difficulty']] += 1
        g['complexity'][x['complexity']] += 1
        if x['year']:
            g['years'].add(int(x['year']))
        rel = x['skill'] if level in ('subject', 'topic') else x['subject']
        if rel:
            g['related'][rel] = g['related'].get(rel, 0) + 1
    total = len(items)
    rows = []
    for g in groups.values():
        mean_b = g['b'] / g['items']
        base = total if level == 'discipline' else totals[g['discipline']]
        rows.append({'discipline': g['discipline'], 'area': g['area'], 'label': g['label'], 'items': g['items'],
                     'share': round(100 * g['items'] / base, 1) if base else 0, 'meanB': round(mean_b, 1), 'level': difficulty(mean_b),
                     'difficulty': g['difficulty'], 'complexity': g['complexity'],
                     'highComplexity': round(100 * g['complexity']['Alta'] / g['items'], 1),
                     'years': sorted(g['years']), 'related': [k for k, _ in sorted(g['related'].items(), key=lambda kv: -kv[1])[:3]]})
    rows.sort(key=lambda r: (-r['items'], -r['meanB']))
    return rows


def subject_index(app, c):
    """Para os relatórios: (disciplina, conteúdo) → nº de itens no ENEM, % da disciplina e dificuldade média."""
    try:
        items = load_items(app, c)
    except Exception:
        return {}
    out = {}
    for r in summary(items, 'subject'):
        out[(DC.key(r['discipline']), DC.key(r['label']))] = {'items': r['items'], 'share': r['share'], 'level': r['level'], 'meanB': r['meanB']}
    return out


def handle(app, c, user, path, method, data, query, start, HTTPError):
    if user.get('role') not in ('master', 'coordenador'):
        raise HTTPError(403, 'Banco de itens do ENEM reservado ao Master e à coordenação.')
    schema(app, c)
    q = lambda k: (query.get(k, [''])[0] or '').strip()
    if path == '/api/enem-items/template' and method == 'POST':
        blob, mime = template()
        return app.reply(start, 200, blob, mime, [('Content-Disposition', 'attachment; filename="Modelo_itens_ENEM_TRI.xlsx"')])
    if path == '/api/enem-items/preview' and method == 'POST':
        return app.reply(start, 200, preview(app, c, data))
    if path == '/api/enem-items/confirm' and method == 'POST':
        return app.reply(start, 200, confirm(app, c, user, data))
    if path == '/api/enem-items/summary' and method == 'GET':
        if q('year') and not q('year').isdigit():
            raise ValueError('Ano inválido.')
        items = load_items(app, c, q('area').upper() if q('area').upper() in AREAS else '', q('discipline'), q('year'))
        every = load_items(app, c)
        return app.reply(start, 200, {'rows': summary(items, q('level') or 'subject'), 'total': len(items), 'all': len(every),
                                      'years': sorted({x['year'] for x in every if x['year']}),
                                      'disciplines': sorted({x['discipline'] for x in every}),
                                      'difficulty': {d: sum(1 for x in items if x['difficulty'] == d) for d in DIFFICULTY},
                                      'complexity': {d: sum(1 for x in items if x['complexity'] == d) for d in COMPLEXITY}})
    raise HTTPError(404, 'Página não encontrada.')
