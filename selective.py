"""Selective result import and template construction. No auto enrolment or planning changes."""
from __future__ import annotations
import base64, csv, io, json, re
import performance as F
import templates_v23 as T

AREAS=['LC','CH','CN','MT']
GENERAL=[('NOME','Identificação',True),('LOGIN','Identificação',False),('TURMA','Identificação',False),('COR DA PROVA','Identificação',False),('TIPO de prova','Identificação',True),('data de aplicação','Identificação',True),('L. estrangeira selecionada','Identificação',False),('Ranking','Notas e totais',False),('Nota TRI','Notas e totais',False),('Bonificação','Notas e totais',False),('Nota com bonificação','Notas e totais',False),('Acertos totais','Notas e totais',False),('Acertos em Linguagens','Notas e totais',False),('Acertos em Humanas','Notas e totais',False),('Acertos em Natureza','Notas e totais',False),('Acertos em Matemática','Notas e totais',False),('Nota TRI Linguagens','Notas e totais',False),('Nota TRI Humanas','Notas e totais',False),('Nota TRI Natureza','Notas e totais',False),('Nota TRI Matemática','Notas e totais',False),('Nota de redação','Notas e totais',False)]
SUBJECTS=['Língua estrangeira']+F.BASE_SUBJECTS
BASE_CANON=['NOME','LOGIN','TURMA','COR DA PROVA','TIPO','data','L.E','RANKING','TRI','BONIFICAÇÃO','TRI 10%','Acerto','Lc','Ch','Cn','Mt','TRI LING','TRI HUM','TRI NAT','TRI MAT','RED']
DISPLAY={F.norm(c):g[0]for c,g in zip(BASE_CANON,GENERAL)}
CANON={F.norm(g[0]):c for c,g in zip(BASE_CANON,GENERAL)}
for c in BASE_CANON:CANON[F.norm(c)]=c
EXTRA_ALIASES={'nome do aluno':'NOME','aluno':'NOME','tipo':'TIPO','atividade':'TIPO','avaliacao':'TIPO','simulado':'TIPO','simulado ou atividade':'TIPO','data':'data','data aplicacao':'data','lingua estrangeira':'L.E','lingua estrangeira selecionada':'L.E','l.e.':'L.E','le':'L.E','nota tri linguagens':'TRI LING','nota tri humanas':'TRI HUM','nota tri natureza':'TRI NAT','nota tri matematica':'TRI MAT','nota de redacao':'RED','cor':'COR DA PROVA','tipo de prova':'TIPO','cor da prova':'COR DA PROVA'}
CANON.update(EXTRA_ALIASES)

def fix_header(s):
 s=str(s or '').strip()
 # Repair only reversible mojibake. Never modifies student names or cell values.
 for _ in range(2):
  candidates=[s]
  for enc in ('cp1252','latin1'):
   try:candidates.append(s.encode(enc).decode('utf-8'))
   except (UnicodeError,LookupError):pass
  score=lambda x:x.count('Ã')+x.count('Â')+x.count('�')+x.count('â€')
  best=min(candidates,key=score)
  if best==s:break
  s=best
 return s

def canonical(h):
 h=fix_header(h);n=F.norm(h)
 if n.startswith('_'):raise ValueError('Cabeçalhos iniciados por _ são reservados ao sistema.')
 if n in CANON:return CANON[n]
 m=re.fullmatch(r'acertos\s+(?:hab(?:ilidade)?\.?\s*)(\d{1,2})',n)
 if m:
  num=int(m[1])
  if not 1<=num<=30:raise ValueError('Use habilidades de 01 a 30.')
  return f'Acertos Hab {num:02d}'
 m=re.fullmatch(r'acerto\s*/\s*erro\s+(?:questao|q)\s*0*(\d{1,3})',n)
 if m:
  num=int(m[1])
  if not 1<=num<=180:raise ValueError('Use questões de 01 a 180.')
  return f'Acerto/erro questão {num:02d}'
 p=re.split(r'\s*[-–—]\s*',h,maxsplit=1)
 if len(p)==2 and F.norm(p[0])in('acertos','questoes','total de questoes'):
  label=F.text(p[1],150);labels={F.norm(s):s for s in SUBJECTS}
  label=labels.get(F.norm(label),label)
  if not label:raise ValueError('Informe o nome da disciplina depois do hífen.')
  return ('Acertos'if F.norm(p[0])=='acertos'else'Questões')+' - '+label
 if n in ('area das habilidades','area habilidade','area de conhecimento','area'):return 'ÁREA DAS HABILIDADES'
 return h

