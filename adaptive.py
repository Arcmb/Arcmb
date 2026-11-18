"""Objective routine mapping, reviewable proposals and bounded statistical hints.
No AI calls, psychological labels, inferred availability or automatic consent.
"""
from __future__ import annotations
import copy
import json
import time
import secrets
import planner as P
import motor_profiles as MOTOR  # === MOTOR PROFILES V3.9.0 ===

VERSION = '2.3'
QUESTIONS = [
 ('goal','Objetivos','Qual é sua prioridade atual?', [('exam','Preparar uma prova'),('routine','Manter uma rotina'),('recover','Retomar conteúdos'),('balance','Equilibrar estudo e outras atividades')]),
 ('stability','Objetivos','Seus horários livres se repetem entre semanas?', [('stable','Quase sempre'),('mixed','Parte se repete'),('variable','Mudam bastante')]),
 ('deadline','Objetivos','Existe uma avaliação próxima?', [('week','Nos próximos 7 dias'),('month','Nos próximos 30 dias'),('later','Depois de 30 dias'),('none','Não há prazo definido')]),
 ('load','Objetivos','Como está a carga do planejamento atual?', [('light','Cabe com folga'),('adequate','Cabe com esforço razoável'),('heavy','Não consigo cumprir'),('new','Ainda não testei')]),
 ('support','Objetivos','Que apoio está disponível quando há dificuldade?', [('teacher','Professor ou monitor'),('peer','Colega ou familiar'),('self','Material com resolução'),('none','Ainda não tenho apoio definido')]),
 ('focus','Blocos e horários','Por quanto tempo costuma trabalhar antes de precisar de pausa?', [('15','Até 15 minutos'),('25','Cerca de 25 minutos'),('40','Cerca de 40 minutos'),('60','Cerca de 60 minutos')]),
 ('energy','Blocos e horários','Em qual período relata maior disposição?', [('manha','Manhã'),('tarde','Tarde'),('noite','Noite'),('qualquer','Varia / sem preferência')]),
 ('interruptions','Blocos e horários','Com que frequência um bloco é interrompido?', [('rare','Raramente'),('some','Às vezes'),('often','Frequentemente')]),
 ('break','Blocos e horários','Que duração de pausa deseja testar?', [('5','5 minutos'),('10','10 minutos'),('15','15 minutos')]),
 ('reserve','Blocos e horários','Quanto do tempo livre prefere reservar para imprevistos?', [('10','10%'),('20','20%'),('30','30%')]),
 ('starting','Execução','Qual é a principal dificuldade para começar?', [('none','Não tenho dificuldade habitual'),('unclear','Não sei qual é o primeiro passo'),('distraction','Distrações'),('tired','Cansaço'),('time','O horário não fica disponível')]),
 ('delay','Execução','Com que frequência adia o início do estudo?', [('rare','Raramente'),('some','Às vezes'),('often','Frequentemente')]),
 ('environment','Execução','Como é o ambiente disponível para estudar?', [('quiet','Geralmente tranquilo'),('mixed','Varia conforme o horário'),('noisy','Tem interrupções frequentes')]),
 ('recovery','Execução','Quando não cumpre um bloco, qual opção prefere avaliar?', [('reschedule','Reagendar o que couber'),('shorter','Dividir em blocos menores'),('support','Revisar o plano com apoio')]),
 ('flexibility','Execução','Como prefere organizar a próxima semana?', [('stable','Preservar horários já combinados'),('flexible','Reorganizar blocos ainda não fixados'),('review','Conferir as duas alternativas antes de decidir')]),
 ('method','Estudo e revisão','Qual ação ocupa a maior parte do estudo?', [('practice','Resolver exercícios'),('retrieval','Responder ou explicar sem consulta'),('reading','Ler / assistir aula'),('mixed','Combinar essas ações')]),
 ('review','Estudo e revisão','Com que frequência retoma conteúdos anteriores?', [('none','Ainda não faço revisões'),('occasional','Quando lembro ou tenho dificuldade'),('weekly','Tenho revisões semanais'),('same_day','Tento retomar no mesmo dia')]),
 ('checking','Estudo e revisão','Como costuma verificar as respostas?', [('answers','Gabarito ou resolução'),('teacher','Professor ou monitor'),('self','Somente minha impressão'),('none','Nem sempre verifico')]),
 ('difficulty','Estudo e revisão','O que faz quando não consegue resolver?', [('retry','Retomo a explicação e tento outra questão'),('support','Procuro ajuda'),('skip','Pulo e sigo adiante'),('unsure','Não tenho uma estratégia definida')]),
 ('recording','Estudo e revisão','Quando consegue registrar o que realizou?', [('after','Ao terminar cada bloco'),('daily','Ao final do dia'),('weekly','Na revisão da semana'),('irregular','Ainda não consigo registrar regularmente')]),
]
from questions_v23 import QUESTIONS, HELPS
QUESTION_MAP = {q[0]: q for q in QUESTIONS}
REASONS = {
 'preference':'Preferência de horário', 'availability':'Disponibilidade mudou',
 'duration':'Ajuste de duração', 'priority':'Mudança de prioridade',
 'fatigue':'Ajuste de carga / descanso', 'support':'Orientação do responsável',
 'exception':'Imprevisto pontual', 'correction':'Correção de cadastro',
 'proposal':'Proposta conferida', 'not_informed':'Não informado',
}
SETTING_LABELS = {'preferred':'Período preferido','sessionMin':'Estudo contínuo mínimo (min)',
 'sessionMax':'Estudo contínuo máximo (min)','reviewMin':'Revisão (min)','breakMin':'Pausa (min)',
 'reservePct':'Reserva para imprevistos (%)','sameDay':'Retomada no mesmo dia'}

