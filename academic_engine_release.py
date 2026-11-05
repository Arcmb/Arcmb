"""Integrate imported academic results into the mathematical routine engine.

Academic evidence changes only the relative weight of matching study subjects
when a new preview is generated. It never creates availability, changes a saved
schedule, creates subjects, or bypasses preview/confirmation.
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def replace_once(text, old, new, label):
    if old not in text:
        raise RuntimeError(f'{label}: trecho esperado não encontrado.')
    return text.replace(old, new, 1)


ACADEMIC_HELPERS = r'''

# === MEU CRONOGRAMA: RESULTADOS ACADÊMICOS NO MOTOR MATEMÁTICO ===
_ACADEMIC_AREA_LABELS = {
    'LC': 'Linguagens', 'CH': 'Humanas',
    'CN': 'Natureza', 'MT': 'Matemática',
}
_ACADEMIC_ALIASES = {
    'lingua portuguesa': 'portugues', 'portugues': 'portugues',
    'lingua inglesa': 'ingles', 'ingles': 'ingles',
    'lingua espanhola': 'espanhol', 'espanhol': 'espanhol',
    'lingua estrangeira': 'lingua estrangeira',
    'matematica': 'matematica',
    'ciencias humanas': 'humanas', 'humanas': 'humanas',
    'ciencias da natureza': 'natureza', 'natureza': 'natureza',
    'linguagens codigos e suas tecnologias': 'linguagens', 'linguagens': 'linguagens',
    'tecnologias da informacao e comunicacao': 'tics', 'tic': 'tics', 'tics': 'tics',
    'educacao fisica': 'educacao fisica', 'linguagem corporal': 'linguagem corporal',
}


def _academic_norm(value):
    import re as _re
    import unicodedata as _unicodedata
    text = _unicodedata.normalize('NFKD', str(value or ''))
    text = ''.join(ch for ch in text if not _unicodedata.combining(ch)).casefold()
    text = ' '.join(_re.findall(r'[a-z0-9]+', text))
    return _ACADEMIC_ALIASES.get(text, text)


def _academic_json(value):
    try:
        parsed = json.loads(value or '{}')
    except (TypeError, ValueError):
        return {}
    return parsed


def _academic_language(metadata):
    if not isinstance(metadata, dict):
        return ''
    accepted = {'l e', 'lingua estrangeira', 'l estrangeira selecionada'}
    for key, value in metadata.items():
        if _academic_norm(key) in accepted:
            return _academic_norm(value)
    return ''


def _academic_subject_match(item, subjects):
    discipline = _academic_norm(item.get('discipline'))
    area = _academic_norm(_ACADEMIC_AREA_LABELS.get(str(item.get('area') or '').upper(), item.get('area')))
    exact = {}
    for subject in subjects:
        exact.setdefault(_academic_norm(subject.get('name')), []).append(subject)
    for key in (discipline, area):
        matches = exact.get(key, [])
        if len(matches) == 1:
            return matches[0]
    if discipline in ('ingles', 'espanhol'):
        matches = exact.get('lingua estrangeira', [])
        if len(matches) == 1:
            return matches[0]
    for key in (discipline, area):
        if len(key) < 5:
            continue
        candidates = []
        for subject in subjects:
            subject_key = _academic_norm(subject.get('name'))
            if len(subject_key) >= 5 and (key in subject_key or subject_key in key):
                candidates.append(subject)
        unique = {subject['id']: subject for subject in candidates}
        if len(unique) == 1:
            return next(iter(unique.values()))
    return None


def academic_priority(app, c, target, profile):
    info = {
        'enabled': True, 'used': False, 'bonuses': {}, 'subjects': [],
        'unmatched': [],
        'notice': 'Nenhum resultado acadêmico recente pôde ser associado às disciplinas ativas.',
    }
    subjects = [
        subject for subject in profile.get('subjects', [])
        if subject.get('active') and subject.get('kind') == 'study'
    ]
    if not subjects:
        info['notice'] = 'Cadastre disciplinas de estudo para que os resultados possam orientar a distribuição da semana.'
        return info
    try:
        rows = app.db.execute(
            c,
            'SELECT id,activity_key,activity,applied_on,metrics,metadata '
            'FROM hmay_performance WHERE user_id=? ORDER BY applied_on DESC,updated_at DESC LIMIT 24',
            (target,),
        ).fetchall()
    except Exception:
        info['notice'] = 'A base de resultados acadêmicos ainda não está disponível para esta conta.'
        return info
    if not rows:
        info['notice'] = 'Ainda não há simulados importados para esta conta.'
        return info

    today = P.date(P.today())
    cutoff = P.date(P.add(P.today(), -365))
    exam_cache = {}
    grouped = {}
    unmatched = set()
    for source in rows:
        row = dict(source)
        try:
            applied = P.date(row.get('applied_on'))
        except Exception:
            continue
        if applied < cutoff:
            continue
        metadata = _academic_json(row.get('metadata'))
        metrics = _academic_json(row.get('metrics'))
        exam_id = metadata.get('_exam_id')
        if not exam_id:
            continue
        if exam_id not in exam_cache:
            exam_row = app.db.execute(c, 'SELECT items FROM hmay_exams WHERE id=?', (exam_id,)).fetchone()
            parsed_items = _academic_json(exam_row['items']) if exam_row else []
            exam_cache[exam_id] = parsed_items if isinstance(parsed_items, list) else []
        language = _academic_language(metadata)
        age = max(0, (today - applied).days)
        recency = max(.35, 1 - min(age, 365) * .65 / 365)
        simulation_key = str(row.get('id') or row.get('activity_key') or '')
        for item in exam_cache[exam_id]:
            if not isinstance(item, dict):
                continue
            item_language = _academic_norm(item.get('language'))
            if item_language and item_language != language:
                continue
            answer = str(item.get('answer') or '').strip().upper()
            if not answer or answer == 'ANULADA':
                continue
            try:
                number = int(item.get('number') or 0)
            except (TypeError, ValueError):
                continue
            metric = metrics.get(f'questao:{number:03d}')
            result = metric.get('correct') if isinstance(metric, dict) else None
            if result not in (0, 1):
                continue
            subject = _academic_subject_match(item, subjects)
            if not subject:
                label = str(item.get('discipline') or _ACADEMIC_AREA_LABELS.get(str(item.get('area') or '').upper(), '') or 'Não informada').strip()
                if label:
                    unmatched.add(label)
                continue
            bucket = grouped.setdefault(subject['id'], {
                'subjectId': subject['id'], 'subject': subject['name'],
                'questions': 0, 'correct': 0, 'weightedTotal': 0.0,
                'weightedCorrect': 0.0, 'simulations': set(),
                'disciplines': set(), 'latest': '',
            })
            bucket['questions'] += 1
            bucket['correct'] += int(result)
            bucket['weightedTotal'] += recency
            bucket['weightedCorrect'] += recency * int(result)
            bucket['simulations'].add(simulation_key)
            discipline = str(item.get('discipline') or '').strip()
            if discipline:
                bucket['disciplines'].add(discipline)
            if row.get('applied_on', '') > bucket['latest']:
                bucket['latest'] = row.get('applied_on', '')

    for subject in subjects:
        bucket = grouped.get(subject['id'])
        if not bucket:
            continue
        questions = bucket['questions']
        simulations = len(bucket['simulations'])
        raw_accuracy = bucket['correct'] / questions if questions else 0
        posterior = (bucket['weightedCorrect'] + 2) / (bucket['weightedTotal'] + 4)
        confidence = min(1.0, questions / 20) * min(1.0, .6 + .2 * max(0, simulations - 1))
        need = max(0.0, .70 - posterior) / .70
        multiplier = min(1.25, 1 + .25 * need * confidence) if questions >= 5 else 1.0
        multiplier = round(multiplier, 4)
        used = multiplier > 1.001
        if used:
            info['bonuses'][subject['id']] = multiplier
        info['subjects'].append({
            'subjectId': subject['id'], 'subject': subject['name'],
            'disciplines': sorted(bucket['disciplines']),
            'questions': questions, 'correct': bucket['correct'],
            'simulations': simulations, 'accuracy': round(raw_accuracy, 4),
            'smoothedAccuracy': round(posterior, 4),
            'confidence': round(confidence, 4), 'multiplier': multiplier,
            'boostPct': round((multiplier - 1) * 100, 1),
            'used': used, 'latest': bucket['latest'],
            'reason': 'Amostra mínima de 5 questões.' if questions < 5 else ('Prioridade aumentada por desempenho recente abaixo de 70%.' if used else 'Resultado suficiente, sem necessidade de aumento de prioridade.'),
        })
    info['subjects'].sort(key=lambda item: (-item['boostPct'], item['subject'].casefold()))
    info['unmatched'] = sorted(unmatched)[:30]
    info['used'] = bool(info['bonuses'])
    if info['used']:
        info['notice'] = 'Resultados dos últimos 365 dias aumentam, de forma limitada, o peso das disciplinas com maior necessidade. O aumento máximo é 25% e só vale na nova prévia.'
    elif info['subjects']:
        info['notice'] = 'Os resultados foram analisados, mas não produziram aumento de prioridade: desempenho igual ou superior ao limiar, ou amostra insuficiente.'
    elif unmatched:
        info['notice'] = 'Há resultados importados, mas nenhuma disciplina do mapa corresponde às disciplinas ativas do cronograma.'
    return info
'''


def patch_planner():
    path = ROOT / 'planner.py'
    source = path.read_text(encoding='utf-8')
    source = replace_once(
        source,
        'def generate(p,week_start,current=None,mode="reorganize",bonuses=None):',
        'def generate(p,week_start,current=None,mode="reorganize",bonuses=None,subject_bonuses=None):',
        'assinatura do motor',
    )
    source = replace_once(
        source,
        '    bonuses=bonuses or {}\n',
        '    bonuses=bonuses or {}\n    subject_bonuses=subject_bonuses or {}\n',
        'pesos acadêmicos do motor',
    )
    old = "        weights.append(max(1,sub['weeklyMin'])*(1+.10*(diff-3)+.06*(sub['importance']-3)+.15*urgency))"
    new = "        academic=max(1.0,min(1.25,float(subject_bonuses.get(sub['id'],1.0))))\n        weights.append(max(1,sub['weeklyMin'])*(1+.10*(diff-3)+.06*(sub['importance']-3)+.15*urgency)*academic)"
    source = replace_once(source, old, new, 'multiplicador acadêmico')
    old_reason = "reason='Distribuição por meta, dificuldade verificada, importância e prazo. Não é previsão de nota.')"
    new_reason = "reason='Distribuição por meta, dificuldade verificada, importância, prazo e resultados acadêmicos recentes quando há evidência suficiente. Não é previsão de nota.')"
    source = replace_once(source, old_reason, new_reason, 'explicação da sessão')
    path.write_text(source, encoding='utf-8')


def patch_adaptive():
    path = ROOT / 'adaptive.py'
    source = path.read_text(encoding='utf-8')
    if '# === MEU CRONOGRAMA: RESULTADOS ACADÊMICOS NO MOTOR MATEMÁTICO ===' not in source:
        source = replace_once(source, '\ndef delta(before,after):\n', ACADEMIC_HELPERS + '\n\ndef delta(before,after):\n', 'funções acadêmicas')
    source = source.replace("VERSION = '2.2'", "VERSION = '2.3'", 1)
    old_get = """    if path=='/api/adaptive' and method=='GET':
        weights,own,shared=bonuses(app,c,user,target,p)
        return app.reply(start,200,dict(version=VERSION,questions=[dict(key=k,group=g,label=l,options=o) for k,g,l,o in QUESTIONS],answers=answers(p),suggestions=suggestions(p),personal=own,collective=shared,history=history(app,c,target),canConsent=target==user['id'] and user['role'] in ('aluno','user'),profileVersion=row['version']))
