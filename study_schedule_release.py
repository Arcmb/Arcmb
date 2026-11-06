"""Add evidence-based review planning, explicit subject priority and editable presets.

The release preserves the existing deterministic planner and its hard constraints.
It adds explicit priority, separate theory/exercise review moments, multi-week
previews, collapsible review tables and manager-created operational presets.
"""
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parent
PLANNER_MARK = '# === MEU CRONOGRAMA: ESTUDO E REVISAO ESTRUTURADOS V1 ==='
ADAPTIVE_MARK = '# === MEU CRONOGRAMA: PERFIS OPERACIONAIS DE ESTUDO V1 ==='


def replace_once(text, old, new, label):
    if old not in text:
        raise RuntimeError(f'{label}: trecho esperado não encontrado.')
    return text.replace(old, new, 1)


def patch_planner():
    path = ROOT / 'planner.py'
    source = path.read_text(encoding='utf-8')
    if PLANNER_MARK in source:
        return

    source = replace_once(
        source,
        "settings=dict(sleepStart='23:00',sleepEnd='07:00',sessionMin=20,sessionMax=50,breakMin=10,dailyMax=150,weeklyGoal=600,reservePct=20,intervals=[1,7,30],sameDay=False,reviewMin=20,preferred='noite'),",
        "settings=dict(sleepStart='23:00',sleepEnd='07:00',sessionMin=20,sessionMax=50,breakMin=10,dailyMax=150,weeklyGoal=600,reservePct=20,intervals=[1,7,30],sameDay=False,reviewMin=20,preferred='noite',studyPresetId='',studyPresetName='',defaultReviewPlan='both',defaultTheoryMin=10,defaultExerciseMin=20),",
        'configurações padrão de estudo',
    )
    source = replace_once(
        source,
        "    s=p['settings'];a=minute(s['sleepStart']);b=minute(s['sleepEnd'])\n",
        "    p['settings']={**default_profile(p['name'])['settings'],**p.get('settings',{})}\n    s=p['settings'];a=minute(s['sleepStart']);b=minute(s['sleepEnd'])\n",
        'compatibilidade das configurações',
    )
    source = replace_once(
        source,
        "    for k,lo,hi in [('sessionMin',10,120),('sessionMax',s['sessionMin'],180),('breakMin',0,60),('dailyMax',10,720),('weeklyGoal',10,5040),('reservePct',0,80),('reviewMin',10,s['sessionMax'])]:numeric(s[k],lo,hi,k)\n",
        "    for k,lo,hi in [('sessionMin',10,120),('sessionMax',s['sessionMin'],180),('breakMin',0,60),('dailyMax',10,720),('weeklyGoal',10,5040),('reservePct',0,80),('reviewMin',10,s['sessionMax']),('defaultTheoryMin',5,180),('defaultExerciseMin',5,240)]:numeric(s[k],lo,hi,k)\n    if s.get('defaultReviewPlan') not in ('both','exercise_only','theory_only'):raise ValueError('Plano padrão de revisão inválido.')\n    if not isinstance(s.get('studyPresetId',''),str) or not isinstance(s.get('studyPresetName',''),str):raise ValueError('Perfil-base inválido.')\n",
        'validação das configurações de revisão',
    )
    source = replace_once(
        source,
        "    for x in p['subjects']:\n        if not isinstance(x['name'],str) or not 1<=len(x['name'])<=150 or x['kind'] not in ('study','personal') or type(x['active'])is not bool:raise ValueError('Disciplina inválida.')\n        for k,lo,hi in [('weeklyMin',0,3000),('difficulty',1,5),('importance',1,5)]:numeric(x[k],lo,hi,k)\n",
        "    for x in p['subjects']:\n        x.setdefault('priority',3);x.setdefault('reviewPlan',s.get('defaultReviewPlan','both'));x.setdefault('theoryReviewMin',s.get('defaultTheoryMin',10));x.setdefault('exerciseReviewMin',s.get('defaultExerciseMin',20));x.setdefault('preferredReviewDay',-1)\n        if not isinstance(x['name'],str) or not 1<=len(x['name'])<=150 or x['kind'] not in ('study','personal') or type(x['active'])is not bool:raise ValueError('Disciplina inválida.')\n        for k,lo,hi in [('weeklyMin',0,3000),('difficulty',1,5),('importance',1,5),('priority',1,5),('theoryReviewMin',5,180),('exerciseReviewMin',5,240)]:numeric(x[k],lo,hi,k)\n        if x.get('reviewPlan') not in ('both','exercise_only','theory_only') or type(x.get('preferredReviewDay')) is not int or not -1<=x['preferredReviewDay']<=6:raise ValueError('Configuração de revisão da disciplina inválida.')\n",
        'prioridade e revisão da disciplina',
    )
    source = replace_once(
        source,
        "    for x in p['contents']:\n        if x['subjectId']not in subjects or x['status']not in ('studied','planned') or not x['title'] or len(x['title'])>300:raise ValueError('Conteúdo inválido.')\n        date(x['studiedOn']);minute(x['studiedTime']);numeric(x['studyMinutes'],0,720,'Duração');numeric(x['reviewMinutes'],10,180,'Revisão');numeric(x['difficulty'],1,5,'Dificuldade')\n",
        "    subject_map={x['id']:x for x in p['subjects']}\n    for x in p['contents']:\n        parent=subject_map.get(x.get('subjectId'),{})\n        x.setdefault('reviewPlan',parent.get('reviewPlan',s.get('defaultReviewPlan','both')));x.setdefault('theoryReviewMin',parent.get('theoryReviewMin',s.get('defaultTheoryMin',10)));x.setdefault('exerciseReviewMin',parent.get('exerciseReviewMin',s.get('defaultExerciseMin',20)));x.setdefault('preferredReviewDay',parent.get('preferredReviewDay',-1))\n        if x['subjectId']not in subjects or x['status']not in ('studied','planned') or not x['title'] or len(x['title'])>300:raise ValueError('Conteúdo inválido.')\n        date(x['studiedOn']);minute(x['studiedTime']);numeric(x['studyMinutes'],0,720,'Duração');numeric(x['reviewMinutes'],10,420,'Revisão');numeric(x['difficulty'],1,5,'Dificuldade');numeric(x['theoryReviewMin'],5,180,'Revisão teórica');numeric(x['exerciseReviewMin'],5,240,'Exercícios')\n        if x.get('reviewPlan') not in ('both','exercise_only','theory_only') or type(x.get('preferredReviewDay')) is not int or not -1<=x['preferredReviewDay']<=6:raise ValueError('Configuração de revisão do conteúdo inválida.')\n",
        'revisão estruturada do conteúdo',
    )

    source = replace_once(
        source,
        "                if task.get('studiedOn')==d:a=max(a,minute(task['studiedTime'])+max(120,task['studyMinutes']))\n",
        "                if task.get('studiedOn')==d:a=max(a,minute(task['studiedTime'])+max(120,task['studyMinutes']))\n                if task.get('notBeforeDate')==d:a=max(a,int(task.get('notBeforeMin',a)))\n",
        'ordenação temporal das partes da revisão',
    )
    source = replace_once(
        source,
        "                    score+=max(-3,min(3,float(bonuses.get(slot_period,0))))\n",
        "                    score+=max(-3,min(3,float(bonuses.get(slot_period,0))))\n                    score+=(6-max(1,min(5,int(task.get('priority',3)))))*2.5\n                    preferred_day=task.get('preferredDay',-1)\n                    if preferred_day in range(7):score+=8 if date(d).weekday()==preferred_day else -1.5\n",
        'prioridade no encaixe',
    )
    source = replace_once(
        source,
        "        created.append(dict(id=uid(),date=d,start=t,end=t+duration,kind=task['kind'],subjectId=task['subjectId'],contentId=task.get('contentId',''),title=task['title'],status='planned',locked=False,reason=task['reason'],createdAt=now().isoformat()))\n        day_used[d]+=duration;used+=duration;slots[d]=subtract(slots[d],[[t-br,t+duration+br]]);return True\n",
        "        created.append(dict(id=uid(),date=d,start=t,end=t+duration,kind=task['kind'],subjectId=task['subjectId'],contentId=task.get('contentId',''),reviewContentId=task.get('reviewContentId',''),reviewPart=task.get('reviewPart',''),reviewCycleId=task.get('reviewCycleId',''),title=task['title'],status='planned',locked=False,reason=task['reason'],createdAt=now().isoformat()))\n        day_used[d]+=duration;used+=duration;slots[d]=subtract(slots[d],[[t-br,t+duration+br]]);return created[-1]\n",
        'metadados das sessões de revisão',
    )
    source = replace_once(
        source,
        "    due.sort(key=lambda x:((date(x['nextDue'])-date(td)).days,-x['difficulty']))\n    for c in due:\n        previous=next((x for x in p['sessions']if x.get('contentId')==c['id'] and x['kind']=='review' and x['status']=='planned'),None)\n        if previous:\n            if previous['date']<td:pending.append(dict(title=c['title'],reason='Revisão anterior sem registro. Verifique ou registre que não realizou antes de reagendar.',minutes=c['reviewMinutes']))\n            continue\n        task=dict(kind='review',subjectId=c['subjectId'],contentId=c['id'],title='Revisar: '+c['title'],earliest=c['nextDue'],due=c['nextDue'],studiedOn=c['studiedOn'],studiedTime=c['studiedTime'],studyMinutes=c['studyMinutes'],reason='Revisão periódica. Data-alvo: '+c['nextDue']+'.')\n        duration=min(c['reviewMinutes'],s['sessionMax'])\n        if not place(task,duration):pending.append(dict(title=c['title'],minutes=duration,reason='Sem encaixe após a data-alvo, preservando pausas, disponibilidade e limites.'))\n",
        "    subject_priority={x['id']:int(x.get('priority',3)) for x in subjects}\n    due.sort(key=lambda x:(subject_priority.get(x['subjectId'],3),(date(x['nextDue'])-date(td)).days,-x['difficulty']))\n    for c in due:\n        linked=lambda x:(x.get('contentId')==c['id'] or x.get('reviewContentId')==c['id']) and x['kind']=='review' and x['status']=='planned'\n        existing=[x for x in p['sessions'] if linked(x)]\n        if existing:\n            if any(x['date']<td for x in existing):pending.append(dict(title=c['title'],reason='Revisão anterior sem registro. Verifique ou registre que não realizou antes de reagendar.',minutes=c['reviewMinutes']))\n            continue\n        plan=c.get('reviewPlan','both');theory=max(5,int(c.get('theoryReviewMin',10)));exercise=max(5,int(c.get('exerciseReviewMin',20)));cycle=uid()\n        if plan=='exercise_only':parts=[('exercise',theory+exercise,'Exercícios: '+c['title'],True)]\n        elif plan=='theory_only':parts=[('theory',theory+exercise,'Revisão de teoria: '+c['title'],True)]\n        else:parts=[('theory',theory,'Revisão de teoria: '+c['title'],False),('exercise',exercise,'Exercícios: '+c['title'],True)]\n        previous_part=None\n        for part,duration,title,closes_cycle in parts:\n            task=dict(kind='review',subjectId=c['subjectId'],contentId=c['id'] if closes_cycle else '',reviewContentId=c['id'],reviewPart=part,reviewCycleId=cycle,title=title,earliest=c['nextDue'],due=c['nextDue'],studiedOn=c['studiedOn'],studiedTime=c['studiedTime'],studyMinutes=c['studyMinutes'],preferredDay=int(c.get('preferredReviewDay',-1)),priority=subject_priority.get(c['subjectId'],3),reason=('Prática de recuperação por exercícios. ' if part=='exercise' else 'Retomada orientada da teoria. ')+'Data-alvo: '+c['nextDue']+'.')\n            if previous_part:\n                task['earliest']=previous_part['date'];task['notBeforeDate']=previous_part['date'];task['notBeforeMin']=previous_part['end']+br\n            placed=place(task,min(duration,240))\n            if not placed:pending.append(dict(title=title,minutes=duration,reason='Sem encaixe após a data-alvo, preservando pausas, disponibilidade e limites.'))\n            else:previous_part=placed\n",
        'separação de teoria e exercícios',
    )
    source = replace_once(
        source,
        "        weights.append(max(1,sub['weeklyMin'])*(1+.10*(diff-3)+.06*(sub['importance']-3)+.15*urgency)*academic)\n",
        "        declared={1:1.65,2:1.35,3:1.0,4:.78,5:.60}.get(int(sub.get('priority',3)),1.0)\n        weights.append(max(1,sub['weeklyMin'])*(1+.10*(diff-3)+.06*(sub['importance']-3)+.15*urgency)*academic*declared)\n",
        'peso da prioridade declarada',
    )
    source = replace_once(
        source,
        "        options=sorted([x for x in targets if x['left']>=s['sessionMin']],key=lambda x:x['left']/(x['allocated']+20),reverse=True)\n",
        "        options=sorted([x for x in targets if x['left']>=s['sessionMin']],key=lambda x:(6-int(x['sub'].get('priority',3)),x['left']/(x['allocated']+20)),reverse=True)\n",
        'ordem de alocação por prioridade',
    )
    source = replace_once(
        source,
        "            task=dict(kind='action' if sub['kind']=='personal' else 'study',subjectId=sub['id'],contentId=planned['id']if planned else '',title='Estudar: '+planned['title']if planned else(sub.get('action')or'Estudar e praticar')+' · '+sub['name'],earliest=planned['studiedOn']if planned else td,reason='Distribuição por meta, dificuldade verificada, importância, prazo e resultados acadêmicos recentes quando há evidência suficiente. Não é previsão de nota.')\n",
        "            task=dict(kind='action' if sub['kind']=='personal' else 'study',subjectId=sub['id'],contentId=planned['id']if planned else '',title='Estudar: '+planned['title']if planned else(sub.get('action')or'Estudar e praticar')+' · '+sub['name'],earliest=planned['studiedOn']if planned else td,priority=int(sub.get('priority',3)),reason='Distribuição por prioridade declarada, meta, dificuldade verificada, importância, prazo e resultados acadêmicos recentes quando há evidência suficiente. Não é previsão de nota.')\n",
        'prioridade da tarefa de estudo',
    )
    source = replace_once(
        source,
        "    elif op=='review':\n        c=next(x for x in p['contents']if x['id']==data['id']);c['paused']=bool(data.get('paused',False));c['nextDue']=data.get('nextDue')or c['nextDue']\n",
        "    elif op=='review_preferences':\n        c=next(x for x in p['contents']if x['id']==data['id']);plan=str(data.get('reviewPlan','both'));theory=int(data.get('theoryReviewMin',10));exercise=int(data.get('exerciseReviewMin',20));preferred=int(data.get('preferredReviewDay',-1))\n        if plan not in ('both','exercise_only','theory_only') or not 5<=theory<=180 or not 5<=exercise<=240 or not -1<=preferred<=6:raise ValueError('Preferências de revisão inválidas.')\n        c.update(reviewPlan=plan,theoryReviewMin=theory,exerciseReviewMin=exercise,preferredReviewDay=preferred,reviewMinutes=theory+exercise,paused=bool(data.get('paused',False)),nextDue=data.get('nextDue')or c.get('nextDue'))\n        p['sessions']=[x for x in p['sessions']if not((x.get('contentId')==c['id']or x.get('reviewContentId')==c['id'])and x['kind']=='review'and x['status']=='planned'and not x.get('locked')and x['date']>=today())]\n        if p.get('planMeta'):p['planMeta']['dirty']=True\n    elif op=='review':\n        c=next(x for x in p['contents']if x['id']==data['id']);c['paused']=bool(data.get('paused',False));c['nextDue']=data.get('nextDue')or c['nextDue']\n",
        'edição estruturada da revisão',
    )
    source = source.rstrip() + '\n\n' + PLANNER_MARK + '\n'
    path.write_text(source, encoding='utf-8')


