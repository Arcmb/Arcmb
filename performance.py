"""Desempenho: XLSX/CSV com disciplinas por cabeçalho, prévia e confirmação.
Não infere dificuldade, não cadastra contas e não modifica a rotina na importação.
"""
from __future__ import annotations
import base64, csv, datetime as dt, hashlib, hmac, io, json, math, posixpath, re, time, unicodedata, zipfile
from defusedxml import ElementTree as ET
import planner as P

MAX_FILE=3_000_000
MAX_ROWS=5000
MAX_COLS=300
MAX_CELLS=300000
MAIN='http://schemas.openxmlformats.org/spreadsheetml/2006/main'
REL='http://schemas.openxmlformats.org/officeDocument/2006/relationships'
BASE_HEADERS=['NOME','TURMA','TIPO','data','L.E','RANKING','TRI','TRI 10%','Acerto','Lc','Ch','Cn','Mt','TRI LING','TRI HUM','TRI NAT','TRI MAT','RED']
BASE_SUBJECTS=['Português','Literatura','Artes','Linguagem corporal','História','Geografia','Filosofia','Sociologia','Química','Física','Biologia','Matemática']
ALIASES={'nome':'name','nome do aluno':'name','aluno':'name','turma':'class','tipo':'activity','simulado ou atividade':'activity','simulado':'activity','atividade':'activity','avaliacao':'activity','data':'date','data de aplicacao':'date','data aplicacao':'date','login':'login','usuario':'login'}

def norm(v):
    return ' '.join(''.join(c for c in unicodedata.normalize('NFKD',str(v or '')) if not unicodedata.combining(c)).casefold().split())
def text(v,limit=250):
    s=str(v if v is not None else '').strip()
    if len(s)>limit:raise ValueError('Texto excede o limite permitido.')
    return s

