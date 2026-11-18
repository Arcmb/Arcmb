"""Horário da May: planejamento determinístico, sem IA ou serviços externos."""
from __future__ import annotations
import copy, datetime as dt, math, uuid
from zoneinfo import ZoneInfo

TZ = ZoneInfo('America/Belem')
DAY_NAMES = ['Segunda','Terça','Quarta','Quinta','Sexta','Sábado','Domingo']
def now(): return dt.datetime.now(TZ)
def today(): return now().date().isoformat()
def uid(): return 'r'+uuid.uuid4().hex
def date(value): return dt.date.fromisoformat(str(value))
def add(value, days): return (date(value)+dt.timedelta(days=days)).isoformat()
def week(value): return add(value,-((date(value).weekday()+1)%7))  # domingo a sábado (v3.7.18)
def hm(value): return f'{value//60:02d}:{value%60:02d}'
def minute(value):
    if not isinstance(value,str) or len(value)!=5 or value[2]!=':': raise ValueError('Horário inválido.')
    h,m=map(int,value.split(':'))
    if not 0<=h<24 or not 0<=m<60: raise ValueError('Horário inválido.')
    return h*60+m

def default_profile(name, profile_id=None):
    return dict(id=profile_id or uid(),name=name,demo=False,createdAt=now().isoformat(),updatedAt=now().isoformat(),
        answers=dict(goal='',context='',deadline='',obstacles=[],responsibilities='',energy='noite',startDifficulty='',focus='',environment='',support='',recovery='',notes='',completedAt=''),
        settings=dict(sleepStart='23:00',sleepEnd='07:00',sessionMin=20,sessionMax=50,breakMin=10,dailyMax=150,weeklyGoal=600,reservePct=20,intervals=[1,7,30],sameDay=False,reviewMin=20,preferred='noite',studyPresetId='',studyPresetName='',defaultReviewPlan='both',defaultTheoryMin=10,defaultExerciseMin=20),
        availability=[dict(day=d,status='unknown',ranges=[]) for d in range(7)],fixed=[],exceptions=[],subjects=[],contents=[],studyLogs=[],sessions=[],feedback=[],audit=[],pending=[],planMeta=None,lastBackup=None)

def audit(p, kind, message):
    p['audit'].insert(0,dict(id=uid(),at=now().isoformat(),type=kind,message=message))
    p['audit']=p['audit'][:1000];p['updatedAt']=now().isoformat()

def numeric(value, low, high, label):
    if isinstance(value,bool) or not isinstance(value,(int,float)) or not math.isfinite(value) or not low<=value<=high:
        raise ValueError(f'{label}: valor deve estar entre {low} e {high}.')

