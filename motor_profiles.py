"""Perfis de foco do motor de estudos (v3.9.0).

Decisões do responsável (18/11/2026):
- Faixas por média ENEM sem bônus (_tri_general): abaixo de 650, 650 a 759, 760 ou mais.
- Só simulados completos (quatro áreas com nota) dos últimos 12 meses; mínimo de 2 simulados
  para a classificação deixar de ser provisória.
- Quatro perfis visíveis ao aluno; a faixa de nota não aparece para o aluno.
- Recorrência medida por assunto: erros em assuntos errados em 2 ou mais simulados.
- Troca automática só quando 2 atualizações seguidas de simulados indicarem o mesmo perfil novo.
- O aluno (ou Master/coordenação pela visão do aluno) pode fixar um perfil; o motor passa a só sugerir.
- Master e coordenação ajustam limites e parâmetros na aba Motor de estudos.
"""
import copy
import json

import planner as P

STUDENT_ROLES = ('aluno', 'user', 'especial')
PROFILE_KEYS = ('base', 'pratica', 'intensiva', 'precisao')

DEFAULT_CONFIG = {
    'thresholds': {'base': 650, 'high': 760, 'recurrence': 0.25, 'accuracyBase': 0.55, 'minSims': 2, 'windowDays': 365},
    'profiles': {
        'base': {'label': 'Base Sólida', 'description': 'Retomar a teoria antes de praticar.',
                 'reviewPlan': 'both', 'theoryMin': 15, 'exerciseMin': 20, 'intervals': [1, 7, 30], 'reviewShare': 0.70},
        'pratica': {'label': 'Prática Ativa', 'description': 'Aprender resolvendo questões.',
                    'reviewPlan': 'exercise_only', 'theoryMin': 5, 'exerciseMin': 25, 'intervals': [1, 7, 30], 'reviewShare': 0.60},
        'intensiva': {'label': 'Revisão Intensiva', 'description': 'Fixar o que ainda escapa.',
                      'reviewPlan': 'both', 'theoryMin': 10, 'exerciseMin': 20, 'intervals': [1, 3, 7, 15, 30], 'reviewShare': 0.70},
        'precisao': {'label': 'Precisão', 'description': 'Lapidar detalhes e ganhar pontos.',
                     'reviewPlan': 'exercise_only', 'theoryMin': 5, 'exerciseMin': 20, 'intervals': [7, 30, 60], 'reviewShare': 0.40},
    },
}


def _json(value, fallback):
    if isinstance(value, (dict, list)):
        return value
    try:
        out = json.loads(value or '')
        return out if isinstance(out, type(fallback)) else fallback
    except (TypeError, ValueError):
        return fallback


def _row(row, key, default=None):
    try:
        return row[key]
    except (KeyError, IndexError, TypeError):
        return default


def schema(app, c):
    app.db.execute(c, 'CREATE TABLE IF NOT EXISTS hmay_motor_config (id TEXT PRIMARY KEY, config TEXT NOT NULL, updated_by TEXT NOT NULL, updated_at TEXT NOT NULL)')
    app.db.execute(c, 'CREATE TABLE IF NOT EXISTS hmay_motor_profile (user_id TEXT PRIMARY KEY, data TEXT NOT NULL, updated_at TEXT NOT NULL)')


# ---------------------------------------------------------------- configuração

def _num(value, low, high, label, cast=float):
    try:
        out = cast(value)
    except (TypeError, ValueError):
        raise ValueError(f'{label}: informe um número.')
    if isinstance(value, bool) or not low <= out <= high:
        raise ValueError(f'{label}: use um valor entre {low} e {high}.')
    return out