def dumps(x):
    return json.dumps(x,ensure_ascii=False,separators=(',',':'),allow_nan=False)

def schema(db,c):
    statements = [
      'CREATE TABLE IF NOT EXISTS hmay_adjustments (id TEXT PRIMARY KEY, actor_id TEXT NOT NULL, target_id TEXT NOT NULL, kind TEXT NOT NULL, reason TEXT NOT NULL, details TEXT NOT NULL, at TEXT NOT NULL)',
      'CREATE INDEX IF NOT EXISTS hmay_adjustments_target ON hmay_adjustments(target_id,at)',
      'CREATE TABLE IF NOT EXISTS hmay_proposals (id TEXT PRIMARY KEY, actor_id TEXT NOT NULL, target_id TEXT NOT NULL, base_version INTEGER NOT NULL, profile TEXT NOT NULL, summary TEXT NOT NULL, expires BIGINT NOT NULL)',
      'CREATE TABLE IF NOT EXISTS hmay_adaptive_consent (user_id TEXT PRIMARY KEY, enabled INTEGER NOT NULL, at TEXT NOT NULL)',
      'CREATE TABLE IF NOT EXISTS hmay_adaptive_observations (user_id TEXT NOT NULL, session_id TEXT NOT NULL, cohort TEXT NOT NULL, period TEXT NOT NULL, result REAL NOT NULL, at TEXT NOT NULL, PRIMARY KEY(user_id,session_id))',
      'CREATE INDEX IF NOT EXISTS hmay_adaptive_cohort ON hmay_adaptive_observations(cohort,period)',
    ]
    for sql in statements:db.execute(c,sql)

def answers(p):
    mapping=p.get('objective',{})
    if not isinstance(mapping,dict):return {}
    obj=mapping.get('answers',{})
    if not isinstance(obj,dict):return {}
    return {k:v for k,v in obj.items() if k in QUESTION_MAP and isinstance(v,str) and v in dict(QUESTION_MAP[k][3])}

def validate_answers(obj):
    if not isinstance(obj,dict) or set(obj)-set(QUESTION_MAP):raise ValueError('Questionário não reconhecido. Atualize a página.')
    clean={}
    for k,v in obj.items():
        if v in ('',None):continue
        if not isinstance(v,str) or v not in dict(QUESTION_MAP[k][3]):raise ValueError('Alternativa inválida: '+k)
        clean[k]=v
    return clean

def suggestions(p):
    a=answers(p);s=p['settings'];updates={};reasons={};tips=[]
    def put(k,v,why):
        if s.get(k)!=v:updates[k]=v;reasons[k]=why
    if 'focus' in a:
        block=int(a['focus'])
        if a.get('interruptions')=='often' or a.get('environment')=='noisy':block=min(block,25)
        if a.get('delay')=='often' and a.get('recovery')=='shorter':block=min(block,25)
        put('sessionMax',block,'Duração relatada de foco, com redução quando há interrupções frequentes.')
        put('sessionMin',min(s['sessionMin'],block),'Mantém o período mínimo de estudo compatível com o máximo proposto.')
        put('reviewMin',min(s['reviewMin'],block),'Mantém a revisão dentro do período máximo de estudo proposto.')
    if 'energy' in a:put('preferred',a['energy'],'Preferência informada; não cria disponibilidade nesse período.')
    if 'break' in a:put('breakMin',int(a['break']),'Duração de pausa escolhida para testar.')
    if 'reserve' in a:
        reserve=int(a['reserve'])
        if a.get('stability')=='variable':reserve=max(reserve,30)
        put('reservePct',reserve,'Reserva escolhida; mínimo de 30% sugerido quando a rotina varia bastante.')
    if a.get('review')=='same_day':put('sameDay',True,'Retomada no mesmo dia solicitada; somente quando houver encaixe após o estudo.')
    if a.get('goal')=='balance':tips.append('Mantenha ações pessoais e descanso no planejamento, não apenas tarefas acadêmicas.')
    if a.get('goal')=='recover':tips.append('Cadastre os conteúdos que precisam de retomada, separando-os dos conteúdos já verificados.')
    if a.get('flexibility')=='stable':tips.append('Use Completar espaços livres para preservar os blocos já combinados.')
    if a.get('flexibility')=='flexible':tips.append('Confira a opção Reorganizar blocos futuros, mantendo fixos os compromissos que não podem mudar.')
    if a.get('starting')=='unclear':tips.append('Cadastre ações concretas, como resolver 5 questões, em vez de somente estudar.')
    if a.get('starting')=='time' or a.get('stability')=='variable':tips.append('Confirme as janelas realmente disponíveis antes de gerar a semana; horários não informados não são livres.')
    if a.get('load')=='heavy':tips.append('Reavalie as metas com o responsável. A proposta não aumenta a carga semanal e não considera 100% de cumprimento como único objetivo.')
    if a.get('review') in ('none','occasional'):tips.append('Cadastre cada conteúdo estudado para programar revisões dentro do tempo disponível.')
    if a.get('method')=='reading' or a.get('checking') in ('self','none'):tips.append('Inclua uma tentativa sem consulta e confira a resposta no material ou com o professor.')
    if a.get('difficulty') in ('skip','unsure'):tips.append('Registre a dificuldade específica e selecione uma retomada ou apoio, sem marcar o conteúdo como dominado.')
    if a.get('deadline') in ('week','month'):tips.append('Informe a data exata da avaliação na disciplina. O questionário não inventa datas de prova.')
    if a.get('support')=='none' or a.get('recovery')=='support':tips.append('Combine com a coordenação um ponto de apoio para revisar o planejamento.')
    if a.get('recording') in ('weekly','irregular'):tips.append('Registre somente execuções que você consegue confirmar. Falta de registro não é automaticamente uma falta.')
    return dict(changes=[dict(key=k,label=SETTING_LABELS[k],before=s.get(k),after=v,reason=reasons[k]) for k,v in updates.items()],tips=tips,
                answered=len(a),total=len(QUESTIONS),notice='Regras iniciais configuradas, não diagnóstico psicológico ou previsão de nota. Nenhuma disponibilidade, sono ou meta é alterada automaticamente.')