"""
    new_get = """    if path=='/api/adaptive' and method=='GET':
        weights,own,shared=bonuses(app,c,user,target,p)
        academic=academic_priority(app,c,target,p)
        return app.reply(start,200,dict(version=VERSION,questions=[dict(key=k,group=g,label=l,options=o) for k,g,l,o in QUESTIONS],answers=answers(p),suggestions=suggestions(p),personal=own,collective=shared,academic=academic,history=history(app,c,target),canConsent=target==user['id'] and user['role'] in ('aluno','user'),profileVersion=row['version']))
"""
    source = replace_once(source, old_get, new_get, 'diagnóstico acadêmico')
    old_preview = """        weights,own,shared=bonuses(app,c,user,target,p)
        new=P.generate(copy.deepcopy(p),w,mode=mode,bonuses=weights);P.validate(new)
        if len(dumps(new).encode())>5_000_000:raise ValueError('Planejamento excede o limite de dados.')
        report=delta(p,new);report.update(mode=mode,week=w,own=own,collective=shared)
"""
    new_preview = """        weights,own,shared=bonuses(app,c,user,target,p)
        use_academic=data.get('academic','yes')!='no'
        academic=academic_priority(app,c,target,p) if use_academic else {'enabled':False,'used':False,'bonuses':{},'subjects':[],'unmatched':[],'notice':'Resultados acadêmicos desativados para esta prévia.'}
        new=P.generate(copy.deepcopy(p),w,mode=mode,bonuses=weights,subject_bonuses=academic.get('bonuses',{}));P.validate(new)
        if len(dumps(new).encode())>5_000_000:raise ValueError('Planejamento excede o limite de dados.')
        report=delta(p,new);report.update(mode=mode,week=w,own=own,collective=shared,academic=academic)
