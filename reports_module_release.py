"""Student reports module: types, batch XLSX registration, editable report models and student-facing links."""
from pathlib import Path
import re

ROOT=Path(__file__).resolve().parent
STATIC=ROOT/"static"
BACKEND_MARK="# === STUDENT REPORTS MODULE V1 ==="
JS_MARK="// === STUDENT REPORTS MODULE V1 ==="
APP_MARK="// === STUDENT REPORTS NAV V1 ==="
CSS_MARK="/* === STUDENT REPORTS MODULE V1 === */"

BACKEND=r'''
# === STUDENT REPORTS MODULE V1 ===
import base64 as _reports_b64
import json as _reports_json
import uuid as _reports_uuid
import re as _reports_re

_reports_handle_base=handle

def _reports_ensure(app,c):
    app.db.execute(c, """CREATE TABLE IF NOT EXISTS hmay_report_types(
        id text PRIMARY KEY,name text NOT NULL UNIQUE,sort_order integer NOT NULL DEFAULT 0,
        active integer NOT NULL DEFAULT 1,created_at text NOT NULL,updated_at text NOT NULL)""")
    app.db.execute(c, """CREATE TABLE IF NOT EXISTS hmay_report_models(
        id text PRIMARY KEY,type_id text NOT NULL,activity text NOT NULL,applied_on text NOT NULL DEFAULT '',
        title text NOT NULL,description text NOT NULL DEFAULT '',cover text NOT NULL DEFAULT '',
        active integer NOT NULL DEFAULT 1,created_at text NOT NULL,updated_at text NOT NULL,
        UNIQUE(type_id,activity,applied_on))""")
    app.db.execute(c, """CREATE TABLE IF NOT EXISTS hmay_student_reports(
        id text PRIMARY KEY,model_id text NOT NULL,user_id text NOT NULL REFERENCES hmay_users(id),
        report_name text NOT NULL DEFAULT '',report_url text NOT NULL,created_at text NOT NULL,updated_at text NOT NULL,
        UNIQUE(model_id,user_id))""")

def _reports_types(app,c,active_only=False):
    _reports_ensure(app,c)
    sql='SELECT id,name,sort_order,active,created_at,updated_at FROM hmay_report_types'
    if active_only: sql+=' WHERE active=1'
    sql+=' ORDER BY sort_order,lower(name)'
    return [dict(x) for x in app.db.execute(c,sql).fetchall()]

def _reports_models(app,c):
    _reports_ensure(app,c)
    rows=app.db.execute(c, """SELECT m.id,m.type_id,m.activity,m.applied_on,m.title,m.description,m.cover,m.active,
        m.created_at,m.updated_at,t.name AS type_name,t.sort_order,
        COUNT(r.id) AS assignments
        FROM hmay_report_models m
        JOIN hmay_report_types t ON t.id=m.type_id
        LEFT JOIN hmay_student_reports r ON r.model_id=m.id
        GROUP BY m.id,m.type_id,m.activity,m.applied_on,m.title,m.description,m.cover,m.active,m.created_at,m.updated_at,t.name,t.sort_order
        ORDER BY t.sort_order,lower(t.name),m.applied_on DESC,lower(m.activity)""").fetchall()
    return [dict(x) for x in rows]

def _reports_target(app,c,user,target_id):
    if user.get('role') in ('master','coordenador'):
        target_id=F.text(target_id,160)
        if not target_id or target_id==user.get('id'):
            return None
        row=app.db.execute(c,"SELECT id,name,username,role,active FROM hmay_users WHERE id=?",(target_id,)).fetchone()
        if not row or row['role'] not in ('user','aluno') or not row['active']:
            raise ValueError('Aluno não encontrado para consulta de relatórios.')
        return dict(row)
    if user.get('role') in ('user','aluno'):
        return user
    raise ValueError('Perfil sem acesso aos relatórios do aluno.')

def _reports_student_data(app,c,user,target_id):
    _reports_ensure(app,c)
    target=_reports_target(app,c,user,target_id)
    if not target:
        return {'student':None,'groups':[]}
    rows=app.db.execute(c, """SELECT r.id,r.report_name,r.report_url,m.id AS model_id,m.activity,m.applied_on,
        m.title,m.description,m.cover,t.id AS type_id,t.name AS type_name,t.sort_order
        FROM hmay_student_reports r
        JOIN hmay_report_models m ON m.id=r.model_id
        JOIN hmay_report_types t ON t.id=m.type_id
        WHERE r.user_id=? AND m.active=1 AND t.active=1
        ORDER BY t.sort_order,lower(t.name),m.applied_on DESC,lower(m.activity)""",(target['id'],)).fetchall()
    groups={}
    for raw in rows:
        row=dict(raw)
        bucket=groups.setdefault(row['type_id'],{'id':row['type_id'],'name':row['type_name'],'sortOrder':row['sort_order'],'reports':[]})
        bucket['reports'].append({
            'id':row['id'],'modelId':row['model_id'],'name':row['report_name'] or row['title'],
            'title':row['title'],'activity':row['activity'],'date':row['applied_on'],
            'description':row['description'],'cover':row['cover'],'url':row['report_url'],
        })
    return {'student':{'id':target['id'],'name':target['name'],'username':target['username']},'groups':list(groups.values())}

_REPORT_HEADER_ALIASES={
    'name':{'nome','aluno','nome do aluno','nome aluno'},
    'activity':{'atividade','simulado','atividade simulado','nome do simulado','simulado atividade'},
    'type':{'tipo','tipo de relatorio','tipo relatorio','categoria'},
    'url':{'link','url','link de acesso','link acesso','link do relatorio','url do relatorio'},
    'reportName':{'nome do relatorio','nome relatorio','titulo','titulo do relatorio'},
    'date':{'data','data de aplicacao','data aplicacao'},
}

def _reports_header_map(row):
    result={}
    for i,value in enumerate(row):
        key=F.norm(value)
        for field,aliases in _REPORT_HEADER_ALIASES.items():
            if key in {F.norm(x) for x in aliases}:
                result.setdefault(field,i)
    return result

def _reports_parse(data):
    sheets=_tri_xlsx_rows(data)
    candidate=None
    for sheet_order,sheet in enumerate(sheets):
        for row_index,row in enumerate(sheet.get('rows',[])[:25]):
            columns=_reports_header_map(row)
            score=sum(1 for key in ('name','activity','type','url') if key in columns)
            if score>=4:
                item=(score,-sheet_order,-row_index,sheet,row_index,columns)
                if candidate is None or item[:3]>candidate[:3]:
                    candidate=item
    if not candidate:
        raise ValueError('Não encontrei as colunas NOME DO ALUNO, ATIVIDADE/SIMULADO, TIPO DE RELATÓRIO e LINK.')
    _,_,_,sheet,header_row,columns=candidate
    records=[]
    for line,row in enumerate(sheet.get('rows',[])[header_row+1:],start=header_row+2):
        def value(key):
            idx=columns.get(key)
            return row[idx] if idx is not None and idx<len(row) else ''
        name=F.text(value('name'),250)
        activity=F.text(value('activity'),250)
        type_name=F.text(value('type'),160)
        url=F.text(value('url'),2000)
        report_name=F.text(value('reportName'),250)
        date_raw=F.text(value('date'),60)
        if not any((name,activity,type_name,url,report_name,date_raw)):
            continue
        if not name:
            raise ValueError(f'Linha {line}: informe o nome do aluno.')
        if not activity:
            raise ValueError(f'Linha {line}: informe a atividade ou simulado.')
        if not type_name:
            raise ValueError(f'Linha {line}: informe o tipo de relatório.')
        if not url:
            raise ValueError(f'Linha {line}: informe o link do relatório.')
        if not (url.startswith('https://') or url.startswith('http://')):
            raise ValueError(f'Linha {line}: o link deve começar com http:// ou https://.')
        date=''
        if date_raw:
            date=_tri_iso_date(date_raw)
        records.append({'line':line,'name':name,'activity':activity,'type':type_name,'url':url,'reportName':report_name,'date':date})
    if not records:
        raise ValueError('O arquivo não possui relatórios preenchidos.')
    if len(records)>5000:
        raise ValueError('O arquivo possui mais de 5.000 linhas de relatórios.')
    return {'sheet':sheet.get('name',''),'records':records}

def _reports_match(app,c,parsed):
    users=app.db.execute(c,"SELECT id,name,username FROM hmay_users WHERE role IN ('user','aluno') AND active=1 ORDER BY name").fetchall()
    by_name={}
    for raw in users:
        row=dict(raw);by_name.setdefault(F.norm(row['name']),[]).append(row)
    types=_reports_types(app,c,True)
    by_type={F.norm(x['name']):x for x in types}
    matched=[];unmatched=[];ambiguous=[];unknown_types=[]
    for record in parsed['records']:
        candidates=by_name.get(F.norm(record['name']),[])
        type_row=by_type.get(F.norm(record['type']))
        if not type_row:
            unknown_types.append(record['type']);continue
        if len(candidates)==0:
            unmatched.append(record['name']);continue
        if len(candidates)>1:
            ambiguous.append(record['name']);continue
        matched.append({'record':record,'user':candidates[0],'type':type_row})
    return {
        'matched':matched,
        'unmatched':sorted(set(unmatched),key=F.norm),
        'ambiguous':sorted(set(ambiguous),key=F.norm),
        'unknownTypes':sorted(set(unknown_types),key=F.norm),
    }

def _reports_preview(app,c,data):
    parsed=_reports_parse(data)
    match=_reports_match(app,c,parsed)
    return {
        'sheet':parsed['sheet'],'rows':len(parsed['records']),'matched':len(match['matched']),
        'unmatched':match['unmatched'],'ambiguous':match['ambiguous'],'unknownTypes':match['unknownTypes'],
        'sample':[{
            'name':x['record']['name'],'activity':x['record']['activity'],'type':x['type']['name'],
            'date':x['record']['date'],'reportName':x['record']['reportName'],'url':x['record']['url']
        } for x in match['matched'][:40]],
    },parsed,match

def _reports_confirm(app,c,user,data):
    preview,parsed,match=_reports_preview(app,c,data)
    issues=[]
    if match['unmatched']: issues.append('alunos não encontrados: '+', '.join(match['unmatched'][:20]))
    if match['ambiguous']: issues.append('nomes de alunos duplicados: '+', '.join(match['ambiguous'][:20]))
    if match['unknownTypes']: issues.append('tipos não cadastrados: '+', '.join(match['unknownTypes'][:20]))
    if issues:
        raise ValueError('Não foi possível confirmar: '+'; '.join(issues)+'.')
    stamp=P.now().isoformat()
    new_models=0;new_reports=0;updated_reports=0
    model_cache={}
    for item in match['matched']:
        record=item['record'];type_row=item['type'];user_row=item['user']
        mkey=(type_row['id'],F.norm(record['activity']),record['date'])
        model=model_cache.get(mkey)
        if not model:
            row=app.db.execute(c,
                'SELECT id,title FROM hmay_report_models WHERE type_id=? AND activity=? AND applied_on=?',
                (type_row['id'],record['activity'],record['date'])).fetchone()
            if row:
                model=dict(row)
            else:
                model={'id':'rmdl_'+_reports_uuid.uuid4().hex,'title':record['activity']}
                app.db.execute(c,
                    'INSERT INTO hmay_report_models(id,type_id,activity,applied_on,title,description,cover,active,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?,?,?)',
                    (model['id'],type_row['id'],record['activity'],record['date'],record['activity'],'','',1,stamp,stamp))
                new_models+=1
            model_cache[mkey]=model
        existing=app.db.execute(c,'SELECT id,report_url,report_name FROM hmay_student_reports WHERE model_id=? AND user_id=?',(model['id'],user_row['id'])).fetchone()
        report_name=record['reportName'] or model.get('title') or record['activity']
        if existing:
            app.db.execute(c,'UPDATE hmay_student_reports SET report_name=?,report_url=?,updated_at=? WHERE id=?',
                (report_name,record['url'],stamp,existing['id']))
            updated_reports+=1
        else:
            app.db.execute(c,'INSERT INTO hmay_student_reports(id,model_id,user_id,report_name,report_url,created_at,updated_at) VALUES (?,?,?,?,?,?,?)',
                ('rptlink_'+_reports_uuid.uuid4().hex,model['id'],user_row['id'],report_name,record['url'],stamp,stamp))
            new_reports+=1
    app.event(c,user,user['id'],'student_reports_batch_import')
    return {'summary':{'rows':len(parsed['records']),'matched':len(match['matched']),'newModels':new_models,'newReports':new_reports,'updatedReports':updated_reports}}

def _reports_template():
    headers=['NOME DO ALUNO','ATIVIDADE/SIMULADO','TIPO DE RELATÓRIO','NOME DO RELATÓRIO (opcional)','DATA (opcional)','LINK DE ACESSO']
    rows=[['' for _ in headers] for _ in range(200)]
    help_headers=['Campo','Orientação']
    help_rows=[
        ['NOME DO ALUNO','Deve corresponder ao nome cadastrado no sistema.'],
        ['ATIVIDADE/SIMULADO','Nome do simulado, treino, teste ou atividade.'],
        ['TIPO DE RELATÓRIO','Use um tipo previamente criado pelo Master, como Simulado, Treino ou Mapa de Metas.'],
        ['NOME DO RELATÓRIO','Opcional. Se vazio, usa o nome geral do modelo.'],
        ['DATA','Opcional. Use dd/mm/aaaa ou aaaa-mm-dd.'],
        ['LINK DE ACESSO','URL individual do PDF/relatório online. Deve começar com http:// ou https://.'],
    ]
    return T.export(headers,rows,first_name='RELATORIOS',extra_sheets=[('Como preencher',help_headers,help_rows)])

def _reports_admin_data(app,c):
    return {'types':_reports_types(app,c,False),'models':_reports_models(app,c)}

def _reports_save_type(app,c,user,data):
    _reports_ensure(app,c)
    type_id=F.text(data.get('id'),160)
    name=F.text(data.get('name'),160)
    if not name: raise ValueError('Informe o nome do tipo.')
    try: sort_order=int(data.get('sortOrder') or 0)
    except Exception: sort_order=0
    active=1 if data.get('active',True) else 0
    stamp=P.now().isoformat()
    duplicate=app.db.execute(c,'SELECT id FROM hmay_report_types WHERE lower(name)=lower(?) AND id<>?',(name,type_id or '')).fetchone()
    if duplicate: raise ValueError('Já existe um tipo com esse nome.')
    if type_id:
        app.db.execute(c,'UPDATE hmay_report_types SET name=?,sort_order=?,active=?,updated_at=? WHERE id=?',(name,sort_order,active,stamp,type_id))
    else:
        type_id='rtype_'+_reports_uuid.uuid4().hex
        app.db.execute(c,'INSERT INTO hmay_report_types(id,name,sort_order,active,created_at,updated_at) VALUES (?,?,?,?,?,?)',(type_id,name,sort_order,active,stamp,stamp))
    app.event(c,user,user['id'],'report_type_update')
    return _reports_admin_data(app,c)

def _reports_save_model(app,c,user,data):
    _reports_ensure(app,c)
    model_id=F.text(data.get('id'),160)
    if not model_id: raise ValueError('Modelo de relatório não informado.')
    row=app.db.execute(c,'SELECT id FROM hmay_report_models WHERE id=?',(model_id,)).fetchone()
    if not row: raise ValueError('Modelo não encontrado.')
    title=F.text(data.get('title'),250)
    description=F.text(data.get('description'),1000)
    cover=F.text(data.get('cover'),800000)
    active=1 if data.get('active',True) else 0
    if cover and not (cover.startswith('http://') or cover.startswith('https://') or cover.startswith('data:image/')):
        raise ValueError('A capa deve ser uma URL http(s) ou uma imagem enviada pelo formulário.')
    stamp=P.now().isoformat()
    app.db.execute(c,'UPDATE hmay_report_models SET title=?,description=?,cover=?,active=?,updated_at=? WHERE id=?',
        (title or 'Relatório',description,cover,active,stamp,model_id))
    app.event(c,user,user['id'],'report_model_update')
    return _reports_admin_data(app,c)

def handle(app,c,user,path,method,data,query,start,HTTPError):
    if path=='/api/model-data/student-reports':
        if method!='GET': raise HTTPError(405,'Use GET para consultar relatórios.')
        return app.reply(start,200,_reports_student_data(app,c,user,(query or {}).get('userId')))

    if path=='/api/model-data/report-admin-data':
        if user.get('role') not in ('master','coordenador'): raise HTTPError(403,'Acesso reservado.')
        if method!='GET': raise HTTPError(405,'Use GET.')
        return app.reply(start,200,_reports_admin_data(app,c))

    if path=='/api/model-data/report-type-save':
        if user.get('role') not in ('master','coordenador'): raise HTTPError(403,'Acesso reservado.')
        if method!='POST': raise HTTPError(405,'Use POST.')
        return app.reply(start,200,_reports_save_type(app,c,user,data))

    if path=='/api/model-data/report-model-save':
        if user.get('role') not in ('master','coordenador'): raise HTTPError(403,'Acesso reservado.')
        if method!='POST': raise HTTPError(405,'Use POST.')
        return app.reply(start,200,_reports_save_model(app,c,user,data))

    if path=='/api/model-data/report-batch-template':
        if user.get('role') not in ('master','coordenador'): raise HTTPError(403,'Acesso reservado.')
        blob=_reports_template()
        if not isinstance(blob,(bytes,bytearray)): raise RuntimeError('Falha ao gerar o modelo XLSX.')
        return app.reply(start,200,{'filename':'MODELO_CADASTRO_RELATORIOS.xlsx','mime':'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet','file':_reports_b64.b64encode(blob).decode('ascii')})

    if path=='/api/model-data/report-batch-preview':
        if user.get('role') not in ('master','coordenador'): raise HTTPError(403,'Acesso reservado.')
        preview,_,_=_reports_preview(app,c,data)
        return app.reply(start,200,preview)

    if path=='/api/model-data/report-batch-confirm':
        if user.get('role') not in ('master','coordenador'): raise HTTPError(403,'Acesso reservado.')
        return app.reply(start,200,_reports_confirm(app,c,user,data))

    return _reports_handle_base(app,c,user,path,method,data,query,start,HTTPError)
'''