def period(minutes):return 'manha' if minutes<720 else 'tarde' if minutes<1080 else 'noite'

def cohort(p):
    a=answers(p)
    if a.get('focus') and a.get('stability'):
        return ('short' if int(a['focus'])<=25 else 'long')+':'+('stable' if a['stability']=='stable' else 'variable')
    return ''

def observation(p,f):
    s=next((s for s in p['sessions'] if s['id']==f.get('sessionId')),None)
    if not s or f.get('reason') in ('unexpected',) or f.get('detail')=='exception':return None
    if f['status']=='done':result=1.0
    elif f['status']=='partial':result=min(.99,max(0,f['actualMin']/max(1,s['end']-s['start'])))
    elif f['status']=='missed':result=0.0
    else:return None
    return dict(period=period(s['start']),result=result,date=f['date'])

def personal(p):
    grouped={};seen=set()
    for f in sorted(p['feedback'],key=lambda f:f.get('at',''),reverse=True):
        if f.get('sessionId') in seen:continue
        seen.add(f.get('sessionId'))
        o=observation(p,f)
        if o and o['date']>=P.add(P.today(),-90):grouped.setdefault(o['period'],[]).append(o)
    stats=[];bonuses={}
    for key,obs in grouped.items():
        obs=obs[:40];n=len(obs);days=len({x['date'] for x in obs});score=(2+sum(x['result'] for x in obs))/(4+n)
        reliable=n>=6 and days>=3
        stats.append(dict(period=key,observations=n,days=days,completion=round(score,3),used=reliable))
        if reliable:bonuses[key]=round(6*(score-.5),3)
    return dict(stats=stats,bonuses=bonuses,notice='Usa execução registrada nos últimos 90 dias; não é medida de aprendizagem. Alterar o horário, sozinho, não comprova melhoria.')

def collective(app,c,user,target,p):
    info=dict(enabled=False,used=False,stats=[],bonuses={},notice='Contribuição coletiva desativada. Não são usados dados de contas especiais.')
    role=app.db.execute(c,'SELECT role FROM hmay_users WHERE id=?',(target,)).fetchone()
    if not role or role['role'] not in ('aluno','user'):return info
    consent=app.db.execute(c,'SELECT enabled FROM hmay_adaptive_consent WHERE user_id=?',(target,)).fetchone()
    if not consent or not consent['enabled']:return info
    info['enabled']=True;key=cohort(p)
    if not key:
        info['notice']='Responda foco e estabilidade da rotina para formar um grupo comparável.';return info
    rows=app.db.execute(c,"SELECT o.user_id,o.period,o.result,o.at FROM hmay_adaptive_observations o JOIN hmay_users u ON u.id=o.user_id JOIN hmay_adaptive_consent a ON a.user_id=u.id WHERE u.active=1 AND u.role IN ('aluno','user') AND a.enabled=1 AND o.cohort=? AND o.user_id<>? AND o.at>=? ORDER BY o.at DESC LIMIT 6000",(key,target,P.add(P.today(),-90))).fetchall()
    groups={};contrib={}
    for r in rows:
        pair=(r['user_id'],r['period'])
        if contrib.get(pair,0)>=10:continue
        contrib[pair]=contrib.get(pair,0)+1;groups.setdefault(r['period'],[]).append(dict(r))
    for k,rs in groups.items():
        count=len({r['user_id'] for r in rs})
        if count<10 or len(rs)<30:continue
        # Equal participant weighting, not pooled dominance by frequent reporters.
        scores={}
        for r in rs:scores.setdefault(r['user_id'],[]).append(r['result'])
        score=(2+sum(sum(v)/len(v) for v in scores.values()))/(4+count)
        info['stats'].append(dict(period=k,participants=count,observations=len(rs),completion=round(score,3)))
        info['bonuses'][k]=round(3*(score-.5),3)
    info['used']=bool(info['bonuses'])
    info['notice']='Ajuste leve por resultados declarados de grupos semelhantes; não demonstra causa nem garante melhor desempenho.' if info['used'] else 'Base insuficiente: cada período exige pelo menos 10 outros participantes e 30 registros. Ainda não influencia o cronograma.'
    return info