PRESET_EXTENSION = r'''

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
            if profile.get('planMeta'):profile['planMeta']['dirty']=True
            P.audit(profile,'perfil-base','Perfil-base aplicado: '+preset['name']+'. Horários existentes foram preservados até nova prévia.')
            P.validate(profile)
            app.db.execute(c,'UPDATE hmay_state SET profile=?,version=version+1,updated_at=? WHERE user_id=?',(json.dumps(profile,ensure_ascii=False,separators=(',',':')),P.now().isoformat(),target));app.event(c,user,target,'study_preset_apply')
            return app.reply(start,200,app.state(c,user,target))
        raise HTTPError(405,'Ação não permitida.')
    return _study_original_handle(app,c,user,path,method,data,query,start,HTTPError)
'''


def patch_adaptive():
    path = ROOT / 'adaptive.py'
    source = path.read_text(encoding='utf-8')
    if ADAPTIVE_MARK not in source:
        source = source.rstrip() + '\n' + PRESET_EXTENSION + '\n'

    old = """        w=P.week(data.get('week') or P.today())
        if w<P.week(P.today()) or w>P.add(P.week(P.today()),364):raise ValueError('Escolha uma semana atual ou nos próximos 12 meses.')
        weights,own,shared=bonuses(app,c,user,target,p)
        academic=academic_priority(app,c,target,p)
        new=P.generate(copy.deepcopy(p),w,mode=mode,bonuses=weights,subject_bonuses=academic.get('bonuses',{}));P.validate(new)
        if len(dumps(new).encode())>5_000_000:raise ValueError('Planejamento excede o limite de dados.')
        report=delta(p,new);report.update(mode=mode,week=w,own=own,collective=shared,academic=academic)
"""
    new = """        w=P.week(data.get('week') or P.today())
        try:weeks=max(1,min(4,int(data.get('weeks',1))))
        except (TypeError,ValueError):raise ValueError('Quantidade de semanas inválida.')
        last_week=P.add(w,7*(weeks-1))
        if w<P.week(P.today()) or last_week>P.add(P.week(P.today()),364):raise ValueError('Escolha uma semana atual ou nos próximos 12 meses.')
        weights,own,shared=bonuses(app,c,user,target,p)
        academic=academic_priority(app,c,target,p)
        new=copy.deepcopy(p)
        for index in range(weeks):new=P.generate(new,P.add(w,7*index),mode=mode,bonuses=weights,subject_bonuses=academic.get('bonuses',{}))
        P.validate(new)
        if len(dumps(new).encode())>5_000_000:raise ValueError('Planejamento excede o limite de dados.')
        report=delta(p,new);report.update(mode=mode,week=w,endWeek=last_week,weeks=weeks,own=own,collective=shared,academic=academic)
"""
    if old in source:
        source = source.replace(old, new, 1)
    source = source.replace(
        "sessions=[s for s in new['sessions'] if w<=s['date']<=P.add(w,6)],pending=new['pending'],notice='Prévia: nenhum horário foi substituído. Confirme para salvar. Blocos fixados e registros de execução são preservados.'",
        "sessions=[s for s in new['sessions'] if w<=s['date']<=P.add(last_week,6)],pending=new['pending'],notice=('Prévia de '+str(weeks)+' semana(s): nenhum horário foi substituído. Confirme para salvar. Blocos fixados e registros de execução são preservados.')",
        1,
    )
    path.write_text(source, encoding='utf-8')