def validate_config(data):
    if not isinstance(data, dict):
        raise ValueError('Configuração inválida.')
    base = copy.deepcopy(DEFAULT_CONFIG)
    t_in = data.get('thresholds') if isinstance(data.get('thresholds'), dict) else {}
    t = base['thresholds']
    t['base'] = _num(t_in.get('base', t['base']), 300, 900, 'Limite da faixa de base', int)
    t['high'] = _num(t_in.get('high', t['high']), t['base'] + 1, 1000, 'Limite de alto desempenho', int)
    t['recurrence'] = round(_num(t_in.get('recurrence', t['recurrence']), 0.05, 0.9, 'Recorrência'), 3)
    t['accuracyBase'] = round(_num(t_in.get('accuracyBase', t['accuracyBase']), 0.2, 0.9, 'Acerto mínimo'), 3)
    t['minSims'] = _num(t_in.get('minSims', t['minSims']), 1, 5, 'Mínimo de simulados', int)
    t['windowDays'] = _num(t_in.get('windowDays', t['windowDays']), 90, 730, 'Período considerado', int)
    p_in = data.get('profiles') if isinstance(data.get('profiles'), dict) else {}
    for key in PROFILE_KEYS:
        src = p_in.get(key) if isinstance(p_in.get(key), dict) else {}
        dst = base['profiles'][key]
        label = str(src.get('label', dst['label'])).strip()
        if not 1 <= len(label) <= 40:
            raise ValueError('Nome do perfil: de 1 a 40 caracteres.')
        dst['label'] = label
        dst['description'] = str(src.get('description', dst['description'])).strip()[:160]
        plan = src.get('reviewPlan', dst['reviewPlan'])
        if plan not in ('both', 'exercise_only', 'theory_only'):
            raise ValueError('Forma de revisar inválida.')
        dst['reviewPlan'] = plan
        dst['theoryMin'] = _num(src.get('theoryMin', dst['theoryMin']), 5, 120, f'{label}: minutos de teoria', int)
        dst['exerciseMin'] = _num(src.get('exerciseMin', dst['exerciseMin']), 5, 180, f'{label}: minutos de exercícios', int)
        intervals = src.get('intervals', dst['intervals'])
        if isinstance(intervals, str):
            intervals = [x for x in intervals.replace(';', ',').split(',') if x.strip()]
        try:
            intervals = [int(str(x).strip()) for x in intervals]
        except (TypeError, ValueError):
            raise ValueError(f'{label}: intervalos devem ser dias inteiros separados por vírgula.')
        if not 1 <= len(intervals) <= 8 or intervals != sorted(set(intervals)) or any(not 1 <= x <= 365 for x in intervals):
            raise ValueError(f'{label}: intervalos crescentes, sem repetição, de 1 a 365 dias (até 8).')
        dst['intervals'] = intervals
        dst['reviewShare'] = round(_num(src.get('reviewShare', dst['reviewShare']), 0.2, 0.9, f'{label}: fatia de revisões'), 3)
    return base


def load_config(app, c):
    schema(app, c)
    row = app.db.execute(c, 'SELECT config FROM hmay_motor_config WHERE id=?', ('default',)).fetchone()
    if not row:
        return copy.deepcopy(DEFAULT_CONFIG)
    try:
        return validate_config(_json(_row(row, 'config'), {}))
    except ValueError:
        return copy.deepcopy(DEFAULT_CONFIG)


def save_config(app, c, user, data):
    cfg = validate_config(data)
    stamp = P.now().isoformat()
    app.db.execute(c, 'DELETE FROM hmay_motor_config WHERE id=?', ('default',))
    app.db.execute(c, 'INSERT INTO hmay_motor_config(id,config,updated_by,updated_at) VALUES (?,?,?,?)',
                   ('default', json.dumps(cfg, ensure_ascii=False), user['id'], stamp))
    app.event(c, user, user['id'], 'motor_config_update')
    return cfg


# ---------------------------------------------------------------- sinais e classificação

def _complete(metadata):
    try:
        general = float(metadata.get('_tri_general'))
        areas = [float(metadata.get(k) or 0) for k in ('_tri_lc', '_tri_ch', '_tri_cn', '_tri_mt')]
    except (TypeError, ValueError):
        return None
    return general if min(areas) > 0 else None