def validate(p):
    """Valida inclusive backups; dados nunca alteram contas ou permissões."""
    if not isinstance(p,dict): raise ValueError('Perfil inválido.')
    def inspect(obj,depth=0):
        if depth>25: raise ValueError('Estrutura excessivamente profunda.')
        if isinstance(obj,dict):
            for k,v in obj.items():
                if k in ('__proto__','constructor','prototype'): raise ValueError('Chave inválida.')
                inspect(v,depth+1)
        elif isinstance(obj,list):
            if len(obj)>20000: raise ValueError('Lista muito extensa.')
            for x in obj: inspect(x,depth+1)
        elif isinstance(obj,str) and len(obj)>20000: raise ValueError('Texto muito extenso.')
        elif isinstance(obj,float) and not math.isfinite(obj): raise ValueError('Número inválido.')
    inspect(p)
    if not isinstance(p.get('name'),str) or not 1<=len(p['name'].strip())<=150: raise ValueError('Nome inválido.')
    for k in ('subjects','contents','sessions','feedback','fixed','exceptions','studyLogs','audit','pending'):
        if not isinstance(p.get(k),list): raise ValueError('Coleção ausente: '+k)
    if not isinstance(p.get('answers'),dict): raise ValueError('Questionário inválido.')
    p['answers']={**default_profile(p['name'])['answers'],**p['answers']}
    for k,v in p['answers'].items():
        if k=='obstacles':
            if not isinstance(v,list) or len(v)>20 or any(not isinstance(x,str) for x in v): raise ValueError('Obstáculos inválidos.')
        elif not isinstance(v,str): raise ValueError('Resposta inválida.')
    p['settings']={**default_profile(p['name'])['settings'],**p.get('settings',{})}
    s=p['settings'];s.setdefault('reviewStartDate','')
    if s.get('reviewStartDate'):date(s['reviewStartDate'])
    a=minute(s['sleepStart']);b=minute(s['sleepEnd'])
    for k in ('sessionMin','sessionMax','breakMin','dailyMax','weeklyGoal','reservePct','reviewMin'):
        if type(s[k]) is not int:raise ValueError('Use minutos e percentuais inteiros.')
    if a==b: raise ValueError('O sono precisa ter início e fim diferentes.')
    for k,lo,hi in [('sessionMin',10,120),('sessionMax',s['sessionMin'],180),('breakMin',0,60),('dailyMax',10,720),('weeklyGoal',10,5040),('reservePct',0,80),('reviewMin',10,s['sessionMax']),('defaultTheoryMin',5,180),('defaultExerciseMin',5,240)]:numeric(s[k],lo,hi,k)
    if s.get('defaultReviewPlan') not in ('both','exercise_only','theory_only'):raise ValueError('Plano padrão de revisão inválido.')
    if not isinstance(s.get('studyPresetId',''),str) or not isinstance(s.get('studyPresetName',''),str):raise ValueError('Perfil-base inválido.')
    if s['preferred'] not in ('manha','tarde','noite','qualquer') or type(s['sameDay']) is not bool: raise ValueError('Preferência inválida.')
    ints=s['intervals']
    if not isinstance(ints,list) or not 1<=len(ints)<=12 or any(type(x)is not int or not 1<=x<=365 for x in ints) or ints!=sorted(set(ints)): raise ValueError('Intervalos: use dias inteiros, crescentes e diferentes, de 1 a 365.')
    if len(p.get('availability',[]))!=7:raise ValueError('Informe os sete dias.')
    for i,a in enumerate(p['availability']):
        if a['day']!=i or a['status'] not in ('unknown','available','unavailable') or len(a['ranges'])>12:raise ValueError('Disponibilidade inválida.')
        for r in a['ranges']:
            if minute(r['end'])<=minute(r['start']):raise ValueError('Faixa de disponibilidade invertida.')
    ids=set()
    for k in ('subjects','contents','sessions','feedback','fixed','exceptions','studyLogs','audit'):
        for x in p[k]:
            i=x.get('id','')
            if not isinstance(i,str) or not i or len(i)>100 or not all(c.isascii() and (c.isalnum() or c in '_-') for c in i) or i in ids:raise ValueError('Identificador inválido ou repetido.')
            ids.add(i)
    text_fields={'subjects':{'name':150,'action':300},'contents':{'title':300,'topic':300,'notes':20000,'material':5000},'fixed':{'title':250,'category':100},'sessions':{'title':500},'feedback':{'notes':20000},'exceptions':{'title':250},'audit':{'message':20000,'at':100,'type':100}}
    for collection,fields in text_fields.items():
        for item in p[collection]:
            for key,limit in fields.items():
                if not isinstance(item.get(key),str) or len(item[key])>limit:raise ValueError('Texto inválido: '+key)
    subjects={x['id'] for x in p['subjects']};contents={x['id'] for x in p['contents']}
    for x in p['subjects']:
        x.setdefault('color','')
        _subject_color=str(x.get('color') or '').strip().lower()
        if _subject_color and (len(_subject_color)!=7 or _subject_color[0]!='#' or any(ch not in '0123456789abcdef' for ch in _subject_color[1:])):raise ValueError('Cor da disciplina inválida.')
        x['color']=_subject_color
        if 'priorityManual' not in x:
            try:x['priorityManual']=int(x.get('priority',3) or 3)!=3
            except (TypeError,ValueError):x['priorityManual']=False
        if not x.get('priorityManual'):
            try:_priority_score=.60*float(x.get('importance',3))+.40*float(x.get('difficulty',3))
            except (TypeError,ValueError):_priority_score=3
            x['priority']=1 if _priority_score>=4.5 else 2 if _priority_score>=3.5 else 3 if _priority_score>=2.5 else 4 if _priority_score>=1.5 else 5
        else:x.setdefault('priority',3)
        x.setdefault('reviewPlan',s.get('defaultReviewPlan','both'));x.setdefault('theoryReviewMin',s.get('defaultTheoryMin',10));x.setdefault('exerciseReviewMin',s.get('defaultExerciseMin',20));x.setdefault('preferredReviewDay',-1)
        if not isinstance(x['name'],str) or not 1<=len(x['name'])<=150 or x['kind'] not in ('study','personal') or type(x['active'])is not bool:raise ValueError('Disciplina inválida.')
        for k,lo,hi in [('weeklyMin',0,3000),('difficulty',1,5),('importance',1,5),('priority',1,5),('theoryReviewMin',5,180),('exerciseReviewMin',5,240)]:numeric(x[k],lo,hi,k)
        if x.get('reviewPlan') not in ('both','exercise_only','theory_only') or type(x.get('preferredReviewDay')) is not int or not -1<=x['preferredReviewDay']<=6:raise ValueError('Configuração de revisão da disciplina inválida.')
        if type(x.get('priorityManual')) is not bool:raise ValueError('Modo de prioridade da disciplina inválido.')
        if x.get('examDate'):date(x['examDate'])
    for x in p['fixed']:
        if not x.get('title') or len(x['title'])>250 or x['recurrence'] not in ('weekly','biweekly','once'):raise ValueError('Compromisso inválido.')
        minute(x['start']);minute(x['end']);date(x['anchor'])
        if x['start']==x['end']:raise ValueError('Compromisso sem duração.')
        if x.get('until') and date(x['until'])<date(x['anchor']):raise ValueError('Fim da recorrência anterior ao início.')
        if not isinstance(x['days'],list) or any(type(d)is not int or not 0<=d<=6 for d in x['days']):raise ValueError('Dias inválidos.')
        numeric(x['before'],0,240,'Deslocamento');numeric(x['after'],0,240,'Deslocamento')
    for x in p['exceptions']:
        date(x['date'])
        if minute(x['end'])<=minute(x['start']):raise ValueError('Bloqueio invertido.')
    subject_map={x['id']:x for x in p['subjects']}
    for x in p['contents']:
        parent=subject_map.get(x.get('subjectId'),{})
        x.setdefault('reviewPlan',parent.get('reviewPlan',s.get('defaultReviewPlan','both')));x.setdefault('theoryReviewMin',parent.get('theoryReviewMin',s.get('defaultTheoryMin',10)));x.setdefault('exerciseReviewMin',parent.get('exerciseReviewMin',s.get('defaultExerciseMin',20)));x.setdefault('preferredReviewDay',parent.get('preferredReviewDay',-1))
        if x['subjectId']not in subjects or x['status']not in ('studied','planned') or not x['title'] or len(x['title'])>300:raise ValueError('Conteúdo inválido.')
        date(x['studiedOn']);minute(x['studiedTime']);numeric(x['studyMinutes'],0,720,'Duração');numeric(x['reviewMinutes'],10,420,'Revisão');numeric(x['difficulty'],1,5,'Dificuldade');numeric(x['theoryReviewMin'],5,180,'Revisão teórica');numeric(x['exerciseReviewMin'],5,240,'Exercícios')
        if x.get('reviewPlan') not in ('both','exercise_only','theory_only') or type(x.get('preferredReviewDay')) is not int or not -1<=x['preferredReviewDay']<=6:raise ValueError('Configuração de revisão do conteúdo inválida.')
        if x.get('nextDue'):date(x['nextDue'])
        x['stage']=min(max(0,int(x.get('stage',0))),len(ints)-1)
        if type(x['paused'])is not bool:raise ValueError('Pausa inválida.')
    for x in p['sessions']:
        if x['subjectId']not in subjects or (x.get('contentId') and x['contentId']not in contents):raise ValueError('Vínculo de sessão inválido.')
        date(x['date']);numeric(x['start'],0,1439,'Início');numeric(x['end'],1,1440,'Término')
        if x['end']<=x['start'] or x['status']not in ('planned','done','partial','missed') or x['kind']not in ('study','review','action'):raise ValueError('Sessão inválida.')
    for x in p['feedback']:
        if x['subjectId']not in subjects or (x.get('contentId') and x['contentId']not in contents):raise ValueError('Vínculo da verificação inválido.')
        date(x['date']);numeric(x['actualMin'],0,720,'Tempo real');numeric(x['total'],0,500,'Questões');numeric(x['correct'],0,x['total'],'Acertos')
        if x['status']not in ('done','partial','missed') or x['help']not in ('none','some','full') or x['confidence']not in ('low','medium','high'):raise ValueError('Verificação inválida.')
    return p

