"""Assessment item catalogue. Pedagogical metadata only; never stores student passwords."""
from __future__ import annotations
import hashlib,json,re,time
import planner as P
import performance as F
import selective as S
import templates_v23 as T

HEADERS=['QUESTÃO','ÁREA','DISCIPLINA','TÓPICO','ASSUNTO','HABILIDADE','LÍNGUA ESTRANGEIRA','GABARITO']
ALIASES={'questao':'QUESTÃO','numero':'QUESTÃO','numero da questao':'QUESTÃO','nº':'QUESTÃO','prova azul':'QUESTÃO','prova amarela':'QUESTÃO','prova branca':'QUESTÃO','prova rosa':'QUESTÃO','area':'ÁREA','area de conhecimento':'ÁREA','disciplina':'DISCIPLINA','topico':'TÓPICO','topico geral':'TÓPICO','assunto':'ASSUNTO','conteudo':'ASSUNTO','assunto principal':'ASSUNTO','habilidade':'HABILIDADE','lingua estrangeira':'LÍNGUA ESTRANGEIRA','l.e':'LÍNGUA ESTRANGEIRA','idioma':'LÍNGUA ESTRANGEIRA','gabarito':'GABARITO'}
DISC_AREAS={F.norm(s):area for area,ss in [('CN',['Biologia','Química','Física']),('CH',['História','Geografia','Filosofia','Sociologia']),('MT',['Matemática']),('LC',['Português','Literatura','Artes','Linguagem corporal','Língua estrangeira','Inglês','Espanhol'])]for s in ss}

def schema(db,c):
 db.execute(c,'CREATE TABLE IF NOT EXISTS hmay_exams (id TEXT PRIMARY KEY, identity_key TEXT NOT NULL UNIQUE, owner_id TEXT NOT NULL REFERENCES hmay_users(id), title TEXT NOT NULL, applied_on TEXT NOT NULL, color TEXT NOT NULL, area TEXT NOT NULL, items TEXT NOT NULL, version INTEGER NOT NULL, updated_at TEXT NOT NULL)')
 db.execute(c,'CREATE INDEX IF NOT EXISTS hmay_exams_title_date ON hmay_exams(title,applied_on)')

def enc(x):return json.dumps(x,ensure_ascii=False,separators=(',',':'),sort_keys=True)
def get_exam(app,c,eid):
 row=app.db.execute(c,'SELECT * FROM hmay_exams WHERE id=?',(eid,)).fetchone()
 if not row:raise ValueError('Simulado não encontrado.')
 return {**dict(row),'items':json.loads(row['items'])}
def area(v):
 n=F.norm(v)
 return {'linguagens':'LC','humanas':'CH','ciencias humanas':'CH','natureza':'CN','ciencias da natureza':'CN','matematica':'MT','lc':'LC','ch':'CH','cn':'CN','mt':'MT','':'','mista':''}.get(n,str(v or '').upper())
def language(v):
 n=F.norm(v)
 return {'ingles':'Inglês','english':'Inglês','0':'Inglês','espanhol':'Espanhol','spanish':'Espanhol','1':'Espanhol','':'','nao se aplica':''}.get(n,str(v or '').strip())
def inspect(data):
 rows,ep,sheets,sheet,blob=S.matrix(data)
 if not rows:raise ValueError('Planilha vazia.')
 columns=[dict(index=i,header=str(h or ''),suggested=ALIASES.get(F.norm(S.fix_header(h)),''),examples=[str(r[i])[:100]for r in rows[1:4]if len(r)>i and r[i] is not None])for i,h in enumerate(rows[0])]
 return dict(columns=columns,fields=[dict(name=n)for n in HEADERS],sheets=sheets,sheet=sheet,rows=len(rows)-1)