JS=r'''
// === STUDENT REPORTS MODULE V1 ===
let studentReportsCache=new Map();
let reportAdminCache=null;
let reportAdminLoading=false;
let reportBatchDraft=null;
let reportBatchPreviewData=null;

function reportTargetId(){
 if(typeof ME==='undefined'||!ME)return '';
 if(['master','coordenador'].includes(ME.role)){
  const id=typeof studentSummaryTarget==='function'?studentSummaryTarget():'';
  return id&&id!==ME.id?id:'';
 }
 return ME.id||'';
}
async function loadStudentReports(force=false){
 const id=reportTargetId();
 const key=id||'__none__';
 if(!force&&studentReportsCache.has(key))return;
 try{
  const d=await api('/api/model-data/student-reports'+(id?'?userId='+encodeURIComponent(id):''));
  studentReportsCache.set(key,d);
 }catch(error){studentReportsCache.set(key,{error:error?.message||'Não foi possível carregar os relatórios.'});}
 if(view==='reports')render();
}
function reportCoverHtml(report){
 const cover=String(report.cover||'').trim();
 if(cover)return '<img class="student-report-cover" src="'+esc(cover)+'" alt="Capa do relatório">';
 return '<div class="student-report-cover placeholder"><span>PDF</span></div>';
}
function reportsView(){
 const id=reportTargetId(),key=id||'__none__';
 if(!studentReportsCache.has(key))queueMicrotask(()=>loadStudentReports());
 const d=studentReportsCache.get(key);
 if(!d)return head('Meus relatórios','Relatórios individuais disponibilizados pela coordenação.')+'<section class="card"><p>Carregando relatórios…</p></section>';
 if(d.error)return head('Meus relatórios','Relatórios individuais disponibilizados pela coordenação.')+'<section class="card"><div class="notice warning">'+esc(d.error)+'</div></section>';
 if(!d.student&&['master','coordenador'].includes(ME.role))return head('Meus relatórios','Selecione um aluno no campo de pesquisa para visualizar os relatórios dele.')+'<section class="card"><div class="notice">Nenhum aluno selecionado.</div></section>';
 const groups=d.groups||[];
 const body=groups.length?groups.map(group=>'<section class="card student-report-group"><div class="student-report-group-head"><h2>'+esc(group.name)+'</h2><span>'+group.reports.length+' relatório(s)</span></div><div class="student-report-row">'+group.reports.map(report=>'<article class="student-report-card">'+reportCoverHtml(report)+'<div class="student-report-content"><p class="eyebrow">'+esc(group.name)+'</p><h3>'+esc(report.name||report.title||'Relatório')+'</h3><p><strong>'+esc(report.activity||'')+'</strong>'+(report.date?' · '+esc(report.date):'')+'</p>'+(report.description?'<p>'+esc(report.description)+'</p>':'')+'<a class="primary report-open-link" href="'+esc(report.url)+'" target="_blank" rel="noopener noreferrer">Abrir relatório</a></div></article>').join('')+'</div></section>').join(''):'<section class="card"><div class="notice">Ainda não há relatórios publicados para este aluno.</div></section>';
 return head('Meus relatórios',d.student?'Relatórios disponíveis para '+esc(d.student.name)+'.':'Relatórios individuais disponibilizados pela coordenação.')+body;
}

function reportsFileBase64(file){
 return file.arrayBuffer().then(buffer=>{const bytes=new Uint8Array(buffer),step=0x8000;let binary='';for(let i=0;i<bytes.length;i+=step)binary+=String.fromCharCode(...bytes.subarray(i,i+step));return btoa(binary);});
}
function reportsDownload(filename,mime,encoded){
 const binary=atob(encoded),bytes=new Uint8Array(binary.length);for(let i=0;i<binary.length;i++)bytes[i]=binary.charCodeAt(i);
 const url=URL.createObjectURL(new Blob([bytes],{type:mime})),a=document.createElement('a');a.href=url;a.download=filename;document.body.appendChild(a);a.click();a.remove();setTimeout(()=>URL.revokeObjectURL(url),1500);
}
async function loadReportAdmin(force=false){
 if(!managementDashboardAllowed()||reportAdminLoading||(!force&&reportAdminCache))return;
 reportAdminLoading=true;
 try{reportAdminCache=await api('/api/model-data/report-admin-data');}
 catch(error){reportAdminCache={error:error?.message||'Não foi possível carregar o cadastro de relatórios.'};}
 finally{reportAdminLoading=false;if(view==='report-admin')render();}
}
function reportTypesAdminHtml(types){
 const rows=(types||[]).map(t=>'<tr><td><input data-report-type-name="'+esc(t.id)+'" value="'+esc(t.name)+'"></td><td><input type="number" data-report-type-order="'+esc(t.id)+'" value="'+Number(t.sort_order||0)+'"></td><td><label class="check"><input type="checkbox" data-report-type-active="'+esc(t.id)+'"'+(t.active?' checked':'')+'> Ativo</label></td><td><button type="button" class="secondary" data-act="report-type-save" data-type-id="'+esc(t.id)+'">Salvar</button></td></tr>').join('');
 return '<section class="card"><h2>Tipos de relatório</h2><p>Os tipos definem as linhas/seções que o aluno verá em “Meus relatórios”.</p><div class="report-type-new"><label>Novo tipo<input id="report-type-new-name" placeholder="Ex.: Diagnóstico"></label><label>Ordem<input id="report-type-new-order" type="number" value="10"></label><button type="button" class="primary" data-act="report-type-new">Criar tipo</button></div><div class="table-wrap"><table><thead><tr><th>Tipo</th><th>Ordem</th><th>Status</th><th></th></tr></thead><tbody>'+rows+'</tbody></table></div></section>';
}
function reportModelsAdminHtml(models){
 const rows=(models||[]).map(m=>'<tr><td><strong>'+esc(m.type_name)+'</strong></td><td>'+esc(m.activity)+(m.applied_on?'<br><small>'+esc(m.applied_on)+'</small>':'')+'</td><td><input data-report-model-title="'+esc(m.id)+'" value="'+esc(m.title||'')+'"><textarea data-report-model-description="'+esc(m.id)+'" rows="2" placeholder="Descrição geral">'+esc(m.description||'')+'</textarea></td><td><div class="report-cover-edit">'+(m.cover?'<img src="'+esc(m.cover)+'" alt="Capa">':'')+'<input data-report-model-cover="'+esc(m.id)+'" value="'+esc(m.cover||'')+'" placeholder="URL da capa ou imagem enviada"><input type="file" accept="image/*" data-report-cover-file="'+esc(m.id)+'"></div></td><td>'+Number(m.assignments||0)+'</td><td><label class="check"><input type="checkbox" data-report-model-active="'+esc(m.id)+'"'+(m.active?' checked':'')+'> Ativo</label></td><td><button type="button" class="secondary" data-act="report-model-save" data-model-id="'+esc(m.id)+'">Salvar</button></td></tr>').join('');
 return '<section class="card"><h2>Modelos cadastrados</h2><p>Título, descrição e capa são informações gerais replicadas a todos os alunos vinculados ao mesmo modelo.</p><div class="table-wrap"><table><thead><tr><th>Tipo</th><th>Atividade</th><th>Informações gerais</th><th>Capa</th><th>Alunos</th><th>Status</th><th></th></tr></thead><tbody>'+rows+'</tbody></table></div></section>';
}
function reportBatchHtml(){
 let preview='';
 if(reportBatchPreviewData){
  const p=reportBatchPreviewData,issues=[];
  if((p.unmatched||[]).length)issues.push('Alunos não encontrados: '+p.unmatched.join(', '));
  if((p.ambiguous||[]).length)issues.push('Nomes duplicados: '+p.ambiguous.join(', '));
  if((p.unknownTypes||[]).length)issues.push('Tipos não cadastrados: '+p.unknownTypes.join(', '));
  preview='<div class="'+(issues.length?'notice warning':'notice success')+'"><strong>'+Number(p.matched||0)+' de '+Number(p.rows||0)+' linha(s) prontas.</strong>'+(issues.length?'<ul>'+issues.map(x=>'<li>'+esc(x)+'</li>').join('')+'</ul>':'<p>Todos os alunos e tipos foram reconhecidos.</p>')+'</div><div class="table-wrap"><table><thead><tr><th>Aluno</th><th>Atividade</th><th>Tipo</th><th>Data</th><th>Relatório</th></tr></thead><tbody>'+(p.sample||[]).map(x=>'<tr><td>'+esc(x.name)+'</td><td>'+esc(x.activity)+'</td><td>'+esc(x.type)+'</td><td>'+esc(x.date||'')+'</td><td>'+esc(x.reportName||'')+'</td></tr>').join('')+'</tbody></table></div><div class="actions"><button type="button" class="primary" data-act="report-batch-confirm"'+(issues.length?' disabled':'')+'>Confirmar cadastro em lote</button></div>';
 }
 return '<section class="card"><h2>Cadastro em lote</h2><p>Envie um XLSX com aluno, atividade/simulado, tipo de relatório e link individual.</p><div class="actions"><button type="button" class="secondary" data-act="report-batch-template">Baixar modelo XLSX</button></div><label>Arquivo preenchido<input id="report-batch-file" type="file" accept=".xlsx"></label><p class="micro">'+esc(reportBatchDraft?.filename||'Nenhum arquivo selecionado.')+'</p><div class="actions"><button type="button" class="primary" data-act="report-batch-preview"'+(reportBatchDraft?.file?'':' disabled')+'>Ler e conferir</button></div>'+preview+'</section>';
}
function reportAdminView(){
 if(!managementDashboardAllowed())return head('Cadastro de relatórios','Acesso reservado ao Master e à coordenação.');
 if(!reportAdminCache&&!reportAdminLoading)queueMicrotask(()=>loadReportAdmin());
 if(reportAdminLoading||!reportAdminCache)return head('Cadastro de relatórios','Gerencie tipos, modelos, capas e links individuais.')+'<section class="card"><p>Carregando…</p></section>';
 if(reportAdminCache.error)return head('Cadastro de relatórios','Gerencie tipos, modelos, capas e links individuais.')+'<section class="card"><div class="notice warning">'+esc(reportAdminCache.error)+'</div></section>';
 return head('Cadastro de relatórios','Gerencie tipos, modelos, capas e cadastros individuais em lote.')+reportTypesAdminHtml(reportAdminCache.types||[])+reportBatchHtml()+reportModelsAdminHtml(reportAdminCache.models||[]);
}

acts['report-type-new']=async()=>{
 const name=document.querySelector('#report-type-new-name')?.value||'',sortOrder=Number(document.querySelector('#report-type-new-order')?.value||0);
 if(!name.trim())throw new Error('Informe o nome do tipo.');
 reportAdminCache=await api('/api/model-data/report-type-save',{name,sortOrder,active:true});render();toast('Tipo criado.');
};
acts['report-type-save']=async el=>{
 const id=el?.dataset?.typeId||'',name=document.querySelector('[data-report-type-name="'+CSS.escape(id)+'"]')?.value||'',sortOrder=Number(document.querySelector('[data-report-type-order="'+CSS.escape(id)+'"]')?.value||0),active=!!document.querySelector('[data-report-type-active="'+CSS.escape(id)+'"]')?.checked;
 reportAdminCache=await api('/api/model-data/report-type-save',{id,name,sortOrder,active});render();toast('Tipo atualizado.');
};
acts['report-model-save']=async el=>{
 const id=el?.dataset?.modelId||'',title=document.querySelector('[data-report-model-title="'+CSS.escape(id)+'"]')?.value||'',description=document.querySelector('[data-report-model-description="'+CSS.escape(id)+'"]')?.value||'',cover=document.querySelector('[data-report-model-cover="'+CSS.escape(id)+'"]')?.value||'',active=!!document.querySelector('[data-report-model-active="'+CSS.escape(id)+'"]')?.checked;
 reportAdminCache=await api('/api/model-data/report-model-save',{id,title,description,cover,active});studentReportsCache.clear();render();toast('Modelo atualizado.');
};
acts['report-batch-template']=async()=>{const d=await api('/api/model-data/report-batch-template',{});reportsDownload(d.filename,d.mime,d.file);};
acts['report-batch-preview']=async()=>{
 if(!reportBatchDraft?.file)throw new Error('Selecione o XLSX.');
 reportBatchPreviewData=await api('/api/model-data/report-batch-preview',{file:reportBatchDraft.file,filename:reportBatchDraft.filename});
 render();
};
acts['report-batch-confirm']=async()=>{
 if(!reportBatchDraft?.file)throw new Error('Selecione o XLSX.');
 if(!confirm('Cadastrar/atualizar os relatórios individuais listados na prévia?'))return;
 const d=await api('/api/model-data/report-batch-confirm',{file:reportBatchDraft.file,filename:reportBatchDraft.filename});
 reportAdminCache=null;reportBatchPreviewData=null;studentReportsCache.clear();await loadReportAdmin(true);
 toast('Cadastro concluído: '+Number(d.summary?.newReports||0)+' novo(s), '+Number(d.summary?.updatedReports||0)+' atualizado(s).');
};
document.addEventListener('change',async event=>{
 const el=event.target;
 if(el?.id==='report-batch-file'){
  const file=el.files?.[0];el.value='';if(!file)return;
  if(!/\.xlsx$/i.test(file.name))throw new Error('Selecione um arquivo .xlsx.');
  if(file.size>5000000)throw new Error('O arquivo excede 5 MB.');
  reportBatchDraft={filename:file.name,file:await reportsFileBase64(file)};reportBatchPreviewData=null;render();return;
 }
 if(el?.matches('[data-report-cover-file]')){
  const file=el.files?.[0];if(!file)return;
  if(!file.type.startsWith('image/'))throw new Error('Selecione uma imagem.');
  if(file.size>600000)throw new Error('A capa deve ter no máximo 600 KB.');
  const data=await new Promise((resolve,reject)=>{const reader=new FileReader();reader.onload=()=>resolve(String(reader.result||''));reader.onerror=()=>reject(new Error('Não foi possível ler a imagem.'));reader.readAsDataURL(file);});
  const id=el.dataset.reportCoverFile,input=document.querySelector('[data-report-model-cover="'+CSS.escape(id)+'"]');if(input)input.value=data;
 }
},true);
'''