def load_matrix(filename,blob,sheet=''):
    if not 0<len(blob)<=MAX_FILE:raise ValueError('Use arquivo de até 3 MB.')
    if filename.lower().endswith('.csv'):
        try:s=blob.decode('utf-8-sig')
        except UnicodeError:s=blob.decode('cp1252')
        try:delimiter=csv.Sniffer().sniff(s[:8192],delimiters=';,\t').delimiter
        except csv.Error:delimiter=';'
        rows=[]
        for r in csv.reader(io.StringIO(s),delimiter=delimiter):
            if len(rows)>MAX_ROWS:raise ValueError('Limite de 5.000 registros por arquivo.')
            if len(r)>MAX_COLS:raise ValueError('Limite de 300 colunas.')
            rows.append(r)
        if sum(len(r)for r in rows)>MAX_CELLS:raise ValueError('Divida a planilha em lotes menores: limite de 300.000 células.')
        return rows,False,[],''
    if not filename.lower().endswith('.xlsx'):raise ValueError('Use .xlsx ou .csv. Arquivos .xls e com macros não são aceitos.')
    try:
        with zipfile.ZipFile(io.BytesIO(blob)) as z:
            infos=z.infolist()
            if len(infos)>2000 or sum(i.file_size for i in infos)>25_000_000:raise ValueError('Arquivo descompactado excede 25 MB.')
            if len({i.filename for i in infos})!=len(infos):raise ValueError('Pacote com arquivos duplicados.')
            if any(i.flag_bits&1 or 'vbaproject' in i.filename.lower() or i.filename.startswith('xl/externalLinks/') for i in infos):raise ValueError('Não são aceitos arquivos protegidos, macros ou vínculos externos.')
            def xml(path):
                raw=z.read(path)
                return ET.fromstring(raw,forbid_dtd=True,forbid_entities=True,forbid_external=True)
            workbook=xml('xl/workbook.xml');props=workbook.find('{'+MAIN+'}workbookPr');epoch1904=props is not None and props.get('date1904')in('1','true')
            rels={x.get('Id'):x for x in xml('xl/_rels/workbook.xml.rels')}
            sheets=list(workbook.find('{'+MAIN+'}sheets'))
            options=[x.get('name')for x in sheets]
            chosen=next((x for x in sheets if x.get('name')==sheet),None) if sheet else sheets[0]
            if chosen is None:raise ValueError('Aba não encontrada.')
            rel=rels.get(chosen.get('{'+REL+'}id'))
            if rel is None or rel.get('TargetMode')=='External':raise ValueError('Referência de aba inválida.')
            path=posixpath.normpath(posixpath.join('xl',rel.get('Target',''))) if not rel.get('Target','').startswith('/') else rel.get('Target')[1:]
            if not path.startswith('xl/worksheets/')or '..'in path:raise ValueError('Caminho de aba inválido.')
            strings=[]
            if 'xl/sharedStrings.xml'in z.namelist():
                strings=[''.join(x.itertext()) for x in xml('xl/sharedStrings.xml')]
            rows=[];seen_rows=set();cells=0
            sheet_xml=xml(path)
            for row in sheet_xml.findall('.//{'+MAIN+'}sheetData/{'+MAIN+'}row'):
                rn=int(row.get('r',len(rows)+1))
                if rn<1 or rn>MAX_ROWS+1 or rn in seen_rows:raise ValueError('Limite de 5.000 registros ou linha duplicada.')
                seen_rows.add(rn)
                values={}
                for cell in row:
                    if cell.tag!='{'+MAIN+'}c':continue
                    cells+=1
                    if cells>MAX_CELLS:raise ValueError('Divida a planilha em lotes menores: limite de 300.000 células.')
                    ref=cell.get('r','');match=re.fullmatch(r'([A-Z]+)([1-9][0-9]*)',ref)
                    if not match or int(match[2])!=rn:raise ValueError('Referência de célula inválida.')
                    index=0
                    for c in match[1]:index=index*26+ord(c)-64
                    if not 1<=index<=MAX_COLS or index in values:raise ValueError('Limite de 300 colunas ou célula duplicada.')
                    value=cell.find('{'+MAIN+'}v');kind=cell.get('t')
                    if cell.find('{'+MAIN+'}f')is not None and (value is None or value.text is None):raise ValueError(f'{ref}: fórmula sem resultado salvo. Abra no Excel, recalcule e salve ou cole como valores.')
                    if kind=='e':raise ValueError(f'{ref}: corrija o erro da fórmula antes de importar.')
                    if kind=='inlineStr':v=''.join(cell.find('{'+MAIN+'}is').itertext()) if cell.find('{'+MAIN+'}is')is not None else ''
                    elif value is None:v=None
                    elif kind=='s':v=strings[int(value.text)]
                    else:v=value.text
                    if v is not None and len(str(v))>20000:raise ValueError(f'{ref}: texto excessivo.')
                    values[index]=v
                if not any(v not in(None,'')for v in values.values()):continue
                while len(rows)<rn:rows.append([])
                rows[rn-1]=[values.get(i)for i in range(1,max(values,default=0)+1)]
            return rows,epoch1904,options,chosen.get('name')
    except ValueError:raise
    except Exception as ex:raise ValueError('Não foi possível ler o XLSX com segurança. Salve novamente como .xlsx.')from ex

def date_value(v,epoch1904=False):
    s=text(v,40)
    try:
        if re.fullmatch(r'[0-9]+(?:\.0+)?',s):
            n=int(float(s))
            if not 1<=n<=2950000:raise ValueError()
            if not epoch1904 and n==60:raise ValueError()
            epoch=dt.date(1904,1,1)if epoch1904 else dt.date(1899,12,30 if n>=61 else 31)
            d=epoch+dt.timedelta(days=n)
        else:
            try:d=dt.date.fromisoformat(s[:10])
            except ValueError:d=dt.datetime.strptime(s,'%d/%m/%Y').date()
        if d.year<1900 or d.year>2100:raise ValueError()
        return d.isoformat()
    except (ValueError,OverflowError):raise ValueError('Data inválida. Use dd/mm/aaaa ou uma data válida do Excel.')

