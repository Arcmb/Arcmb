"""Deployment smoke check with disposable staff/student data; never changes real accounts."""
import base64,hashlib,secrets,os
from pathlib import Path
from verify_release import Client,require
from webapp import App
import performance as F
import selective as S
import questions_v23 as Q
from site_version import PUBLIC_VERSION

def csvdata(text):return dict(filename='verificacao.csv',file=base64.b64encode(text.encode()).decode())
def main():
 require(len(Q.QUESTIONS)==20 and len(Q.HELPS)==20,'Question wording missing.')
 source=(Path(__file__).resolve().parents[1]/'static/app.html').read_text()
 require('v'+PUBLIC_VERSION in source and '/static/selective.js'in source,'v'+PUBLIC_VERSION+' assets missing.')
 blob,_=S.template(dict(fields=['NOME','TIPO de prova','data de aplicação','Acertos - Física'],format='xlsx'))
 require(F.load_matrix('x.xlsx',blob)[0][0][-1]=='Acertos - Física','Selective XLSX template failed.')
 app=App();app.db.initialize(app.owner,app.env.get('MASTER_PASSWORD',''),app.env.get('MAYRA_INITIAL_PASSWORD',''))
 host=os.getenv('RENDER_EXTERNAL_HOSTNAME')or sorted(app.hosts)[0]
 nonce=secrets.token_hex(8);logins=['v23staff_'+nonce,'v23aluno_'+nonce];password=secrets.token_urlsafe(32);ids=[];exam_id=None
 title='Verificação v23 '+nonce;student_name='Participante técnico '+nonce
 try:
  with app.db.connection(write=True)as c:
   ids.append(app.db.create_user(c,logins[0],'Verificação técnica',password,'coordenador',False));ids.append(app.db.create_user(c,logins[1],student_name,password,'aluno',False))
  staff=Client(app,host);staff.login(logins[0],password)
  p={**csvdata('QUESTÃO;DISCIPLINA;ÁREA;TÓPICO;ASSUNTO;HABILIDADE\n91;Química;CN;Tópico teste;Assunto teste;H24'),'title':title,'date':'2026-10-28','color':'Única'}
  preview=staff.request('/api/exams/preview',p);require(preview['status']==200,'Exam preview failed.')
  saved=staff.request('/api/exams/confirm',{**p,'token':preview['data']['token']});require(saved['status']==200,'Exam save failed.');exam_id=saved['data']['id']
  p={**csvdata('NOME;TIPO;data;Acerto/erro questão 91;Acertos - Física\n'+student_name+';'+title+';28/10/2026;1;ignorar'),'columnMapping':{'0':'NOME','1':'TIPO de prova','2':'data de aplicação','3':'Acerto/erro questão 91','4':''},'examId':exam_id}
  preview=staff.request('/api/performance/preview',p);require(preview['status']==200,'Selective preview failed.')
  saved=staff.request('/api/performance/confirm',{**p,'mapping':preview['data']['mapping'],'token':preview['data']['token']});require(saved['status']==200,'Selective save failed.')
  student=Client(App(),host);student.login(logins[1],password);r=student.request('/api/performance');require(r['status']==200 and len(r['data']['records'])==1,'Selective persistence failed.')
  rec=r['data']['records'][0];require(rec['metrics']['questao:091']['correct']==1 and rec['analysis']['groups']['Disciplina'][0]['correct']==1,'Item classification failed.')
  require(student.request('/api/exams')['status']==403,'Student catalogue access must be blocked.')
 finally:
  if ids:
   with app.db.connection(write=True)as c:
    for uid in ids:
     for table,column in [('hmay_performance','user_id'),('hmay_exams','owner_id'),('hmay_proposals','target_id'),('hmay_adjustments','target_id'),('hmay_adaptive_consent','user_id'),('hmay_adaptive_observations','user_id'),('hmay_sessions','user_id'),('hmay_state','user_id')]:app.db.execute(c,f'DELETE FROM {table} WHERE {column}=?',(uid,))
     app.db.execute(c,'DELETE FROM hmay_events WHERE actor_id=? OR target_id=?',(uid,uid));app.db.execute(c,'DELETE FROM hmay_users WHERE id=?',(uid,))
    for login in logins:app.db.execute(c,'DELETE FROM hmay_attempts WHERE key=?',('user:'+hashlib.sha256(login.encode()).hexdigest(),))
 print('MEUCRONOGRAMA_V23_CHECK_OK: clear questions, selected XLSX, exam map, selective import, classified results, isolation, persistence and cleanup passed.',flush=True)
if __name__=='__main__':
 try:main()
 except Exception as exc:
  print('MEUCRONOGRAMA_V23_CHECK_FAILED: '+type(exc).__name__+'. Credentials omitted.',flush=True);raise SystemExit(1)