def parse(data):
 rows,ep,sheets,sheet,blob=S.matrix(data)
 if not rows:raise ValueError('Planilha vazia.')
 mapping=data.get('columnMapping')
 if mapping is not None and not isinstance(mapping,dict):raise ValueError('Mapeamento inválido.')
 idx={}
 for i,h in enumerate(rows[0]):
  label=mapping.get(str(i),'')if mapping is not None else ALIASES.get(F.norm(S.fix_header(h)),'')
  if not label:continue
  if label not in HEADERS or label in idx:raise ValueError('Campos do simulado desconhecidos ou repetidos.')
  idx[label]=i
 if not all(k in idx for k in ('QUESTÃO','DISCIPLINA')):raise ValueError('Selecione QUESTÃO e DISCIPLINA. Tópico, assunto e habilidade podem ser completados depois.')
 default=area(data.get('area',''))
 if default not in S.AREAS+['']:raise ValueError('Área inválida.')
 # === CORREÇÃO NA INTERFACE V3.17.0 ===
 # Cada linha com problema vira uma divergência (linha, coluna, valor, opções); a validação
 # continua nas próximas linhas e a interface corrige tudo de uma vez.
 import import_fixes as IF
 items=[];seen=set();issues=[];header=rows[0];lines={}
 def problem(line,row,field,message,options=None):
  col=idx.get(field)
  value=row[col]if col is not None and col<len(row)else ''
  issues.append(IF.issue(sheet,line,col,header[col]if col is not None and col<len(header)else field,value,message,options))
 for line,row in enumerate(rows[1:],2):
  if not any(v not in(None,'')for v in row):continue
  at=lambda k:row[idx[k]]if k in idx and idx[k]<len(row)else ''
  try:number=F.count_value(at('QUESTÃO'),'Questão')
  except ValueError as exc:problem(line,row,'QUESTÃO',f'Linha {line}: {exc}');continue
  if number is None or not 1<=number<=180:problem(line,row,'QUESTÃO',f'Linha {line}: questão deve estar entre 1 e 180.');continue
  disc=F.text(at('DISCIPLINA'),150)
  if not disc:problem(line,row,'DISCIPLINA',f'Linha {line}: informe a disciplina da questão {number:02d}.');continue
  ar=area(at('ÁREA'))or default or DISC_AREAS.get(F.norm(disc),'')
  if ar not in S.AREAS+['']:problem(line,row,'ÁREA',f'Linha {line}: área inválida.',['LC','CH','CN','MT']);continue
  skill=F.text(at('HABILIDADE'),40).upper().replace(' ','')
  if skill:
   m=re.fullmatch(r'(?:C\d+)?H0*([1-9]|[12][0-9]|30)',skill)
   if not m:problem(line,row,'HABILIDADE',f'Linha {line}: habilidade deve ter formato H01 a H30 ou C2H5.');continue
   skill='H'+str(int(m[1])).zfill(2)
   if not ar:problem(line,row,'ÁREA',f'Linha {line}: informe a área para distinguir a habilidade.',['LC','CH','CN','MT']);continue
  lang=language(at('LÍNGUA ESTRANGEIRA'))
  if lang not in ('','Inglês','Espanhol'):problem(line,row,'LÍNGUA ESTRANGEIRA',f'Linha {line}: língua deve ser Inglês, Espanhol ou vazia.',['','Inglês','Espanhol']);continue
  key=(number,lang)
  if key in seen:problem(line,row,'QUESTÃO',f'Linha {line}: questão {number:02d} e língua repetidas (já aparece na linha {lines[key]}). Corrija o número ou ignore a linha.');continue
  answer=F.text(at('GABARITO'),30).upper()
  if answer and answer not in ('A','B','C','D','E','ANULADA'):problem(line,row,'GABARITO',f'Linha {line}: gabarito deve ser A–E, ANULADA ou vazio.',['A','B','C','D','E','ANULADA','']);continue
  seen.add(key);lines[key]=line
  items.append(dict(number=number,area=ar,discipline=disc,topic=F.text(at('TÓPICO'),250),subject=F.text(at('ASSUNTO'),250),skill=skill,language=lang,answer=answer))
 for (number,lang),line in sorted(lines.items(),key=lambda x:x[1]):
  if lang and (number,'')in seen:
   issues.append(IF.issue(sheet,lines[(number,'')],idx.get('LÍNGUA ESTRANGEIRA'),'LÍNGUA ESTRANGEIRA','',
    f'Linha {lines[(number,"")]}: a questão {number:02d} tem versão geral e versão por língua (linha {line}). Identifique a língua desta linha.',['Inglês','Espanhol']))
 if issues:raise IF.ImportIssues(issues)
 if not items:raise ValueError('Nenhuma questão encontrada.')
 return dict(items=items,sheet=sheet,hash=hashlib.sha256(blob+IF.digest(data.get('fixes')).encode()).hexdigest())