def bonuses(app,c,user,target,p):
    own=personal(p);shared=collective(app,c,user,target,p)
    weights=dict(shared['bonuses']);weights.update(own['bonuses'])
    return weights,own,shared


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
    _qi_year = _qi_active_year(app, c, target)
    exam_cache = {}
    grouped = {}
    unmatched = set()
    for source in rows:
        row = dict(source)
        try:
            applied = P.date(row.get('applied_on'))
        except Exception:
            continue
        if applied < cutoff or (_qi_year and applied.year != _qi_year):
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


def delta(before,after):
    b={s['id']:s for s in before['sessions']};a={s['id']:s for s in after['sessions']}
    added=[a[i] for i in a.keys()-b.keys()];removed=[b[i] for i in b.keys()-a.keys()]
    changed=[]
    for i in b.keys()&a.keys():
        keys=[k for k in ('date','start','end','locked','status') if b[i].get(k)!=a[i].get(k)]
        if keys:changed.append(dict(id=i,fields=keys,before={k:b[i].get(k) for k in ('date','start','end','locked','status')},after={k:a[i].get(k) for k in ('date','start','end','locked','status')}))
    total=lambda ss:sum(s['end']-s['start'] for s in ss if s['status']!='missed')
    settings={k:dict(before=before['settings'].get(k),after=v) for k,v in after['settings'].items() if before['settings'].get(k)!=v}
    return dict(added=len(added),removed=len(removed),changed=len(changed),minutesBefore=total(before['sessions']),minutesAfter=total(after['sessions']),
                movedMinutes=sum(abs(x['after']['start']-x['before']['start']) for x in changed if x['before']['date']==x['after']['date']),settings=settings,changes=changed[:100])

def record(app,c,user,target,before,after,op,data):
    d=delta(before,after);reason=data.get('reason','not_informed')
    if reason not in REASONS:reason='not_informed'
    app.db.execute(c,'INSERT INTO hmay_adjustments(id,actor_id,target_id,kind,reason,details,at) VALUES (?,?,?,?,?,?,?)',(P.uid(),user['id'],target,op,reason,dumps(d),P.now().isoformat()))
    if op=='feedback':
        oldids={f['id'] for f in before['feedback']}
        role=app.db.execute(c,'SELECT role FROM hmay_users WHERE id=?',(target,)).fetchone()
        consent=app.db.execute(c,'SELECT enabled FROM hmay_adaptive_consent WHERE user_id=?',(target,)).fetchone()
        key=cohort(after)
        if role and role['role'] in ('user','aluno') and consent and consent['enabled'] and key:
            for f in after['feedback']:
                if f['id'] in oldids:continue
                obs=observation(after,f)
                if obs:app.db.execute(c,'INSERT INTO hmay_adaptive_observations(user_id,session_id,cohort,period,result,at) VALUES (?,?,?,?,?,?) ON CONFLICT(user_id,session_id) DO NOTHING',(target,f['sessionId'],key,obs['period'],obs['result'],P.now().isoformat()))
    return d

def apply_action(app,c,user,target,before,op,data):
    if not isinstance(data,dict):raise ValueError('Dados da ação inválidos.')
    if op=='objective':
        p=copy.deepcopy(before);p['objective']=dict(version=1,answers=validate_answers(data.get('answers')),at=P.now().isoformat(),actor=user['id'])
        P.audit(p,'mapeamento','Respostas objetivas salvas. Parâmetros e cronograma não foram alterados.')
    elif op=='objective_settings':
        proposed=suggestions(before);keys=data.get('keys',[])
        if not isinstance(keys,list) or any(not isinstance(k,str) for k in keys):raise ValueError('Seleção inválida.')
        allowed={x['key']:x['after'] for x in proposed['changes']}
        if set(keys)-set(allowed):raise ValueError('As sugestões mudaram; confira novamente.')
        p=copy.deepcopy(before);p['settings'].update({k:allowed[k] for k in keys})
        if p.get('planMeta'):p['planMeta']['dirty']=True
        P.audit(p,'mapeamento','Parâmetros sugeridos aprovados. Confira a prévia antes de substituir horários existentes.')
    else:
        p=P.action(before,op,data)
        if op=='import' and 'objective' in p:
            if not isinstance(p['objective'],dict):raise ValueError('Mapeamento do backup inválido.')
            p['objective']=dict(version=1,answers=validate_answers(p['objective'].get('answers',{})),at=P.now().isoformat(),actor=user['id'])
    P.validate(p);record(app,c,user,target,before,p,op,data);return p