def merge(ranges):
    out=[]
    for a,b in sorted(ranges):
        if b<=a:continue
        if out and a<=out[-1][1]:out[-1][1]=max(out[-1][1],b)
        else:out.append([a,b])
    return out

def subtract(ranges,blocked):
    result=merge(ranges)
    for a,b in merge(blocked):
        result=[part for x,y in result for part in ([[x,y]] if x>=b or a>=y else ([[x,a]] if x<a else [])+([[b,y]] if y>b else []))]
    return result

def occurs(f,d):
    if f['recurrence']=='once':return d==f['anchor']
    if d<f['anchor'] or f.get('until') and d>f['until'] or date(d).weekday() not in f['days']:return False
    return f['recurrence']=='weekly' or ((date(week(d))-date(week(f['anchor']))).days//7)%2==0

def fixed_on(p,d):
    result=[]
    for f in p['fixed']:
        for offset in (-2,-1,0,1):
            if not occurs(f,add(d,offset)):continue
            start,end=minute(f['start']),minute(f['end'])
            if end<=start:end+=1440
            a,b=offset*1440+start-f['before'],offset*1440+end+f['after']
            if b>0 and a<1440:result.append(dict(id=f['id'],date=d,start=max(0,a),end=min(1440,b),title=f['title'],kind='fixed',status='fixed'))
    for x in p['exceptions']:
        if x['date']==d:result.append(dict(id=x['id'],date=d,start=minute(x['start']),end=minute(x['end']),title=x['title'],kind='fixed',status='fixed'))
    return sorted(result,key=lambda x:x['start'])

def free(p,d):
    a=p['availability'][date(d).weekday()];s=p['settings'];start,end=minute(s['sleepStart']),minute(s['sleepEnd'])
    if a['status']!='available':return []
    sleep=[[0,end],[start,1440]] if start>end else [[start,end]]
    return subtract([[minute(r['start']),minute(r['end'])] for r in a['ranges']],sleep+[[x['start'],x['end']]for x in fixed_on(p,d)])

def evidence(p,subject_id,content_id=None):
    observations=[x for x in p['feedback'] if x['subjectId']==subject_id and (not content_id or x.get('contentId')==content_id) and x['status']!='missed' and x['total']>0 and x['help']=='none']
    total=sum(x['total']for x in observations)
    return dict(total=total,rate=sum(x['correct']for x in observations)/total if total else None,days=len({x['date']for x in observations}))

def generate(p,week_start,current=None,mode="reorganize",bonuses=None,subject_bonuses=None):
    current=current or now();start=week(week_start);end=add(start,6);td=current.date().isoformat();mins=current.hour*60+current.minute;s=p['settings']
    if mode not in ('fill','reorganize'):raise ValueError('Modo inválido.')
    bonuses=bonuses or {}
    subject_bonuses=subject_bonuses or {}
    if mode=='reorganize':
        p['sessions']=[x for x in p['sessions'] if not(start<=x['date']<=end and x['status']=='planned' and not x.get('locked') and (x['date']>td or x['date']==td and x['start']>=mins))]
    _qi_drop_conflicts(p,start,end,td,mins)
    kept=[x for x in p['sessions']if start<=x['date']<=end and x['status']!='missed'];used=sum(x['end']-x['start']for x in kept)
    slots={};caps={};day_used={};created=[];pending=[];br=s['breakMin']
    for i in range(7):
        d=add(start,i);r=free(p,d);caps[d]=min(s['dailyMax'],int(sum(b-a for a,b in r)*(1-s['reservePct']/100)));day_used[d]=sum(x['end']-x['start']for x in kept if x['date']==d)
        blocked=[[x['start']-br,x['end']+br]for x in kept if x['date']==d]
        if d==td:blocked.append([0,math.ceil(mins/5)*5])
        slots[d]=subtract(r,blocked) if d>=td else []
    _qi_rev=dict(used=0,cap=10**9);_qi_deferred=[];_qi_failed=set()
    def place(task,duration):
        nonlocal used
        best=None
        for d,rs in slots.items():
            if d<task.get('earliest',td) or day_used[d]+duration>caps[d] or used+duration>s['weeklyGoal'] or (task['kind']=='review' and _qi_rev['used']+duration>_qi_rev['cap']):continue
            for a,b in rs:
                a=math.ceil(a/5)*5
                if task.get('studiedOn')==d:a=max(a,minute(task['studiedTime'])+max(120,task['studyMinutes']))
                if task.get('notBeforeDate')==d:a=max(a,int(task.get('notBeforeMin',a)))
                for t in range(a,b-duration+1,5):
                    preferred=s['preferred'];energy=12 if preferred=='manha' and t<720 or preferred=='tarde' and 720<=t<1080 or preferred=='noite' and t>=1080 else 0
                    repetitions=sum(x['date']==d and x['subjectId']==task['subjectId']for x in kept+created)
                    delay=max(0,(date(d)-date(task.get('due',max(td,start)))).days)
                    score=energy-8*day_used[d]/max(caps[d],1)-repetitions*4-delay*(20 if task.get('due') else .35)-t/10000
                    slot_period='manha' if t<720 else 'tarde' if t<1080 else 'noite'
                    score+=max(-3,min(3,float(bonuses.get(slot_period,0))))
                    score+=(6-max(1,min(5,int(task.get('priority',3)))))*2.5
                    preferred_day=task.get('preferredDay',-1)
                    if preferred_day in range(7):score+=8 if date(d).weekday()==preferred_day else -1.5
                    if best is None or score>best[0]:best=(score,d,t)
        if best is None:return False
        _,d,t=best
        created.append(dict(id=uid(),date=d,start=t,end=t+duration,kind=task['kind'],subjectId=task['subjectId'],subjectName=task.get('subjectName',''),contentId=task.get('contentId',''),reviewContentId=task.get('reviewContentId',''),reviewPart=task.get('reviewPart',''),reviewCycleId=task.get('reviewCycleId',''),title=task['title'],status='planned',locked=False,reason=task['reason'],createdAt=now().isoformat()))
        day_used[d]+=duration;used+=duration;_qi_rev['used']+=duration*(task['kind']=='review');slots[d]=subtract(slots[d],[[t-br,t+duration+br]]);return created[-1]
    subjects=[x for x in p['subjects']if x['active']];subject_ids={x['id']for x in subjects}
    due=[x for x in p['contents']if x['status']=='studied' and not x['paused'] and x.get('nextDue') and x['nextDue']<=end and x['subjectId']in subject_ids]
    subject_priority={x['id']:int(x.get('priority',3)) for x in subjects}
    subject_names={x['id']:x.get('name','Disciplina') for x in subjects}
    due=_qi_review_order(due,subjects,subject_bonuses,td);_qi_rev['cap']=_qi_review_cap(s,caps,td,used)
    review_start=str(s.get('reviewStartDate') or '').strip()
    for c in due:
        if review_start and c.get('nextDue','')<review_start:c=dict(c,nextDue=review_start)
        linked=lambda x:(x.get('contentId')==c['id'] or x.get('reviewContentId')==c['id']) and x['kind']=='review' and x['status']=='planned'
        existing=[x for x in p['sessions'] if linked(x) and (not review_start or x.get('date','')>=review_start)]
        if existing:
            if any(x['date']<td for x in existing):pending.append(dict(title=c['title'],reason='Revisão anterior sem registro. Verifique ou registre que não realizou antes de reagendar.',minutes=c['reviewMinutes']))
            continue
        plan,theory,exercise=_qi_profile_review(c,s);cycle=uid();discipline=subject_names.get(c['subjectId'],'Disciplina')
        if plan=='exercise_only':parts=[('exercise',theory+exercise,discipline+' · Exercícios: '+c['title'],True)]
        elif plan=='theory_only':parts=[('theory',theory+exercise,discipline+' · Revisão de teoria: '+c['title'],True)]
        else:parts=[('theory',theory,discipline+' · Revisão de teoria: '+c['title'],False),('exercise',exercise,discipline+' · Exercícios: '+c['title'],True)]
        previous_part=None
        for part,duration,title,closes_cycle in parts:
            task=dict(kind='review',subjectId=c['subjectId'],subjectName=discipline,contentId=c['id'] if closes_cycle else '',reviewContentId=c['id'],reviewPart=part,reviewCycleId=cycle,title=title,earliest=c['nextDue'],due=c['nextDue'],studiedOn=c['studiedOn'],studiedTime=c['studiedTime'],studyMinutes=c['studyMinutes'],preferredDay=int(c.get('preferredReviewDay',-1)),priority=subject_priority.get(c['subjectId'],3),reason=('Prática de recuperação por exercícios. ' if part=='exercise' else 'Retomada orientada da teoria. ')+' Disciplina: '+discipline+'. Data-alvo: '+c['nextDue']+'.')
            if previous_part:
                task['earliest']=previous_part['date'];task['notBeforeDate']=previous_part['date'];task['notBeforeMin']=previous_part['end']+br
            placed=False if (_qi_deferred and _qi_deferred[-1][0].get('reviewCycleId')==cycle) else place(task,min(duration,240))
            if not placed:_qi_deferred.append((task,min(duration,240),dict(title=title,minutes=duration,reason='Sem encaixe após a data-alvo, preservando pausas, disponibilidade e limites.')))
            else:previous_part=placed
    budget=min(sum(caps.values()),s['weeklyGoal'],sum(x['weeklyMin']for x in subjects));weights=[]
    for sub in subjects:
        ev=evidence(p,sub['id']);diff=sub['difficulty']
        if ev['total']>=6 and ev['days']>=2:diff=.5*diff+.5*(1+4*(1-ev['rate']))
        days=(date(sub['examDate'])-date(td)).days if sub.get('examDate') else 999
        urgency=max(0,(30-days)/30) if 0<=days<=30 else 0
        academic=max(1.0,min(1.25,float(subject_bonuses.get(sub['id'],1.0))))
        declared={1:1.65,2:1.35,3:1.0,4:.78,5:.60}.get(int(sub.get('priority',3)),1.0)
        weights.append(max(1,sub['weeklyMin'])*(1+.10*(diff-sub['difficulty'])+.15*urgency)*academic*declared)
    targets=[]
    for sub,weight in zip(subjects,weights):
        amount=sum(x['end']-x['start']for x in kept+created if x['subjectId']==sub['id'])
        target=min(sub['weeklyMin']*1.25,budget*weight/max(sum(weights),1));targets.append(dict(sub=sub,left=max(0,target-amount),allocated=amount))
    for _ in range(500):
        options=sorted([x for x in targets if x['left']>=s['sessionMin']],key=lambda x:(6-int(x['sub'].get('priority',3)),x['left']/(x['allocated']+20)),reverse=True)
        if not options:break
        made=False
        for x in options:
            sub=x['sub'];planned=next((c for c in p['contents']if c['subjectId']==sub['id'] and c['status']=='planned' and not c['paused'] and c['studiedOn']<=end and not any(e.get('contentId')==c['id'] and e['status']=='planned' for e in kept+created)),None)
            task=dict(kind='action' if sub['kind']=='personal' else 'study',subjectId=sub['id'],contentId=planned['id']if planned else '',title='Estudar: '+planned['title']if planned else(sub.get('action')or'Estudar e praticar')+' · '+sub['name'],earliest=planned['studiedOn']if planned else td,priority=int(sub.get('priority',3)),reason='Distribuição por prioridade declarada, meta, dificuldade verificada, importância, prazo e resultados acadêmicos recentes quando há evidência suficiente. Não é previsão de nota.')
            duration=min(s['sessionMax'],int(x['left']//5)*5)
            while duration>=s['sessionMin']:
                if place(task,duration):x['left']-=duration;x['allocated']+=duration;made=True;break
                duration-=5
            if made:break
            x['left']=0
        if not made:break
    _qi_rev['cap']=10**9;_qi_last={}
    for _qi_task,_qi_dur,_qi_pend in _qi_deferred:
        _qi_cycle=_qi_task.get('reviewCycleId')
        if _qi_cycle in _qi_failed:pending.append(_qi_pend);continue
        if _qi_cycle in _qi_last:_qi_task.update(earliest=_qi_last[_qi_cycle]['date'],notBeforeDate=_qi_last[_qi_cycle]['date'],notBeforeMin=_qi_last[_qi_cycle]['end']+br)
        _qi_placed=place(_qi_task,_qi_dur)
        if _qi_placed:_qi_last[_qi_cycle]=_qi_placed
        else:pending.append(_qi_pend);_qi_failed.add(_qi_cycle)
    p['sessions']+=created;p['sessions'].sort(key=lambda x:(x['date'],x['start']))
    for sub in subjects:
        scheduled=sum(x['end']-x['start']for x in p['sessions']if start<=x['date']<=end and x['subjectId']==sub['id'] and x['status']!='missed')
        if scheduled+5<sub['weeklyMin']:pending.append(dict(title=sub['name'],minutes=round(sub['weeklyMin']-scheduled),reason='Parte da meta não foi distribuída. Revise a capacidade e as prioridades.'))
    for item in kept:
        if item.get('locked') and item['date']>=td:
            try:valid_session(p,item,item['id'])
            except ValueError as ex:pending.append(dict(title=item['title'],minutes=item['end']-item['start'],reason='Bloco fixado exige revisão manual: '+str(ex)))
    p['pending']=_qi_compact_pending(pending,caps,s,subjects,td,0);p['planMeta']=dict(week=start,generatedAt=now().isoformat(),dirty=False,created=len(created),minutes=used,capacity=min(sum(caps.values()),s['weeklyGoal']))
    audit(p,'planejamento',f'{len(created)} novos blocos para a semana de {start}. Heurística de encaixe: não garante ótimo global.')
    return p

ADVICE={
 'time':('O horário deixou de estar disponível ou a tarefa demorou mais?',{'exception':'Reagende a pendência sem alterar toda a rotina.','recurring':'Atualize a disponibilidade ou o compromisso recorrente.','duration':'Compare tarefas de tamanho semelhante e ajuste a estimativa de duração.'}),
 'tired':('Foi excepcional ou se repete nesse horário?',{'exception':'Preserve o descanso e reduza a carga do dia, sem compensação excessiva.','recurring':'Experimente outro horário ou menos carga diária. O sistema não faz avaliação de saúde.'}),
 'difficulty':('A dificuldade está na orientação, no conteúdo ou em um pré-requisito?',{'instruction':'Defina o primeiro passo e confirme a orientação.','current':'Retome um exemplo e tente uma questão diferente. Solicite apoio se persistir.','prerequisite':'Cadastre e verifique o pré-requisito antes de avançar.'}),
 'distraction':('Qual foi a principal interrupção?',{'phone':'Teste um bloco sem notificações.','environment':'Experimente um ambiente com menos interrupções.','long':'Teste blocos menores com pausas e compare a execução.'}),
 'unclear':('O primeiro passo estava claro?',{'no':'Substitua uma tarefa vaga por uma ação concreta e pequena.','yes':'Teste um bloco inicial menor e registre o obstáculo, sem se rotular.'}),
 'unexpected':('Isso deve acontecer novamente?',{'exception':'Cadastre um bloqueio apenas nessa data.','recurring':'Cadastre o compromisso recorrente e recalcule a semana.'}),
 'other':('Qual encaminhamento prefere?',{'review':'Descreva o obstáculo e teste uma mudança verificável.','support':'Registre a dúvida para conversar com professor ou responsável.'})}

def feedback(p,data):
    session=next((x for x in p['sessions']if x['id']==data.get('sessionId')),None)
    c=next((x for x in p['contents']if x['id']==(session.get('contentId')if session else data.get('contentId'))),None)
    if not session and not c:raise ValueError('Selecione uma atividade ou conteúdo.')
    if session and session['status']!='planned':raise ValueError('Esta atividade já tem resultado registrado.')
    d=data.get('date')or today()
    if date(d)>date(today()):raise ValueError('Não registre uma execução em data futura.')
    if session and date(d)<date(session['date']):raise ValueError('Mova o bloco para a data da execução antes de registrar.')
    if c and (c['status']!='studied' or d<c['studiedOn']) and not(session and session['kind']=='study'):raise ValueError('Confirme primeiro o estudo do conteúdo.')
    f=dict(id=uid(),sessionId=session['id']if session else '',subjectId=session['subjectId']if session else c['subjectId'],contentId=c['id']if c else '',date=d,status=data['status'],actualMin=int(data['actualMin']),total=int(data.get('total',0)),correct=int(data.get('correct',0)),help=data.get('help','none'),confidence=data.get('confidence','medium'),reason=data.get('reason',''),detail=data.get('detail',''),notes=str(data.get('notes',''))[:1200],methods=[str(x) for x in data.get('methods',[]) if str(x) in ('questoes','correcao','resumo','flashcards','releitura','videoaula','explicacao','mapa','monitoria','outro')][:12],monitoring=bool(data.get('monitoring',False)),monitoringNotes=str(data.get('monitoringNotes',''))[:500],reviewDescription=str(data.get('reviewDescription',''))[:1200],perceivedDifficulty=max(1,min(5,int(data.get('perceivedDifficulty',3) or 3))),needsAttention=bool(data.get('needsAttention',False)),at=now().isoformat())
    if f['status']=='missed':f['actualMin']=0;f['total']=0;f['correct']=0
    if session:session['status']=f['status']
    p['feedback'].insert(0,f)
    if c and session and session['kind']=='study' and f['status']=='done':
        c['status']='studied';c['studiedOn']=d;c['studiedTime']=hm(session['start']);c['studyMinutes']=f['actualMin'];c['stage']=0;c['nextDue']=d if p['settings']['sameDay']else add(d,p['settings']['intervals'][0]);p['studyLogs'].append(dict(id=uid(),contentId=c['id'],date=d,minutes=f['actualMin']))
        f['message']='Estudo registrado. Revisões habilitadas após a execução.'
    elif c and f['status']!='missed':
        s=p['settings'];ev=evidence(p,c['subjectId'],c['id']);rate=f['correct']/f['total']if f['total']else None
        if f['status']=='done' and rate is not None and rate>=.8 and f['help']=='none' and not f.get('needsAttention') and f.get('perceivedDifficulty',3)<=3 and ev['total']>=6 and ev['days']>=2 and ev['rate']>=.8:
            c['stage']=min(c['stage']+1,len(s['intervals'])-1);interval=s['intervals'][c['stage']];f['message']=f'Evidências independentes em dias diferentes: próxima revisão em {interval} dia(s).'
        elif (rate is not None and rate<.6) or f['help']=='full' or f.get('needsAttention') or f.get('perceivedDifficulty',3)>=4:
            interval=s['intervals'][0];f['message']='Revisão antecipada para retomar a dificuldade. Considere apoio ou um pré-requisito.'
        else:
            interval=s['intervals'][min(c['stage'],len(s['intervals'])-1)];f['message']='Intervalo mantido: ainda não há evidência suficiente para ampliar.'
        c['nextDue']=add(d,interval)
        if f['status']=='done' and f['actualMin']>0:c['reviewMinutes']=max(10,min(180,round(.8*c['reviewMinutes']+.2*f['actualMin'])))
        p['sessions']=[x for x in p['sessions']if not(x.get('contentId')==c['id'] and x['kind']=='review' and x['status']=='planned' and not x.get('locked') and x['date']>=d)]
    else:f['message']='Não realizado não significa desconhecimento. Recalcule para procurar outro horário.' if f['status']=='missed' else 'Execução registrada.'
    if f['reason']:
        _,choices=ADVICE.get(f['reason'],ADVICE['other']);f['advice']=choices.get(f['detail'],next(iter(choices.values())))
    audit(p,'verificação',f['message']);return f

def valid_session(p,item,ignore_id=None):
    d=item['date'];a,b=item['start'],item['end'];s=p['settings']
    if not 0<=a<b<=1440 or not any(x<=a<b<=y for x,y in free(p,d)):raise ValueError('O bloco conflita com disponibilidade, sono ou compromisso.')
    others=[x for x in p['sessions']if x['id']!=ignore_id and x['status']!='missed'];br=s['breakMin']
    if any(x['date']==d and a<x['end']+br and x['start']-br<b for x in others):raise ValueError('Há conflito com outro bloco ou com a pausa.')
    capacity=min(s['dailyMax'],int(sum(y-x for x,y in free(p,d))*(1-s['reservePct']/100)))
    if sum(x['end']-x['start']for x in others if x['date']==d)+b-a>capacity:raise ValueError('Limite diário ou reserva excedidos.')
    if sum(x['end']-x['start']for x in others if week(x['date'])==week(d))+b-a>s['weeklyGoal']:raise ValueError('Limite semanal excedido.')
    c=next((x for x in p['contents']if x['id']==item.get('contentId')),None)
    if c and item['kind']=='review' and(c['status']!='studied' or d<c['studiedOn'] or d==c['studiedOn'] and a<minute(c['studiedTime'])+max(120,c['studyMinutes'])):raise ValueError('A revisão precisa ocorrer após o estudo; no mesmo dia, preserve duas horas desde o início e aguarde seu término.')

def action(p,op,data):
    p=copy.deepcopy(p)
    if op=='diagnosis':
        p['answers'].update({k:str(data.get(k,'')) for k in p['answers']if k!='obstacles'});p['answers']['obstacles']=data.get('obstacles',[]);p['answers']['completedAt']=now().isoformat()
        if data.get('energy') in ('manha','tarde','noite','qualquer'):p['settings']['preferred']=data['energy']
    elif op=='routine_table':
        from routine_entries import save_table
        return save_table(p,data)
    elif op=='routine':
        p['settings'].update(data['settings']);p['availability']=data['availability']
    elif op in ('subject','fixed','exception'):
        collection={'subject':'subjects','fixed':'fixed','exception':'exceptions'}[op];item=copy.deepcopy(data)
        old=next((x for x in p[collection]if x['id']==data.get('id')),None)
        if old:
            old.update({k:v for k,v in item.items()if k!='id'})
            if op=='subject' and not old['active']:
                p['sessions']=[x for x in p['sessions']if not(x['subjectId']==old['id']and x['status']=='planned'and not x.get('locked')and x['date']>=today())]
        else:item['id']=uid();p[collection].append(item)
    elif op=='content':
        item=copy.deepcopy(data);item.update(id=uid(),stage=0,paused=False);item['nextDue']=('' if item['status']=='planned'else item['studiedOn']if p['settings']['sameDay']else add(item['studiedOn'],p['settings']['intervals'][0]));p['contents'].append(item)
        if item['status']=='studied':p['studyLogs'].append(dict(id=uid(),contentId=item['id'],date=item['studiedOn'],minutes=item['studyMinutes']))
    elif op=='restudy':
        c=next(x for x in p['contents']if x['id']==data['id']);c.update(status='studied',studiedOn=data['date'],studiedTime=data['time'],studyMinutes=int(data['minutes']),stage=0)
        if c['studiedOn']>today():raise ValueError('Estudo realizado não pode estar no futuro.')
        p['sessions']=[x for x in p['sessions']if not(x.get('contentId')==c['id']and x['kind']=='review'and x['status']=='planned'and not x.get('locked')and x['date']>=today())]
        c['nextDue']=c['studiedOn']if p['settings']['sameDay']else add(c['studiedOn'],p['settings']['intervals'][0]);p['studyLogs'].append(dict(id=uid(),contentId=c['id'],date=c['studiedOn'],minutes=c['studyMinutes']))
    elif op=='review_preferences':
        c=next(x for x in p['contents']if x['id']==data['id']);plan=str(data.get('reviewPlan','both'));theory=int(data.get('theoryReviewMin',10));exercise=int(data.get('exerciseReviewMin',20));preferred=int(data.get('preferredReviewDay',-1))
        if plan not in ('both','exercise_only','theory_only') or not 5<=theory<=180 or not 5<=exercise<=240 or not -1<=preferred<=6:raise ValueError('Preferências de revisão inválidas.')
        c.update(reviewPrefsCustom=True,reviewPlan=plan,theoryReviewMin=theory,exerciseReviewMin=exercise,preferredReviewDay=preferred,reviewMinutes=theory+exercise,paused=bool(data.get('paused',False)),nextDue=data.get('nextDue')or c.get('nextDue'))
        p['sessions']=[x for x in p['sessions']if not((x.get('contentId')==c['id']or x.get('reviewContentId')==c['id'])and x['kind']=='review'and x['status']=='planned'and not x.get('locked')and x['date']>=today())]
        if p.get('planMeta'):p['planMeta']['dirty']=True
    elif op=='review':
        c=next(x for x in p['contents']if x['id']==data['id']);c['paused']=bool(data.get('paused',False));c['nextDue']=data.get('nextDue')or c['nextDue']
        p['sessions']=[x for x in p['sessions']if not(x.get('contentId')==c['id']and x['status']=='planned'and not x.get('locked')and x['date']>=today())]
    elif op=='delete':
        collection=data['collection']
        if collection not in ('fixed','exceptions','sessions','subjects','contents'):raise ValueError('Exclusão não permitida.')
        item=next(x for x in p[collection]if x['id']==data['id'])
        if collection=='sessions' and item['status']!='planned':raise ValueError('O histórico de execução deve ser preservado.')
        if collection=='subjects' and any(x['subjectId']==item['id']for x in p['contents']+p['sessions']+p['feedback']):raise ValueError('Há histórico vinculado. Pause a disciplina em vez de excluir.')
        if collection=='contents' and any(x.get('contentId')==item['id']for x in p['sessions']+p['feedback']+p['studyLogs']):raise ValueError('Há histórico vinculado. Pause as revisões em vez de excluir.')
        p[collection].remove(item)
    elif op=='session':
        item=next(x for x in p['sessions']if x['id']==data['id'])
        if item['status']!='planned':raise ValueError('Somente atividades pendentes podem mudar.')
        item.update(date=data['date'],start=minute(data['start']),end=minute(data['end']),locked=bool(data.get('locked',False)))
        valid_session(p,item,item['id'])
    elif op=='generate':return validate(generate(p,data.get('week')or today()))
    elif op=='feedback':feedback(p,data)
    elif op=='import':
        incoming=copy.deepcopy(data['profile']);incoming['id']=p['id'];incoming['name']=p['name'];incoming['demo']=False;incoming['pending']=[];incoming['planMeta']=None;p=validate(incoming)
    else:raise ValueError('Ação não reconhecida.')
    for c in p['contents']:
        if c['status']=='studied' and c['studiedOn']>today():raise ValueError('Use “pretendo estudar” para conteúdos futuros.')
    if p.get('planMeta'):p['planMeta']['dirty']=True
    audit(p,op,'Registro atualizado: '+op+'.');return validate(p)

# === REVIEW EVIDENCE V1 ===

# === MEU CRONOGRAMA: ESTUDO E REVISAO ESTRUTURADOS V1 ===

# === REVIEW SUBJECT LABELS V1 ===

# === LEARNER GUIDANCE AND PRIORITY V1 ===

# === LEARNER PRIORITY LEGACY COMPAT V1 ===

# === DISCIPLINE COLORS AND REVIEW RUNTIME V1 ===

# === REVIEW START DATE V1 ===

# === MOTOR V3.7.18 ===
# Decisões do responsável (18/11/2026):
# - Semana de domingo a sábado.
# - As revisões ocupam uma fração da semana que varia com a disponibilidade do aluno.
# - Prioridade às disciplinas com maior dificuldade; tópicos com mais erros primeiro.
# - Questão em branco conta como erro (comportamento já existente da sincronização).

_QI_DECLARED = {1: 1.65, 2: 1.35, 3: 1.0, 4: .78, 5: .60}


def _qi_review_share(weekly_capacity):
    """Fração máxima da semana para revisões na primeira rodada.

    Pouco tempo livre: as revisões de erros ocupam a maior parte (70%).
    Mais tempo livre: sobra mais espaço para estudo novo (60% e 50%).
    O que não for usado pelo estudo novo volta para as revisões na segunda rodada.
    """
    if weekly_capacity <= 300:
        return .70
    if weekly_capacity <= 600:
        return .60
    return .50


def _qi_review_cap(s, caps, td, used):
    future = sum(v for d, v in caps.items() if d >= td)
    weekly = max(0, min(future, s['weeklyGoal'] - used))
    profile = s.get('motorProfile') if isinstance(s.get('motorProfile'), dict) else None
    share = float(profile.get('reviewShare')) if profile and profile.get('reviewShare') else _qi_review_share(weekly)
    return int(weekly * share)


def _qi_subject_weight(sub, subject_bonuses):
    declared = _QI_DECLARED.get(int(sub.get('priority', 3) or 3), 1.0)
    academic = max(1.0, min(1.25, float((subject_bonuses or {}).get(sub['id'], 1.0))))
    return declared * academic


def _qi_review_order(due, subjects, subject_bonuses, td):
    """Rodízio ponderado entre disciplinas: as de maior dificuldade recebem mais vezes.

    Dentro de cada disciplina: mais erros primeiro, depois a data-alvo mais antiga
    e a maior dificuldade. Sem empate pela ordem de cadastro das disciplinas.
    """
    by_subject = {}
    for c in due:
        by_subject.setdefault(c['subjectId'], []).append(c)
    for items in by_subject.values():
        items.sort(key=lambda x: (-int(x.get('errorCount', 0) or 0), x.get('nextDue', ''), -int(x.get('difficulty', 3) or 3), x.get('title', '')))
    subject_map = {x['id']: x for x in subjects}
    weights = {k: _qi_subject_weight(subject_map[k], subject_bonuses) if k in subject_map else 1.0 for k in by_subject}
    names = {k: str(subject_map.get(k, {}).get('name', '')) for k in by_subject}
    taken = {k: 0 for k in by_subject}
    ordered = []
    while any(by_subject.values()):
        key = min((k for k, v in by_subject.items() if v), key=lambda k: ((taken[k] + 1) / weights[k], -weights[k], names[k]))
        ordered.append(by_subject[key].pop(0))
        taken[key] += 1
    return ordered


def _qi_drop_conflicts(p, start, end, td, mins):
    """Remove apenas blocos planejados, não fixados e futuros que perderam a validade.

    Um bloco é inválido quando saiu da disponibilidade (bloqueio, compromisso, sono)
    ou passou a sobrepor outro bloco que permanece. Os demais ficam onde estão.
    """
    br = p['settings']['breakMin']
    week_items = [x for x in p['sessions'] if start <= x['date'] <= end and x['status'] != 'missed']
    movable = lambda x: x['status'] == 'planned' and not x.get('locked') and (x['date'] > td or x['date'] == td and x['start'] >= mins)
    keep = [x for x in week_items if not movable(x)]
    invalid = set()
    free_cache = {}
    for x in sorted([x for x in week_items if movable(x)], key=lambda x: (x['date'], x['start'])):
        if x['date'] not in free_cache:
            free_cache[x['date']] = free(p, x['date'])
        inside = any(a <= x['start'] < x['end'] <= b for a, b in free_cache[x['date']])
        clash = any(y['date'] == x['date'] and x['start'] < y['end'] + br and y['start'] - br < x['end'] for y in keep)
        if inside and not clash:
            keep.append(x)
        else:
            invalid.add(x['id'])
    if invalid:
        p['sessions'] = [x for x in p['sessions'] if x['id'] not in invalid]
    return invalid


def _qi_compact_pending(pending, caps, s, subjects, td, review_minutes):
    """Agrupa pendências repetitivas em mensagens que explicam a causa."""
    capacity = min(sum(v for d, v in caps.items() if d >= td), s['weeklyGoal'])
    out = []
    if capacity <= 0:
        out.append(dict(title='Horários livres', minutes=0, reason='Cadastre seus horários livres em Rotina e horários. Sem disponibilidade, o cronograma não tem onde encaixar estudos e revisões.'))
    reviews = [x for x in pending if str(x.get('reason', '')).startswith('Sem encaixe')]
    stale = [x for x in pending if str(x.get('reason', '')).startswith('Revisão anterior sem registro')]
    goals = [x for x in pending if str(x.get('reason', '')).startswith('Parte da meta')]
    other = [x for x in pending if x not in reviews and x not in stale and x not in goals]
    out.extend(other)
    if reviews and capacity > 0:
        out.append(dict(title=f'{len(reviews)} revisão(ões) aguardando horário', minutes=sum(int(x.get('minutes', 0) or 0) for x in reviews),
                        reason='A semana não comporta todas as revisões. As de disciplinas com maior dificuldade e com mais erros foram encaixadas primeiro; as demais entram nas próximas semanas.'))
    if stale:
        out.append(dict(title=f'{len(stale)} revisão(ões) passada(s) sem registro', minutes=sum(int(x.get('minutes', 0) or 0) for x in stale),
                        reason='Registre se foram feitas ou não antes de reagendar.'))
    if goals and capacity > 0:
        total_goal = sum(int(x.get('weeklyMin', 0) or 0) for x in subjects)
        missing = sum(int(x.get('minutes', 0) or 0) for x in goals)
        out.append(dict(title='Metas semanais acima do tempo livre', minutes=missing,
                        reason=f'As metas somam {total_goal} min e o tempo útil da semana é {capacity} min. A distribuição favoreceu as disciplinas com maior dificuldade.'))
    return out

# === MOTOR PROFILES V3.9.0 ===
def _qi_profile_review(c, s):
    """Forma e minutos da revisão: o perfil de foco vale para conteúdos sem ajuste manual do aluno."""
    mp = s.get('motorProfile') if isinstance(s.get('motorProfile'), dict) else None
    if mp and not c.get('reviewPrefsCustom') and mp.get('reviewPlan') in ('both', 'exercise_only', 'theory_only'):
        return mp['reviewPlan'], max(5, int(mp.get('theoryMin', 10))), max(5, int(mp.get('exerciseMin', 20)))
    return c.get('reviewPlan', 'both'), max(5, int(c.get('theoryReviewMin', 10))), max(5, int(c.get('exerciseReviewMin', 20)))
