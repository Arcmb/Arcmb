"""Selective import, questionnaire wording and assessment catalogue regression tests."""
import sys,tempfile,unittest,base64,copy,json
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1])); sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'checks'))
from webapp import App
from test_system import Browser
import selective as S
import exams as E
import performance as F
import templates_v23 as T
import questions_v23 as Q

def payload(text):return dict(filename='teste.csv',file=base64.b64encode(text.encode()).decode())
def testfile(activity='Prova A',extra=';Acerto/erro questão 91;Acerto/erro questão 92',values=';1;0'):
 return payload('NOME;TIPO;data'+extra+'\nAluno Teste;'+activity+';28/10/2026'+values)
def mapfile(title='Prova A'):
 return {**payload('Prova Azul;Disciplina;Assunto;Habilidade;Gabarito\n91;Química;Oxirredução;H24;D\n92;Química;Propriedades;H19;A'), 'title':title,'date':'2026-10-28','color':'Azul','area':'CN'}

class PureTests(unittest.TestCase):
 def test_01_question_count(self):self.assertEqual(len(Q.QUESTIONS),20);self.assertEqual(len(Q.HELPS),20)
 def test_02_no_undefined_blocks(self):self.assertFalse(any('bloco'in q[2].lower()for q in Q.QUESTIONS));self.assertIn('estuda por conta própria',dict((q[0],q[2])for q in Q.QUESTIONS)['focus'])
 def test_03_preserve_ids(self):self.assertEqual(dict(Q.QUESTIONS[5][3]).keys(),{'15','25','40','60'})
 def test_04_correct_mojibake(self):self.assertEqual(S.fix_header('Acertos - PortuguÃªs'),'Acertos - Português')
 def test_05_item_zero(self):self.assertEqual(S.item_value(0,'Q1'),0);self.assertIsNone(S.item_value(None,'Q1'))
 def test_06_item_invalid(self):
  for v in ('2','D','1,5','-1'):
   with self.assertRaises(ValueError):S.item_value(v,'Q1')
 def test_07_question_namespace(self):
  r=F.parse_file(testfile())['records'][0]['metrics'];self.assertEqual(r['questao:091']['correct'],1);self.assertEqual(r['questao:092']['correct'],0)
 def test_08_skill_requires_area(self):
  with self.assertRaises(ValueError):F.parse_file(testfile(extra=';Acertos Hab 01',values=';2'))
 def test_09_skill_scoped(self):
  p=testfile(extra=';Acertos Hab 01',values=';2');p['skillArea']='CN';self.assertIn('habilidade:CN:h01',F.parse_file(p)['records'][0]['metrics'])
 def test_10_ignore_invalid_column(self):
  p=testfile(extra=';Acertos - Física;Acertos - Química',values=';2;invalido');p['columnMapping']={'0':'NOME','1':'TIPO de prova','2':'data de aplicação','3':'Acertos - Física','4':''};r=F.parse_file(p);self.assertNotIn('quimica',r['records'][0]['metrics'])
 def test_11_map_arbitrary_headers(self):
  p=payload('Estudante;Evento;Quando;Pontos\nAluno;Teste;28/10/2026;3');p['columnMapping']={'0':'NOME','1':'TIPO de prova','2':'data de aplicação','3':'Acertos - Robótica'};self.assertIn('robotica',F.parse_file(p)['records'][0]['metrics'])
 def test_12_duplicate_targets(self):
  p=testfile();p['columnMapping']={'0':'NOME','1':'NOME','2':'data'}
  with self.assertRaises(ValueError):F.parse_file(p)
 def test_13_required_fields(self):
  p=testfile();p['columnMapping']={'0':'NOME'}
  with self.assertRaises(ValueError):F.parse_file(p)
 def test_14_selected_template(self):
  b,m=S.template(dict(fields=['NOME','TIPO de prova','data de aplicação','Acertos - Inglês'],format='xlsx'));rows=F.load_matrix('x.xlsx',b)[0];self.assertEqual(rows[0],['NOME','TIPO de prova','data de aplicação','Acertos - Inglês']);self.assertNotIn('Robótica',str(rows))
 def test_15_csv_encoding(self):
  b,m=S.template(dict(fields=['NOME','TIPO de prova','data de aplicação','Acertos - Português'],format='csv'));self.assertTrue(b.startswith(b'\xef\xbb\xbf'));self.assertIn('Português',b.decode('utf-8-sig'))
 def test_16_template_safety(self):
  b,m=T.export(['=cmd'],kind='csv');self.assertIn("'=cmd",b.decode('utf-8-sig'))
 def test_17_supported_user_model(self):
  x=E.parse(mapfile());self.assertEqual(x['items'][0]['number'],91);self.assertEqual(x['items'][0]['topic'],'');self.assertEqual(x['items'][0]['area'],'CN')
 def test_18_language_variants(self):
  p=payload('QUESTÃO;DISCIPLINA;ÁREA;LÍNGUA ESTRANGEIRA\n1;Inglês;LC;Inglês\n1;Espanhol;LC;Espanhol');self.assertEqual(len(E.parse(p)['items']),2)
 def test_19_duplicate_items(self):
  p=payload('QUESTÃO;DISCIPLINA\n1;Matemática\n1;Matemática')
  with self.assertRaises(ValueError):E.parse(p)
 def test_20_unscoped_skill(self):
  p=payload('QUESTÃO;DISCIPLINA;HABILIDADE\n1;Robótica;H1')
  with self.assertRaises(ValueError):E.parse(p)
 def test_21_analysis_missing_not_error(self):
  x=E.parse(mapfile());a=E.analyse(dict(items=x['items'],title='Teste',version=1,color='Azul'),{'questao:091':{'correct':1}},{});g=a['groups']['Disciplina'][0];self.assertEqual((g['correct'],g['errors'],g['marked'],g['total']),(1,0,1,2))
 def test_22_reserved_columns(self):
  p=testfile(extra=';_exam_id',values=';injetado')
  with self.assertRaises(ValueError):F.parse_file(p)
 def test_23_source_invalid_skill(self):
  p=payload('QUESTÃO;DISCIPLINA;HABILIDADE\n1;Matemática;H99')
  with self.assertRaises(ValueError):E.parse(p)

