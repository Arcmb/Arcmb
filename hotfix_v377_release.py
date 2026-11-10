"""Hotfix v3.7.7: management registry view for reports with filters and nested class/student drill-down."""
from pathlib import Path
import re

ROOT=Path(__file__).resolve().parent
STATIC=ROOT/"static"
BACKEND_MARK="# === REPORT REGISTRY VIEW V3.7.7 ==="
JS_MARK="// === REPORT REGISTRY VIEW V3.7.7 ==="
CSS_MARK="/* === REPORT REGISTRY VIEW V3.7.7 === */"

BACKEND=r'''
# === REPORT REGISTRY VIEW V3.7.7 ===
_reports_handle_v377_base=handle

def _v377_query_value(query,key):
    if not isinstance(query,dict):
        return ''
    raw=query.get(key,[''])
    if isinstance(raw,(list,tuple)):
        raw=raw[0] if raw else ''
    return F.text(raw,250)

def _reports_registry_assignments(app,c):
    rows=app.db.execute(
        c,
        """SELECT r.model_id,r.user_id,r.report_name,r.report_url,
                  u.name,u.username
           FROM hmay_student_reports r
           JOIN hmay_users u ON u.id=r.user_id
           WHERE u.role IN ('user','aluno') AND u.active=1
           ORDER BY lower(u.name),lower(u.username)"""
    ).fetchall()
    user_ids=sorted({row['user_id'] for row in rows})
    class_by_user=_reports_latest_class_by_user(app,c,user_ids)
    result=[]
    for raw in rows:
        row=dict(raw)
        row['turma']=class_by_user.get(row['user_id'],'Sem turma')
        result.append(row)
    return result

def _reports_registry(app,c,query):
    _reports_ensure(app,c)
    q=F.norm(_v377_query_value(query,'q'))
    type_q=F.norm(_v377_query_value(query,'type'))
    student_q=F.norm(_v377_query_value(query,'student'))
    class_q=F.norm(_v377_query_value(query,'turma'))

    models=_reports_models(app,c)
    assignments=_reports_registry_assignments(app,c)
    by_model={}
    for row in assignments:
        by_model.setdefault(row['model_id'],[]).append(row)

    type_suggestions=sorted({m['type_name'] for m in models if m.get('type_name')},key=F.norm)
    report_suggestions=sorted(
        {value for m in models for value in (m.get('title'),m.get('activity')) if value},
        key=F.norm,
    )
    student_suggestions=sorted({row['name'] for row in assignments if row.get('name')},key=F.norm)
    class_suggestions=sorted({row['turma'] for row in assignments if row.get('turma')},key=F.norm)

    result=[]
    for model in models:
        linked=by_model.get(model['id'],[])
        if q:
            hay=' '.join([
                F.norm(model.get('title')),
                F.norm(model.get('activity')),
                F.norm(model.get('type_name')),
            ])
            if q not in hay:
                continue
        if type_q and type_q not in F.norm(model.get('type_name')):
            continue
        if student_q and not any(student_q in F.norm(row.get('name')) for row in linked):
            continue
        if class_q and not any(class_q in F.norm(row.get('turma')) for row in linked):
            continue

        class_counts={}
        for row in linked:
            turma=row.get('turma') or 'Sem turma'
            class_counts[turma]=class_counts.get(turma,0)+1

        result.append({
            'id':model['id'],
            'type':model['type_name'],
            'title':model['title'],
            'activity':model['activity'],
            'date':model['applied_on'],
            'createdAt':model['created_at'],
            'updatedAt':model['updated_at'],
            'active':bool(model['active']),
            'assignments':len(linked),
            'classCount':len(class_counts),
            'classes':[
                {'name':name,'count':count}
                for name,count in sorted(class_counts.items(),key=lambda item:F.norm(item[0]))
            ],
        })

    result.sort(
        key=lambda item:(item.get('createdAt') or '',item.get('title') or ''),
        reverse=True,
    )

    return {
        'models':result,
        'total':len(result),
        'suggestions':{
            'types':type_suggestions,
            'reports':report_suggestions,
            'students':student_suggestions,
            'classes':class_suggestions,
        },
        'filters':{
            'q':_v377_query_value(query,'q'),
            'type':_v377_query_value(query,'type'),
            'student':_v377_query_value(query,'student'),
            'turma':_v377_query_value(query,'turma'),
        },
    }

def _reports_registry_detail(app,c,model_id):
    _reports_ensure(app,c)
    model_id=F.text(model_id,160)
    model=app.db.execute(
        c,
        """SELECT m.id,m.title,m.activity,m.applied_on,m.created_at,
                  t.name AS type_name
           FROM hmay_report_models m
           JOIN hmay_report_types t ON t.id=m.type_id
           WHERE m.id=?""",
        (model_id,),
    ).fetchone()
    if not model:
        raise ValueError('Relatório não encontrado.')

    rows=app.db.execute(
        c,
        """SELECT r.id,r.user_id,r.report_name,r.report_url,
                  u.name,u.username
           FROM hmay_student_reports r
           JOIN hmay_users u ON u.id=r.user_id
           WHERE r.model_id=? AND u.role IN ('user','aluno') AND u.active=1
           ORDER BY lower(u.name),lower(u.username)""",
        (model_id,),
    ).fetchall()
    user_ids=[row['user_id'] for row in rows]
    class_by_user=_reports_latest_class_by_user(app,c,user_ids)

    groups={}
    for raw in rows:
        row=dict(raw)
        turma=class_by_user.get(row['user_id'],'Sem turma')
        bucket=groups.setdefault(turma,[])
        bucket.append({
            'id':row['user_id'],
            'name':row['name'],
            'username':row['username'],
            'reportName':row['report_name'] or model['title'],
            'url':row['report_url'],
        })

    classes=[
        {'name':name,'count':len(students),'students':students}
        for name,students in sorted(groups.items(),key=lambda item:F.norm(item[0]))
    ]
    return {
        'model':{
            'id':model['id'],
            'type':model['type_name'],
            'title':model['title'],
            'activity':model['activity'],
            'date':model['applied_on'],
            'createdAt':model['created_at'],
        },
        'classes':classes,
        'assignments':len(rows),
    }

def handle(app,c,user,path,method,data,query,start,HTTPError):
    if path=='/api/model-data/report-registry':
        if user.get('role') not in ('master','coordenador'):
            raise HTTPError(403,'Acesso reservado ao Master e à coordenação.')
        if method!='GET':
            raise HTTPError(405,'Use GET para consultar os relatórios cadastrados.')
        return app.reply(start,200,_reports_registry(app,c,query))

    if path=='/api/model-data/report-registry-detail':
        if user.get('role') not in ('master','coordenador'):
            raise HTTPError(403,'Acesso reservado ao Master e à coordenação.')
        if method!='GET':
            raise HTTPError(405,'Use GET para consultar os vínculos do relatório.')
        model_id=_v377_query_value(query,'modelId')
        return app.reply(start,200,_reports_registry_detail(app,c,model_id))

    return _reports_handle_v377_base(app,c,user,path,method,data,query,start,HTTPError)
'''

