"""Dados sintéticos para os testes de navegador. Uso: python tests/browser/seed.py <pasta do projeto> <arquivo .sqlite3>"""
import json
import sys;sys.path.insert(0,sys.argv[1])
import os
os.environ.update(LOCAL_TEST='1',LOCAL_DB=sys.argv[2],SECRET_KEY='k'*64,MASTER_PASSWORD='TEST_master_13579')
from webapp import App,encode
import planner as P
app=App();app.db.initialize(app.owner,'TEST_master_13579')
with app.db.connection(write=True) as c:
    app.db.create_user(c,'laise','Laise','TEST_coord_1234','coordenador',False)
    for login,name in (('ana.souza','Ana Souza'),('bruno.lima','Bruno Lima')):
        sid=app.db.create_user(c,login,name,'TEST_aluno_1234','aluno',False)
        p=P.default_profile(name,sid)
        p['subjects']=[dict(id='s1',name='Química',kind='study',action='Estudar',weeklyMin=90,difficulty=3,importance=3,priority=2,priorityManual=True,examDate='',active=True)]
        p['contents']=[dict(id='c1',subjectId='s1',title='Estequiometria',topic='',notes='',material='',status='studied',paused=False,studyMinutes=40,reviewMinutes=30,difficulty=3,studiedOn=P.add(P.today(),-10),studiedTime='09:00',nextDue=P.add(P.today(),2),stage=0)]
        P.validate(p);app.db.execute(c,'UPDATE hmay_state SET profile=? WHERE user_id=?',(encode(p),sid))
    app.db.create_user(c,'mayra','Mayra Especial','TEST_esp_12345','especial',False) if not app.db.execute(c,"SELECT 1 FROM hmay_users WHERE username='mayra'").fetchone() else app.db.execute(c,"UPDATE hmay_users SET password=?,must_change=0,role='especial',name='Mayra Especial' WHERE username='mayra'",(__import__('webapp').password_hash('TEST_esp_12345'),))

with app.db.connection(write=True) as c:
    for login,g,ok in (('ana.souza',790.0,85),('bruno.lima',600.0,45)):
        uid=app.db.execute(c,'SELECT id FROM hmay_users WHERE username=?',(login,)).fetchone()['id']
        for i in range(3):
            md={'_exam_id':'x','_tri_general':g,'_tri_lc':g,'_tri_ch':g,'_tri_cn':g,'_tri_mt':g}
            m={f'questao:{q:03d}':{'correct':int(q<=ok),'total':1} for q in range(1,101)}
            app.db.execute(c,'INSERT INTO hmay_performance(id,user_id,activity_key,activity,applied_on,metrics,metadata,version,updated_at) VALUES (?,?,?,?,?,?,?,?,?)',(P.uid(),uid,f's{i}',f'Sim {i}',P.add(P.today(),-(60+10*i)),json.dumps(m),json.dumps(md),1,P.now().isoformat()))