def history(app,c,target):
    rows=app.db.execute(c,'SELECT e.kind,e.reason,e.details,e.at,u.name AS actor,u.role AS actor_role FROM hmay_adjustments e LEFT JOIN hmay_users u ON u.id=e.actor_id WHERE e.target_id=? ORDER BY e.at DESC LIMIT 30',(target,)).fetchall()
    return [dict(kind=r['kind'],reason=REASONS.get(r['reason'],'Não informado'),details=json.loads(r['details']),at=r['at'],actor=r['actor'] or 'Conta indisponível',actorRole=r['actor_role']) for r in rows]

def handle(app,c,user,path,method,data,query,start,HTTPError):
    target=str(data.get('user') or query.get('user',[user['id']])[0]);app.require_target(user,target,c)
    row=app.db.execute(c,'SELECT * FROM hmay_state WHERE user_id=?'+(' FOR UPDATE' if method=='POST' and not app.db.local_path else ''),(target,)).fetchone()
    if not row:raise HTTPError(404,'Conta não encontrada.')
    p=json.loads(row['profile'])
    if path=='/api/adaptive' and method=='GET':
        weights,own,shared=bonuses(app,c,user,target,p)
        academic=academic_priority(app,c,target,p)
        return app.reply(start,200,dict(version=VERSION,questions=[dict(key=k,group=g,label=l,options=o,help=HELPS.get(k,"")) for k,g,l,o in QUESTIONS],answers=answers(p),suggestions=suggestions(p),personal=own,collective=shared,academic=academic,history=history(app,c,target),canConsent=target==user['id'] and user['role'] in ('aluno','user'),profileVersion=row['version']))
    if method!='POST':raise HTTPError(404,'Ação não encontrada.')
    if type(data.get('version'))is not int or data['version']!=row['version']:raise HTTPError(409,'O planejamento mudou. Atualize a página e confira novamente.')
    if path=='/api/adaptive/consent':
        if target!=user['id'] or user['role'] not in ('aluno','user'):raise HTTPError(403,'Somente o titular de uma conta Aluno pode autorizar sua contribuição.')
        if type(data.get('enabled'))is not bool:raise ValueError('Autorização inválida.')
        app.db.execute(c,'INSERT INTO hmay_adaptive_consent(user_id,enabled,at) VALUES (?,?,?) ON CONFLICT(user_id) DO UPDATE SET enabled=excluded.enabled,at=excluded.at',(target,int(data['enabled']),P.now().isoformat()))
        if not data['enabled']:app.db.execute(c,'DELETE FROM hmay_adaptive_observations WHERE user_id=?',(target,))
        # Invalidate previews produced under the previous sharing choice.
        app.db.execute(c,'UPDATE hmay_state SET version=version+1,updated_at=? WHERE user_id=?',(P.now().isoformat(),target))
        app.event(c,user,target,'collective_optin' if data['enabled'] else 'collective_optout')
        return app.reply(start,200,dict(ok=True))
    if path=='/api/adaptive/preview':
        mode=data.get('mode','fill')
        if mode not in ('fill','reorganize'):raise ValueError('Modo de organização inválido.')
        w=P.week(data.get('week') or P.today())
        try:weeks=max(1,min(4,int(data.get('weeks',1))))
        except (TypeError,ValueError):raise ValueError('Quantidade de semanas inválida.')
        last_week=P.add(w,7*(weeks-1))
        if w<P.week(P.today()) or last_week>P.add(P.week(P.today()),364):raise ValueError('Escolha uma semana atual ou nos próximos 12 meses.')
        weights,own,shared=bonuses(app,c,user,target,p)
        academic=academic_priority(app,c,target,p)
        new=copy.deepcopy(p)
        motor_profile=MOTOR.apply_to_plan(app,c,target,new)
        for index in range(weeks):new=P.generate(new,P.add(w,7*index),mode=mode,bonuses=weights,subject_bonuses=academic.get('bonuses',{}))
        P.validate(new)
        if len(dumps(new).encode())>5_000_000:raise ValueError('Planejamento excede o limite de dados.')
        report=delta(p,new);report.update(mode=mode,week=w,endWeek=last_week,weeks=weeks,own=own,collective=shared,academic=academic)
        token=secrets.token_urlsafe(32)
        app.db.execute(c,'DELETE FROM hmay_proposals WHERE expires<? OR (actor_id=? AND target_id=?)',(int(time.time()),user['id'],target))
        app.db.execute(c,'INSERT INTO hmay_proposals(id,actor_id,target_id,base_version,profile,summary,expires) VALUES (?,?,?,?,?,?,?)',(token,user['id'],target,row['version'],dumps(new),dumps(report),int(time.time())+1800))
        return app.reply(start,200,dict(token=token,summary=report,sessions=[s for s in new['sessions'] if w<=s['date']<=P.add(last_week,6)],pending=new['pending'],notice=('Prévia de '+str(weeks)+' semana(s): nenhum horário foi substituído. Confirme para salvar. Blocos fixados e registros de execução são preservados.')))
    if path=='/api/adaptive/confirm':
        proposal=app.db.execute(c,'SELECT * FROM hmay_proposals WHERE id=? AND actor_id=? AND target_id=?'+(' FOR UPDATE' if not app.db.local_path else ''),(str(data.get('token','')),user['id'],target)).fetchone()
        if not proposal or proposal['expires']<int(time.time()):raise HTTPError(409,'Prévia expirada ou indisponível. Gere outra.')
        if proposal['base_version']!=row['version']:raise HTTPError(409,'Houve alteração após a prévia. Gere outra proposta.')
        new=json.loads(proposal['profile']);report=json.loads(proposal['summary']);current=P.now();oldids={s['id'] for s in p['sessions']}
        if any(s['id'] not in oldids and (s['date']<P.today() or s['date']==P.today() and s['start']<current.hour*60+current.minute) for s in new['sessions']):raise HTTPError(409,'Um horário da prévia já passou. Gere outra proposta.')
        # Re-check all newly generated blocks against current constraints.
        for s in new['sessions']:
            if s['id'] not in oldids:P.valid_session(new,s,s['id'])
        record(app,c,user,target,p,new,'schedule_proposal',{'reason':'proposal'})
        app.db.execute(c,'UPDATE hmay_state SET profile=?,version=version+1,updated_at=? WHERE user_id=?',(dumps(new),P.now().isoformat(),target))
        app.db.execute(c,'DELETE FROM hmay_proposals WHERE id=?',(proposal['id'],));app.event(c,user,target,'schedule_proposal:'+report['mode'])
        return app.reply(start,200,app.state(c,user,target))
    raise HTTPError(404,'Ação não encontrada.')