STUDY_JS = r'''"use strict";
// Meu Cronograma: prioridade explícita, revisão teoria/exercícios e perfis operacionais.
let studyPresetCache=null,studyPresetRequest='';
const studyReviewPlans={both:'Teoria + exercícios separados',exercise_only:'Somente exercícios',theory_only:'Somente teoria'};
const studyDayOptions=[[-1,'Automático'],[0,'Segunda'],[1,'Terça'],[2,'Quarta'],[3,'Quinta'],[4,'Sexta'],[5,'Sábado'],[6,'Domingo']];
const studyPriorityOptions=[[1,'1 — Prioridade máxima'],[2,'2 — Alta'],[3,'3 — Regular'],[4,'4 — Baixa'],[5,'5 — Mínima']];
const studyReviewPlanOptions=[['both','Teoria + exercícios em momentos separados'],['exercise_only','Somente exercícios (o tempo teórico é incorporado)'],['theory_only','Somente teoria']];

function studyDiscipline(c){return c.sourceDiscipline||sub(c.subjectId)||'Sem disciplina cadastrada';}
function studyLinkedReviewSessions(c){return P.sessions.filter(s=>s.kind==='review'&&(s.contentId===c.id||s.reviewContentId===c.id)&&s.status==='planned').sort((a,b)=>a.date.localeCompare(b.date)||a.start-b.start);}
function studyPartLabel(s){return s.reviewPart==='theory'?'Teoria':s.reviewPart==='exercise'?'Exercícios':'Revisão';}
function studyReviewDuration(c){return Number(c.theoryReviewMin||10)+Number(c.exerciseReviewMin||20);}

subjectForm=function(id){
 const x=P.subjects.find(x=>x.id===id)||{name:'',kind:'study',action:'Estudar e praticar',weeklyMin:120,difficulty:3,importance:3,priority:3,examDate:'',active:true,reviewPlan:P.settings.defaultReviewPlan||'both',theoryReviewMin:P.settings.defaultTheoryMin||10,exerciseReviewMin:P.settings.defaultExerciseMin||20,preferredReviewDay:-1};
 modalForm(id?'Editar disciplina ou ação':'Nova disciplina ou ação',`<div class="form-grid">${input('Nome','name',x.name,'text','required maxlength="150"')}${select('Tipo','kind',x.kind,[['study','Disciplina / estudo'],['personal','Ação pessoal']])}${input('Ação exibida no quadro','action',x.action,'text','maxlength="300"')}${input('Meta semanal (min)','weeklyMin',x.weeklyMin,'number','min="0" max="3000" required')}${select('Prioridade declarada','priority',x.priority||3,studyPriorityOptions)}${select('Dificuldade percebida','difficulty',x.difficulty,[1,2,3,4,5].map(n=>[n,n+' / 5']))}${select('Importância','importance',x.importance,[1,2,3,4,5].map(n=>[n,n+' / 5']))}${input('Data de avaliação ou prazo','examDate',x.examDate,'date')}${select('Plano padrão de revisão','reviewPlan',x.reviewPlan||'both',studyReviewPlanOptions)}${input('Tempo de teoria (min)','theoryReviewMin',x.theoryReviewMin||10,'number','min="5" max="180" required')}${input('Tempo de exercícios (min)','exerciseReviewMin',x.exerciseReviewMin||20,'number','min="5" max="240" required')}${select('Dia preferencial para revisar','preferredReviewDay',x.preferredReviewDay??-1,studyDayOptions)}${check('Meta ativa','active',x.active)}</div><div class="notice"><strong>Prioridade declarada</strong><p>Define a ordem inicial de distribuição. Desempenho, prazos, revisões vencidas e capacidade semanal continuam sendo considerados, sem ultrapassar os limites da rotina.</p></div>`,async(f,d)=>{await save('subject',{...d,...(id?{id}:{}),weeklyMin:+d.weeklyMin,priority:+d.priority,difficulty:+d.difficulty,importance:+d.importance,theoryReviewMin:+d.theoryReviewMin,exerciseReviewMin:+d.exerciseReviewMin,preferredReviewDay:+d.preferredReviewDay,active:f.elements.active.checked});});
};

subjectsView=function(){
 const ordered=P.subjects.slice().sort((a,b)=>(a.priority||3)-(b.priority||3)||a.name.localeCompare(b.name));
 return head('Disciplinas e metas','A prioridade declarada define a ordem inicial; dificuldade, prazo e desempenho refinam a distribuição.',button('Adicionar','new-subject','primary'))+`<div class="card">${items(ordered.map(x=>`<div class="item"><div class="item-main"><strong>${esc(x.name)} ${tag(x.active?'Ativa':'Pausada',x.active?'done':'')} ${tag('Prioridade '+(x.priority||3),(x.priority||3)<=2?'warning':'')}</strong><p>${minutes(x.weeklyMin)} por semana · dificuldade ${x.difficulty}/5 · importância ${x.importance}/5</p><small>${esc(x.action)}${x.examDate?' · Prazo: '+br(x.examDate):''} · revisão: ${esc(studyReviewPlans[x.reviewPlan||'both'])}</small></div><div class="item-actions">${button('Editar','edit-subject','secondary',`data-id="${x.id}"`)}${button('Excluir','delete','danger-button',`data-collection="subjects" data-id="${x.id}"`)}</div></div>`))}</div><div class="notice"><strong>Como o motor ordena</strong><p>1) prioridade indicada; 2) revisão vencida ou próxima; 3) prazo; 4) desempenho e erros recorrentes; 5) dificuldade e importância; 6) encaixe real na disponibilidade.</p></div>`;
};

contentForm=function(){
 if(!P.subjects.length){toast('Cadastre primeiro uma disciplina.');view='subjects';render();return;}
 const first=P.subjects.find(x=>x.active)||P.subjects[0];
 modalForm('Registrar conteúdo',`<div class="form-grid">${select('Disciplina','subjectId',first.id,P.subjects.filter(x=>x.active).map(x=>[x.id,x.name]))}${input('Conteúdo','title','','text','required maxlength="300"')}${input('Tópico geral','topic','','text','maxlength="300"')}${select('Situação','status','studied',[['studied','Já estudei'],['planned','Pretendo estudar']])}${input('Data','studiedOn',S.serverDate,'date','required')}${input('Horário de início','studiedTime','09:00','time','required')}${input('Tempo de estudo (min)','studyMinutes',40,'number','min="0" max="720" required')}${select('Plano de revisão','reviewPlan',first.reviewPlan||P.settings.defaultReviewPlan||'both',studyReviewPlanOptions)}${input('Teoria (min)','theoryReviewMin',first.theoryReviewMin||P.settings.defaultTheoryMin||10,'number','min="5" max="180" required')}${input('Exercícios (min)','exerciseReviewMin',first.exerciseReviewMin||P.settings.defaultExerciseMin||20,'number','min="5" max="240" required')}${select('Dia preferencial','preferredReviewDay',first.preferredReviewDay??-1,studyDayOptions)}${select('Dificuldade percebida','difficulty',3,[1,2,3,4,5].map(n=>[n,n+' / 5']))}${input('Material, páginas ou referência','material','','text','maxlength="5000"')}${area('Observações','notes','')}</div><p class="micro">Quando “somente exercícios” for escolhido, o tempo reservado à teoria será incorporado ao bloco de exercícios, preservando a carga prevista.</p>`,async(f,d)=>save('content',{...d,studyMinutes:+d.studyMinutes,reviewMinutes:+d.theoryReviewMin+ +d.exerciseReviewMin,theoryReviewMin:+d.theoryReviewMin,exerciseReviewMin:+d.exerciseReviewMin,preferredReviewDay:+d.preferredReviewDay,difficulty:+d.difficulty}));
};

function studyReviewPreferences(id){
 const c=P.contents.find(x=>x.id===id);if(!c)return;
 modalForm('Ajustar programação da revisão',`<p><strong>${esc(studyDiscipline(c))}</strong> · ${esc(c.title)}</p><div class="form-grid">${input('Data-alvo','nextDue',c.nextDue||S.serverDate,'date','required')}${select('Dia preferencial','preferredReviewDay',c.preferredReviewDay??-1,studyDayOptions)}${select('Como revisar','reviewPlan',c.reviewPlan||'both',studyReviewPlanOptions)}${input('Revisão de teoria (min)','theoryReviewMin',c.theoryReviewMin||10,'number','min="5" max="180" required')}${input('Exercícios (min)','exerciseReviewMin',c.exerciseReviewMin||20,'number','min="5" max="240" required')}${check('Pausar esta revisão','paused',!!c.paused)}</div><div class="notice"><p>Ao salvar, blocos futuros não fixados desse conteúdo serão retirados. Gere novamente a semana para aplicar a nova divisão.</p></div>`,async(f,d)=>save('review_preferences',{id:c.id,nextDue:d.nextDue,preferredReviewDay:+d.preferredReviewDay,reviewPlan:d.reviewPlan,theoryReviewMin:+d.theoryReviewMin,exerciseReviewMin:+d.exerciseReviewMin,paused:f.elements.paused.checked}));
}
acts['study-review-settings']=el=>studyReviewPreferences(el.dataset.id);

function studyReviewRow(c,s,index){
 const date=s?.date||c.nextDue||'';const duration=s?s.end-s.start:studyReviewDuration(c);const plan=c.reviewPlan||'both';
 const action=s?studyPartLabel(s):(plan==='both'?'Teoria + exercícios':plan==='exercise_only'?'Exercícios':'Teoria');
 return `<tr><td>${esc(studyDiscipline(c))}</td><td><strong>${esc(c.title)}</strong>${c.topic?'<br><small>'+esc(c.topic)+'</small>':''}${c.sourceType==='exam_error'?'<br>'+tag((c.errorCount||0)+' erro(s)','warning'):''}</td><td>${date?br(date):'—'}${date?'<br><small>'+esc(days[new Date(date+'T12:00:00').getDay()===0?6:new Date(date+'T12:00:00').getDay()-1])+'</small>':''}</td><td>${s?hm(s.start)+'–'+hm(s.end):'Aguardando geração'}</td><td>${esc(action)}</td><td>${minutes(duration)}</td><td>${c.paused?tag('Pausada','warning'):s?tag('Programada','review'):tag('Data-alvo definida')}</td><td><div class="item-actions">${button('Configurar','study-review-settings','secondary',`data-id="${c.id}"`)}${s?button('Ajustar horário','edit-session','secondary',`data-id="${s.id}"`):''}${button('Registrar','feedback-content','primary',`data-id="${c.id}"`)}</div></td></tr>`;
}

reviewsView=function(){
 const contents=P.contents.filter(c=>c.status==='studied').sort((a,b)=>studyDiscipline(a).localeCompare(studyDiscipline(b))||(a.nextDue||'').localeCompare(b.nextDue||''));
 const groups={};contents.forEach(c=>(groups[studyDiscipline(c)]||(groups[studyDiscipline(c)]=[])).push(c));
 const sections=Object.keys(groups).sort().map(name=>{
  const rows=[];groups[name].forEach(c=>{const sessions=studyLinkedReviewSessions(c);if(sessions.length)sessions.forEach((s,i)=>rows.push(studyReviewRow(c,s,i)));else rows.push(studyReviewRow(c,null,0));});
  const total=groups[name].reduce((n,c)=>n+studyReviewDuration(c),0);
  return `<details class="review-discipline"><summary><span><strong>${esc(name)}</strong><small>${groups[name].length} conteúdo(s) · ${minutes(total)} previstos</small></span><span>Mostrar programação</span></summary><div class="table-wrap"><table class="review-plan-table"><thead><tr><th>Disciplina</th><th>Assunto / conteúdo</th><th>Data / dia</th><th>Horário</th><th>Ação</th><th>Tempo</th><th>Situação</th><th>Ajustes</th></tr></thead><tbody>${rows.join('')}</tbody></table></div></details>`;
 }).join('');
 return head('Minhas revisões','Programação por disciplina, com teoria e exercícios em momentos separados e tempos ajustáveis.')+`<div class="notice"><strong>Revisão ativa</strong><p>Recupere o conteúdo sem consulta, confira e corrija. O intervalo seguinte será ajustado pelo resultado registrado, não apenas pela passagem do tempo.</p></div><div class="actions">${button('Atualizar erros dos simulados','review-errors-refresh','secondary')}${button('Abrir quadro semanal','go-calendar','primary')}</div>${sections||'<section class="card">Nenhum conteúdo de revisão encontrado.</section>'}`;
};

const studyBaseCalendarView=calendarView;
calendarView=function(){
 let html=studyBaseCalendarView();
 const nav=`<div class="study-week-nav">${button('← Semana anterior','study-week-prev','secondary')}${button('Semana atual','study-week-current','secondary')}${button('Próxima semana →','study-week-next','secondary')}<span>Você pode navegar e gerar a programação das próximas semanas.</span></div>`;
 return html.replace('<div class="card"><div class="actions">','<div class="card">'+nav+'<div class="actions">');
};
acts['study-week-prev']=async()=>{week=add(week,-7);await loadCalendar();render();window.scrollTo(0,0);};
acts['study-week-current']=async()=>{week=weekOf(S.serverDate);await loadCalendar();render();window.scrollTo(0,0);};
acts['study-week-next']=async()=>{week=add(week,7);await loadCalendar();render();window.scrollTo(0,0);};

acts['generate']=()=>{
 if(!safeLeave())return;planPreview=null;
 modal('Prévia do cronograma',`<form id="objective-preview-form"><p>O sistema usa somente a disponibilidade cadastrada. Sono, compromissos, pausas, reservas e limites continuam obrigatórios.</p>${input('Semana inicial','week',week||S.serverDate,'date','required')}${select('Programar quantas semanas?','weeks','1',[['1','1 semana'],['2','2 semanas'],['3','3 semanas'],['4','4 semanas']])}${select('Como organizar?','mode','fill',[['fill','Completar espaços livres sem retirar os períodos existentes'],['reorganize','Reorganizar períodos futuros não fixados']])}<p>Prioridades declaradas, revisões vencidas, prazos e resultados acadêmicos entram no cálculo. Nada é salvo antes da confirmação.</p><button class="primary" type="submit">Gerar prévia</button><p id="objective-error" class="form-error" role="alert"></p></form>`,null);
};

acts['edit-session']=el=>{
 const s=P.sessions.find(x=>x.id===el.dataset.id);if(!s)return;
 modalForm('Ajustar horário',`<p>${esc(s.title)}</p><div class="form-grid">${input('Data','date',s.date,'date','required')}${input('Início','start',hm(s.start),'time','required')}${input('Duração (min)','duration',s.end-s.start,'number','min="5" max="240" required')}${check('Fixar este período no recálculo','locked',!!s.locked)}${select('Motivo do ajuste','reason','not_informed',typeof objectiveReasons!=='undefined'?objectiveReasons:[['not_informed','Não informado']])}</div><p class="micro">O término será calculado pelo início + duração. Ao alterar um bloco, os demais horários não são movidos automaticamente.</p>`,async(f,d)=>{const [h,m]=d.start.split(':').map(Number),start=h*60+m,duration=+d.duration,end=start+duration;if(end>1440)throw new Error('O bloco não pode ultrapassar meia-noite.');await save('session',{id:s.id,date:d.date,start:d.start,end:hm(end),locked:f.elements.locked.checked,reason:d.reason});});
};

async function studyLoadPresets(){
 const key=target+':'+S.version;if(studyPresetRequest===key)return;if(studyPresetCache?.key===key)return;
 studyPresetRequest=key;
 try{const data=await api('/api/adaptive/presets?user='+encodeURIComponent(target));if(target+':'+S.version!==key)return;studyPresetCache={key,data};if(view==='routine')render();}catch(e){console.error(e);}finally{studyPresetRequest='';}
}
function studyPresetPanel(){
 const d=studyPresetCache?.key===target+':'+S.version?studyPresetCache.data:null;
 if(!d){queueMicrotask(studyLoadPresets);return '<section class="card"><h2>Perfil-base de organização</h2><p>Carregando perfis…</p></section>';}
 const current=d.current?.name||P.settings.studyPresetName||'Configuração individual';
 const options=(d.presets||[]).map(x=>`<option value="${esc(x.id)}">${esc(x.name)}${x.custom?' · personalizado':''}</option>`).join('');
 const descriptions=(d.presets||[]).map(x=>`<div class="item"><div><strong>${esc(x.name)}</strong><p>${esc(x.description)}</p><small>Blocos ${x.config.sessionMin}–${x.config.sessionMax} min · reserva ${x.config.reservePct}% · ${esc(studyReviewPlans[x.config.defaultReviewPlan])}</small></div></div>`).join('');
 return `<section class="card"><div class="page-head"><div><p class="eyebrow">CONFIGURAÇÃO OPERACIONAL</p><h2>Perfil-base de organização</h2><p>Atual: <strong>${esc(current)}</strong>. É apenas um ponto de partida; o aluno pode alterar horários, tempos e prioridades.</p></div>${d.canManage?button('Criar perfil-base','study-preset-new','primary'):''}</div>${d.canManage?`<div class="form-grid"><label>Aplicar ao aluno<select id="study-preset-select">${options}</select></label><label class="check"><input id="study-preset-existing" type="checkbox" checked> Aplicar também aos conteúdos já cadastrados</label></div><div class="actions">${button('Aplicar perfil selecionado','study-preset-apply','primary')}</div>`:'<div class="notice">O Master ou a coordenação define o perfil-base. Todas as configurações continuam editáveis nesta conta.</div>'}<details><summary>Ver perfis disponíveis</summary>${descriptions}</details></section>`;
}
const studyBaseRoutineView=routineView;
routineView=function(){return studyBaseRoutineView()+studyPresetPanel();};

acts['study-preset-apply']=async()=>{
 const presetId=document.querySelector('#study-preset-select')?.value;if(!presetId)throw new Error('Selecione um perfil-base.');
 const applyExisting=!!document.querySelector('#study-preset-existing')?.checked;
 if(!confirm('Aplicar este perfil-base? Os horários atuais serão preservados até uma nova prévia.'))return;
 const result=await api('/api/adaptive/preset-apply',{user:target,version:S.version,presetId,applyExisting});S=result;P=result.profile;CSRF=result.csrf;studyPresetCache=null;mappingCache=null;await loadCalendar();render();toast('Perfil-base aplicado. Confira prioridades e gere uma nova prévia.');
};
acts['study-preset-new']=()=>{
 modalForm('Criar perfil-base',`<div class="form-grid">${input('Nome','name','','text','required maxlength="100"')}${input('Descrição','description','','text','maxlength="500"')}${input('Bloco mínimo (min)','sessionMin',20,'number','min="10" max="120" required')}${input('Bloco máximo (min)','sessionMax',40,'number','min="10" max="180" required')}${input('Pausa (min)','breakMin',10,'number','min="0" max="60" required')}${input('Limite diário (min)','dailyMax',120,'number','min="10" max="720" required')}${input('Meta semanal (min)','weeklyGoal',480,'number','min="10" max="5040" required')}${input('Reserva para imprevistos (%)','reservePct',25,'number','min="0" max="80" required')}${input('Intervalos de revisão (dias)','intervals','1, 3, 7, 14, 30','text','required')}${select('Plano padrão de revisão','defaultReviewPlan','both',studyReviewPlanOptions)}${input('Teoria padrão (min)','defaultTheoryMin',10,'number','min="5" max="180" required')}${input('Exercícios padrão (min)','defaultExerciseMin',20,'number','min="5" max="240" required')}</div>`,async(f,d)=>{await api('/api/adaptive/preset-save',{user:target,name:d.name,description:d.description,config:{sessionMin:+d.sessionMin,sessionMax:+d.sessionMax,breakMin:+d.breakMin,dailyMax:+d.dailyMax,weeklyGoal:+d.weeklyGoal,reservePct:+d.reservePct,intervals:d.intervals,reviewMin:+d.defaultTheoryMin+ +d.defaultExerciseMin,defaultReviewPlan:d.defaultReviewPlan,defaultTheoryMin:+d.defaultTheoryMin,defaultExerciseMin:+d.defaultExerciseMin}});studyPresetCache=null;closeModal(true);render();toast('Perfil-base criado.');});
};
'''