import random;random.seed(7)
ITEMS=[{'number':n,'area':['LC','CH','CN','MT'][(n-1)//10],'discipline':['Português','História','Química','Matemática'][(n-1)//10],'subject':['Interpretação','Brasil República','Estequiometria','Funções','Gêneros textuais','Era Vargas','Soluções','Porcentagem'][((n-1)//10)+4*((n-1)%2)],'skill':f'H{n:02d}','answer':'ABCDE'[n%5],'language':''} for n in range(1,41)]
with app.db.connection(write=True) as c:
    owner=app.db.execute(c,"SELECT id FROM hmay_users WHERE username='arcmb'").fetchone()['id']
    app.db.execute(c,'INSERT INTO hmay_exams(id,identity_key,owner_id,title,applied_on,color,area,items,version,updated_at) VALUES (?,?,?,?,?,?,?,?,?,?)',('ex1','k1',owner,'4º Simulado',P.add(P.today(),-20),'AZUL','GERAL',json.dumps(ITEMS),1,P.now().isoformat()))
    for i in range(24):
        uid=app.db.create_user(c,f'al{i}',f'Aluno {i:02d}','TEST_aluno_1234','aluno',i%5==0)
        turma=['3º A','3º B','Med 01'][i%3]
        for s,(key,d) in enumerate((('sim3',P.add(P.today(),-50)),('sim4',P.add(P.today(),-20)))):
            if i==7 and s==1: continue
            skill=0.35+0.5*random.random()-(0.15 if (i==4 and s==1) else 0)
            m={};okn=0
            for it in ITEMS:
                p=skill-(0.25 if it['subject'] in ('Estequiometria','Funções') else 0)
                ok=int(random.random()<p);okn+=ok
                m[f"questao:{it['number']:03d}"]={'correct':ok,'total':1,'response':it['answer'] if ok else random.choice([x for x in 'ABCDE' if x!=it['answer']])}
            g=round(450+okn*10+random.random()*20,1)
            comps=[random.choice([80,120,160,200]) for _ in range(5)]
            md={'_exam_id':'ex1','TURMA':turma,'COR DA PROVA':'AZUL','_tri_general':g,'_tri_lc':g,'_tri_ch':g,'_tri_cn':g,'_tri_mt':g,'_tri_redaction':sum(comps),**{f'_redaction_c{k+1}':v for k,v in enumerate(comps)}}
            app.db.execute(c,'INSERT INTO hmay_performance(id,user_id,activity_key,activity,applied_on,metrics,metadata,version,updated_at) VALUES (?,?,?,?,?,?,?,?,?)',(P.uid(),uid,key,['3º Simulado','4º Simulado'][s],d,json.dumps(m),json.dumps(md),1,P.now().isoformat()))

with app.db.connection(write=True) as c:
    items=[{'number':1,'area':'LC','discipline':'ESPANHOL','answer':'A','language':'Espanhol'},{'number':2,'area':'LC','discipline':'L. corporal','answer':'B','language':''},{'number':3,'area':'CN','discipline':'Astronomia','answer':'C','language':''}]
    app.db.execute(c,'INSERT INTO hmay_exams(id,identity_key,owner_id,title,applied_on,color,area,items,version,updated_at) VALUES (?,?,?,?,?,?,?,?,?,?)',('ex2','k2',owner,'5º Simulado',P.today(),'AZUL','GERAL',json.dumps(items),1,P.now().isoformat()))
    app.db.execute(c,'INSERT INTO hmay_exams(id,identity_key,owner_id,title,applied_on,color,area,items,version,updated_at) VALUES (?,?,?,?,?,?,?,?,?,?)',('ex3','k3',owner,'5º Simulado',P.today(),'AMARELA','GERAL',json.dumps([{'number':1,'area':'LC','discipline':'Português','answer':'A','language':''}]),1,P.now().isoformat()))  # cor extra só com disciplina oficial: não altera as contagens do cenário 08

print('seeded')
# Planilha de itens do ENEM para o cenário 07 (gravada ao lado do banco temporário).
import base64 as _b64, os as _os
import enem_items as _E, templates_v23 as _T
_rows=[[2023,'MT','Matemática','Funções','Funções',f'H{20+i%3}',2.0+0.2*i,0.8+0.25*i,0.15] for i in range(6)]+[[2022,'CN','Química','Estequiometria','Estequiometria','H24',2.8,2.2,0.12],[2022,'','Astronomia','','Estrelas','',2,1,0.2]]
_blob,_=_T.export(_E.HEADERS,_rows,first_name='Itens ENEM')
open(_os.path.join(_os.path.dirname(sys.argv[2]),'itens_enem.xlsx'),'wb').write(_blob)
# Ano letivo anterior (para o cenário 07 de comparação entre anos).
_prev=int(str(P.today())[:4])-1
with app.db.connection(write=True) as c:
    for i in range(12):
        uid=app.db.execute(c,'SELECT id FROM hmay_users WHERE username=?',(f'al{i}',)).fetchone()['id']
        m={f"questao:{it['number']:03d}":{'correct':int(random.random()<0.5),'total':1} for it in ITEMS}
        md={'_exam_id':'ex1','TURMA':'3º A','COR DA PROVA':'AZUL','_tri_general':600.0,'_tri_lc':600.0,'_tri_ch':600.0,'_tri_cn':600.0,'_tri_mt':600.0,'_tri_redaction':600,**{f'_redaction_c{k+1}':120 for k in range(5)}}
        app.db.execute(c,'INSERT INTO hmay_performance(id,user_id,activity_key,activity,applied_on,metrics,metadata,version,updated_at) VALUES (?,?,?,?,?,?,?,?,?)',(P.uid(),uid,'simprev','Simulado anterior',f'{_prev}-06-10',json.dumps(m),json.dumps(md),1,P.now().isoformat()))
# Todos os alunos acima já passaram pelo primeiro acesso; "novo.aluno" ainda não (cenário 09).
with app.db.connection(write=True) as c:
    for r in app.db.execute(c,'SELECT user_id,profile FROM hmay_state').fetchall():
        prof=json.loads(r['profile']);prof.setdefault('settings',{})['onboardedAt']='2026-01-01'
        app.db.execute(c,'UPDATE hmay_state SET profile=? WHERE user_id=?',(json.dumps(prof),r['user_id']))
    app.db.create_user(c,'novo.aluno','Novo Aluno da Silva','TEST_aluno_1234','aluno',False)
# Planilha de resultados com divergências, para o cenário da janela de correção (v3.17.0).
import base64 as _b64, pathlib as _pl
import model_data as _M, templates_v23 as _T
_sh=['NOME','LOGIN','TURMA','NOME DO SIMULADO','DATA DE APLICAÇÃO','COR DA PROVA','L. ESTRANGEIRA',6,7,8]
_st=[['Ana Souza','ana.souza','turma um','Simulado Correção','05/11/2026','AZUL','','A','B','C'],
     ['Bruno Lima','bruno.lima','turma um','Simulado Corecao','05/11/2026','AZUL','','A','B','D'],
     ['Novo Aluno da Silva','novo.aluno','turma um','Simulado Correção','05/11/2026','VERDE','','A','A','C'],
     ['Ana Souza','ana.souza','turma um','Simulado Correção','05/11/2026','AZUL','','A','B','C']]
_mh=['NOME DO SIMULADO','DATA DE APLICAÇÃO','COR DA PROVA','QUESTÃO','ÁREA','DISCIPLINA','TÓPICO','ASSUNTO','HABILIDADE','LÍNGUA ESTRANGEIRA','GABARITO']
_mp=[['Simulado Correção','05/11/2026','AZUL',6,'LC','Português','T','A','H01','','A'],
     ['Simulado Correção','05/11/2026','AZUL',7,'XX','Matemática','T','A','H02','','B'],
     ['Simulado Correção','05/11/2026','AZUL',8,'MT','','T','A','H03','','C']]
_blob,_=_T.export(_sh,_st,first_name=_M.STUDENTS_SHEET,extra_sheets=[(_M.EXAM_SHEET,_mh,_mp)])
(_pl.Path(sys.argv[2]).parent/'broken_results.b64').write_text(_b64.b64encode(_blob).decode())
# Notas TRI do mesmo simulado, com um nome digitado errado (cenário 14).
_th=['NOME','NOME DO SIMULADO','DATA DE APLICAÇÃO','TURMA','RANKING','TRI LINGUAGENS','TRI HUMANAS','TRI NATUREZA','TRI MATEMÁTICA','C1','C2','C3','C4','C5']
_tr=[['Ana Souza','Simulado Correção','05/11/2026','Turma 1',1,650,640,630,620,160,160,160,160,160],
     ['Bruno Lma','Simulado Correção','05/11/2026','Turma 1',2,640,630,620,610,140,140,140,140,140]]
_tblob=_T.export(_th,_tr,first_name='TRI e Redação')
_tblob=_tblob[0] if isinstance(_tblob,tuple) else _tblob
(_pl.Path(sys.argv[2]).parent/'tri_names.b64').write_text(_b64.b64encode(_tblob).decode())