# === MEU CRONOGRAMA: PERFIS OPERACIONAIS DE ESTUDO V1 ===
_STUDY_BUILTIN_PRESETS = [
    dict(id='builtin:guided',name='Estrutura guiada',description='Para quem precisa de uma rotina previsível, blocos curtos e revisões frequentes.',config=dict(sessionMin=20,sessionMax=30,breakMin=10,dailyMax=90,weeklyGoal=360,reservePct=30,intervals=[1,3,7,14,30],reviewMin=25,defaultReviewPlan='both',defaultTheoryMin=12,defaultExerciseMin=18)),
    dict(id='builtin:restart',name='Retomada gradual',description='Carga inicial reduzida, mais reserva para imprevistos e progressão conservadora.',config=dict(sessionMin=20,sessionMax=25,breakMin=10,dailyMax=75,weeklyGoal=300,reservePct=35,intervals=[1,3,7,14],reviewMin=25,defaultReviewPlan='both',defaultTheoryMin=10,defaultExerciseMin=15)),
    dict(id='builtin:strategy',name='Estratégia em desenvolvimento',description='Equilibra compreensão, prática e acompanhamento da execução semanal.',config=dict(sessionMin=25,sessionMax=40,breakMin=10,dailyMax=120,weeklyGoal=480,reservePct=25,intervals=[1,4,10,21,45],reviewMin=35,defaultReviewPlan='both',defaultTheoryMin=15,defaultExerciseMin=20)),
    dict(id='builtin:autonomous',name='Autonomia consolidada',description='Blocos mais longos, maior prática independente e pausas ajustáveis pelo aluno.',config=dict(sessionMin=30,sessionMax=60,breakMin=10,dailyMax=180,weeklyGoal=720,reservePct=20,intervals=[1,7,21,45,90],reviewMin=40,defaultReviewPlan='both',defaultTheoryMin=10,defaultExerciseMin=30)),
    dict(id='builtin:exam',name='Pré-prova intensiva',description='Janela temporária com maior frequência de recuperação e predominância de exercícios.',config=dict(sessionMin=25,sessionMax=50,breakMin=10,dailyMax=240,weeklyGoal=900,reservePct=15,intervals=[1,3,7,14],reviewMin=40,defaultReviewPlan='exercise_only',defaultTheoryMin=10,defaultExerciseMin=30)),
    dict(id='builtin:short',name='Rotina curta',description='Para estudantes com pouco tempo disponível, priorizando sessões objetivas e exercícios.',config=dict(sessionMin=20,sessionMax=35,breakMin=8,dailyMax=60,weeklyGoal=240,reservePct=30,intervals=[1,3,7,21],reviewMin=30,defaultReviewPlan='exercise_only',defaultTheoryMin=10,defaultExerciseMin=20)),
]


def _study_schema(app,c):
    app.db.execute(c,'CREATE TABLE IF NOT EXISTS hmay_study_presets (id TEXT PRIMARY KEY, name TEXT NOT NULL, description TEXT NOT NULL, config TEXT NOT NULL, created_by TEXT NOT NULL, active INTEGER NOT NULL, created_at TEXT NOT NULL, updated_at TEXT NOT NULL)')


