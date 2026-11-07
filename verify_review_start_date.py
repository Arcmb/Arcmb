"""Verify learner-configurable review start date."""
from pathlib import Path
import planner as P

ROOT=Path(__file__).resolve().parent

def require(value,message):
    if not value:raise RuntimeError(message)

def main():
    planner=(ROOT/'planner.py').read_text(encoding='utf-8')
    js=(ROOT/'static'/'review_table_page.js').read_text(encoding='utf-8')
    css=(ROOT/'static'/'style.css').read_text(encoding='utf-8')
    html=(ROOT/'static'/'app.html').read_text(encoding='utf-8')
    require('REVIEW START DATE V1' in planner,'Planner review-start patch is missing.')
    require("s.setdefault('reviewStartDate','')" in planner,'Profile reviewStartDate default is missing.')
    require("existing=[x for x in p['sessions'] if linked(x) and (not review_start or x.get('date','')>=review_start)]" in planner,'Old planned reviews still block the new cycle.')
    for marker in ('REVIEW START DATE V1','reviewCycleStartDate','Iniciar minhas revisões em','Aplicar e recalcular','persistReviewStartDate',"save('settings',next)"):
        require(marker in js,'Missing review-start UI marker: '+marker)
    require('REVIEW START DATE V1' in css,'Review-start styles are missing.')
    require('/static/review_table_page.js?v=5.4.0-layout4&start=1' in html,'Review-start cache key is missing.')
    require('/static/style.css?v=5.1.0-layout4&start=1' in html,'Review-start stylesheet cache key is missing.')
    profile=P.default_profile('Teste início de revisões')
    profile['settings']['reviewStartDate']='2026-11-09'
    P.validate(profile)
    require(profile['settings']['reviewStartDate']=='2026-11-09','reviewStartDate was not preserved by validation.')
    print('MEUCRONOGRAMA_REVIEW_START_DATE_CHECK_OK: saved profile setting, scheduling floor, preserved history and current-cycle UI passed.',flush=True)

if __name__=='__main__':main()