def label(h):return DISPLAY.get(F.norm(h),h)
def fields():
 return [dict(name=n,group=g,required=req)for n,g,req in GENERAL]+[dict(name='Acertos - '+s,group='Disciplinas',required=False)for s in SUBJECTS]+[dict(name=f'Acertos Hab {i:02d}',group='Habilidades',required=False)for i in range(1,31)]+[dict(name=f'Acerto/erro questão {i:02d}',group='Questões',required=False)for i in range(1,181)]

def available_fields(app,c,user):
 result=fields();seen={F.norm(x['name'])for x in result}
 ids=[x['id']for x in F.allowed_accounts(app,c,user)]
 for offset in range(0,len(ids),500):
  group=ids[offset:offset+500]
  rows=app.db.execute(c,'SELECT metrics FROM hmay_performance WHERE user_id IN ('+','.join('?'for _ in group)+')',tuple(group)).fetchall()
  for row in rows:
   for key,m in json.loads(row['metrics']).items():
    if key.startswith(('habilidade:','questao:')):continue
    name='Acertos - '+m['name']
    if F.norm(name)not in seen:result.append(dict(name=name,group='Disciplinas',required=False));seen.add(F.norm(name))
 return result

def matrix(data):
 try:blob=base64.b64decode(data.get('file',''),validate=True)
 except (ValueError,TypeError):raise ValueError('Arquivo inválido.')
 return (*F.load_matrix(F.text(data.get('filename',''),200),blob,F.text(data.get('sheet',''),100)),blob)

def inspect(data):
 rows,epoch,sheets,sheet,blob=matrix(data)
 if not rows:raise ValueError('Planilha vazia.')
 headers=[str(x or '')for x in rows[0]]
 while headers and not headers[-1]:headers.pop()
 if not headers:raise ValueError('Cabeçalhos ausentes.')
 columns=[]
 for i,h in enumerate(headers):
  try:target=label(canonical(h))if h.strip()else ''
  except ValueError:target=''
  columns.append(dict(index=i,header=h,suggested=target,repaired=fix_header(h)!=h,examples=[str(r[i])[:100]for r in rows[1:5]if len(r)>i and r[i] is not None]))
 return dict(columns=columns,sheets=sheets,sheet=sheet,rows=max(0,len(rows)-1),fields=fields())

def item_value(v,h):
 if v is None or str(v).strip()=='':return None
 n=F.norm(str(v))
 if not isinstance(v,bool) and re.fullmatch(r'(?:0|1)(?:\.0+)?',n):return int(float(n))
 raise ValueError(h+': use somente 1 para acerto, 0 para erro ou deixe vazio (não informado).')

