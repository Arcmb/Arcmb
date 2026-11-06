"""Verify final priority, review-table and Qi-branding corrections."""
from pathlib import Path
import planner as P

ROOT=Path(__file__).resolve().parent

def require(value,message):
    if not value:raise RuntimeError(message)

def subject(identifier,name,difficulty,importance):
    return dict(id=identifier,name=name,kind='study',action='Estudar e praticar',weeklyMin=120,difficulty=difficulty,importance=importance,priority=3,priorityManual=False,examDate='',active=True,reviewPlan='both',theoryReviewMin=10,exerciseReviewMin=20,preferredReviewDay=-1)

def main():
    profile=P.default_profile('Teste final')
    profile['subjects']=[subject('english','Inglês',1,1),subject('math','Matemática',5,5)]
    P.validate(profile)
    values={row['id']:row['priority'] for row in profile['subjects']}
    require(values['english']==5,'English difficulty 1 / importance 1 must become priority 5.')
    require(values['math']==1,'Mathematics difficulty 5 / importance 5 must become priority 1.')
    js=(ROOT/'static'/'student_guidance.js').read_text(encoding='utf-8')
    for marker in ['FINAL PRIORITY REVIEW BRANDING V1','Calendário mensal de revisões','Visão global e histórico das revisões','qiEffectivePriority','qi-review-overview','Exemplo:']:
        require(marker in js,'Missing final UI marker: '+marker)
    css=(ROOT/'static'/'style.css').read_text(encoding='utf-8')
    require('FINAL PRIORITY REVIEW BRANDING V1' in css,'Final Qi palette is missing.')
    require('html,body{background:#fff!important' in css,'White site background is missing.')
    require('.qi-review-matrix' in css,'Review matrix styling is missing.')
    logo=(ROOT/'static'/'qi-logo.svg').read_text(encoding='utf-8')
    require('<circle cx="256" cy="256" r="244" fill="#d61f3c"' in logo,'Qi red circle is missing.')
    require('stroke="#fff"' in logo and 'fill="#fff"' in logo,'White Qi symbol is missing.')
    html=(ROOT/'static'/'app.html').read_text(encoding='utf-8')
    require('/static/student_guidance.js?v=4.0.0' in html,'Final guidance cache key is missing.')
    require('/static/style.css?v=4.0.0' in html,'Final stylesheet cache key is missing.')
    print('MEUCRONOGRAMA_FINAL_PRIORITY_REVIEW_BRANDING_CHECK_OK: differentiated priorities, visible monthly/global review tables, Qi logo, pastel palette and white background passed.',flush=True)

if __name__=='__main__':main()