JS=r'''
// === REPORT REGISTRY VIEW V3.7.7 ===
let reportRegistryCache=null;
let reportRegistryLoading=false;
let reportRegistryFilters={q:'',type:'',student:'',turma:''};
let reportRegistryDetailCache=new Map();
let reportRegistryExpandedModel='';
let reportRegistryExpandedClass={};
let reportRegistryDebounce=null;

const reportsViewStudentV377=reportsView;

function reportRegistryQuery(){
 const q=new URLSearchParams();
 Object.entries(reportRegistryFilters).forEach(([key,value])=>{if(String(value||'').trim())q.set(key,String(value).trim());});
 return q.toString();
}
async function loadReportRegistry(force=false){
 if(!managementDashboardAllowed()||reportRegistryLoading||(!force&&reportRegistryCache))return;
 reportRegistryLoading=true;
 try{
  const query=reportRegistryQuery();
  reportRegistryCache=await api('/api/model-data/report-registry'+(query?'?'+query:''));
 }catch(error){
  reportRegistryCache={error:error?.message||'Não foi possível carregar os relatórios cadastrados.'};
 }finally{
  reportRegistryLoading=false;
  if(view==='reports')render();
 }
}
async function loadReportRegistryDetail(modelId){
 if(reportRegistryDetailCache.has(modelId))return reportRegistryDetailCache.get(modelId);
 const data=await api('/api/model-data/report-registry-detail?modelId='+encodeURIComponent(modelId));
 reportRegistryDetailCache.set(modelId,data);
 return data;
}
function reportRegistryDatalist(id,values){
 return '<datalist id="'+id+'">'+(values||[]).map(value=>'<option value="'+esc(value)+'"></option>').join('')+'</datalist>';
}
function reportRegistryFilterHtml(data){
 const s=data?.suggestions||{};
 const f=data?.filters||reportRegistryFilters;
 return '<section class="card report-registry-filter">'+
  '<div class="report-registry-filter-head"><div><h2>Relatórios cadastrados</h2><p>Pesquise e filtre pelos dados já cadastrados. As sugestões aparecem conforme você digita.</p></div><span class="tag">'+Number(data?.total||0)+' resultado(s)</span></div>'+
  '<div class="report-registry-filter-grid">'+
   '<label>Relatório / atividade<input id="report-registry-q" list="report-registry-reports" value="'+esc(f.q||'')+'" placeholder="Digite o nome do relatório ou atividade"></label>'+
   '<label>Tipo<input id="report-registry-type" list="report-registry-types" value="'+esc(f.type||'')+'" placeholder="Ex.: Simulado"></label>'+
   '<label>Aluno<input id="report-registry-student" list="report-registry-students" value="'+esc(f.student||'')+'" placeholder="Digite o nome do aluno"></label>'+
   '<label>Turma<input id="report-registry-turma" list="report-registry-classes" value="'+esc(f.turma||'')+'" placeholder="Digite a turma"></label>'+
  '</div>'+
  reportRegistryDatalist('report-registry-reports',s.reports)+
  reportRegistryDatalist('report-registry-types',s.types)+
  reportRegistryDatalist('report-registry-students',s.students)+
  reportRegistryDatalist('report-registry-classes',s.classes)+
  '<div class="actions"><button type="button" class="secondary" data-act="report-registry-clear">Limpar filtros</button><button type="button" class="secondary" data-act="report-registry-refresh">Atualizar</button></div>'+
 '</section>';
}
function reportRegistryDate(value){
 if(!value)return '—';
 const text=String(value);
 if(/^\d{4}-\d{2}-\d{2}/.test(text)){
  const [y,m,d]=text.slice(0,10).split('-');
  return d+'/'+m+'/'+y;
 }
 return text;
}
function reportRegistryCreatedAt(value){
 if(!value)return '—';
 const text=String(value);
 const match=text.match(/^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2})/);
 if(!match)return text;
 return match[3]+'/'+match[2]+'/'+match[1]+' '+match[4]+':'+match[5];
}
function reportRegistryClassesSummary(model){
 const rows=model?.classes||[];
 if(!rows.length)return '<span class="micro">Sem turma vinculada</span>';
 const shown=rows.slice(0,3).map(x=>esc(x.name)+' ('+Number(x.count||0)+')').join(', ');
 const extra=rows.length>3?' +'+(rows.length-3):'';
 return '<span>'+shown+extra+'</span>';
}
function reportRegistryStudentTable(group){
 return '<div class="report-registry-students-table"><table><thead><tr><th>Aluno</th><th>Login</th><th>Relatório</th><th>Link individual</th></tr></thead><tbody>'+
  (group.students||[]).map(student=>
   '<tr><td><strong>'+esc(student.name)+'</strong></td><td>'+esc(student.username||'')+'</td><td>'+esc(student.reportName||'')+'</td><td><a class="secondary report-registry-link" href="'+esc(student.url)+'" target="_blank" rel="noopener noreferrer">Abrir relatório</a></td></tr>'
  ).join('')+
 '</tbody></table></div>';
}
function reportRegistryDetailHtml(modelId){
 const detail=reportRegistryDetailCache.get(modelId);
 if(!detail)return '<div class="report-registry-detail-loading">Carregando turmas vinculadas…</div>';
 const groups=detail.classes||[];
 if(!groups.length)return '<div class="notice">Nenhum aluno possui este relatório.</div>';
 return '<div class="report-registry-class-list">'+groups.map((group,index)=>{
  const key=modelId+'@@'+group.name;
  const open=!!reportRegistryExpandedClass[key];
  return '<section class="report-registry-class'+(open?' open':'')+'">'+
   '<button type="button" class="report-registry-class-button" data-act="report-registry-class-toggle" data-model-id="'+esc(modelId)+'" data-class-name="'+encodeURIComponent(group.name)+'">'+
    '<span><strong>'+esc(group.name)+'</strong><small>'+Number(group.count||0)+' aluno(s) com este relatório</small></span><span class="report-registry-chevron">'+(open?'−':'+')+'</span>'+
   '</button>'+
   (open?reportRegistryStudentTable(group):'')+
  '</section>';
 }).join('')+'</div>';
}
function reportRegistryTableHtml(models){
 if(!(models||[]).length)return '<section class="card"><div class="notice">Nenhum relatório encontrado com os filtros selecionados.</div></section>';
 const body=models.map(model=>{
  const open=reportRegistryExpandedModel===model.id;
  return '<tbody class="report-registry-model-group">'+
   '<tr class="report-registry-row'+(open?' open':'')+'" data-act="report-registry-model-toggle" data-model-id="'+esc(model.id)+'">'+
    '<td><strong>'+esc(model.title||model.activity||'Relatório')+'</strong><br><small>'+esc(model.activity||'')+(model.date?' · '+esc(reportRegistryDate(model.date)):'')+'</small></td>'+
    '<td>'+esc(model.type||'')+'</td>'+
    '<td>'+Number(model.assignments||0)+'</td>'+
    '<td>'+Number(model.classCount||0)+'</td>'+
    '<td>'+reportRegistryClassesSummary(model)+'</td>'+
    '<td>'+esc(reportRegistryCreatedAt(model.createdAt))+'</td>'+
    '<td><button type="button" class="secondary" data-act="report-registry-model-toggle" data-model-id="'+esc(model.id)+'">'+(open?'Fechar':'Ver vínculos')+'</button></td>'+
   '</tr>'+
   (open?'<tr class="report-registry-detail-row"><td colspan="7">'+reportRegistryDetailHtml(model.id)+'</td></tr>':'')+
  '</tbody>';
 }).join('');
 return '<section class="card report-registry-table-card"><div class="table-wrap"><table class="report-registry-table"><thead><tr><th>Relatório / atividade</th><th>Tipo</th><th>Alunos</th><th>Turmas</th><th>Turmas vinculadas</th><th>Cadastrado em</th><th></th></tr></thead>'+body+'</table></div></section>';
}
function reportsRegistryView(){
 if(!reportRegistryCache&&!reportRegistryLoading)queueMicrotask(()=>loadReportRegistry());
 if(reportRegistryLoading||!reportRegistryCache)return head('Meus relatórios','Visão gerencial dos relatórios cadastrados.')+'<section class="card"><p>Carregando relatórios cadastrados…</p></section>';
 if(reportRegistryCache.error)return head('Meus relatórios','Visão gerencial dos relatórios cadastrados.')+'<section class="card"><div class="notice warning">'+esc(reportRegistryCache.error)+'</div></section>';
 return head('Meus relatórios','Pesquise relatórios, turmas e alunos. Clique em um relatório para abrir seus vínculos.')+
  reportRegistryFilterHtml(reportRegistryCache)+
  reportRegistryTableHtml(reportRegistryCache.models||[]);
}
reportsView=function(){
 if(managementDashboardAllowed())return reportsRegistryView();
 return reportsViewStudentV377();
};

acts['report-registry-clear']=()=>{
 reportRegistryFilters={q:'',type:'',student:'',turma:''};
 reportRegistryCache=null;
 reportRegistryExpandedModel='';
 reportRegistryExpandedClass={};
 loadReportRegistry(true);
};
acts['report-registry-refresh']=()=>{reportRegistryCache=null;reportRegistryDetailCache.clear();loadReportRegistry(true);};
acts['report-registry-model-toggle']=async el=>{
 const modelId=el?.dataset?.modelId||'';
 if(!modelId)return;
 if(reportRegistryExpandedModel===modelId){reportRegistryExpandedModel='';render();return;}
 reportRegistryExpandedModel=modelId;
 render();
 try{await loadReportRegistryDetail(modelId);}catch(error){toast(error?.message||'Não foi possível carregar os vínculos.',true);}
 render();
};
acts['report-registry-class-toggle']=el=>{
 const modelId=el?.dataset?.modelId||'',className=decodeURIComponent(el?.dataset?.className||'');
 const key=modelId+'@@'+className;
 reportRegistryExpandedClass[key]=!reportRegistryExpandedClass[key];
 render();
};

document.addEventListener('input',event=>{
 const el=event.target;
 const map={
  'report-registry-q':'q',
  'report-registry-type':'type',
  'report-registry-student':'student',
  'report-registry-turma':'turma'
 };
 const key=map[el?.id];
 if(!key)return;
 reportRegistryFilters[key]=el.value||'';
 clearTimeout(reportRegistryDebounce);
 reportRegistryDebounce=setTimeout(()=>{
  reportRegistryCache=null;
  reportRegistryExpandedModel='';
  reportRegistryExpandedClass={};
  loadReportRegistry(true);
 },280);
},true);
'''

