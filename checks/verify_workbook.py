"""Production smoke check using disposable staff/student accounts only."""
import base64,hashlib,os,secrets
from verify_release import Client,require
from webapp import App
import templates_v23 as T
import unified as U
import exams as E
import performance as F
import planner as P
import selective as S

def main():
    app=App();app.db.initialize(app.owner,app.env.get('MASTER_PASSWORD',''),app.env.get('MAYRA_INITIAL_PASSWORD',''))
    host=os.getenv('RENDER_EXTERNAL_HOSTNAME') or sorted(app.hosts)[0]
    nonce=secrets.token_hex(8);password=secrets.token_urlsafe(32);ids=[];logins=['v24staff_'+nonce,'v24aluno_'+nonce]
    title='Verificação arquivo único '+nonce;student_name='Participante técnico '+nonce;date=P.today()
    try:
        with app.db.connection(write=True)as c:
            ids.append(app.db.create_user(c,logins[0],'Verificação técnica',password,'coordenador',False))
            ids.append(app.db.create_user(c,logins[1],student_name,password,'aluno',False))
        staff=Client(app,host);staff.login(logins[0],password)
        require(staff.request('/readyz')['data'].get('version')=='2.8','Release identity mismatch.')
        require(S.item_value(1,'Questão')==1 and S.item_value(0,'Questão')==0 and S.item_value(None,'Questão')is None,'Binary convention failed.')
        for invalid in ('Acerto','Erro','C','E',2,True):
            try:S.item_value(invalid,'Questão')
            except ValueError:pass
            else:raise RuntimeError('Only numeric 1/0 may be imported.')
        fields=['NOME','TIPO de prova','data de aplicação','Acerto/erro questão 91','Acerto/erro questão 92','Acerto/erro questão 93']
        blob,_=U.template(dict(fields=fields,questionFirst=91,questionLast=93))
        require(F.load_matrix('x.xlsx',blob)[2]==['Resultados','Questoes','Simulado','Como preencher'],'Workbook sheets missing.')
        qs=[[91,'CN','Química','Tópico teste','Assunto teste','H01','',''],[92,'CN','Química','Tópico teste','Assunto teste','H01','',''],[93,'CN','Física','Tópico teste','Outro assunto','H02','','']]
        blob,_=T.export(fields,[[student_name,title,date,1,0,None]],first_name='Resultados',extra_sheets=[('Questoes',E.HEADERS,qs),('Simulado',U.CONFIG_HEADERS,[[title,date,'Única','CN']])])
        p=dict(filename='verificacao.xlsx',file=base64.b64encode(blob).decode())
        pre=staff.request('/api/workbook/preview',p);require(pre['status']==200,'Combined preview failed.')
        sample=pre['data']['sample'][0]['analysis']['overall'];require(sample['marked']==2 and sample['pending']==1 and sample['percentFinal']is None,'Partial coverage check failed.')
        saved=staff.request('/api/workbook/confirm',{**p,'token':pre['data']['token'],'mapping':pre['data']['mapping']});require(saved['status']==200,'Combined transaction failed.')
        reader=Client(App(),host);reader.login(logins[1],password);r=reader.request('/api/performance');require(r['status']==200 and len(r['data']['records'])==1,'Committed results not retained.')
        a=r['data']['records'][0]['analysis'];g=next(x for x in a['groups']['Disciplina']if x['name']=='Química')
        require(g['correctQuestions']==[91] and g['errorQuestions']==[92] and g['accuracy']==50,'Question traceability failed.')
        require(reader.request('/api/workbook/preview',p)['status']==403,'Student import should be denied.')
    finally:
        if ids:
            with app.db.connection(write=True)as c:
                for uid in ids:
                    for table,column in [('hmay_performance','user_id'),('hmay_exams','owner_id'),('hmay_proposals','target_id'),('hmay_adjustments','target_id'),('hmay_adaptive_consent','user_id'),('hmay_adaptive_observations','user_id'),('hmay_sessions','user_id'),('hmay_state','user_id')]:
                        app.db.execute(c,f'DELETE FROM {table} WHERE {column}=?',(uid,))
                    app.db.execute(c,'DELETE FROM hmay_events WHERE actor_id=? OR target_id=?',(uid,uid))
                    app.db.execute(c,'DELETE FROM hmay_users WHERE id=?',(uid,))
                for login in logins:app.db.execute(c,'DELETE FROM hmay_attempts WHERE key=?',('user:'+hashlib.sha256(login.encode()).hexdigest(),))
    print('MEUCRONOGRAMA_V24_CHECK_OK: binary 1/0, single XLSX, atomic map/results import, partial coverage, question lists, isolation, persistence and cleanup passed.',flush=True)

if __name__=='__main__':
    try:main()
    except Exception as exc:
        print('MEUCRONOGRAMA_V24_CHECK_FAILED: '+type(exc).__name__+'. Credentials omitted.',flush=True);raise SystemExit(1)