APP_PATCH=r'''
// === STUDENT REPORTS NAV V1 ===
'''

CSS=r'''
/* === STUDENT REPORTS MODULE V1 === */
.student-report-group{display:grid;gap:.8rem}.student-report-group-head{display:flex;align-items:center;justify-content:space-between;gap:1rem}.student-report-row{display:flex;gap:1rem;overflow-x:auto;padding:.2rem}.student-report-card{min-width:300px;max-width:380px;display:grid;grid-template-columns:110px 1fr;gap:.9rem;border:1px solid var(--line);border-radius:16px;padding:.8rem;background:#fff}.student-report-cover{width:110px;height:145px;object-fit:cover;border-radius:10px;border:1px solid var(--line);background:#faf7f8}.student-report-cover.placeholder{display:grid;place-items:center;font-size:1.5rem;font-weight:800;color:#b65362}.student-report-content{display:flex;flex-direction:column;align-items:flex-start}.student-report-content h3{margin:.1rem 0}.report-open-link{margin-top:auto;text-decoration:none;padding:.55rem .8rem;border-radius:10px}.report-type-new{display:grid;grid-template-columns:1fr 140px auto;gap:.7rem;align-items:end}.report-cover-edit{display:grid;gap:.35rem;min-width:240px}.report-cover-edit img{width:80px;height:105px;object-fit:cover;border-radius:8px}.report-cover-edit input{min-width:220px}
@media(max-width:700px){.student-report-card{min-width:270px;grid-template-columns:90px 1fr}.student-report-cover{width:90px;height:120px}.report-type-new{grid-template-columns:1fr}}
'''