def patch_frontend():
    static = ROOT / 'static'
    (static / 'study_schedule.js').write_text(STUDY_JS, encoding='utf-8')
    html_path = static / 'app.html'
    html = html_path.read_text(encoding='utf-8')
    if '/static/study_schedule.js' not in html:
        html = html.replace('</body>', '<script src="/static/study_schedule.js?v=3.1.0" defer></script>\n</body>', 1)
    html_path.write_text(html, encoding='utf-8')

    adaptive_path = static / 'adaptive.js'
    adaptive = adaptive_path.read_text(encoding='utf-8')
    adaptive = adaptive.replace(
        "api('/api/adaptive/preview',{user:target,version,mode:data.mode,week:data.week})",
        "api('/api/adaptive/preview',{user:target,version,mode:data.mode,week:data.week,weeks:+data.weeks||1})",
        1,
    )
    adaptive_path.write_text(adaptive, encoding='utf-8')

    webapp_path = ROOT / 'webapp.py'
    webapp = webapp_path.read_text(encoding='utf-8')
    if "'study_schedule.js':'application/javascript; charset=utf-8'" not in webapp:
        anchor = "'tri_scores.js':'application/javascript; charset=utf-8'"
        if anchor not in webapp:
            raise RuntimeError('Mapa de arquivos estáticos não encontrado.')
        webapp = webapp.replace(anchor, anchor+",'study_schedule.js':'application/javascript; charset=utf-8'", 1)
    webapp_path.write_text(webapp, encoding='utf-8')

    css_path = static / 'style.css'
    css = css_path.read_text(encoding='utf-8')
    if 'STUDY SCHEDULE V1' not in css:
        css += r'''

/* STUDY SCHEDULE V1 */
.review-discipline{background:#fff;border:1px solid var(--line);border-radius:16px;margin:14px 0;overflow:hidden}
.review-discipline summary{cursor:pointer;display:flex;align-items:center;justify-content:space-between;gap:18px;padding:18px 22px;background:#fff7f8;color:var(--ink)}
.review-discipline summary span:first-child{display:grid;gap:3px}.review-discipline summary small{color:var(--muted);font-weight:500}
.review-discipline[open] summary{border-bottom:1px solid var(--line);background:#fbecee}
.review-plan-table{min-width:1050px}.review-plan-table td{vertical-align:middle}.review-plan-table .item-actions{min-width:250px}
.study-week-nav{display:flex;align-items:center;gap:8px;flex-wrap:wrap;margin-bottom:14px;padding-bottom:14px;border-bottom:1px solid var(--line)}
.study-week-nav span{font-size:12px;color:var(--muted);margin-left:auto}
@media(max-width:760px){.review-discipline summary{align-items:flex-start}.study-week-nav span{width:100%;margin-left:0}.review-plan-table{min-width:900px}}
'''
    css_path.write_text(css, encoding='utf-8')


def main():
    patch_planner()
    patch_adaptive()
    patch_frontend()
    compile((ROOT/'planner.py').read_text(encoding='utf-8'),'planner.py','exec')
    compile((ROOT/'adaptive.py').read_text(encoding='utf-8'),'adaptive.py','exec')
    print('MEUCRONOGRAMA_STUDY_SCHEDULE_READY: priority, split reviews, multi-week planning and editable presets prepared.',flush=True)


if __name__ == '__main__':
    main()