class APITests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.tmp=tempfile.TemporaryDirectory();cls.app=App({'LOCAL_TEST':'1','LOCAL_DB':cls.tmp.name+'/db','SECRET_KEY':'z'*64,'MASTER_PASSWORD':'TEST_master_13579'});cls.master=Browser(cls.app);assert cls.master.login()['status']==303
  cls.clients={}
  with cls.app.db.connection(write=True)as c:
   for role in('aluno','coordenador','especial'):cls.app.db.create_user(c,role,'Aluno Teste'if role=='aluno'else role,'TEST_v23_13579',role,False)
  for role in('aluno','coordenador','especial'):
   b=Browser(cls.app);assert b.login(role,'TEST_v23_13579')['status']==303;cls.clients[role]=b
 @classmethod
 def tearDownClass(cls):cls.tmp.cleanup()
 def preview(self,p,client=None):
  r=(client or self.master).request('/api/performance/preview',p);self.assertEqual(r['status'],200,r);return r['data']
 def commit(self,p,client=None):
  d=self.preview(p,client);return (client or self.master).request('/api/performance/confirm',{**p,'mapping':d['mapping'],'token':d['token']})
 def exam(self,p,client=None):
  b=client or self.master;d=b.request('/api/exams/preview',p);self.assertEqual(d['status'],200,d);r=b.request('/api/exams/confirm',{**p,'token':d['data']['token']});self.assertEqual(r['status'],200,r);return r['data']['id']
 def records(self):return self.clients['aluno'].request('/api/performance')['data']['records']
 def test_24_student_cannot_catalogue(self):self.assertEqual(self.clients['aluno'].request('/api/exams')['status'],403)
 def test_25_special_cannot_catalogue(self):self.assertEqual(self.clients['especial'].request('/api/exams')['status'],403)
 def test_26_fields_staff_only(self):self.assertEqual(self.clients['aluno'].request('/api/performance/fields')['status'],403);self.assertEqual(self.master.request('/api/performance/fields')['status'],200)
 def test_27_inspect_no_writes(self):
  old=len(self.records());r=self.master.request('/api/performance/inspect',testfile());self.assertEqual(r['status'],200);self.assertEqual(old,len(self.records()))
 def test_28_selective_partial_merge(self):
  p=testfile('Parcial');p['columnMapping']={'0':'NOME','1':'TIPO','2':'data','3':'Acerto/erro questão 91'};self.assertEqual(self.commit(p)['status'],200)
  p['columnMapping']={'0':'NOME','1':'TIPO','2':'data','4':'Acerto/erro questão 92'};self.assertEqual(self.commit(p)['status'],200)
  r=next(x for x in self.records()if x['activity']=='Parcial');self.assertEqual(r['metrics']['questao:091']['correct'],1);self.assertEqual(r['metrics']['questao:092']['correct'],0)
 def test_29_mapping_signature(self):
  p=testfile('Assinatura');p['columnMapping']={'0':'NOME','1':'TIPO','2':'data','3':'Acerto/erro questão 91'};d=self.preview(p);p['columnMapping']['3']='Acerto/erro questão 92';r=self.master.request('/api/performance/confirm',{**p,'mapping':d['mapping'],'token':d['token']});self.assertEqual(r['status'],409)
 def test_30_exam_with_analysis(self):
  eid=self.exam(mapfile('Análise'));r=self.commit({**testfile('Análise'),'examId':eid});self.assertEqual(r['status'],200,r);rec=next(x for x in self.records()if x['activity']=='Análise');g=rec['analysis']['groups']['Disciplina'][0];self.assertEqual(g['correct'],1);self.assertEqual(g['errors'],1)
 def test_31_exam_preview_no_write(self):
  before=len(self.master.request('/api/exams')['data']['exams']);r=self.master.request('/api/exams/preview',mapfile('Só prévia'));self.assertEqual(r['status'],200);self.assertEqual(before,len(self.master.request('/api/exams')['data']['exams']))
 def test_32_wrong_title_rejected(self):
  eid=self.exam(mapfile('Certa'));self.assertEqual(self.master.request('/api/performance/preview',{**testfile('Errada'),'examId':eid})['status'],400)
 def test_33_catalogue_owner_edit(self):
  eid=self.exam(mapfile('Master mapa'));p={**mapfile('Master mapa'),'examId':eid};self.assertEqual(self.clients['coordenador'].request('/api/exams/preview',p)['status'],200)  # a coordenação complementa mapas de qualquer autor
 def test_34_special_no_performance(self):
  target=self.clients['especial'].user['id'];self.assertEqual(self.clients['coordenador'].request('/api/performance?user='+target)['status'],403)
 def test_35_stale_catalogue_preview(self):
  p=mapfile('Concorrente');d=self.master.request('/api/exams/preview',p)['data'];self.exam(p);self.assertIn(self.master.request('/api/exams/confirm',{**p,'token':d['token']})['status'],(400,409))
 def test_36_csrf(self):self.assertEqual(self.master.request('/api/exams/preview',mapfile(),csrf=False)['status'],403)
 def test_37_upload_no_schedule_change(self):
  before=self.clients['aluno'].state()['data'];self.commit(testfile('Sem mudar'));self.assertEqual(before,self.clients['aluno'].state()['data'])
 def test_38_exam_merge_blank_preserves(self):
  p=mapfile('Complemento');eid=self.exam(p);p2={**payload('QUESTÃO;DISCIPLINA;TÓPICO\n91;Química;Química geral'), 'title':'Complemento','date':'2026-10-28','color':'Azul','examId':eid};self.exam(p2)
  with self.app.db.connection()as c:r=E.get_exam(self.app,c,eid)
  self.assertEqual(len(r['items']),2);self.assertEqual(r['items'][0]['skill'],'H24');self.assertEqual(r['items'][0]['topic'],'Química geral')
 def test_39_saved_questionnaire(self):
  b=self.clients['aluno'];self.assertEqual(b.action('objective',{'answers':{'focus':'25','recording':'daily'}})['status'],200);d=b.request('/api/adaptive')['data'];self.assertEqual(d['answers']['focus'],'25');self.assertIn('site',next(q for q in d['questions']if q['key']=='recording')['label']);self.assertTrue(all(q['help']for q in d['questions']))
 def test_40_template_api(self):
  r=self.master.request('/api/performance/template-selected',{'fields':['NOME','TIPO de prova','data de aplicação','Acertos Hab 01'],'format':'xlsx'});self.assertEqual(r['status'],200);self.assertTrue(r['raw'].startswith(b'PK'))
 def test_41_scoped_skill_reimport(self):
  p=testfile('Habilidades',extra=';Acertos Hab 01',values=';1');p['skillArea']='CN';self.commit(p);p['skillArea']='LC';self.commit(p);m=next(x for x in self.records()if x['activity']=='Habilidades')['metrics'];self.assertIn('habilidade:LC:h01',m);self.assertIn('habilidade:CN:h01',m)
 def test_42_template_question_range(self):
  r=self.master.request('/api/exams/template',{'first':91,'last':135,'format':'xlsx'});self.assertEqual(r['status'],200);rows=F.load_matrix('x.xlsx',r['raw'])[0];self.assertEqual(rows[1][0],'91');self.assertEqual(rows[-1][0],'135')
if __name__=='__main__':unittest.main()
