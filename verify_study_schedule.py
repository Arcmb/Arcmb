"""Verify the structured study schedule release before serving traffic."""
from pathlib import Path
import datetime as dt
import unicodedata

import planner as P
import adaptive as A

ROOT=Path(__file__).resolve().parent


def require(value,message):
    if not value:raise RuntimeError(message)


def base_profile(name='Teste'):
    p=P.default_profile(name)
    p['settings'].update(sessionMin=20,sessionMax=50,breakMin=5,dailyMax=300,weeklyGoal=600,reservePct=0,intervals=[1,3,7,14],reviewMin=30)
    p['availability']=[dict(day=i,status='available',ranges=[dict(start='08:00',end='20:00')]) for i in range(7)]
    return p


def subject(name,priority):
    normalized=''.join(ch for ch in unicodedata.normalize('NFKD',name.lower()) if ch.isascii() and ch.isalnum())
    return dict(id='sub-'+normalized,name=name,kind='study',action='Estudar e praticar',weeklyMin=120,difficulty=3,importance=3,priority=priority,examDate='',active=True,reviewPlan='both',theoryReviewMin=10,exerciseReviewMin=20,preferredReviewDay=-1)


def content(identifier,subject_id,plan='both'):
    return dict(id=identifier,subjectId=subject_id,title='Conteúdo '+identifier,topic='Tópico',status='studied',studiedOn=P.add(P.today(),-7),studiedTime='09:00',studyMinutes=40,reviewMinutes=30,difficulty=3,nextDue=P.today(),stage=0,paused=False,material='',notes='',reviewPlan=plan,theoryReviewMin=10,exerciseReviewMin=20,preferredReviewDay=-1)


def main():
    js=(ROOT/'static'/'study_schedule.js').read_text(encoding='utf-8')
    html=(ROOT/'static'/'app.html').read_text(encoding='utf-8')
    planner=(ROOT/'planner.py').read_text(encoding='utf-8')
    adaptive=(ROOT/'adaptive.py').read_text(encoding='utf-8')
    css=(ROOT/'static'/'style.css').read_text(encoding='utf-8')
    require('/static/study_schedule.js?v=3.1.0' in html,'Structured schedule asset is not loaded.')
    require('review-plan-table' in js and 'study-review-settings' in js,'Collapsible adjustable review table is missing.')
    require('study-week-next' in js and "Programar quantas semanas?" in js,'Future-week controls are missing.')
    require('study-preset-new' in js and 'study-preset-apply' in js,'Preset management UI is missing.')
    require('PERFIS OPERACIONAIS DE ESTUDO V1' in adaptive and len(A._STUDY_BUILTIN_PRESETS)>=6,'Operational presets are missing.')
    require("weeks=max(1,min(4" in adaptive,'Multi-week preview backend is missing.')
    require('ESTUDO E REVISAO ESTRUTURADOS V1' in planner,'Planner release marker is missing.')
    require('STUDY SCHEDULE V1' in css,'Review table styles are missing.')

    start=P.week(P.today())
    current=dt.datetime.combine(P.date(start),dt.time(7,0),tzinfo=P.TZ)

    p=base_profile('Revisão separada')
    s=subject('História',1);p['subjects']=[s];p['contents']=[content('c-both',s['id'],'both')]
    P.validate(p);out=P.generate(p,start,current=current)
    sessions=[x for x in out['sessions'] if x.get('reviewContentId')=='c-both']
    require({x.get('reviewPart') for x in sessions}=={'theory','exercise'},'Theory and exercise were not scheduled separately.')
    theory=next(x for x in sessions if x['reviewPart']=='theory');exercise=next(x for x in sessions if x['reviewPart']=='exercise')
    require((exercise['date'],exercise['start'])>(theory['date'],theory['start']),'Exercise must be scheduled after theory.')
    require(theory.get('contentId','')=='' and exercise.get('contentId')=='c-both','Only the closing exercise block should advance the review cycle.')

    p=base_profile('Somente exercícios')
    s=subject('Matemática',1);p['subjects']=[s];p['contents']=[content('c-ex',s['id'],'exercise_only')]
    P.validate(p);out=P.generate(p,start,current=current)
    sessions=[x for x in out['sessions'] if x.get('reviewContentId')=='c-ex']
    require(len(sessions)==1 and sessions[0].get('reviewPart')=='exercise','Exercise-only review must create one exercise block.')
    require(sessions[0]['end']-sessions[0]['start']==30,'Theory time was not incorporated into the exercise-only block.')

    p=base_profile('Prioridade')
    p['settings']['weeklyGoal']=120;p['settings']['dailyMax']=120
    high=subject('Alta',1);low=subject('Baixa',5);p['subjects']=[high,low]
    P.validate(p);out=P.generate(p,start,current=current)
    totals={x['id']:sum(s['end']-s['start'] for s in out['sessions'] if s['subjectId']==x['id']) for x in (high,low)}
    require(totals[high['id']]>totals[low['id']],'Declared priority did not affect time distribution.')
    print('MEUCRONOGRAMA_STUDY_SCHEDULE_CHECK_OK: priority, split reviews, exercise-only dilution, future weeks and presets passed.',flush=True)


if __name__=='__main__':main()