def count_value(v,label):
    if v is None or isinstance(v,str)and not v.strip():return None
    if isinstance(v,bool):raise ValueError(label+': use um número inteiro não negativo.')
    s=str(v).strip().replace(',','.')
    if not re.fullmatch(r'\+?\d+(?:\.0+)?',s):raise ValueError(label+': use um número inteiro não negativo; vazio significa não informado.')
    n=int(float(s))
    if not 0<=n<=100000:raise ValueError(label+': valor fora do limite de 0 a 100.000.')
    return n

def parse_file(data):
    try:blob=base64.b64decode(data.get('file',''),validate=True)
    except Exception:raise ValueError('Arquivo codificado inválido.')
    filename=text(data.get('filename',''),200)
    matrix,epoch1904,sheets,sheet=load_matrix(filename,blob,text(data.get('sheet',''),100))
    if not matrix:raise ValueError('Planilha vazia.')
    headers=[text(x,200)for x in matrix[0]]
    while headers and not headers[-1]:headers.pop()
    if not headers or len(headers)>MAX_COLS:raise ValueError('Cabeçalhos ausentes ou excessivos.')
    if any(not h for h in headers):raise ValueError('Toda coluna usada precisa de cabeçalho na primeira linha.')
    if len({norm(h)for h in headers})!=len(headers):raise ValueError('Há colunas repetidas após normalizar acentos, espaços e maiúsculas.')
    ids={};definitions={};metric_cols={};extras=[]
    for i,h in enumerate(headers):
        nh=norm(h)
        if nh in ALIASES:
            key=ALIASES[nh]
            if key in ids:raise ValueError('Mais de uma coluna para '+key+'.')
            ids[key]=i;continue
        pieces=re.split(r'\s+[-–—]\s+',h,maxsplit=1)
        if len(pieces)==2 and norm(pieces[0])in('acertos','questoes','total de questoes'):
            label=text(pieces[1],150)
            if not label:raise ValueError('Informe o nome da disciplina após o hífen.')
            key=norm(label)
            if key in ('__proto__','constructor','prototype'):raise ValueError('Nome de disciplina inválido.')
            field='correct'if norm(pieces[0])=='acertos'else'total'
            if (key,field)in metric_cols.values():raise ValueError('Coluna de disciplina repetida: '+label)
            metric_cols[i]=(key,field);definitions.setdefault(key,label)
        else:extras.append(i)
    if not all(k in ids for k in('name','activity','date')):raise ValueError('Inclua NOME, TIPO (ou Atividade) e data na primeira linha.')
    records=[];errors=[];unique={};students={}
    for line,row in enumerate(matrix[1:],2):
        if not any(v not in(None,'')for v in row):continue
        try:
            if len(row)>len(headers)and any(v not in(None,'')for v in row[len(headers):]):raise ValueError('Há dados em coluna sem cabeçalho.')
            row=list(row)+[None]*max(0,len(headers)-len(row))
            name=text(row[ids['name']],150);activity=text(row[ids['activity']],200)
            if not name or not activity:raise ValueError('Nome e atividade são obrigatórios.')
            applied=date_value(row[ids['date']],epoch1904)
            klass=text(row[ids['class']],150)if'class'in ids else''
            login=text(row[ids['login']],40).lower()if'login'in ids else''
            student_key=hashlib.sha256(json.dumps([norm(name),norm(klass),login],ensure_ascii=False).encode()).hexdigest()[:24]
            meta={headers[i]:row[i]for i in extras if row[i]not in(None,'')}
            meta['TURMA']=klass
            metrics={key:{'name':label,'correct':None,'total':None}for key,label in definitions.items()}
            for i,(key,field)in metric_cols.items():metrics[key][field]=count_value(row[i],headers[i])
            for metric in metrics.values():
                if metric['correct']is not None and metric['total']is not None and metric['correct']>metric['total']:raise ValueError('Acertos maiores que o total de questões em '+metric['name']+'.')
            rec=dict(line=line,student=student_key,name=name,activity=activity,activityKey=norm(activity),date=applied,metrics=metrics,metadata=meta)
            dup=(student_key,rec['activityKey'],applied)
            if dup in unique:raise ValueError('Aluno, atividade e data repetidos no arquivo (linha '+str(unique[dup])+'). Separe homônimos com LOGIN.')
            unique[dup]=line;students.setdefault(student_key,dict(key=student_key,name=name,group=klass,login=login))
            records.append(rec)
        except ValueError as ex:
            errors.append(f'Linha {line}: {ex}')
            if len(errors)>=30:break
    if errors:raise ValueError('\n'.join(errors))
    if not records:raise ValueError('Nenhum registro. Os cabeçalhos podem permanecer no modelo, mas é necessário ao menos um aluno e atividade para importar.')
    return dict(headers=headers,subjects=[dict(key=k,name=v)for k,v in definitions.items()],records=records,students=list(students.values()),sheets=sheets,sheet=sheet,hash=hashlib.sha256(blob).hexdigest(),filename=filename)