def signals_from_rows(rows, profile, cfg):
    """rows: iterável de (applied_on, metadata, metrics) já filtrado pelo período."""
    scores, ok, total, last = [], 0, 0, ''
    for applied_on, metadata, metrics in rows:
        md = _json(metadata, {})
        general = _complete(md)
        if general is None:
            continue
        scores.append(general)
        last = max(last, str(applied_on or ''))
        for key, value in _json(metrics, {}).items():
            if key.startswith('questao:') and isinstance(value, dict) and value.get('total') not in (None, ''):
                try:
                    ok += float(value.get('correct') or 0)
                    total += float(value.get('total') or 0)
                except (TypeError, ValueError):
                    pass
    nerr = nrec = 0
    for content in (profile or {}).get('contents', []) if isinstance(profile, dict) else []:
        if not isinstance(content, dict) or content.get('sourceType') != 'exam_error':
            continue
        errors = content.get('examErrors') if isinstance(content.get('examErrors'), list) else []
        nerr += len(errors)
        if len({str(e.get('simulation') or '') for e in errors if isinstance(e, dict)}) >= 2:
            nrec += len(errors)
    return {
        'sims': len(scores),
        'media': round(sum(scores) / len(scores), 1) if scores else None,
        'accuracy': round(ok / total, 4) if total else None,
        'errors': nerr, 'recurrentErrors': nrec,
        'recurrence': round(nrec / nerr, 4) if nerr else 0.0,
        'lastSimulation': last,
    }


def classify(sig, cfg):
    """Retorna (perfil, motivo para o aluno). Sem simulado completo: (None, motivo)."""
    t = cfg['thresholds']
    if not sig.get('sims'):
        return None, 'Ainda não há simulado completo para definir o foco.'
    media, acc, rec = sig['media'], sig.get('accuracy'), sig.get('recurrence') or 0
    if media >= t['high'] and rec < t['recurrence']:
        return 'precisao', 'Poucos erros e pouca repetição de assuntos nos simulados: o foco é lapidar detalhes.'
    if rec >= t['recurrence']:
        return 'intensiva', f"{sig['recurrentErrors']} dos seus {sig['errors']} erros foram em assuntos que você já tinha errado em outro simulado."
    if media < t['base'] or (acc is not None and acc < t['accuracyBase']):
        pct = f'{round(acc * 100)}%' if acc is not None else 'baixo'
        return 'base', f'Seu acerto nos simulados foi de {pct}: retomar a teoria antes de praticar rende mais.'
    return 'pratica', 'Seus erros estão espalhados por assuntos diferentes: resolver questões é o caminho mais eficiente.'


def signals(app, c, user_id, profile, cfg):
    cutoff = P.add(P.today(), -int(cfg['thresholds']['windowDays']))
    rows = app.db.execute(c, 'SELECT applied_on,metadata,metrics FROM hmay_performance WHERE user_id=? AND applied_on>=? ORDER BY applied_on',
                          (user_id, cutoff)).fetchall()
    return signals_from_rows([(_row(r, 'applied_on'), _row(r, 'metadata'), _row(r, 'metrics')) for r in rows], profile, cfg)


# ---------------------------------------------------------------- estado por aluno

def _default_state():
    return {'mode': 'auto', 'current': None, 'pendingKey': None, 'pendingCount': 0, 'lastSims': 0, 'history': []}


def load_state(app, c, user_id):
    schema(app, c)
    row = app.db.execute(c, 'SELECT data FROM hmay_motor_profile WHERE user_id=?', (user_id,)).fetchone()
    state = _default_state()
    if row:
        state.update({k: v for k, v in _json(_row(row, 'data'), {}).items() if k in state})
    if state['current'] not in PROFILE_KEYS:
        state['current'] = None
    if state['mode'] not in ('auto', 'manual'):
        state['mode'] = 'auto'
    return state


def save_state(app, c, user_id, state):
    state['history'] = list(state.get('history') or [])[-20:]
    app.db.execute(c, 'DELETE FROM hmay_motor_profile WHERE user_id=?', (user_id,))
    app.db.execute(c, 'INSERT INTO hmay_motor_profile(user_id,data,updated_at) VALUES (?,?,?)',
                   (user_id, json.dumps(state, ensure_ascii=False), P.now().isoformat()))