def parse(data):
 rows,epoch,sheets,sheet,blob=matrix(data)
 if not rows:raise ValueError('Planilha vazia.')
 raw=[str(x or '')for x in rows[0]]
 while raw and not raw[-1]:raw.pop()
 mapping=data.get('columnMapping')
 if mapping is not None:
  if not isinstance(mapping,dict)or len(mapping)>F.MAX_COLS:raise ValueError('Seleção de campos inválida.')
  if any(not str(k).isdigit()or not 0<=int(k)<len(raw)for k in mapping):raise ValueError('A seleção inclui coluna inexistente.')
  selected=[(i,canonical(mapping[str(i)]))for i in range(len(raw))if str(i)in mapping and isinstance(mapping[str(i)],str)and mapping[str(i)].strip()]
 else:selected=[(i,canonical(h))for i,h in enumerate(raw)]
 if not selected:raise ValueError('Selecione os campos que deseja importar.')
 names=[h for _,h in selected]
 if any(not h for h in names)or len({F.norm(x)for x in names})!=len(names):raise ValueError('Dois campos foram vinculados à mesma informação. Deixe somente um ou ignore a coluna repetida.')
 if not all(x in names for x in ('NOME','TIPO','data')):raise ValueError('Selecione NOME, TIPO de prova e data de aplicação.')
 skills={i:h for i,h in selected if h.startswith('Acertos Hab ')}
 questions={i:h for i,h in selected if h.startswith('Acerto/erro questão ')}
 special=set(skills)|set(questions)
 # Core parser continues handling account identity and all ordinary subject columns.
 ordinary=[(i,h)for i,h in selected if i not in special]
 out=io.StringIO();writer=csv.writer(out,delimiter=';');writer.writerow([h for i,h in ordinary])
 details=[]
 for line,row in enumerate(rows[1:],2):
  if not any(v not in(None,'')for v in row):continue
  if mapping is None and any(v not in(None,'')for v in row[len(raw):]):raise ValueError('Há dados em coluna sem cabeçalho.')
  def at(i):return row[i]if i<len(row)else None
  converted=[]
  for i,h in ordinary:
   v=at(i)
   if h=='data' and v not in(None,''):v=F.date_value(v,epoch)
   converted.append(v)
  writer.writerow(converted)
  area=F.text(data.get('skillArea',''),10).upper()
  for i,h in ordinary:
   if h=='ÁREA DAS HABILIDADES' and at(i)not in(None,''):area=F.text(at(i),10).upper()
  if skills and area not in AREAS:raise ValueError('Selecione a área das habilidades (LC, CH, CN ou MT). H01 de áreas diferentes não é a mesma habilidade.')
  metrics={}
  for i,h in skills.items():
   num=int(h.rsplit(' ',1)[-1]);metrics[f'habilidade:{area}:h{num:02d}']=dict(name=f'{area} · H{num:02d}',correct=F.count_value(at(i),h),total=None)
  for i,h in questions.items():
   num=int(h.rsplit(' ',1)[-1])
   try:v=item_value(at(i),h)
   except ValueError as exc:raise ValueError(f'Linha {line} · {exc}')from exc
   metrics[f'questao:{num:03d}']=dict(name=f'Questão {num:02d}',correct=v,total=1 if v is not None else None)
  details.append((line,metrics))
 packed=dict(filename='selecao.csv',file=base64.b64encode(out.getvalue().encode()).decode())
 parsed=F._legacy_parse_file(packed)
 for rec,(line,metrics)in zip(parsed['records'],details):
  rec['line']=line;rec['metrics'].update(metrics)
  if data.get('_validatedExam'):
   ex=data['_validatedExam'];rec['metadata']['_exam_id']=ex['id'];rec['metadata']['_exam_version']=ex['version']
   # Explicit selection may supply missing metadata, never a conflicting one.
   for k,v in [('COR DA PROVA',ex['color'])]:
    previous=rec['metadata'].get(k)
    if previous and F.norm(previous)!=F.norm(v):raise ValueError('A cor da prova do aluno difere do simulado selecionado.')
    if v:rec['metadata'][k]=v
   if F.norm(rec['activity'])!=F.norm(ex['title'])or rec['date']!=ex['applied_on']:raise ValueError('O nome e a data da atividade devem coincidir com o simulado selecionado.')
 import hashlib
 parsed.update(hash=hashlib.sha256(blob).hexdigest(),headers=names,sheets=sheets,sheet=sheet,filename=data['filename'])
 # Only actual disciplines enter this list; skill/item results have separate tables.
 parsed['selection']=names
 return parsed

def signature(data):
 return dict(columnMapping=data.get('columnMapping'),skillArea=data.get('skillArea',''),examId=data.get('examId',''),examVersion=data.get('_validatedExam',{}).get('version'))