def schema(db,c):
    db.execute(c,'CREATE TABLE IF NOT EXISTS hmay_performance (id TEXT PRIMARY KEY, user_id TEXT NOT NULL REFERENCES hmay_users(id), activity_key TEXT NOT NULL, activity TEXT NOT NULL, applied_on TEXT NOT NULL, metrics TEXT NOT NULL, metadata TEXT NOT NULL, version INTEGER NOT NULL, updated_at TEXT NOT NULL, UNIQUE(user_id, activity_key, applied_on))')
    db.execute(c,'CREATE INDEX IF NOT EXISTS hmay_perf_user_date ON hmay_performance(user_id,applied_on)')

def allowed_accounts(app,c,user):
    fields='id,username,name,role,active,must_change'
    if user['role']=='master':rows=app.db.execute(c,f'SELECT {fields} FROM hmay_users WHERE active=1 ORDER BY name').fetchall()
    elif user['role']=='coordenador':rows=app.db.execute(c,f"SELECT {fields} FROM hmay_users WHERE active=1 AND (role IN ('user','aluno') OR id=?) ORDER BY name",(user['id'],)).fetchall()
    else:rows=[]
    return [app.user_public(x)for x in rows]

def merged_metrics(old,new,replace):
    result=json.loads(json.dumps(old))
    conflicts=0
    for key,metric in new.items():
        dest=result.setdefault(key,dict(name=metric['name'],correct=None,total=None))
        for f in('correct','total'):
            val=metric[f]
            if val is None:continue
            if dest.get(f)is not None and dest[f]!=val:
                conflicts+=1
                if not replace:continue
            dest[f]=val
        if dest.get('correct')is not None and dest.get('total')is not None and dest['correct']>dest['total']:raise ValueError('O resultado final teria mais acertos que questões em '+dest['name']+'. Corrija os valores ou revise a opção de substituir.')
    return result,conflicts

