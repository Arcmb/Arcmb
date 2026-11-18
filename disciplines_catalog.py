"""Cadastro de disciplinas oficiais (v3.12.0).

Master e coordenação cadastram o nome oficial de cada disciplina e as variações que aparecem
nas planilhas ("L. corporal", "ESPANHOL"...). Toda importação de mapa de simulado passa a gravar
o nome oficial. Diferenças só de maiúsculas, acentos, pontuação e espaços já são reconhecidas
sem precisar cadastrar a variação. As provas importadas antes podem ser convertidas pelo botão
"Aplicar às provas já importadas", que mostra antes o que vai mudar.
"""
import copy
import json
import re
import unicodedata

import planner as P

AREAS = ('LC', 'CH', 'CN', 'MT')

DEFAULT_CATALOG = {'disciplines': [
    {'name': 'Artes', 'area': 'LC', 'aliases': []},
    {'name': 'Biologia', 'area': 'CN', 'aliases': []},
    {'name': 'Espanhol', 'area': 'LC', 'aliases': []},
    {'name': 'Filosofia', 'area': 'CH', 'aliases': []},
    {'name': 'Física', 'area': 'CN', 'aliases': []},
    {'name': 'Geografia', 'area': 'CH', 'aliases': []},
    {'name': 'História', 'area': 'CH', 'aliases': []},
    {'name': 'Inglês', 'area': 'LC', 'aliases': []},
    {'name': 'Linguagem Corporal', 'area': 'LC', 'aliases': ['L. Corporal']},
    {'name': 'Literatura', 'area': 'LC', 'aliases': []},
    {'name': 'Matemática', 'area': 'MT', 'aliases': []},
    {'name': 'Português', 'area': 'LC', 'aliases': []},
    {'name': 'Química', 'area': 'CN', 'aliases': []},
    {'name': 'Sociologia', 'area': 'CH', 'aliases': []},
    {'name': 'TICs', 'area': 'LC', 'aliases': []},
]}


def key(value):
    """Chave de comparação: sem acento, minúscula, sem pontuação e com espaços simples."""
    text = unicodedata.normalize('NFKD', str(value or '')).encode('ascii', 'ignore').decode('ascii').lower()
    return re.sub(r'\s+', ' ', re.sub(r'[^a-z0-9]+', ' ', text)).strip()


def _json(value, fallback):
    if isinstance(value, (dict, list)):
        return value
    try:
        out = json.loads(value or '')
        return out if isinstance(out, type(fallback)) else fallback
    except (TypeError, ValueError):
        return fallback


def _row(row, name, default=None):
    try:
        return row[name]
    except (KeyError, IndexError, TypeError):
        return default


def schema(app, c):
    app.db.execute(c, 'CREATE TABLE IF NOT EXISTS hmay_discipline_catalog (id TEXT PRIMARY KEY, data TEXT NOT NULL, version INTEGER NOT NULL, updated_by TEXT NOT NULL, updated_at TEXT NOT NULL)')


def validate(data):
    rows = data.get('disciplines') if isinstance(data, dict) else None
    if not isinstance(rows, list) or not rows:
        raise ValueError('Cadastre pelo menos uma disciplina.')
    if len(rows) > 80:
        raise ValueError('Limite de 80 disciplinas.')
    out, owner = [], {}
    for i, r in enumerate(rows, 1):
        if not isinstance(r, dict):
            raise ValueError(f'Linha {i}: formato inválido.')
        name = re.sub(r'\s+', ' ', str(r.get('name') or '')).strip()[:80]
        if not key(name):
            raise ValueError(f'Linha {i}: informe o nome oficial.')
        area = str(r.get('area') or '').strip().upper()
        if area not in AREAS:
            raise ValueError(f'{name}: escolha a área (LC, CH, CN ou MT).')
        raw = r.get('aliases') or []
        if isinstance(raw, str):
            raw = raw.split(';')
        aliases = []
        for a in raw[:30]:
            a = re.sub(r'\s+', ' ', str(a or '')).strip()[:80]
            if key(a) and key(a) != key(name) and key(a) not in [key(x) for x in aliases]:
                aliases.append(a)
        for k in [key(name)] + [key(a) for a in aliases]:
            if k in owner:
                raise ValueError(f'"{k}" aparece em {owner[k]} e em {name}. Cada nome ou variação só pode apontar para uma disciplina.')
            owner[k] = name
        out.append({'name': name, 'area': area, 'aliases': aliases})
    out.sort(key=lambda x: key(x['name']))
    return {'disciplines': out}


