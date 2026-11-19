"""Relatórios da escola (v3.10.0) para Master e coordenação.

1. Alunos que pedem atenção  2. Análise por questão  3. Assuntos × turmas
4. Redação por competência e turma  5. Perfis de foco por turma
Coordenação nunca vê contas Especiais (mesma regra de require_target).
"""
import json
import unicodedata
from collections import defaultdict
from functools import lru_cache

import planner as P
import motor_profiles as MOTOR
import results_store as RS

TRI_AREAS = ('_tri_lc', '_tri_ch', '_tri_cn', '_tri_mt')


def _json(value, fallback):
    if isinstance(value, (dict, list)):
        return value
    try:
        out = json.loads(value or '')
        return out if isinstance(out, type(fallback)) else fallback
    except (TypeError, ValueError):
        return fallback


def _r(row, key, default=None):
    try:
        return row[key]
    except (KeyError, IndexError, TypeError):
        return default


def _f(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


@lru_cache(maxsize=8192)
def _norm_text(value):
    text = unicodedata.normalize('NFKD', value).encode('ascii', 'ignore').decode().lower()
    return ' '.join(text.split())


def _norm(value):
    # Os relatórios normalizam os mesmos poucos nomes (disciplina, assunto, turma) milhões
    # de vezes; o resultado de cada texto fica guardado.
    return _norm_text(str(value or ''))


class Data:
    """Carrega uma vez, por requisição, o que todos os relatórios usam."""

    def __init__(self, app, c, user, days=365, year=None):
        self.app, self.c, self.user = app, c, user
        roles = ('aluno', 'user') if user.get('role') == 'coordenador' else ('aluno', 'user', 'especial')
        marks = ','.join('?' for _ in roles)
        self.users = {_r(r, 'id'): dict(r) for r in app.db.execute(
            c, f'SELECT id,username,name,role,active,must_change FROM hmay_users WHERE active=1 AND role IN ({marks})', roles).fetchall()}
        self.year = int(year) if year else None
        self.cutoff = f'{self.year}-01-01' if self.year else P.add(P.today(), -int(days))
        until = f'{self.year}-12-31' if self.year else '9999-12-31'
        # Os resultados vêm da cópia compacta compartilhada (results_store): nada de reler o
        # banco inteiro a cada relatório. "md" e "metrics" são compartilhados: não altere.
        self.rows = []
        for rec in RS.STORE.records(app, c):
            if self.cutoff <= rec.date <= until and rec.user in self.users:
                self.rows.append({'user': rec.user, 'key': rec.key, 'activity': rec.activity,
                                  'date': rec.date, 'md': rec.md, 'metrics': rec})
        try:
            import model_data as MD
            self.lookup = MD._v36_class_lookup(app, c)
        except Exception:
            self.lookup = {}
        self._exams = {}
        self._by_number = {}

    def turma(self, md):
        raw = str(md.get('TURMA') or md.get('Turma') or '').strip()
        return self.lookup.get(_norm(raw)) or self.lookup.get(raw.lower()) or raw or 'Sem turma'

    def metrics(self, row):
        """Respostas do resultado, montadas na hora e descartadas depois (não ficam guardadas)."""
        value = row['metrics']
        if isinstance(value, RS.Record):
            return value.metrics()
        return _json(value, {})

    def states(self, uids, only=None, size=40):
        """(uid, perfil em texto) em lotes, para não ter todos os perfis na memória de uma vez.

        Com "only", só busca no banco os perfis desses alunos; os demais vêm como None.
        """
        uids = list(uids)
        for start in range(0, len(uids), size):
            chunk = uids[start:start + size]
            wanted = [u for u in chunk if only is None or u in only]
            found = {}
            if wanted:
                marks = ','.join('?' for _ in wanted)
                for r in self.app.db.execute(self.c, f'SELECT user_id,profile FROM hmay_state WHERE user_id IN ({marks})', tuple(wanted)).fetchall():
                    found[_r(r, 'user_id')] = _r(r, 'profile')
            for uid in chunk:
                yield uid, found.get(uid)
            del found

    def exam(self, exam_id):
        if exam_id not in self._exams:
            er = self.app.db.execute(self.c, 'SELECT id,title,applied_on,color,items FROM hmay_exams WHERE id=?', (exam_id,)).fetchone()
            self._exams[exam_id] = {'id': exam_id, 'color': _r(er, 'color', ''), 'items': _json(_r(er, 'items'), [])} if er else None
        return self._exams[exam_id]

    def items_by_number(self, ex, lang):
        """Número da questão → item da prova, para o idioma do aluno. Montado uma vez por prova e idioma."""
        key = (ex['id'], lang)
        by_n = self._by_number.get(key)
        if by_n is None:
            by_n = {}
            for it in ex['items']:
                if not isinstance(it, dict):
                    continue
                il = _norm(it.get('language'))
                if il and lang and il != lang:
                    continue
                try:
                    by_n.setdefault(int(it.get('number') or 0), it)
                except (TypeError, ValueError):
                    continue
            self._by_number[key] = by_n
        return by_n

    def simulations(self):
        sims = {}
        for row in self.rows:
            token = row['key'] + '@@' + row['date']
            s = sims.setdefault(token, {'token': token, 'activity': row['activity'], 'date': row['date'], 'participants': 0})
            s['participants'] += 1
        return sorted(sims.values(), key=lambda s: (s['date'], s['activity']), reverse=True)

    def latest_turma(self):
        out = {}
        for row in self.rows:
            out[row['user']] = self.turma(row['md'])
        return out


def _complete(md):
    general = _f(md.get('_tri_general'))
    areas = [_f(md.get(k)) or 0 for k in TRI_AREAS]
    return general if general is not None and min(areas) > 0 else None


def _pct(ok, tot):
    return round(100 * ok / tot, 1) if tot else None


# ---------------------------------------------------------------- 1. atenção

def attention(d, cfg):
    sims = d.simulations()
    big = [s for s in sims if s['participants'] >= max(5, int(0.2 * len(d.users)))]
    latest = big[0] if big else None
    by_user = defaultdict(list)
    for row in d.rows:
        by_user[row['user']].append(row)
    logins = {_r(r, 'actor_id') for r in d.app.db.execute(d.c, "SELECT DISTINCT actor_id FROM hmay_events WHERE kind='login'").fetchall()}
    out = []
    turmas = d.latest_turma()
    for uid, raw_profile in d.states(d.users):
        u = d.users[uid]
        rows = by_user.get(uid, [])
        complete = [(r['date'], _complete(r['md'])) for r in rows if _complete(r['md']) is not None]
        flags = []
        last = complete[-1][1] if complete else None
        delta = round(complete[-1][1] - complete[-2][1], 1) if len(complete) >= 2 else None
        if delta is not None and delta <= -30:
            flags.append(('queda', f'Caiu {abs(delta):.0f} pontos no último simulado'))
        if latest and rows and not any(r['key'] + '@@' + r['date'] == latest['token'] for r in rows):
            flags.append(('falta', f'Não fez o {latest["activity"]}'))
        profile = _json(raw_profile, {})
        if rows:
            sig = MOTOR.signals_from_rows([(r['date'], r['md'], d.metrics(r)) for r in rows], profile, cfg)
            key, _ = MOTOR.classify(sig, cfg)
            if key == 'intensiva':
                flags.append(('recorrencia', f'{sig["recurrentErrors"]} de {sig["errors"]} erros em assuntos repetidos'))
        if int(u.get('must_change') or 0) or uid not in logins:
            flags.append(('acesso', 'Nunca concluiu o primeiro acesso'))
        elif not any(isinstance(a, dict) and a.get('status') == 'available' for a in profile.get('availability', [])):
            flags.append(('horarios', 'Não cadastrou horários livres'))
        if flags:
            out.append({'id': uid, 'name': u['name'], 'username': u['username'], 'turma': turmas.get(uid, 'Sem turma'),
                        'lastTri': last, 'delta': delta, 'flags': [{'kind': k, 'text': t} for k, t in flags]})
    weight = {'queda': 0, 'falta': 1, 'recorrencia': 2, 'horarios': 3, 'acesso': 4}
    out.sort(key=lambda x: (min(weight[f['kind']] for f in x['flags']), -len(x['flags']), x['name']))
    counts = defaultdict(int)
    for x in out:
        for f in x['flags']:
            counts[f['kind']] += 1
    return {'students': out, 'counts': dict(counts), 'latest': latest, 'total': len(d.users)}


# ---------------------------------------------------------------- 2. questões

def questions(d, token, exam_id=None):
    rows = [r for r in d.rows if r['key'] + '@@' + r['date'] == token]
    if not rows:
        return {'simulation': None, 'colors': [], 'questions': [], 'turmas': []}
    by_exam = defaultdict(list)
    for r in rows:
        by_exam[str(r['md'].get('_exam_id') or '')].append(r)
    colors = []
    for eid, rs in by_exam.items():
        ex = d.exam(eid) if eid else None
        colors.append({'examId': eid, 'color': (ex or {}).get('color') or rs[0]['md'].get('COR DA PROVA') or 'Sem cor', 'participants': len(rs)})
    colors.sort(key=lambda x: -x['participants'])
    eid = exam_id if exam_id in by_exam else colors[0]['examId']
    ex = d.exam(eid) or {'items': []}
    items = {}
    for it in ex['items']:
        if isinstance(it, dict):
            try:
                n = int(it.get('number') or 0)
            except (TypeError, ValueError):
                continue
            items.setdefault(n, it)
    stats = {}
    turmas = set()
    for r in by_exam[eid]:
        t = d.turma(r['md'])
        turmas.add(t)
        for k, v in d.metrics(r).items():
            if not k.startswith('questao:') or not isinstance(v, dict) or v.get('correct') not in (0, 1):
                continue
            n = int(k.split(':')[1])
            s = stats.setdefault(n, {'ok': 0, 'tot': 0, 'turma': defaultdict(lambda: [0, 0]), 'letters': defaultdict(int)})
            s['ok'] += v['correct']; s['tot'] += 1
            s['turma'][t][0] += v['correct']; s['turma'][t][1] += 1
            letter = str(v.get('response') or '').strip().upper()
            if v['correct'] == 0 and letter in ('A', 'B', 'C', 'D', 'E'):
                s['letters'][letter] += 1
    out = []
    for n, s in sorted(stats.items()):
        it = items.get(n, {})
        wrong = sum(s['letters'].values())
        top = max(s['letters'].items(), key=lambda x: x[1]) if s['letters'] else None
        out.append({'number': n, 'area': it.get('area', ''), 'discipline': it.get('discipline', ''), 'topic': it.get('topic', ''),
                    'subject': it.get('subject', ''), 'skill': it.get('skill', ''), 'answer': it.get('answer', ''),
                    'accuracy': _pct(s['ok'], s['tot']), 'answered': s['tot'],
                    'turmas': {t: _pct(a, b) for t, (a, b) in s['turma'].items()},
                    'distractor': {'letter': top[0], 'share': _pct(top[1], wrong)} if top and wrong else None})
    sim = next((x for x in d.simulations() if x['token'] == token), None)
    return {'simulation': sim, 'colors': colors, 'examId': eid, 'questions': out, 'turmas': sorted(turmas)}


# ---------------------------------------------------------------- 3. assuntos × turmas

def topics(d, tokens=None, area=''):
    tokens = set(tokens or [])
    cells = defaultdict(lambda: defaultdict(lambda: [0, 0]))
    meta = {}
    turmas = set()
    for r in d.rows:
        if tokens and r['key'] + '@@' + r['date'] not in tokens:
            continue
        ex = d.exam(str(r['md'].get('_exam_id') or ''))
        if not ex:
            continue
        by_n = d.items_by_number(ex, _norm(r['md'].get('L.E')))
        t = d.turma(r['md'])
        turmas.add(t)
        for k, v in d.metrics(r).items():
            if not k.startswith('questao:') or not isinstance(v, dict) or v.get('correct') not in (0, 1):
                continue
            it = by_n.get(int(k.split(':')[1]))
            if not it or str(it.get('answer') or '').upper() == 'ANULADA':
                continue
            if area and str(it.get('area') or '').upper() != area.upper():
                continue
            disc = str(it.get('discipline') or 'Não informada').strip()
            subj = str(it.get('subject') or it.get('topic') or 'Não informado').strip()
            key = (_norm(disc), _norm(subj))
            meta.setdefault(key, (disc, subj, str(it.get('area') or '')))
            cells[key][t][0] += v['correct']; cells[key][t][1] += 1
            cells[key]['__all__'][0] += v['correct']; cells[key]['__all__'][1] += 1
    rows = []
    for key, per in cells.items():
        disc, subj, ar = meta[key]
        total = per['__all__']
        rows.append({'area': ar, 'discipline': disc, 'subject': subj, 'answers': total[1], 'accuracy': _pct(*total),
                     'turmas': {t: _pct(a, b) for t, (a, b) in per.items() if t != '__all__'}})
    rows.sort(key=lambda x: (x['accuracy'] if x['accuracy'] is not None else 999, x['discipline']))
    return {'rows': rows, 'turmas': sorted(turmas)}


# ---------------------------------------------------------------- 4. redação

def redaction(d, tokens=None):
    tokens = set(tokens or [])
    acc = defaultdict(lambda: {'n': 0, 'c': [0.0] * 5, 'total': 0.0})
    for r in d.rows:
        if tokens and r['key'] + '@@' + r['date'] not in tokens:
            continue
        md = r['md']
        comps = [_f(md.get(f'_redaction_c{i}')) for i in range(1, 6)]
        total = _f(md.get('_tri_redaction'))
        if any(x is None for x in comps) or not total:
            continue
        for t in (d.turma(md), '__all__'):
            a = acc[t]
            a['n'] += 1; a['total'] += total
            for i in range(5):
                a['c'][i] += comps[i]
    rows = []
    for t, a in acc.items():
        if not a['n']:
            continue
        cs = [round(x / a['n'], 1) for x in a['c']]
        rows.append({'turma': 'Todas as turmas' if t == '__all__' else t, 'essays': a['n'], 'competencies': cs,
                     'total': round(a['total'] / a['n'], 1), 'weakest': 'C' + str(cs.index(min(cs)) + 1)})
    rows.sort(key=lambda x: (x['turma'] != 'Todas as turmas', x['turma']))
    return {'rows': rows}


# ---------------------------------------------------------------- 5. perfis por turma

def profiles(d, cfg):
    by_user = defaultdict(list)
    for r in d.rows:
        by_user[r['user']].append(r)
    turmas = d.latest_turma()
    table = defaultdict(lambda: {k: 0 for k in MOTOR.PROFILE_KEYS + ('sem',)})
    for uid, raw_profile in d.states(d.users, only=by_user):
        rows = by_user.get(uid, [])
        key = None
        if rows:
            sig = MOTOR.signals_from_rows([(r['date'], r['md'], d.metrics(r)) for r in rows], _json(raw_profile, {}), cfg)
            key, _ = MOTOR.classify(sig, cfg)
        t = turmas.get(uid, 'Sem turma')
        table[t][key or 'sem'] += 1
    labels = {k: cfg['profiles'][k]['label'] for k in MOTOR.PROFILE_KEYS}
    rows = [{'turma': t, **counts, 'students': sum(counts.values())} for t, counts in sorted(table.items())]
    return {'rows': rows, 'labels': labels, 'order': list(MOTOR.PROFILE_KEYS)}


# ---------------------------------------------------------------- respostas item a item

def _answers(d, tokens=None, turma=''):
    """Gera (linha, item, turma, acerto) para cada questão respondida no período."""
    tokens = set(tokens or [])
    for r in d.rows:
        if tokens and r['key'] + '@@' + r['date'] not in tokens:
            continue
        t = d.turma(r['md'])
        if turma and t != turma:
            continue
        ex = d.exam(str(r['md'].get('_exam_id') or ''))
        if not ex:
            continue
        by_n = d.items_by_number(ex, _norm(r['md'].get('L.E')))
        for k, v in d.metrics(r).items():
            if not k.startswith('questao:') or not isinstance(v, dict) or v.get('correct') not in (0, 1):
                continue
            try:
                it = by_n.get(int(k.split(':')[1]))
            except (TypeError, ValueError):
                continue
            if not it or str(it.get('answer') or '').upper() == 'ANULADA':
                continue
            yield r, it, t, v['correct'], ex['id']


def _err(ok, tot):
    return round(100 * (tot - ok) / tot, 1) if tot else None


MIN_ANSWERS = 10


def _priority(error, answers, questions):
    """Regra explicável: dificuldade (erro) combinada com recorrência nos simulados (nº de questões)."""
    if answers < MIN_ANSWERS or error is None:
        return 'dados'
    if error >= 60 or (error >= 50 and questions >= 3):
        return 'alta'
    if error >= 40:
        return 'media'
    return 'baixa'


_PRI_ORDER = {'alta': 0, 'media': 1, 'baixa': 2, 'dados': 3}


# ---------------------------------------------------------------- 6. por disciplina (professor)

def by_discipline(d, tokens=None, turma=''):
    discs = {}
    turmas = set()
    for r, it, t, ok, exam_id in _answers(d, tokens):
        turmas.add(t)
        if turma and t != turma:
            continue
        disc = str(it.get('discipline') or 'Não informada').strip()
        subj = str(it.get('subject') or it.get('topic') or 'Não informado').strip()
        skill = str(it.get('skill') or '').strip() or 'Sem habilidade'
        D = discs.setdefault(_norm(disc), {'name': disc, 'area': str(it.get('area') or ''), 'ok': 0, 'tot': 0, 'subjects': {}, 'skills': {}})
        D['ok'] += ok; D['tot'] += 1
        for bucket, key, label in (('subjects', _norm(subj), subj), ('skills', _norm(skill), skill)):
            e = D[bucket].setdefault(key, {'label': label, 'ok': 0, 'tot': 0, 'questions': set(), 'users': defaultdict(lambda: [0, 0]), 'related': defaultdict(int)})
            e['ok'] += ok; e['tot'] += 1
            e['questions'].add((exam_id, it.get('number')))
            e['users'][r['user']][0] += ok; e['users'][r['user']][1] += 1
            e['related'][skill if bucket == 'subjects' else subj] += 1

    def pack(e):
        error = _err(e['ok'], e['tot'])
        struggling = sum(1 for a, b in e['users'].values() if b >= 2 and (b - a) / b >= 0.5)
        related = [k for k, _ in sorted(e['related'].items(), key=lambda kv: -kv[1])[:3]]
        return {'label': e['label'], 'answers': e['tot'], 'questions': len(e['questions']), 'error': error,
                'students': len(e['users']), 'struggling': struggling, 'related': related,
                'priority': _priority(error, e['tot'], len(e['questions']))}

    try:
        import enem_items as ENEM
        import disciplines_catalog as DC
        enem = ENEM.subject_index(d.app, d.c)
    except Exception:
        enem, DC = {}, None
    out = []
    for D in discs.values():
        packed = []
        for e in D['subjects'].values():
            x = pack(e)
            x['enem'] = enem.get((DC.key(D['name']), DC.key(x['label']))) if DC else None
            packed.append(x)
        subjects = sorted(packed, key=lambda x: (_PRI_ORDER[x['priority']], -(x['error'] or 0)))
        skills = sorted((pack(e) for e in D['skills'].values()), key=lambda x: (_PRI_ORDER[x['priority']], -(x['error'] or 0)))
        out.append({'discipline': D['name'], 'area': D['area'], 'answers': D['tot'], 'error': _err(D['ok'], D['tot']),
                    'high': sum(1 for x in subjects if x['priority'] == 'alta'), 'subjects': subjects, 'skills': skills})
    out.sort(key=lambda x: (x['area'], x['discipline']))
    return {'disciplines': out, 'turmas': sorted(turmas), 'minAnswers': MIN_ANSWERS}


# ---------------------------------------------------------------- 7. mais errados em todas as turmas

def most_missed(d, tokens=None, area='', limit=60):
    cells = defaultdict(lambda: defaultdict(lambda: [0, 0]))
    meta, qs = {}, defaultdict(set)
    turmas = set()
    for r, it, t, ok, exam_id in _answers(d, tokens):
        if area and str(it.get('area') or '').upper() != area.upper():
            continue
        turmas.add(t)
        disc = str(it.get('discipline') or 'Não informada').strip()
        subj = str(it.get('subject') or it.get('topic') or 'Não informado').strip()
        key = (_norm(disc), _norm(subj))
        meta.setdefault(key, (disc, subj, str(it.get('area') or '')))
        qs[key].add((exam_id, it.get('number')))
        for k in (t, '__all__'):
            cells[key][k][0] += ok; cells[key][k][1] += 1
    rows = []
    for key, per in cells.items():
        a, b = per['__all__']
        if b < MIN_ANSWERS:
            continue
        disc, subj, ar = meta[key]
        by_t = {t: _err(x, y) for t, (x, y) in per.items() if t != '__all__' and y >= 3}
        above = [t for t, e in by_t.items() if e is not None and e >= 50]
        worst = max(by_t.items(), key=lambda kv: kv[1])[0] if by_t else ''
        rows.append({'area': ar, 'discipline': disc, 'subject': subj, 'answers': b, 'questions': len(qs[key]), 'error': _err(a, b),
                     'turmas': by_t, 'above': len(above), 'withData': len(by_t), 'everywhere': bool(by_t) and len(above) == len(by_t),
                     'worst': worst})
    rows.sort(key=lambda x: (-x['above'] / max(1, x['withData']), -(x['error'] or 0)))
    return {'rows': rows[:limit], 'turmas': sorted(turmas), 'minAnswers': MIN_ANSWERS}


# ---------------------------------------------------------------- anos letivos

def years(app, c):
    out = set()
    for r in app.db.execute(c, 'SELECT DISTINCT applied_on FROM hmay_performance').fetchall():
        v = str(_r(r, 'applied_on') or '')[:4]
        if v.isdigit():
            out.add(int(v))
    return sorted(out, reverse=True)


# ---------------------------------------------------------------- API

def handle(app, c, user, path, method, data, query, start, HTTPError):
    if user.get('role') not in ('master', 'coordenador'):
        raise HTTPError(403, 'Relatórios da escola reservados ao Master e à coordenação.')
    if method != 'GET':
        raise HTTPError(405, 'Use GET.')
    q = lambda k: (query.get(k, [''])[0] or '').strip()
    year = int(q('year')) if q('year').isdigit() and 2000 <= int(q('year')) <= 2100 else None
    compare = int(q('compare')) if q('compare').isdigit() and 2000 <= int(q('compare')) <= 2100 and int(q('compare')) != year else None
    d = Data(app, c, user, year=year)
    prev = (lambda: Data(app, c, user, year=compare)) if compare else None
    cfg = MOTOR.load_config(app, c)
    tokens = [x for x in q('sims').split('||') if x]
    if path == '/api/school-reports/simulations':
        return app.reply(start, 200, {'simulations': d.simulations(), 'years': years(app, c)})
    if path == '/api/school-reports/attention':
        return app.reply(start, 200, attention(d, cfg))
    if path == '/api/school-reports/questions':
        token = q('sim') or (d.simulations()[0]['token'] if d.simulations() else '')
        return app.reply(start, 200, questions(d, token, q('exam') or None))
    if path == '/api/school-reports/topics':
        out = topics(d, tokens, q('area'))
        if prev:
            old = {(_norm(r['discipline']), _norm(r['subject'])): r['accuracy'] for r in topics(prev(), [], q('area'))['rows']}
            for r in out['rows']:
                r['previous'] = old.get((_norm(r['discipline']), _norm(r['subject'])))
            out['compare'] = compare
        return app.reply(start, 200, out)
    if path == '/api/school-reports/redaction':
        out = redaction(d, tokens)
        if prev:
            old = next((r for r in redaction(prev(), [])['rows'] if r['turma'] == 'Todas as turmas'), None)
            if old:
                out['rows'].append({**old, 'turma': f'Todas as turmas · {compare}', 'previousYear': True})
            out['compare'] = compare
        return app.reply(start, 200, out)
    if path == '/api/school-reports/disciplines':
        out = by_discipline(d, tokens, q('turma'))
        if prev:
            old = {}
            for D in by_discipline(prev(), [], '')['disciplines']:
                old[_norm(D['discipline'])] = D['error']
                for x in D['subjects']:
                    old[(_norm(D['discipline']), 's', _norm(x['label']))] = x['error']
                for x in D['skills']:
                    old[(_norm(D['discipline']), 'h', _norm(x['label']))] = x['error']
            for D in out['disciplines']:
                D['previous'] = old.get(_norm(D['discipline']))
                for x in D['subjects']:
                    x['previous'] = old.get((_norm(D['discipline']), 's', _norm(x['label'])))
                for x in D['skills']:
                    x['previous'] = old.get((_norm(D['discipline']), 'h', _norm(x['label'])))
            out['compare'] = compare
        return app.reply(start, 200, out)
    if path == '/api/school-reports/most-missed':
        out = most_missed(d, tokens, q('area'))
        if prev:
            old = {(_norm(r['discipline']), _norm(r['subject'])): r['error'] for r in most_missed(prev(), [], q('area'), limit=100000)['rows']}
            for r in out['rows']:
                r['previous'] = old.get((_norm(r['discipline']), _norm(r['subject'])))
            out['compare'] = compare
        return app.reply(start, 200, out)
    if path == '/api/school-reports/profiles':
        return app.reply(start, 200, profiles(d, cfg))
    raise HTTPError(404, 'Relatório não encontrado.')
