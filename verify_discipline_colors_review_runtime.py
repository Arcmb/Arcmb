"""Verify review-table runtime assets and learner-scoped discipline colors."""
from pathlib import Path
import hashlib
import os
import secrets

import planner as P
from webapp import App
from verify_release import Client, require

ROOT=Path(__file__).resolve().parent


def main():
    planner=(ROOT/'planner.py').read_text(encoding='utf-8')
    webapp=(ROOT/'webapp.py').read_text(encoding='utf-8')
    html=(ROOT/'static'/'app.html').read_text(encoding='utf-8')
    js=(ROOT/'static'/'discipline_colors.js').read_text(encoding='utf-8')
    css=(ROOT/'static'/'style.css').read_text(encoding='utf-8')
    require('DISCIPLINE COLORS AND REVIEW RUNTIME V1' in planner,'Subject color validation patch is missing.')
    for asset in ('review_history.js','review_calendar_table.js','discipline_colors.js'):
        require(f"'{asset}':'application/javascript; charset=utf-8'" in webapp,f'{asset} is missing from the static allowlist.')
    require('/static/review_history.js?v=5.1.0' in html,'Review history cache key is missing.')
    require('/static/review_calendar_table.js?v=5.1.0' in html,'Review calendar cache key is missing.')
    require('/static/discipline_colors.js?v=5.1.0' in html,'Discipline colors asset is not loaded.')
    for marker in ('disciplinePastelPalette','discipline-color-swatch','applyDisciplineColors','Configurar cores'):
        require(marker in js,'Missing discipline-color UI marker: '+marker)
    require('DISCIPLINE COLORS AND REVIEW RUNTIME V1' in css,'Discipline color styles are missing.')

    profile=P.default_profile('Validação de cor')
    profile['subjects']=[dict(id='math',name='Matemática',kind='study',action='Estudar e praticar',weeklyMin=120,difficulty=5,importance=5,priority=1,priorityManual=False,examDate='',active=True,reviewPlan='both',theoryReviewMin=15,exerciseReviewMin=35,preferredReviewDay=-1,color='#c9dcf4')]
    P.validate(profile)
    require(profile['subjects'][0]['color']=='#c9dcf4','Valid pastel subject color was not preserved.')

    app=App();require(app.db.configured,'DATABASE_URL is required.')
    app.db.initialize(app.owner,app.env.get('MASTER_PASSWORD',''),app.env.get('MAYRA_INITIAL_PASSWORD',''))
    host=os.getenv('RENDER_EXTERNAL_HOSTNAME') or sorted(app.hosts)[0]
    login='cor_disciplina_'+secrets.token_hex(8);password=secrets.token_urlsafe(28);test_id=None
    try:
        with app.db.connection(write=True) as conn:
            test_id=app.db.create_user(conn,login,'Aluno Cor '+login[-6:],password,must_change=False)
        client=Client(app,host)
        for asset in ('review_history.js','review_calendar_table.js','discipline_colors.js'):
            require(client.request('/static/'+asset)['status']==200,asset+' did not return HTTP 200.')
        user=client.login(login,password)
        state=client.request('/api/state')['data']
        data=dict(name='Matemática',kind='study',action='Estudar e praticar',weeklyMin=120,difficulty=5,importance=5,priority=1,priorityManual=False,examDate='',active=True,reviewPlan='both',theoryReviewMin=15,exerciseReviewMin=35,preferredReviewDay=-1,color='#c9dcf4')
        payload=dict(user=user['id'],version=state['version'],op='subject',data=data)
        saved=client.request('/api/action',payload)
        require(saved['status']==200,'Subject color write failed.')
        subjects=saved['data']['profile']['subjects']
        row=next((x for x in subjects if x.get('name')=='Matemática'),None)
        require(row and row.get('color')=='#c9dcf4','Subject color was not persisted in the learner profile.')
        reread=client.request('/api/state')['data']['profile']['subjects']
        row=next((x for x in reread if x.get('name')=='Matemática'),None)
        require(row and row.get('color')=='#c9dcf4','Subject color was not retained after reread.')
    finally:
        if test_id:
            with app.db.connection(write=True) as conn:
                app.db.execute(conn,'DELETE FROM hmay_events WHERE actor_id=? OR target_id=?',(test_id,test_id))
                app.db.execute(conn,'DELETE FROM hmay_sessions WHERE user_id=?',(test_id,))
                app.db.execute(conn,'DELETE FROM hmay_state WHERE user_id=?',(test_id,))
                app.db.execute(conn,'DELETE FROM hmay_users WHERE id=?',(test_id,))
                key='user:'+hashlib.sha256(login.encode()).hexdigest()
                app.db.execute(conn,'DELETE FROM hmay_attempts WHERE key=?',(key,))
    print('MEUCRONOGRAMA_DISCIPLINE_COLORS_REVIEW_RUNTIME_CHECK_OK: review assets served, pastel colors rendered and learner color persisted.',flush=True)


if __name__=='__main__':main()