def load(app, c):
    schema(app, c)
    row = app.db.execute(c, 'SELECT data,version FROM hmay_discipline_catalog WHERE id=?', ('default',)).fetchone()
    if not row:
        return copy.deepcopy(DEFAULT_CATALOG), 0
    try:
        return validate(_json(_row(row, 'data'), {})), int(_row(row, 'version') or 0)
    except ValueError:
        return copy.deepcopy(DEFAULT_CATALOG), int(_row(row, 'version') or 0)


def save(app, c, user, data, version):
    catalog = validate(data)
    _, current = load(app, c)
    if int(version or 0) != current:
        raise ValueError('O cadastro foi alterado por outra pessoa. Recarregue a página e refaça a alteração.')
    stamp = P.now().isoformat()
    app.db.execute(c, 'DELETE FROM hmay_discipline_catalog WHERE id=?', ('default',))
    app.db.execute(c, 'INSERT INTO hmay_discipline_catalog(id,data,version,updated_by,updated_at) VALUES (?,?,?,?,?)',
                   ('default', json.dumps(catalog, ensure_ascii=False), current + 1, user['id'], stamp))
    app.event(c, user, user['id'], 'discipline_catalog_update')
    return catalog, current + 1


def index(catalog):
    out = {}
    for d in catalog['disciplines']:
        out[key(d['name'])] = d['name']
        for a in d['aliases']:
            out[key(a)] = d['name']
    return out


def canonical(name, idx):
    text = re.sub(r'\s+', ' ', str(name or '')).strip()
    return idx.get(key(text), text)


def canon_items(app, c, items):
    """Troca, no próprio lugar, o nome da disciplina de cada questão pelo nome oficial. Retorna quantas mudaram."""
    catalog, _ = load(app, c)
    idx = index(catalog)
    changed = 0
    for it in items or []:
        if isinstance(it, dict) and it.get('discipline'):
            new = canonical(it['discipline'], idx)
            if new != it['discipline']:
                it['discipline'] = new
                changed += 1
    return changed


def found(app, c, idx):
    """Nomes de disciplina hoje gravados nos mapas de simulado, com o nome oficial correspondente."""
    names = {}
    for r in app.db.execute(c, 'SELECT items FROM hmay_exams').fetchall():
        for it in _json(_row(r, 'items'), []):
            if isinstance(it, dict) and it.get('discipline'):
                n = str(it['discipline'])
                e = names.setdefault(n, {'name': n, 'area': str(it.get('area') or ''), 'questions': 0})
                e['questions'] += 1
    out = []
    for e in names.values():
        official = idx.get(key(e['name']))
        out.append({**e, 'official': official or '', 'changes': bool(official and official != e['name'])})
    out.sort(key=lambda x: (key(x['official'] or x['name']), x['name']))
    return out


def apply_existing(app, c, user, dry_run=True):
    catalog, _ = load(app, c)
    idx = index(catalog)
    exams = changed_items = 0
    for r in app.db.execute(c, 'SELECT id,items,version FROM hmay_exams').fetchall():
        items = _json(_row(r, 'items'), [])
        n = 0
        for it in items:
            if isinstance(it, dict) and it.get('discipline'):
                new = canonical(it['discipline'], idx)
                if new != it['discipline']:
                    it['discipline'] = new
                    n += 1
        if not n:
            continue
        exams += 1
        changed_items += n
        if not dry_run:
            cur = app.db.execute(c, 'UPDATE hmay_exams SET items=?,version=version+1,updated_at=? WHERE id=? AND version=?',
                                 (json.dumps(items, ensure_ascii=False), P.now().isoformat(), _row(r, 'id'), _row(r, 'version')))
            if cur.rowcount != 1:
                raise ValueError('Um mapa de simulado mudou durante a conversão. Nada foi salvo; tente de novo.')
    if not dry_run and exams:
        app.event(c, user, user['id'], 'discipline_catalog_apply')
    return {'exams': exams, 'questions': changed_items, 'applied': not dry_run}


def handle(app, c, user, path, method, data, query, start, HTTPError):
    if user.get('role') not in ('master', 'coordenador'):
        raise HTTPError(403, 'Cadastro de disciplinas reservado ao Master e à coordenação.')
    schema(app, c)
    if path == '/api/disciplines/catalog':
        if method == 'POST':
            catalog, version = save(app, c, user, data.get('catalog'), data.get('version'))
        else:
            catalog, version = load(app, c)
        idx = index(catalog)
        return app.reply(start, 200, {'catalog': catalog, 'version': version, 'found': found(app, c, idx),
                                      'pending': apply_existing(app, c, user, dry_run=True)})
    if path == '/api/disciplines/apply' and method == 'POST':
        return app.reply(start, 200, apply_existing(app, c, user, dry_run=False))
    raise HTTPError(404, 'Página não encontrada.')