def _study_manager(user):
    return str(user.get('role') or '') in ('master','coordenador')


def _study_clean_config(raw):
    if not isinstance(raw,dict):raise ValueError('Configuração do perfil-base inválida.')
    def number(key,default,lo,hi):
        try:value=int(raw.get(key,default))
        except (TypeError,ValueError):raise ValueError('Valor inválido: '+key)
        if not lo<=value<=hi:raise ValueError('Valor fora do limite: '+key)
        return value
    intervals=raw.get('intervals',[1,3,7,14,30])
    if isinstance(intervals,str):
        try:intervals=[int(x.strip()) for x in intervals.split(',') if x.strip()]
        except ValueError:raise ValueError('Intervalos de revisão inválidos.')
    if not isinstance(intervals,list) or not 1<=len(intervals)<=10 or any(type(x)is not int or not 1<=x<=365 for x in intervals):raise ValueError('Intervalos de revisão inválidos.')
    intervals=sorted(set(intervals))
    plan=str(raw.get('defaultReviewPlan','both'))
    if plan not in ('both','exercise_only','theory_only'):raise ValueError('Plano de revisão inválido.')
    session_min=number('sessionMin',20,10,120);session_max=number('sessionMax',40,session_min,180)
    return dict(sessionMin=session_min,sessionMax=session_max,breakMin=number('breakMin',10,0,60),dailyMax=number('dailyMax',120,10,720),weeklyGoal=number('weeklyGoal',480,10,5040),reservePct=number('reservePct',25,0,80),intervals=intervals,reviewMin=number('reviewMin',30,10,180),defaultReviewPlan=plan,defaultTheoryMin=number('defaultTheoryMin',10,5,180),defaultExerciseMin=number('defaultExerciseMin',20,5,240))


def _study_presets(app,c):
    _study_schema(app,c)
    custom=[]
    for row in app.db.execute(c,'SELECT id,name,description,config,created_by,active,created_at,updated_at FROM hmay_study_presets WHERE active=1 ORDER BY name').fetchall():
        item=dict(row)
        try:item['config']=json.loads(item.get('config') or '{}')
        except Exception:item['config']={}
        item['custom']=True;custom.append(item)
    return [dict(x,custom=False) for x in _STUDY_BUILTIN_PRESETS]+custom


def _study_find_preset(app,c,preset_id):
    for item in _study_presets(app,c):
        if item['id']==preset_id:return item
    return None


_study_original_handle=handle

def handle(app,c,user,path,method,data,query,start,HTTPError):
    if path in ('/api/adaptive/presets','/api/adaptive/preset-save','/api/adaptive/preset-apply'):
        target=str(data.get('user') or query.get('user',[user['id']])[0]);app.require_target(user,target,c);_study_schema(app,c)
        if path=='/api/adaptive/presets' and method=='GET':
            state=app.db.execute(c,'SELECT profile FROM hmay_state WHERE user_id=?',(target,)).fetchone();profile=json.loads(state['profile']) if state else {}
            settings=profile.get('settings',{}) if isinstance(profile,dict) else {}
            return app.reply(start,200,dict(presets=_study_presets(app,c),current=dict(id=settings.get('studyPresetId',''),name=settings.get('studyPresetName','')),canManage=_study_manager(user)))
        if not _study_manager(user):raise HTTPError(403,'Perfis-base podem ser administrados somente pelo Master e pela coordenação.')
        if path=='/api/adaptive/preset-save' and method=='POST':
            name=str(data.get('name') or '').strip();description=str(data.get('description') or '').strip()
            if not 2<=len(name)<=100 or len(description)>500:raise ValueError('Informe um nome e uma descrição válidos.')
            config=_study_clean_config(data.get('config',{}));preset_id=str(data.get('id') or '')
            if preset_id.startswith('builtin:'):raise ValueError('Perfis internos não podem ser substituídos; crie uma cópia personalizada.')
            now=P.now().isoformat()
            if preset_id:
                row=app.db.execute(c,'SELECT id FROM hmay_study_presets WHERE id=?',(preset_id,)).fetchone()
                if not row:raise ValueError('Perfil-base não encontrado.')
                app.db.execute(c,'UPDATE hmay_study_presets SET name=?,description=?,config=?,active=1,updated_at=? WHERE id=?',(name,description,json.dumps(config,ensure_ascii=False,separators=(',',':')),now,preset_id))
            else:
                preset_id='preset:'+P.uid()
                app.db.execute(c,'INSERT INTO hmay_study_presets(id,name,description,config,created_by,active,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?)',(preset_id,name,description,json.dumps(config,ensure_ascii=False,separators=(',',':')),user['id'],1,now,now))
            app.event(c,user,target,'study_preset_save')
            return app.reply(start,200,dict(ok=True,id=preset_id,presets=_study_presets(app,c)))
        if path=='/api/adaptive/preset-apply' and method=='POST':
            row=app.db.execute(c,'SELECT * FROM hmay_state WHERE user_id=?'+(' FOR UPDATE' if not app.db.local_path else ''),(target,)).fetchone()
            if not row:raise HTTPError(404,'Conta não encontrada.')
            if type(data.get('version'))is not int or data['version']!=row['version']:raise HTTPError(409,'O planejamento mudou. Atualize a página antes de aplicar o perfil-base.')
            preset=_study_find_preset(app,c,str(data.get('presetId') or ''))
            if not preset:raise ValueError('Perfil-base não encontrado.')
            config=_study_clean_config(preset['config']);profile=json.loads(row['profile']);settings=profile.setdefault('settings',{})
            settings.update(config);settings['studyPresetId']=preset['id'];settings['studyPresetName']=preset['name']
            if bool(data.get('applyExisting',True)):
                for subject in profile.get('subjects',[]):
                    subject['reviewPlan']=config['defaultReviewPlan'];subject['theoryReviewMin']=config['defaultTheoryMin'];subject['exerciseReviewMin']=config['defaultExerciseMin'];subject.setdefault('priority',3);subject.setdefault('preferredReviewDay',-1)
                for content in profile.get('contents',[]):
                    content['reviewPlan']=config['defaultReviewPlan'];content['theoryReviewMin']=config['defaultTheoryMin'];content['exerciseReviewMin']=config['defaultExerciseMin'];content['reviewMinutes']=config['defaultTheoryMin']+config['defaultExerciseMin'];content.setdefault('preferredReviewDay',-1)
                if preset['id']=='builtin:math':_study_apply_math_focus(profile)
            if profile.get('planMeta'):profile['planMeta']['dirty']=True
            P.audit(profile,'perfil-base','Perfil-base aplicado: '+preset['name']+'. Horários existentes foram preservados até nova prévia.')
            P.validate(profile)
            app.db.execute(c,'UPDATE hmay_state SET profile=?,version=version+1,updated_at=? WHERE user_id=?',(json.dumps(profile,ensure_ascii=False,separators=(',',':')),P.now().isoformat(),target));app.event(c,user,target,'study_preset_apply')
            return app.reply(start,200,app.state(c,user,target))
        raise HTTPError(405,'Ação não permitida.')
    return _study_original_handle(app,c,user,path,method,data,query,start,HTTPError)