def advance(state, suggested, sims, reason):
    """Aplica a regra de troca: 2 atualizações seguidas de simulados indicando o mesmo perfil."""
    state = copy.deepcopy(state)
    changed = False
    if sims > int(state.get('lastSims') or 0):
        if suggested and suggested != state.get('current'):
            if state.get('pendingKey') == suggested:
                state['pendingCount'] = int(state.get('pendingCount') or 0) + 1
            else:
                state['pendingKey'], state['pendingCount'] = suggested, 1
        else:
            state['pendingKey'], state['pendingCount'] = None, 0
        state['lastSims'] = sims
    if state.get('current') is None and suggested:
        state['current'] = suggested
        state['history'].append({'to': suggested, 'at': P.now().isoformat(), 'by': 'motor', 'reason': reason})
        state['pendingKey'], state['pendingCount'] = None, 0
        changed = True
    elif state.get('mode') == 'auto' and state.get('pendingKey') and int(state.get('pendingCount') or 0) >= 2:
        state['history'].append({'from': state.get('current'), 'to': state['pendingKey'], 'at': P.now().isoformat(), 'by': 'motor', 'reason': reason})
        state['current'] = state['pendingKey']
        state['pendingKey'], state['pendingCount'] = None, 0
        changed = True
    return state, changed


def refresh(app, c, user_id, profile=None, cfg=None):
    cfg = cfg or load_config(app, c)
    if profile is None:
        row = app.db.execute(c, 'SELECT profile FROM hmay_state WHERE user_id=?', (user_id,)).fetchone()
        profile = _json(_row(row, 'profile'), {}) if row else {}
    sig = signals(app, c, user_id, profile, cfg)
    suggested, reason = classify(sig, cfg)
    before = load_state(app, c, user_id)
    state, _ = advance(before, suggested, sig['sims'], reason)
    if state != before:
        save_state(app, c, user_id, state)
    return state, sig, suggested, reason, cfg


def params_for(state, cfg):
    key = state.get('current')
    if key not in PROFILE_KEYS:
        return None
    return dict(key=key, **copy.deepcopy(cfg['profiles'][key]))


def apply_to_plan(app, c, target, plan_profile):
    """Chamado na prévia do cronograma: aplica o perfil atual ao planejamento gerado."""
    row = app.db.execute(c, 'SELECT role FROM hmay_users WHERE id=?', (target,)).fetchone()
    if not row or _row(row, 'role') not in STUDENT_ROLES:
        return None
    state, _sig, _suggested, _reason, cfg = refresh(app, c, target, plan_profile)
    params = params_for(state, cfg)
    if not params:
        return None
    settings = plan_profile.setdefault('settings', {})
    settings['motorProfile'] = {k: params[k] for k in ('key', 'label', 'reviewPlan', 'theoryMin', 'exerciseMin', 'reviewShare')}
    settings['intervals'] = list(params['intervals'])
    return params


# ---------------------------------------------------------------- API

def _public(state, sig, suggested, reason, cfg, manager):
    profiles = {k: {'label': v['label'], 'description': v['description']} for k, v in cfg['profiles'].items()}
    out = {
        'available': True, 'mode': state['mode'], 'current': state['current'], 'suggested': suggested,
        'reason': reason, 'provisional': bool(sig['sims']) and sig['sims'] < cfg['thresholds']['minSims'],
        'pending': state.get('pendingKey'), 'profiles': profiles, 'order': list(PROFILE_KEYS),
        'history': [{k: h.get(k) for k in ('from', 'to', 'at', 'by')} for h in state.get('history', [])][-5:],
    }
    if manager:
        out['signals'] = sig
    return out


def _target_row(app, c, user, target_id, HTTPError):
    app.require_target(user, target_id, c)
    row = app.db.execute(c, 'SELECT id,name,role,active FROM hmay_users WHERE id=?', (target_id,)).fetchone()
    if not row:
        raise HTTPError(404, 'Conta não encontrada.')
    return dict(row)