def prepare_import(app,c,user,data):
    parsed=parse_file(data);accounts=allowed_accounts(app,c,user);byid={a['id']:a for a in accounts}
    mapping=data.get('mapping',{})
    if not isinstance(mapping,dict):raise ValueError('Vínculos inválidos.')
    known_keys={s['key']for s in parsed['students']}
    if any(k not in known_keys for k in mapping):raise ValueError('Há vínculos que não pertencem a este arquivo.')
    resolved={};unresolved=0
    for s in parsed['students']:
        selected=mapping.get(s['key'])
        if selected is None:
            candidates=[a for a in accounts if (a['username']==s['login']if s['login']else norm(a['name'])==norm(s['name']))]
            selected=candidates[0]['id']if len(candidates)==1 else ''
        if selected and selected not in byid:raise ValueError('Vínculo não autorizado ou conta desativada.')
        resolved[s['key']]=selected
        s['selected']=selected
        if not selected:unresolved+=1
    if type(data.get('replace',False))is not bool:raise ValueError('Opção de substituição inválida.')
    replace=data.get('replace',False);prepared=[];snapshots=[];seen=set();conflicts=0
    # Fetch existing results in bounded groups instead of one SQL query per row.
    existing={};targets=sorted({x for x in resolved.values()if x})
    dates=[r['date']for r in parsed['records']]
    for offset in range(0,len(targets),800):
        group=targets[offset:offset+800];placeholders=','.join('?'for _ in group)
        sql='SELECT * FROM hmay_performance WHERE user_id IN ('+placeholders+') AND applied_on>=? AND applied_on<=?'
        rows=app.db.execute(c,sql,(*group,min(dates),max(dates))).fetchall()
        for x in rows:existing[(x['user_id'],x['activity_key'],x['applied_on'])]=x
    # A preview is read-only. The table is installed by the release initializer.
    for r in parsed['records']:
        target=resolved[r['student']]
        if not target:continue
        key=(target,r['activityKey'],r['date'])
        if key in seen:raise ValueError('Dois registros foram vinculados à mesma conta, atividade e data.')
        seen.add(key)
        row=existing.get(key)
        old=json.loads(row['metrics'])if row else{}
        metrics,n=merged_metrics(old,r['metrics'],replace);conflicts+=n
        metadata=json.loads(row['metadata'])if row else{}
        for k,v in r['metadata'].items():
            if v in(None,''):continue
            if k in metadata and metadata[k]!=v:
                conflicts+=1
                if not replace:continue
            metadata[k]=v
        changed=not row or metrics!=old or metadata!=json.loads(row['metadata'])
        prepared.append(dict(target=target,record=r,metrics=metrics,metadata=metadata,existing=dict(row)if row else None,changed=changed))
        snapshots.append((key,row['version']if row else 0))
    payload=json.dumps([user['id'],parsed['hash'],parsed['sheet'],resolved,replace,snapshots],ensure_ascii=False,sort_keys=True,separators=(',',':'))
    return parsed,accounts,resolved,prepared,conflicts,unresolved,payload

def sign(app,payload,stamp):return hmac.new(app.secret.encode(),(str(stamp)+'\n'+payload).encode(),'sha256').hexdigest()

