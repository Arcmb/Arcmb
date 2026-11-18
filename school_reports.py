"""Relatórios da escola (v3.10.0) para Master e coordenação.

1. Alunos que pedem atenção  2. Análise por questão  3. Assuntos × turmas
4. Redação por competência e turma  5. Perfis de foco por turma
Coordenação nunca vê contas Especiais (mesma regra de require_target).
"""
import json
from collections import defaultdict

import planner as P
import motor_profiles as MOTOR

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


def _norm(value):
    import unicodedata
    text = unicodedata.normalize('NFKD', str(value or '')).encode('ascii', 'ignore').decode().lower()
    return ' '.join(text.split())


class Data:
    """Carrega uma vez, por requisição, o que todos os relatórios usam."""

    def __init__(self, app, c, user, days=365):
        self.app, self.c, self.user = app, c, user
        roles = ('aluno', 'user') if user.get('role') == 'coordenador' else ('aluno', 'user', 'especial')
        marks = ','.join('?' for _ in roles)
        self.users = {_r(r, 'id'): dict(r) for r in app.db.execute(
            c, f'SELECT id,username,name,role,active,must_change FROM hmay_users WHERE active=1 AND role IN ({marks})', roles).fetchall()}
        self.cutoff = P.add(P.today(), -int(days))
        self.rows = []
        for r in app.db.execute(c, 'SELECT user_id,activity_key,activity,applied_on,metrics,metadata FROM hmay_performance WHERE applied_on>=? ORDER BY applied_on',
                                (self.cutoff,)).fetchall():
            if _r(r, 'user_id') in self.users:
                md = _json(_r(r, 'metadata'), {})
                self.rows.append({'user': _r(r, 'user_id'), 'key': str(_r(r, 'activity_key') or ''), 'activity': str(_r(r, 'activity') or ''),
                                  'date': str(_r(r, 'applied_on') or ''), 'md': md, 'metrics': _r(r, 'metrics')})
        try:
            import model_data as MD
            self.lookup = MD._v36_class_lookup(app, c)
        except Exception:
            self.lookup = {}
        self._exams = {}

    def turma(self, md):
        raw = str(md.get('TURMA') or md.get('Turma') or '').strip()
        return self.lookup.get(_norm(raw)) or self.lookup.get(raw.lower()) or raw or 'Sem turma'

    def metrics(self, row):
        if not isinstance(row['metrics'], dict):
            row['metrics'] = _json(row['metrics'], {})
        return row['metrics']

    def exam(self, exam_id):
        if exam_id not in self._exams:
            er = self.app.db.execute(self.c, 'SELECT id,title,applied_on,color,items FROM hmay_exams WHERE id=?', (exam_id,)).fetchone()
            self._exams[exam_id] = {'id': exam_id, 'color': _r(er, 'color', ''), 'items': _json(_r(er, 'items'), [])} if er else None
        return self._exams[exam_id]

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
    states = {}
    for r in d.app.db.execute(d.c, 'SELECT user_id,profile FROM hmay_state').fetchall():
        if _r(r, 'user_id') in d.users:
            states[_r(r, 'user_id')] = _r(r, 'profile')
    logins = {_r(r, 'actor_id') for r in d.app.db.execute(d.c, "SELECT DISTINCT actor_id FROM hmay_events WHERE kind='login'").fetchall()}
    out = []
    turmas = d.latest_turma()
    for uid, u in d.users.items():
        rows = by_user.get(uid, [])
        complete = [(r['date'], _complete(r['md'])) for r in rows if _complete(r['md']) is not None]
        flags = []
        last = complete[-1][1] if complete else None
        delta = round(complete[-1][1] - complete[-2][1], 1) if len(complete) >= 2 else None
        if delta is not None and delta <= -30:
            flags.append(('queda', f'Caiu {abs(delta):.0f} pontos no último simulado'))
        if latest and rows and not any(r['key'] + '@@' + r['date'] == latest['token'] for r in rows):
            flags.append(('falta', f'Não fez o {latest["activity"]}'))
        profile = _json(states.get(uid), {})
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
        lang = _norm(r['md'].get('L.E'))
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
    states = {_r(r, 'user_id'): _r(r, 'profile') for r in d.app.db.execute(d.c, 'SELECT user_id,profile FROM hmay_state').fetchall() if _r(r, 'user_id') in by_user}
    turmas = d.latest_turma()
    table = defaultdict(lambda: {k: 0 for k in MOTOR.PROFILE_KEYS + ('sem',)})
    for uid in d.users:
        rows = by_user.get(uid, [])
        key = None
        if rows:
            sig = MOTOR.signals_from_rows([(r['date'], r['md'], d.metrics(r)) for r in rows], _json(states.get(uid), {}), cfg)
            key, _ = MOTOR.classify(sig, cfg)
        t = turmas.get(uid, 'Sem turma')
        table[t][key or 'sem'] += 1
    labels = {k: cfg['profiles'][k]['label'] for k in MOTOR.PROFILE_KEYS}
    rows = [{'turma': t, **counts, 'students': sum(counts.values())} for t, counts in sorted(table.items())]
    return {'rows': rows, 'labels': labels, 'order': list(MOTOR.PROFILE_KEYS)}


# ---------------------------------------------------------------- API

def handle(app, c, user, path, method, data, query, start, HTTPError):
    if user.get('role') not in ('master', 'coordenador'):
        raise HTTPError(403, 'Relatórios da escola reservados ao Master e à coordenação.')
    if method != 'GET':
        raise HTTPError(405, 'Use GET.')
    q = lambda k: (query.get(k, [''])[0] or '').strip()
    d = Data(app, c, user)
    cfg = MOTOR.load_config(app, c)
    tokens = [x for x in q('sims').split('||') if x]
    if path == '/api/school-reports/simulations':
        return app.reply(start, 200, {'simulations': d.simulations()})
    if path == '/api/school-reports/attention':
        return app.reply(start, 200, attention(d, cfg))
    if path == '/api/school-reports/questions':
        token = q('sim') or (d.simulations()[0]['token'] if d.simulations() else '')
        return app.reply(start, 200, questions(d, token, q('exam') or None))
    if path == '/api/school-reports/topics':
        return app.reply(start, 200, topics(d, tokens, q('area')))
    if path == '/api/school-reports/redaction':
        return app.reply(start, 200, redaction(d, tokens))
    if path == '/api/school-reports/profiles':
        return app.reply(start, 200, profiles(d, cfg))
    raise HTTPError(404, 'Relatório não encontrado.')