"""
    source = replace_once(source, old_preview, new_preview, 'uso acadêmico na prévia')
    path.write_text(source, encoding='utf-8')


def patch_frontend():
    path = ROOT / 'static' / 'adaptive.js'
    source = path.read_text(encoding='utf-8')
    helper_anchor = "const objectiveValue=(key,v)=>key==='preferred'?(objectivePeriods[v]||v):typeof v==='boolean'?(v?'Sim':'Não'):String(v);\n"
    helper = r'''const objectiveValue=(key,v)=>key==='preferred'?(objectivePeriods[v]||v):typeof v==='boolean'?(v?'Sim':'Não'):String(v);
function academicPriorityHtml(info,compact=false){
 const rows=(info?.subjects||[]).map(x=>`<div class="item"><div><strong>${esc(x.subject)}</strong><p>${x.correct}/${x.questions} acertos (${Math.round(x.accuracy*100)}%) em ${x.simulations} simulado(s)${x.used?` · prioridade +${x.boostPct}%`:' · sem aumento de prioridade'}</p><small>${esc(x.reason)}${x.latest?' · resultado mais recente: '+br(x.latest):''}</small></div></div>`).join('');
 const unmatched=(info?.unmatched||[]).length&&!compact?`<p class="micro"><strong>Sem disciplina correspondente:</strong> ${(info.unmatched||[]).map(esc).join(', ')}. Cadastre a disciplina com nome equivalente para que ela entre no cálculo.</p>`:'';
 return `<p>${esc(info?.notice||'Sem informação acadêmica.')}</p>${rows||empty('Nenhuma disciplina do cronograma recebeu evidência acadêmica suficiente.')}${unmatched}`;
}
'''
    source = replace_once(source, helper_anchor, helper, 'apresentação acadêmica')
    old_section = """ `<section class="card"><h2>O que o histórico indica</h2>${stats||empty('Ainda não há execuções suficientes registradas.')}<p>${esc(d.personal.notice)}</p><p class="micro">Amostra individual mínima por período: 6 registros em 3 dias. O índice é suavizado e não equivale a nota, domínio ou diagnóstico.</p></section>`+
 `<section class="card"><h2>Contribuição coletiva opcional</h2>"""
    new_section = """ `<section class="card"><h2>O que o histórico indica</h2>${stats||empty('Ainda não há execuções suficientes registradas.')}<p>${esc(d.personal.notice)}</p><p class="micro">Amostra individual mínima por período: 6 registros em 3 dias. O índice é suavizado e não equivale a nota, domínio ou diagnóstico.</p></section>`+
 `<section class="card"><h2>Resultados acadêmicos no motor matemático</h2>${academicPriorityHtml(d.academic)}<p class="micro">O resultado altera somente a distribuição relativa entre disciplinas ativas. Não cria horários, não muda a carga total e não salva nada sem prévia e confirmação.</p></section>`+
 `<section class="card"><h2>Contribuição coletiva opcional</h2>"""
    source = replace_once(source, old_section, new_section, 'seção acadêmica do mapeamento')
    old_form = """modal('Prévia do cronograma',`<form id="objective-preview-form"><p>O sistema usa somente a disponibilidade cadastrada. Sono, compromissos, pausas, reservas e limites continuam obrigatórios.</p>${input('Semana','week',week||S.serverDate,'date','required')}${select('Como organizar?','mode','fill',[['fill','Completar espaços livres sem retirar os blocos existentes'],['reorganize','Reorganizar blocos futuros não fixados']])}<p>Blocos fixados e resultados registrados serão preservados. Nada é salvo antes da confirmação.</p><button class="primary" type="submit">Gerar prévia</button><p id="objective-error" class="form-error" role="alert"></p></form>`,null);"""
    new_form = """modal('Prévia do cronograma',`<form id="objective-preview-form"><p>O sistema usa somente a disponibilidade cadastrada. Sono, compromissos, pausas, reservas e limites continuam obrigatórios.</p>${input('Semana','week',week||S.serverDate,'date','required')}${select('Como organizar?','mode','fill',[['fill','Completar espaços livres sem retirar os blocos existentes'],['reorganize','Reorganizar blocos futuros não fixados']])}${select('Usar resultados acadêmicos recentes?','academic','yes',[['yes','Sim — ajustar prioridades por disciplina com limites'],['no','Não — usar somente metas, dificuldade, importância e prazo']])}<p>Blocos fixados e resultados registrados serão preservados. Nada é salvo antes da confirmação.</p><button class="primary" type="submit">Gerar prévia</button><p id="objective-error" class="form-error" role="alert"></p></form>`,null);"""
    source = replace_once(source, old_form, new_form, 'controle acadêmico da prévia')
    old_preview = """<p>${esc(s.own.notice)}</p><p>${esc(s.collective.notice)}</p><div class="table-wrap">"""
    new_preview = """<p>${esc(s.own.notice)}</p><p>${esc(s.collective.notice)}</p><section class="notice"><strong>Influência dos resultados acadêmicos</strong>${academicPriorityHtml(s.academic,true)}</section><div class="table-wrap">"""
    source = replace_once(source, old_preview, new_preview, 'resumo acadêmico da proposta')
    path.write_text(source, encoding='utf-8')

    html_path = ROOT / 'static' / 'app.html'
    html = html_path.read_text(encoding='utf-8')
    html = html.replace('/static/adaptive.js?v=2.6', '/static/adaptive.js?v=2.9.0')
    html_path.write_text(html, encoding='utf-8')


def main():
    patch_planner()
    patch_adaptive()
    patch_frontend()
    print('MEUCRONOGRAMA_ACADEMIC_ENGINE_READY: imported results now provide bounded subject priorities in previewed schedules.')


if __name__ == '__main__':
    main()
