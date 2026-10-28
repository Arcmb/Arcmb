"""Objective routine mapping, reviewable proposals and bounded statistical hints.
No AI calls, psychological labels, inferred availability or automatic consent.
"""
from __future__ import annotations
import copy
import json
import time
import secrets
import planner as P

VERSION = '2.2'
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
QUESTION_MAP = {q[0]: q for q in QUESTIONS}
REASONS = {
 'preference':'Preferência de horário', 'availability':'Disponibilidade mudou',
 'duration':'Ajuste de duração', 'priority':'Mudança de prioridade',
 'fatigue':'Ajuste de carga / descanso', 'support':'Orientação do responsável',
 'exception':'Imprevisto pontual', 'correction':'Correção de cadastro',
 'proposal':'Proposta conferida', 'not_informed':'Não informado',
}
SETTING_LABELS = {'preferred':'Período preferido','sessionMin':'Bloco mínimo (min)',
 'sessionMax':'Bloco máximo (min)','reviewMin':'Revisão (min)','breakMin':'Pausa (min)',
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
        put('sessionMin',min(s['sessionMin'],block),'Mantém o bloco mínimo compatível com o máximo proposto.')
        put('reviewMin',min(s['reviewMin'],block),'Mantém a revisão dentro do bloco máximo proposto.')
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
        return app.reply(start,200,dict(version=VERSION,questions=[dict(key=k,group=g,label=l,options=o) for k,g,l,o in QUESTIONS],answers=answers(p),suggestions=suggestions(p),personal=own,collective=shared,history=history(app,c,target),canConsent=target==user['id'] and user['role'] in ('aluno','user'),profileVersion=row['version']))
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
        if w<P.week(P.today()) or w>P.add(P.week(P.today()),364):raise ValueError('Escolha uma semana atual ou nos próximos 12 meses.')
        weights,own,shared=bonuses(app,c,user,target,p)
        new=P.generate(copy.deepcopy(p),w,mode=mode,bonuses=weights);P.validate(new)
        if len(dumps(new).encode())>5_000_000:raise ValueError('Planejamento excede o limite de dados.')
        report=delta(p,new);report.update(mode=mode,week=w,own=own,collective=shared)
        token=secrets.token_urlsafe(32)
        app.db.execute(c,'DELETE FROM hmay_proposals WHERE expires<? OR (actor_id=? AND target_id=?)',(int(time.time()),user['id'],target))
        app.db.execute(c,'INSERT INTO hmay_proposals(id,actor_id,target_id,base_version,profile,summary,expires) VALUES (?,?,?,?,?,?,?)',(token,user['id'],target,row['version'],dumps(new),dumps(report),int(time.time())+1800))
        return app.reply(start,200,dict(token=token,summary=report,sessions=[s for s in new['sessions'] if w<=s['date']<=P.add(w,6)],pending=new['pending'],notice='Prévia: nenhum horário foi substituído. Confirme para salvar. Blocos fixados e registros de execução são preservados.'))
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