def overview(app, c, user, cfg):
    roles = ('aluno', 'user') if user.get('role') == 'coordenador' else ('aluno', 'user', 'especial')
    marks = ','.join('?' for _ in roles)
    users = {(_row(r, 'id')): r for r in app.db.execute(c, f'SELECT id,role FROM hmay_users WHERE active=1 AND role IN ({marks})', roles).fetchall()}
    cutoff = P.add(P.today(), -int(cfg['thresholds']['windowDays']))
    # Resultados da cópia compacta compartilhada (results_store); as respostas de cada aluno
    # só são montadas na hora de calcular os sinais dele.
    import results_store as RS
    perf = {}
    for rec in RS.STORE.records(app, c):
        if rec.date >= cutoff and rec.user in users:
            perf.setdefault(rec.user, []).append(rec)
    states = {_row(r, 'user_id'): _json(_row(r, 'data'), {}) for r in app.db.execute(c, 'SELECT user_id,data FROM hmay_motor_profile').fetchall()}
    counts = {k: {'suggested': 0, 'current': 0, 'manual': 0, 'provisional': 0, 'media': [], 'accuracy': [], 'recurrence': []} for k in PROFILE_KEYS}
    without = 0
    for uid in users:
        if uid not in perf:
            without += 1
            continue
        srow = app.db.execute(c, 'SELECT profile FROM hmay_state WHERE user_id=?', (uid,)).fetchone()
        sig = signals_from_rows([(rec.date, rec.md, rec.metrics()) for rec in perf[uid]], _json(_row(srow, 'profile'), {}) if srow else {}, cfg)
        key, _ = classify(sig, cfg)
        if not key:
            without += 1
            continue
        bucket = counts[key]
        bucket['suggested'] += 1
        bucket['provisional'] += int(sig['sims'] < cfg['thresholds']['minSims'])
        bucket['media'].append(sig['media'])
        if sig['accuracy'] is not None:
            bucket['accuracy'].append(sig['accuracy'])
        bucket['recurrence'].append(sig['recurrence'])
        st = states.get(uid) or {}
        if st.get('current') in PROFILE_KEYS:
            counts[st['current']]['current'] += 1
            counts[st['current']]['manual'] += int(st.get('mode') == 'manual')
    rows = []
    for key in PROFILE_KEYS:
        b = counts[key]
        avg = lambda xs, f=1: round(sum(xs) / len(xs) * f, 1) if xs else None
        rows.append({'key': key, 'label': cfg['profiles'][key]['label'], 'suggested': b['suggested'], 'current': b['current'],
                     'manual': b['manual'], 'provisional': b['provisional'], 'media': avg(b['media']),
                     'accuracy': avg(b['accuracy'], 100), 'recurrence': avg(b['recurrence'], 100)})
    return {'rows': rows, 'withoutData': without, 'students': len(users)}


def handle(app, c, user, path, method, data, query, start, HTTPError):
    schema(app, c)
    manager = user.get('role') in ('master', 'coordenador')
    if path == '/api/motor/profile':
        target_id = str((data.get('user') if method == 'POST' else None) or query.get('user', [user['id']])[0])
        target = _target_row(app, c, user, target_id, HTTPError)
        if target['role'] not in STUDENT_ROLES:
            return app.reply(start, 200, {'available': False})
        if method == 'POST':
            mode = data.get('mode')
            if mode not in ('auto', 'manual'):
                raise ValueError('Escolha automático ou um perfil.')
            state, sig, suggested, reason, cfg = refresh(app, c, target_id)
            if mode == 'manual':
                key = data.get('key')
                if key not in PROFILE_KEYS:
                    raise ValueError('Perfil inválido.')
                state['history'].append({'from': state.get('current'), 'to': key, 'at': P.now().isoformat(), 'by': 'manual'})
                state['mode'], state['current'] = 'manual', key
            else:
                state['mode'] = 'auto'
                if suggested and suggested != state.get('current'):
                    state['history'].append({'from': state.get('current'), 'to': suggested, 'at': P.now().isoformat(), 'by': 'auto'})
                    state['current'] = suggested
                state['pendingKey'], state['pendingCount'] = None, 0
            save_state(app, c, target_id, state)
            app.event(c, user, target_id, 'motor_profile_' + mode)
            return app.reply(start, 200, _public(state, sig, suggested, reason, cfg, manager))
        state, sig, suggested, reason, cfg = refresh(app, c, target_id)
        return app.reply(start, 200, _public(state, sig, suggested, reason, cfg, manager))
    if not manager:
        raise HTTPError(403, 'Configuração do motor reservada ao Master e à coordenação.')
    if path == '/api/motor/config':
        if method == 'POST':
            return app.reply(start, 200, {'config': save_config(app, c, user, data.get('config')), 'defaults': DEFAULT_CONFIG})
        return app.reply(start, 200, {'config': load_config(app, c), 'defaults': DEFAULT_CONFIG})
    if path == '/api/motor/overview' and method == 'GET':
        return app.reply(start, 200, overview(app, c, user, load_config(app, c)))
    raise HTTPError(404, 'Página não encontrada.')
