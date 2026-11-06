"""Verify automatic/manual discipline priorities and the learner-guidance UI."""
from pathlib import Path
import planner as P

ROOT=Path(__file__).resolve().parent

def require(condition,message):
    if not condition:raise RuntimeError(message)

def subject(identifier,name,difficulty,importance,manual=False,priority=3):
    return dict(id=identifier,name=name,kind='study',action='Estudar e praticar',weeklyMin=120,difficulty=difficulty,importance=importance,priority=priority,priorityManual=manual,examDate='',active=True,reviewPlan='both',theoryReviewMin=10,exerciseReviewMin=20,preferredReviewDay=-1)

def main():
    profile=P.default_profile('Aluno teste')
    profile['subjects']=[
        subject('s-low','Baixa demanda',1,2),
        subject('s-high','Alta demanda',5,5),
        subject('s-manual','Escolha manual',5,5,True,4),
    ]
    P.validate(profile)
    values={x['id']:x['priority'] for x in profile['subjects']}
    require(values['s-low']==4,'Difficulty 1 and importance 2 should derive low priority 4.')
    require(values['s-high']==1,'Difficulty 5 and importance 5 should derive maximum priority 1.')
    require(values['s-manual']==4,'Manual priority must be preserved.')
    js=(ROOT/'static'/'student_guidance.js').read_text(encoding='utf-8')
    for text in ['Descobrir perfil indicado','Maior importância','Maior dificuldade','Ordem alfabética','Disciplina: ']:
        require(text in js,'Missing learner-guidance UI marker: '+text)
    calendar=(ROOT/'static'/'review_calendar_table.js').read_text(encoding='utf-8')
    require('CALENDÁRIO DE REVISÕES' in calendar,'Monthly review calendar title is missing.')
    require('Disciplina' in calendar and 'Assunto' in calendar,'Monthly review calendar columns are missing.')
    html=(ROOT/'static'/'app.html').read_text(encoding='utf-8')
    require('/static/student_guidance.js?v=3.4.0' in html,'Learner-guidance asset is not loaded.')
    require('/static/review_calendar_table.js' in html,'Monthly review calendar asset is not loaded.')
    print('MEUCRONOGRAMA_STUDENT_GUIDANCE_CHECK_OK: priorities, sorting, questionnaire, review table and discipline labels passed.',flush=True)

if __name__=='__main__':main()