def template(data):
 chosen=data.get('fields',[])
 if not isinstance(chosen,list)or not 1<=len(chosen)<=300:raise ValueError('Selecione até 300 campos.')
 headers=[label(canonical(F.text(x,200)))for x in chosen]
 normalized=[canonical(x)for x in headers]
 if len(set(normalized))!=len(normalized):raise ValueError('Há campos repetidos no modelo.')
 if not all(x in normalized for x in ('NOME','TIPO','data')):raise ValueError('O modelo deve conter Nome, Tipo de prova e Data de aplicação.')
 guide=[['Identificação','NOME, TIPO de prova e data de aplicação são obrigatórios. LOGIN ajuda a distinguir homônimos.'],['Importação por partes','Colunas não selecionadas e células vazias não apagam informações existentes.'],['Zero e vazio','0 é um resultado conhecido; vazio significa não informado.'],['Acertos - Disciplina','Inteiro não negativo. Acrescente novas disciplinas com esse prefixo.'],['Questões - Disciplina','Opcional: número total de questões daquela disciplina.'],['Acertos Hab 01 a 30','Na importação, selecione LC, CH, CN ou MT. Pode enviar cada área em um lote separado.'],['Questões 01 a 180','1 = acerto; 0 = erro; vazio = não informado. Não coloque a letra marcada pelo aluno.'],['Bonificação','Informação descritiva: informe se é percentual ou pontos, por exemplo 10%. Não recalcula a nota TRI.'],['Data','Preencha dd/mm/aaaa ou uma data válida do Excel.'],['Codificação CSV','Prefira XLSX. CSV é exportado como UTF-8 com BOM; selecione UTF-8 ao abrir no Excel.']]
 return T.export(headers,kind=data.get('format','xlsx'),guide=guide)

def route(app,c,user,path,method,data,query,start,HTTPError):
 if path in ('/api/performance/fields','/api/performance/inspect','/api/performance/template-selected'):
  if user['role']not in('master','coordenador'):raise HTTPError(403,'Área exclusiva do Master e coordenação.')
  if path.endswith('/fields')and method=='GET':return app.reply(start,200,dict(fields=available_fields(app,c,user),areas=AREAS))
  if path.endswith('/inspect')and method=='POST':return app.reply(start,200,{**inspect(data),'fields':available_fields(app,c,user)})
  if path.endswith('/template-selected')and method=='POST':
   blob,mime=template(data);ext=data.get('format','xlsx')
   return app.reply(start,200,blob,mime,[('Content-Disposition',f'attachment; filename="Modelo_seletivo.{ext}"')])
  raise HTTPError(405,'Método não permitido.')
 # Do not trust a client-provided internal exam object.
 data.pop('_validatedExam',None)
 if path in ('/api/performance/preview','/api/performance/confirm')and data.get('examId'):
  import exams
  if user['role']not in('master','coordenador'):raise HTTPError(403,'Importação restrita à equipe.')
  data['_validatedExam']=exams.get_exam(app,c,str(data['examId']))
 return None

def guard_merge(old_metadata,new_metadata):
 old_id=old_metadata.get('_exam_id');new_id=new_metadata.get('_exam_id')
 if old_id and new_id and old_id!=new_id:raise ValueError('A atividade já está vinculada a outro simulado. Não misture cadernos diferentes no mesmo resultado.')
 a=old_metadata.get('COR DA PROVA');b=new_metadata.get('COR DA PROVA')
 if a and b and F.norm(a)!=F.norm(b):raise ValueError('A atividade já possui outra cor de prova. Use uma atividade distinta para outro caderno.')

def decorate(app,c,user,records):
 import exams
 cache={}
 for rec in records:
  eid=rec['metadata'].get('_exam_id')
  if not eid:continue
  if eid not in cache:
   try:cache[eid]=exams.get_exam(app,c,eid)
   except ValueError:cache[eid]=None
  if cache[eid]:rec['analysis']=exams.analyse(cache[eid],rec['metrics'],rec['metadata'])
 return records