CSS=r'''
/* === REPORT REGISTRY VIEW V3.7.7 === */
.report-registry-filter{display:grid;gap:.9rem}.report-registry-filter-head{display:flex;justify-content:space-between;gap:1rem;align-items:flex-start}.report-registry-filter-head h2{margin:0 0 .25rem}.report-registry-filter-grid{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:.7rem}.report-registry-filter-grid label{display:grid;gap:.3rem}.report-registry-row{cursor:pointer}.report-registry-row:hover,.report-registry-row.open{background:#fff8f9}.report-registry-row td{vertical-align:middle}.report-registry-detail-row>td{padding:0!important;background:#fffafb}.report-registry-detail-loading{padding:1rem;color:var(--muted)}.report-registry-class-list{display:grid;gap:.45rem;padding:.75rem}.report-registry-class{border:1px solid var(--line);border-radius:12px;background:#fff;overflow:hidden}.report-registry-class.open{border-color:#d6919c}.report-registry-class-button{width:100%;display:flex;justify-content:space-between;align-items:center;gap:1rem;border:0;background:transparent;padding:.75rem .9rem;text-align:left;color:inherit;cursor:pointer}.report-registry-class-button span:first-child{display:grid}.report-registry-class-button small{font-weight:400;color:var(--muted)}.report-registry-chevron{font-size:1.2rem;color:#b65362}.report-registry-students-table{border-top:1px solid var(--line);overflow:auto}.report-registry-students-table table{margin:0}.report-registry-link{display:inline-block;text-decoration:none;white-space:nowrap}.report-registry-model-group+tbody tr:first-child td{border-top:1px solid var(--line)}
@media(max-width:1000px){.report-registry-filter-grid{grid-template-columns:repeat(2,minmax(0,1fr))}}
@media(max-width:620px){.report-registry-filter-head{display:grid}.report-registry-filter-grid{grid-template-columns:1fr}.report-registry-table{min-width:900px}}
'''