def prepared(app,c,user,data):
 parsed=parse(data);eid=F.text(data.get('examId',''),80);old=get_exam(app,c,eid)if eid else None
 if old and not _exam_metadata.can_edit(user):raise ValueError('A edição dos mapas é exclusiva do Master e da coordenação.')
 title=F.text(data.get('title',''),200);date=F.date_value(data.get('date',''));color=F.text(data.get('color',''),80);ar=area(data.get('area',''))
 if not title or not color:raise ValueError('Informe nome da avaliação e cor da prova. Para prova sem cor, informe Única.')
 if old and (F.norm(title)!=F.norm(old['title'])or date!=old['applied_on']or F.norm(color)!=F.norm(old['color'])):raise ValueError('Para outro nome, data ou cor, cadastre um novo simulado. O existente pode receber complementos de questões.')
 if type(data.get('replace',False))is not bool:raise ValueError('Opção de substituir inválida.')
 if not old:
  exists=app.db.execute(c,'SELECT title,color FROM hmay_exams WHERE applied_on=?',(date,)).fetchall()
  if any(F.norm(x['title'])==F.norm(title)and F.norm(x['color'])==F.norm(color)for x in exists):raise ValueError('Este nome, data e cor já estão cadastrados. Selecione o simulado existente para complementar.')
 bykey={(x['number'],x['language']):dict(x)for x in (old['items']if old else [])};added=updated=conflicts=0
 for item in parsed['items']:
  k=(item['number'],item['language'])
  if k not in bykey:bykey[k]=dict(item);added+=1;continue
  current=bykey[k];before=dict(current)
  for f,v in item.items():
   if v in('',None):continue
   if current.get(f)not in('',None)and current[f]!=v:
    conflicts+=1
    if not data.get('replace'):continue
   current[f]=v
  updated+=current!=before
 items=sorted(bykey.values(),key=lambda x:(x['number'],x['language']))
 for item in items:
  if item['language']and (item['number'],'')in bykey:raise ValueError('Versões por língua conflitam com uma questão geral já cadastrada.')
 result=dict(id=eid,title=title,applied_on=date,color=color,area=ar,items=items,version=old['version']if old else 0,owner_id=old['owner_id']if old else user['id'])
 summary=dict(new=added,updated=updated,conflicts=conflicts,total=len(items),topicMissing=sum(not x['topic']for x in items),skillMissing=sum(not x['skill']for x in items))
 payload=enc([user['id'],result,parsed['hash'],data.get('columnMapping'),bool(data.get('replace'))])
 return result,summary,payload

def analyse(exam,metrics,metadata):
 lang=language(metadata.get('L.E',''));groups={k:{}for k in('Área','Disciplina','Tópico','Assunto','Habilidade')};known=set();unknown_language=0
 for item in exam['items']:
  if item['language']:
   if not lang:unknown_language+=1;continue
   if item['language']!=lang:continue
  n=item['number'];known.add(n);m=metrics.get(f'questao:{n:03d}',{});value=m.get('correct')
  pairs=[('Área',item['area']),('Disciplina',item['discipline']),('Tópico',item['discipline']+' · '+item['topic']if item['topic']else''),('Assunto',item['discipline']+' · '+item['subject']if item['subject']else''),('Habilidade',item['area']+' · '+item['skill']if item['skill']else'')]
  for kind,name in pairs:
   if not name:continue
   g=groups[kind].setdefault(name,dict(name=name,correct=0,errors=0,marked=0,total=0));g['total']+=1
   if value in(0,1)and value is not None:g['marked']+=1;g['correct']+=int(value);g['errors']+=int(value==0)
 unknown=sum(k.startswith('questao:')and int(k.split(':')[1])not in known and v.get('correct')is not None for k,v in metrics.items())
 return dict(exam=exam['title'],version=exam['version'],color=exam['color'],groups={k:list(v.values())for k,v in groups.items()},unclassified=unknown,languageMissing=unknown_language>0,notice='Calculado apenas a partir das questões informadas e do mapa selecionado. Questões vazias não contam como erro. Não substitui os totais enviados diretamente.')