def handle(app,c,user,path,method,data,query,start,HTTPError):
    db=app.db
    if path=='/api/performance'and method=='GET':
        target=query.get('user',[user['id']])[0];app.require_target(user,target,c)
        rows=db.execute(c,'SELECT id,activity,applied_on,metrics,metadata,version,updated_at FROM hmay_performance WHERE user_id=? ORDER BY applied_on DESC,activity LIMIT 500',(target,)).fetchall()
        total=db.execute(c,'SELECT COUNT(*) AS n FROM hmay_performance WHERE user_id=?',(target,)).fetchone()['n']
        return app.reply(start,200,dict(records=[{**dict(r),'metrics':json.loads(r['metrics']),'metadata':json.loads(r['metadata'])}for r in rows],total=total))
    if user['role']not in('master','coordenador'):raise HTTPError(403,'A importação em lote é exclusiva do Master e da coordenação.')
    if path=='/api/performance/template'and method=='GET':
        names=dict((norm(n),n)for n in BASE_SUBJECTS)
        accounts=allowed_accounts(app,c,user)
        for a in accounts:
            rows=db.execute(c,'SELECT metrics FROM hmay_performance WHERE user_id=?',(a['id'],)).fetchall()
            for row in rows:
                for k,v in json.loads(row['metrics']).items():names.setdefault(k,v['name'])
        headers=BASE_HEADERS+['Acertos - '+n for n in names.values()]
        if len(headers)>MAX_COLS:raise ValueError('O catálogo excede 300 colunas. Divida o modelo por grupo de disciplinas.')
        out=io.StringIO();writer=csv.writer(out,delimiter=';',lineterminator='\r\n');writer.writerow(headers)
        return app.reply(start,200,'\ufeff'+out.getvalue(),'text/csv; charset=utf-8',[('Content-Disposition','attachment; filename="Modelo_disciplinas_dinamicas.csv"')])
    if path not in('/api/performance/preview','/api/performance/confirm')or method!='POST':raise HTTPError(404,'Página não encontrada.')
    parsed,accounts,resolved,prepared,conflicts,unresolved,payload=prepare_import(app,c,user,data)
    summary=dict(rows=len(parsed['records']),linked=len(prepared),skipped=len(parsed['records'])-len(prepared),new=sum(x['existing']is None for x in prepared),updated=sum(x['existing']is not None and x['changed']for x in prepared),unchanged=sum(not x['changed']for x in prepared),conflicts=conflicts,unresolved=unresolved)
    if path.endswith('/preview'):
        stamp=int(time.time());token=str(stamp)+'.'+sign(app,payload,stamp)
        sample=[dict(line=x['record']['line'],name=x['record']['name'],activity=x['record']['activity'],date=x['record']['date'],target=x['target'],metrics=x['record']['metrics'])for x in prepared[:10]]
        return app.reply(start,200,dict(summary=summary,token=token,students=parsed['students'],accounts=accounts,subjects=parsed['subjects'],sheets=parsed['sheets'],sheet=parsed['sheet'],sample=sample,columns=parsed['headers'],mapping=resolved))
    if not prepared:raise ValueError('Vincule ao menos um aluno a uma conta antes de confirmar.')
    if unresolved and data.get('skipUnmapped')is not True:raise ValueError('Confirme explicitamente que os alunos sem vínculo serão ignorados.')
    try:stamp_str,sig=data.get('token','').split('.');stamp=int(stamp_str)
    except (ValueError,AttributeError):raise ValueError('Faça a conferência novamente.')
    if not 0<=time.time()-stamp<=1800 or not hmac.compare_digest(sig,sign(app,payload,stamp)):raise HTTPError(409,'Arquivo, vínculos ou resultados mudaram. Faça nova conferência antes de confirmar.')
    # Deterministic locking + insert conflict handling keep concurrent imports safe.
    for item in sorted(prepared,key=lambda x:(x['target'],x['record']['activityKey'],x['record']['date'])):
        if not item['changed']:continue
        r=item['record'];old=item['existing'];at=P.now().isoformat();enc=lambda x:json.dumps(x,ensure_ascii=False,separators=(',',':'),allow_nan=False)
        if old:
            cursor=db.execute(c,'UPDATE hmay_performance SET metrics=?,metadata=?,version=version+1,updated_at=? WHERE id=? AND version=?',(enc(item['metrics']),enc(item['metadata']),at,old['id'],old['version']))
        else:
            cursor=db.execute(c,'INSERT INTO hmay_performance(id,user_id,activity_key,activity,applied_on,metrics,metadata,version,updated_at) VALUES (?,?,?,?,?,?,?,?,?) ON CONFLICT(user_id,activity_key,applied_on) DO NOTHING',(P.uid(),item['target'],r['activityKey'],r['activity'],r['date'],enc(item['metrics']),enc(item['metadata']),1,at))
        if cursor.rowcount!=1:raise HTTPError(409,'Outra importação alterou os resultados. Nenhum dado deste lote foi confirmado; refaça a conferência.')
    for target in {x['target']for x in prepared if x['changed']}:app.event(c,user,target,'performance_import')
    return app.reply(start,200,dict(ok=True,summary=summary))
