"""Verify that imported exam errors become schedulable spaced-review contents."""
from pathlib import Path
import hashlib, json, secrets

from webapp import App
import model_data as M
import planner as P

ROOT=Path(__file__).resolve().parent

def require(cond,msg):
    if not cond: raise RuntimeError(msg)

def main():
    app=App()
    require(app.db.configured,'DATABASE_URL is required.')
    app.db.initialize(app.owner,app.env.get('MASTER_PASSWORD',''),app.env.get('MAYRA_INITIAL_PASSWORD',''))
    token=secrets.token_hex(8)
    student_id=exam_id=perf_id=None
    login='exam_review_'+token
    try:
        with app.db.connection(write=True) as c:
            owner=app.db.execute(c,'SELECT id,username,name,role,active FROM hmay_users WHERE username=?',(app.owner,)).fetchone()
            require(owner,'Master account is required.')
            student_id=app.db.create_user(c,login,'Aluno Revisão '+token,secrets.token_urlsafe(24),role='aluno',must_change=False)
            state=app.db.execute(c,'SELECT profile FROM hmay_state WHERE user_id=?',(student_id,)).fetchone()
            profile=json.loads(state['profile'])
            profile['subjects']=[{'id':'sub-hist','name':'História','kind':'study','action':'Estudar','weeklyMin':120,'difficulty':3,'importance':3,'examDate':'','active':True}]
            app.db.execute(c,'UPDATE hmay_state SET profile=?,version=version+1,updated_at=? WHERE user_id=?',(json.dumps(profile,ensure_ascii=False),P.now().isoformat(),student_id))
            exam_id='exam_review_exam_'+token
            perf_id='exam_review_perf_'+token
            items=[
                {'number':1,'area':'CH','discipline':'História','topic':'Brasil República','subject':'Era Vargas','skill':'H11','language':'','answer':'A'},
                {'number':2,'area':'CH','discipline':'História','topic':'Brasil República','subject':'Era Vargas','skill':'H12','language':'','answer':'B'},
                {'number':3,'area':'CH','discipline':'Geografia','topic':'Urbanização','subject':'Rede urbana','skill':'H06','language':'','answer':'C'},
            ]
            now=P.now().isoformat()
            app.db.execute(c,'INSERT INTO hmay_exams(id,identity_key,owner_id,title,applied_on,color,area,items,version,updated_at) VALUES (?,?,?,?,?,?,?,?,?,?)',
                           (exam_id,'exam_review_identity_'+token,owner['id'],'Simulado Revisão','2026-10-25','AZUL','',json.dumps(items,ensure_ascii=False),1,now))
            metrics={
                'questao:001':{'name':'Questão 01','correct':0,'total':1,'response':'D'},
                'questao:002':{'name':'Questão 02','correct':0,'total':1,'response':'A'},
                'questao:003':{'name':'Questão 03','correct':0,'total':1,'response':'D'},
            }
            metadata={'COR DA PROVA':'AZUL','L.E':'','TURMA':'TESTE','_exam_id':exam_id,'_exam_version':1}
            app.db.execute(c,'INSERT INTO hmay_performance(id,user_id,activity_key,activity,applied_on,metrics,metadata,version,updated_at) VALUES (?,?,?,?,?,?,?,?,?)',
                           (perf_id,student_id,'exam_review_activity_'+token,'Simulado Revisão','2026-10-25',json.dumps(metrics),json.dumps(metadata),1,now))
            result=M._er_sync_target(app,c,dict(owner),student_id)
            require(result['created']==2 and result['errors']==3,'Three errors in two contents must create two grouped reviews.')
            require(result.get('subjectsCreated')==1,'A missing discipline must create one schedulable subject.')
            state=app.db.execute(c,'SELECT profile FROM hmay_state WHERE user_id=?',(student_id,)).fetchone()
            profile=json.loads(state['profile'])
            imported=[x for x in profile['contents'] if x.get('sourceType')=='exam_error']
            require(len(imported)==2,'Two imported review contents were expected.')
            history=next(x for x in imported if x.get('sourceDiscipline')=='História')
            geography=next(x for x in imported if x.get('sourceDiscipline')=='Geografia')
            require(history.get('title')=='Era Vargas' and history.get('subjectId')=='sub-hist','Existing discipline linkage was not preserved.')
            require(history.get('errorCount')==2 and len(history.get('examErrors',[]))==2,'Grouped History errors were not preserved.')
            auto_subject=next((x for x in profile['subjects'] if x.get('name')=='Geografia'),None)
            require(auto_subject and auto_subject.get('priority')==2,'Automatic Geografia subject was not created with initial priority.')
            require(geography.get('subjectId')==auto_subject.get('id'),'Imported Geografia review was not linked to the automatic subject.')
            require(all(str(x.get('id','')).startswith('ERR-') for row in imported for x in row.get('examErrors',[])),'Error identifiers were not generated.')
            require(all(row.get('nextDue')==str(P.today()) for row in imported),'Imported error reviews must be due for review.')
            P.validate(profile)
            second=M._er_sync_target(app,c,dict(owner),student_id)
            require(second['created']==0 and second['updated']==0 and second.get('subjectsCreated')==0,'Sync must be idempotent.')
            js=(ROOT/'static'/'app.js').read_text(encoding='utf-8')
            require('EXAM ERROR REVIEW SYNC V1' in js and 'Atualizar erros dos simulados' in js,'Review UI sync is missing.')
    finally:
        if student_id:
            with app.db.connection(write=True) as c:
                app.db.execute(c,'DELETE FROM hmay_performance WHERE user_id=?',(student_id,))
                if exam_id: app.db.execute(c,'DELETE FROM hmay_exams WHERE id=?',(exam_id,))
                app.db.execute(c,'DELETE FROM hmay_events WHERE actor_id=? OR target_id=?',(student_id,student_id))
                app.db.execute(c,'DELETE FROM hmay_sessions WHERE user_id=?',(student_id,))
                app.db.execute(c,'DELETE FROM hmay_state WHERE user_id=?',(student_id,))
                app.db.execute(c,'DELETE FROM hmay_users WHERE id=?',(student_id,))
                key='user:'+hashlib.sha256(login.encode()).hexdigest()
                app.db.execute(c,'DELETE FROM hmay_attempts WHERE key=?',(key,))
    print('MEUCRONOGRAMA_EXAM_REVIEW_SYNC_CHECK_OK: imported errors became grouped reviews and missing disciplines became schedulable subjects.',flush=True)

if __name__=='__main__':
    main()