def handle(app,c,user,path,method,data,query,start,HTTPError):
 if not _exam_metadata.can_edit(user):raise HTTPError(403,'Cadastro de simulados exclusivo da equipe.')
 if path=='/api/exams'and method=='GET':
  rows=app.db.execute(c,'SELECT id,owner_id,title,applied_on,color,area,version,updated_at FROM hmay_exams ORDER BY applied_on DESC,title LIMIT 500').fetchall()
  return app.reply(start,200,dict(exams=[{**dict(r),'canEdit':_exam_metadata.can_edit(user)}for r in rows]))
 if path=='/api/exams/inspect'and method=='POST':return app.reply(start,200,inspect(data))
 if path=='/api/exams/template'and method=='POST':
  lo=F.count_value(data.get('first',1),'Primeira questão');hi=F.count_value(data.get('last',90),'Última questão')
  if lo is None or hi is None or not 1<=lo<=hi<=180:raise ValueError('Escolha um intervalo entre 1 e 180.')
  blob,mime=T.export(HEADERS,[[n]+['']*7 for n in range(lo,hi+1)],kind=data.get('format','xlsx'),guide=[['Uma linha por questão','QUESTÃO e DISCIPLINA são necessárias. Tópico, assunto e habilidade podem ser complementados depois.'],['Numeração','Mantenha a numeração original: por exemplo 91 a 135 para o modelo enviado.'],['Área','LC, CH, CN ou MT. A habilidade é identificada junto com a área.'],['Língua estrangeira','Preencha Inglês/Espanhol nas versões alternativas da mesma questão.'],['Separação de arquivos','Este arquivo é o mapa da prova. Os resultados dos alunos são importados separadamente na aba Desempenho.']])
  return app.reply(start,200,blob,mime,[('Content-Disposition','attachment; filename="Modelo_simulado.'+data.get('format','xlsx')+'"')])
 if path not in('/api/exams/preview','/api/exams/confirm')or method!='POST':raise HTTPError(404,'Página não encontrada.')
 result,summary,payload=prepared(app,c,user,data)
 if path.endswith('/preview'):
  stamp=int(time.time());return app.reply(start,200,dict(exam=result,summary=summary,token=str(stamp)+'.'+F.sign(app,payload,stamp)))
 try:t,sig=data.get('token','').split('.');stamp=int(t)
 except (ValueError,AttributeError):raise ValueError('Confira o mapa antes de confirmar.')
 import hmac
 if not 0<=time.time()-stamp<=1800 or not hmac.compare_digest(sig,F.sign(app,payload,stamp)):raise HTTPError(409,'Arquivo ou mapa alterado. Refaça a conferência.')
 at=P.now().isoformat()
 import disciplines_catalog as _DC;_DC.canon_items(app,c,result['items'])  # === DISCIPLINES CATALOG V3.12.0 ===
 if result['id']:
  cur=app.db.execute(c,'UPDATE hmay_exams SET items=?,area=?,version=version+1,updated_at=? WHERE id=? AND version=?',(enc(result['items']),result['area'],at,result['id'],result['version']))
  if cur.rowcount!=1:raise HTTPError(409,'O mapa foi alterado por outra pessoa. Refaça a conferência.')
 else:
  result['id']=P.uid();identity=hashlib.sha256(enc([F.norm(result['title']),result['applied_on'],F.norm(result['color'])]).encode()).hexdigest()
  _exam_metadata.release_obsolete_key(app, c, identity)
  cur=app.db.execute(c,'INSERT INTO hmay_exams(id,identity_key,owner_id,title,applied_on,color,area,items,version,updated_at) VALUES (?,?,?,?,?,?,?,?,?,?) ON CONFLICT(identity_key) DO NOTHING',(result['id'],identity,user['id'],result['title'],result['applied_on'],result['color'],result['area'],enc(result['items']),1,at))
  if cur.rowcount!=1:raise HTTPError(409,'Outro cadastro criou este mapa. Refaça a conferência.')
 app.event(c,user,user['id'],'exam_catalogue_import')
 return app.reply(start,200,dict(ok=True,id=result['id'],summary=summary))

import exam_metadata as _exam_metadata