def main():
    model=ROOT/'model_data.py'
    source=model.read_text(encoding='utf-8')
    if BACKEND_MARK not in source:
        model.write_text(source.rstrip()+"\n\n"+BACKEND.strip()+"\n",encoding='utf-8')

    js=STATIC/'student_summary.js'
    source=js.read_text(encoding='utf-8')
    if JS_MARK not in source:
        js.write_text(source.rstrip()+"\n\n"+JS.strip()+"\n",encoding='utf-8')

    css=STATIC/'style.css'
    source=css.read_text(encoding='utf-8')
    if CSS_MARK not in source:
        css.write_text(source.rstrip()+"\n\n"+CSS.strip()+"\n",encoding='utf-8')

    html=STATIC/'app.html'
    source=html.read_text(encoding='utf-8')
    source=re.sub(r'/static/student_summary\.js\?v=[^"\']+','/static/student_summary.js?v=3.7.7',source)
    html.write_text(source,encoding='utf-8')

    for verifier in ROOT.glob('verify_*.py'):
        source=verifier.read_text(encoding='utf-8')
        source=source.replace('/static/student_summary.js?v=3.7.6','/static/student_summary.js?v=3.7.7')
        source=source.replace('/static/student_summary.js?v=3.7.5','/static/student_summary.js?v=3.7.7')
        verifier.write_text(source,encoding='utf-8')

    site=ROOT/'site_version_release.py'
    source=site.read_text(encoding='utf-8').replace('PUBLIC_VERSION="3.7.6"','PUBLIC_VERSION="3.7.7"')
    site.write_text(source,encoding='utf-8')
    vsite=ROOT/'verify_site_version.py'
    source=vsite.read_text(encoding='utf-8').replace('v3.7.6','v3.7.7')
    vsite.write_text(source,encoding='utf-8')

    print("MEUCRONOGRAMA_REPORT_REGISTRY_READY: managers get searchable report table with autocomplete and nested class/student/link drill-down.",flush=True)

if __name__=='__main__':
    main()