def _patch_app(source):
    if APP_MARK not in source:
        source=source.rstrip()+"\n"+APP_PATCH.strip()+"\n"
    if "['reports','Meus relatórios']" not in source:
        source=source.replace("['performance','Desempenho'],","['performance','Desempenho'],['reports','Meus relatórios'],['report-admin','Cadastro de relatórios'],",1)
    source=source.replace(
        "!['exams','result-model','result-export','result-import'].includes(x[0])||manages()",
        "!['exams','result-model','result-export','result-import','report-admin'].includes(x[0])||manages()",
        1,
    )
    if "reports:reportsView" not in source:
        source=source.replace("performance:performanceView,","performance:performanceView,reports:reportsView,'report-admin':reportAdminView,",1)
    return source

def main():
    model=ROOT/"model_data.py"
    text=model.read_text(encoding="utf-8")
    if BACKEND_MARK not in text:
        model.write_text(text.rstrip()+"\n\n"+BACKEND.strip()+"\n",encoding="utf-8")

    appjs=STATIC/"app.js"
    appjs.write_text(_patch_app(appjs.read_text(encoding="utf-8")),encoding="utf-8")

    summary=STATIC/"student_summary.js"
    text=summary.read_text(encoding="utf-8")
    if JS_MARK not in text:
        summary.write_text(text.rstrip()+"\n\n"+JS.strip()+"\n",encoding="utf-8")

    css=STATIC/"style.css"
    text=css.read_text(encoding="utf-8")
    if CSS_MARK not in text:
        css.write_text(text.rstrip()+"\n\n"+CSS.strip()+"\n",encoding="utf-8")

    html=STATIC/"app.html"
    text=html.read_text(encoding="utf-8")
    text=re.sub(r'/static/app\.js\?v=[^"\']+','/static/app.js?v=3.7.0',text)
    text=re.sub(r'/static/student_summary\.js\?v=[^"\']+','/static/student_summary.js?v=3.7.0',text)
    html.write_text(text,encoding="utf-8")
    print("MEUCRONOGRAMA_REPORTS_MODULE_READY: student reports tab, report types, batch XLSX, editable shared models and covers installed.",flush=True)

if __name__=="__main__":
    main()