# === MATHEMATICS STUDY PRESET V1 ===
import unicodedata as _math_ud


def _math_norm(value):
    raw=str(value or '').strip().lower()
    return ''.join(ch for ch in _math_ud.normalize('NFD',raw) if _math_ud.category(ch)!='Mn')


def _study_apply_math_focus(profile):
    subjects=profile.get('subjects',[]) if isinstance(profile,dict) else []
    subject_kind={}
    for subject in subjects:
        if not isinstance(subject,dict):continue
        name=_math_norm(subject.get('name'))
        kind=''
        if 'matematica' in name:
            kind='math'
            subject['priority']=1
            subject['weeklyMin']=max(180,int(subject.get('weeklyMin') or 0))
            subject['reviewPlan']='both'
            subject['theoryReviewMin']=15
            subject['exerciseReviewMin']=35
            subject['importance']=max(4,int(subject.get('importance') or 3))
        elif 'fisica' in name or 'quimica' in name:
            kind='exact'
            subject['priority']=min(2,int(subject.get('priority') or 3))
            subject['weeklyMin']=max(120,int(subject.get('weeklyMin') or 0))
            subject['reviewPlan']='both'
            subject['theoryReviewMin']=15
            subject['exerciseReviewMin']=30
        if kind and subject.get('id'):subject_kind[subject['id']]=kind
    for content in profile.get('contents',[]):
        if not isinstance(content,dict):continue
        kind=subject_kind.get(content.get('subjectId'))
        if not kind:continue
        content['reviewPlan']='both'
        content['theoryReviewMin']=15
        content['exerciseReviewMin']=35 if kind=='math' else 30
        content['reviewMinutes']=content['theoryReviewMin']+content['exerciseReviewMin']
    return profile

if not any(x.get('id')=='builtin:math' for x in _STUDY_BUILTIN_PRESETS):
    _STUDY_BUILTIN_PRESETS.append(dict(
        id='builtin:math',
        name='Matemática e Exatas',
        description='Prioriza Matemática, resolução progressiva de problemas, correção de erros e prática frequente. Física e Química recebem prioridade alta quando cadastradas.',
        config=dict(sessionMin=25,sessionMax=50,breakMin=10,dailyMax=180,weeklyGoal=660,reservePct=20,intervals=[1,3,7,14,30,60],reviewMin=50,defaultReviewPlan='both',defaultTheoryMin=15,defaultExerciseMin=35)
    ))

# === MOTOR V3.7.18 ===
def _qi_active_year(app, c, target):
    """Ano letivo ativo do aluno; None quando nunca foi definido."""
    try:
        row = app.db.execute(c, 'SELECT active_year FROM hmay_academic_year WHERE user_id=?', (target,)).fetchone()
    except Exception:
        return None
    try:
        return int(row['active_year']) if row else None
    except (KeyError, TypeError, ValueError):
        return None
