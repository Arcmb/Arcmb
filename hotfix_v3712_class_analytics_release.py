"""Hotfix v3.7.12: hierarchical class/simulation/student ENEM analytics."""
from pathlib import Path
import re

ROOT=Path(__file__).resolve().parent
STATIC=ROOT/'static'
BACKEND_MARK='# === CLASS ENEM ANALYTICS V3.7.12 ==='
JS_MARK='// === CLASS ENEM ANALYTICS V3.7.12 ==='
CSS_MARK='/* === CLASS ENEM ANALYTICS V3.7.12 === */'

BACKEND=r'''
# === CLASS ENEM ANALYTICS V3.7.12 ===
_v3712_handle_base=handle

def _v3712_num(value):
    try:
        if value in (None,''):
            return None
        return float(value)
    except Exception:
        return None

def _v3712_query_scalar(query,key,limit=500):
    if not isinstance(query,dict):
        return ''
    raw=query.get(key,'')
    if isinstance(raw,(list,tuple)):
        raw=raw[0] if raw else ''
    return F.text(raw,limit)

def _v3712_selected_sims(query):
    raw=_v3712_query_scalar(query,'sims',5000)
    return {x for x in raw.split('||') if x} if raw else set()

def _v3712_sim_token(activity_key,date):
    return F.text(activity_key,250)+'@@'+F.text(date,40)

def _v3712_scores(metadata):
    vals={
        'lc':_v3712_num(metadata.get('_tri_lc')),
        'ch':_v3712_num(metadata.get('_tri_ch')),
        'cn':_v3712_num(metadata.get('_tri_cn')),
        'mt':_v3712_num(metadata.get('_tri_mt')),
        'red':_v3712_num(metadata.get('_tri_redaction')),
        'c1':_v3712_num(metadata.get('_redaction_c1')),
        'c2':_v3712_num(metadata.get('_redaction_c2')),
        'c3':_v3712_num(metadata.get('_redaction_c3')),
        'c4':_v3712_num(metadata.get('_redaction_c4')),
        'c5':_v3712_num(metadata.get('_redaction_c5')),
    }
    has_any=any(vals[k] is not None for k in ('lc','ch','cn','mt','red'))
    if has_any:
        enem=sum(vals[k] or 0.0 for k in ('lc','ch','cn','mt','red'))/5.0
        bonus=enem*1.10
    else:
        enem=bonus=None
    vals['enem']=enem
    vals['bonus']=bonus
    return vals

def _v3712_row_accuracy(row,metadata,area_maps):
    metrics=_rx_json(row.get('metrics'))
    if not isinstance(metrics,dict):
        metrics={}
    exam_id=F.text(metadata.get('_exam_id'),160)
    qmap=area_maps.get(exam_id,{})
    result={key:{'correct':0,'valid':0} for key in ('ALL','LC','CH','CN','MT')}
    for mkey,mval in metrics.items():
        if not isinstance(mval,dict):
            continue
        try:
            correct=max(0,int(mval.get('correct') or 0))
            valid=max(0,int(mval.get('total') or 0))
        except Exception:
            continue
        result['ALL']['correct']+=correct
        result['ALL']['valid']+=valid
        number=_v36_metric_number(mkey)
        area=qmap.get(number)
        if not area and number:
            area='LC' if number<=45 else 'CH' if number<=90 else 'CN' if number<=135 else 'MT' if number<=180 else None
        if area in result:
            result[area]['correct']+=correct
            result[area]['valid']+=valid
    return result

def _v3712_bucket():
    return {
        'records':0,'students':set(),'simulations':set(),
        'correct':{key:0 for key in ('ALL','LC','CH','CN','MT')},
        'valid':{key:0 for key in ('ALL','LC','CH','CN','MT')},
        'enem':[],'bonus':[],
        'c1':[],'c2':[],'c3':[],'c4':[],'c5':[],
    }

def _v3712_add(bucket,row,metadata,area_maps):
    bucket['records']+=1
    bucket['students'].add(row['user_id'])
    bucket['simulations'].add(_v3712_sim_token(row['activity_key'],row['applied_on']))
    acc=_v3712_row_accuracy(row,metadata,area_maps)
    for key in ('ALL','LC','CH','CN','MT'):
        bucket['correct'][key]+=acc[key]['correct']
        bucket['valid'][key]+=acc[key]['valid']
    scores=_v3712_scores(metadata)
    for key in ('enem','bonus','c1','c2','c3','c4','c5'):
        value=scores.get(key)
        if value is not None:
            bucket[key].append(value)

def _v3712_pct(bucket,key):
    valid=bucket['valid'][key]
    return None if not valid else round(100.0*bucket['correct'][key]/valid,2)

def _v3712_summary(bucket):
    means={key:_mgmt_mean(bucket[key]) for key in ('enem','bonus','c1','c2','c3','c4','c5')}
    red_parts=[means[k] for k in ('c1','c2','c3','c4','c5')]
    redaction=None if all(v is None for v in red_parts) else round(sum(v or 0 for v in red_parts),2)
    return {
        'participants':len(bucket['students']),
        'simulations':len(bucket['simulations']),
        'records':bucket['records'],
        'enem':means['enem'],'bonus':means['bonus'],
        'accuracy':_v3712_pct(bucket,'ALL'),
        'lcAccuracy':_v3712_pct(bucket,'LC'),
        'chAccuracy':_v3712_pct(bucket,'CH'),
        'cnAccuracy':_v3712_pct(bucket,'CN'),
        'mtAccuracy':_v3712_pct(bucket,'MT'),
        'c1':means['c1'],'c2':means['c2'],'c3':means['c3'],'c4':means['c4'],'c5':means['c5'],
        'redaction':redaction,
    }

def _v3712_rows(app,c,year=''):
    class_lookup=_v36_class_lookup(app,c)
    sql="""SELECT p.user_id,p.activity_key,p.activity,p.applied_on,p.metrics,p.metadata,
                  u.name AS student_name,u.username
           FROM hmay_performance p
           JOIN hmay_users u ON u.id=p.user_id
           WHERE u.role IN ('user','aluno') AND u.active=1"""
    args=[]
    if year:
        sql+=' AND p.applied_on LIKE ?'
        args.append(year+'%')
    sql+=' ORDER BY p.applied_on,p.activity,u.name'
    rows=[]
    for raw in app.db.execute(c,sql,tuple(args)).fetchall():
        row=dict(raw)
        meta=_rx_json(row.get('metadata'))
        raw_class=F.text(meta.get('TURMA'),160) or 'Sem turma'
        row['_meta']=meta
        row['_turma']=class_lookup.get(F.norm(raw_class),raw_class)
        row['_token']=_v3712_sim_token(row['activity_key'],row['applied_on'])
        rows.append(row)
    return rows

def _v3712_options(rows):
    options={}
    for row in rows:
        options[row['_token']]={
            'token':row['_token'],'activityKey':row['activity_key'],
            'activity':row['activity'],'date':row['applied_on'],
        }
    return sorted(options.values(),key=lambda x:(x['date'],F.norm(x['activity'])),reverse=True)

def _v3712_class_analytics(app,c,query):
    year=_v3712_query_scalar(query,'year',4)
    selected=_v3712_selected_sims(query)
    rows=_v3712_rows(app,c,year)
    area_maps=_v36_exam_area_maps(app,c)
    options=_v3712_options(rows)
    buckets={}
    for row in rows:
        if selected and row['_token'] not in selected:
            continue
        bucket=buckets.setdefault(row['_turma'],_v3712_bucket())
        _v3712_add(bucket,row,row['_meta'],area_maps)
    classes=[]
    for turma,bucket in buckets.items():
        classes.append({'turma':turma,**_v3712_summary(bucket)})
    classes.sort(key=lambda x:F.norm(x['turma']))
    return {
        'year':year,'selectedSims':sorted(selected),
        'simulations':options,'classes':classes,
    }

def _v3712_class_detail(app,c,query):
    year=_v3712_query_scalar(query,'year',4)
    turma=_v3712_query_scalar(query,'turma',160)
    selected=_v3712_selected_sims(query)
    if not turma:
        raise ValueError('Turma não informada.')
    rows=_v3712_rows(app,c,year)
    area_maps=_v36_exam_area_maps(app,c)
    buckets={}
    labels={}
    for row in rows:
        if row['_turma']!=turma:
            continue
        if selected and row['_token'] not in selected:
            continue
        bucket=buckets.setdefault(row['_token'],_v3712_bucket())
        labels[row['_token']]={'activityKey':row['activity_key'],'activity':row['activity'],'date':row['applied_on']}
        _v3712_add(bucket,row,row['_meta'],area_maps)
    result=[]
    for token,bucket in buckets.items():
        result.append({'token':token,**labels[token],**_v3712_summary(bucket)})
    result.sort(key=lambda x:(x['date'],F.norm(x['activity'])),reverse=True)
    return {'turma':turma,'simulations':result}

def _v3712_student_detail(app,c,query):
    turma=_v3712_query_scalar(query,'turma',160)
    activity_key=_v3712_query_scalar(query,'activityKey',250)
    date=_v3712_query_scalar(query,'date',40)
    if not turma or not activity_key or not date:
        raise ValueError('Turma, simulado e data são obrigatórios.')
    rows=_v3712_rows(app,c,date[:4] if len(date)>=4 else '')
    area_maps=_v36_exam_area_maps(app,c)
    students=[]
    for row in rows:
        if row['_turma']!=turma or row['activity_key']!=activity_key or row['applied_on']!=date:
            continue
        bucket=_v3712_bucket()
        _v3712_add(bucket,row,row['_meta'],area_maps)
        summary=_v3712_summary(bucket)
        students.append({
            'userId':row['user_id'],'name':row['student_name'],'username':row['username'],
            **summary,
        })
    students.sort(key=lambda x:(-(x['enem'] if x['enem'] is not None else -1e9),F.norm(x['name'])))
    for index,row in enumerate(students,1):
        row['ranking']=index
    return {'turma':turma,'activityKey':activity_key,'date':date,'students':students}

def handle(app,c,user,path,method,data,query,start,HTTPError):
    if path in (
        '/api/model-data/management-class-analytics',
        '/api/model-data/management-class-detail',
        '/api/model-data/management-simulation-students',
    ):
        if user.get('role') not in ('master','coordenador'):
            raise HTTPError(403,'Acesso reservado ao Master e à coordenação.')
        if method!='GET':
            raise HTTPError(405,'Use GET para consultar a análise de turmas.')
        if path.endswith('management-class-analytics'):
            return app.reply(start,200,_v3712_class_analytics(app,c,query))
        if path.endswith('management-class-detail'):
            return app.reply(start,200,_v3712_class_detail(app,c,query))
        return app.reply(start,200,_v3712_student_detail(app,c,query))
    return _v3712_handle_base(app,c,user,path,method,data,query,start,HTTPError)
'''

JS=r'''
// === CLASS ENEM ANALYTICS V3.7.12 ===
let managementClassAnalyticsCache=null;
let managementClassAnalyticsLoading=false;
let managementClassSelectedSims=new Set();
let managementClassOpen='';
let managementClassDetailCache=new Map();
let managementSimulationOpen='';
let managementStudentDetailCache=new Map();

function mgmtAnalyticsQuery(extra={}){
 const q=new URLSearchParams();
 const year=managementDashboardFilters?.year||'';
 if(year)q.set('year',year);
 if(managementClassSelectedSims.size)q.set('sims',[...managementClassSelectedSims].join('||'));
 Object.entries(extra).forEach(([k,v])=>{if(v!==undefined&&v!==null&&String(v)!=='')q.set(k,String(v));});
 return q.toString();
}
async function loadManagementClassAnalytics(force=false){
 if(!managementDashboardAllowed()||managementClassAnalyticsLoading||(!force&&managementClassAnalyticsCache))return;
 managementClassAnalyticsLoading=true;
 try{
  managementClassAnalyticsCache=await api('/api/model-data/management-class-analytics?'+mgmtAnalyticsQuery());
 }catch(error){
  managementClassAnalyticsCache={error:error?.message||'Não foi possível carregar a análise por turma.'};
 }finally{
  managementClassAnalyticsLoading=false;
  if(view==='home')render();
 }
}
async function loadManagementClassDetail(turma){
 const key=turma+'@@'+[...managementClassSelectedSims].sort().join('|')+'@@'+(managementDashboardFilters?.year||'');
 if(managementClassDetailCache.has(key))return managementClassDetailCache.get(key);
 const data=await api('/api/model-data/management-class-detail?'+mgmtAnalyticsQuery({turma}));
 managementClassDetailCache.set(key,data);return data;
}
async function loadManagementStudentDetail(turma,activityKey,date){
 const key=[turma,activityKey,date].join('@@');
 if(managementStudentDetailCache.has(key))return managementStudentDetailCache.get(key);
 const data=await api('/api/model-data/management-simulation-students?'+mgmtAnalyticsQuery({turma,activityKey,date}));
 managementStudentDetailCache.set(key,data);return data;
}
function mgmtVal(v,d=1,suffix=''){return managementFmt(v,d,suffix);}
function mgmtAnalyticsCells(x){
 return '<td>'+mgmtVal(x.enem,1)+'</td><td>'+mgmtVal(x.bonus,1)+'</td>'+
 '<td>'+mgmtVal(x.accuracy,1,'%')+'</td><td>'+mgmtVal(x.lcAccuracy,1,'%')+'</td>'+
 '<td>'+mgmtVal(x.chAccuracy,1,'%')+'</td><td>'+mgmtVal(x.cnAccuracy,1,'%')+'</td>'+
 '<td>'+mgmtVal(x.mtAccuracy,1,'%')+'</td><td>'+mgmtVal(x.c1,1)+'</td><td>'+mgmtVal(x.c2,1)+'</td>'+
 '<td>'+mgmtVal(x.c3,1)+'</td><td>'+mgmtVal(x.c4,1)+'</td><td>'+mgmtVal(x.c5,1)+'</td><td>'+mgmtVal(x.redaction,1)+'</td>';
}
function mgmtAnalyticsHead(first){
 return '<tr><th>'+first+'</th><th>Participantes</th><th>Simulados</th><th>Nota ENEM</th><th>+10%</th><th>Acertos</th><th>LC</th><th>CH</th><th>CN</th><th>MT</th><th>C1</th><th>C2</th><th>C3</th><th>C4</th><th>C5</th><th>Redação</th></tr>';
}
function managementSimulationSelectorHtml(data){
 const options=managementSafeArray(data?.simulations);
 const selected=managementClassSelectedSims;
 return '<div class="management-multi-sims"><div class="management-multi-sims-head"><div><strong>Simulados considerados nas médias</strong><p class="micro">Se nenhum estiver marcado, entram todos os simulados realizados pela turma.</p></div><div class="actions"><button type="button" class="secondary" data-act="management-sims-clear">Limpar seleção</button><button type="button" class="primary" data-act="management-sims-apply">Aplicar seleção</button></div></div><div class="management-sim-checks">'+
 options.map(x=>'<label><input type="checkbox" data-management-sim-token="'+esc(x.token)+'"'+(selected.has(x.token)?' checked':'')+'><span><strong>'+esc(x.activity)+'</strong><small>'+esc(x.date)+'</small></span></label>').join('')+
 '</div></div>';
}
function managementStudentRowsHtml(data){
 const rows=managementSafeArray(data?.students);
 if(!rows.length)return '<div class="notice">Nenhum aluno encontrado neste simulado.</div>';
 return '<div class="table-wrap management-nested-table"><table><thead><tr><th>Ranking</th><th>Aluno</th><th>Nota ENEM</th><th>+10%</th><th>Acertos</th><th>LC</th><th>CH</th><th>CN</th><th>MT</th><th>C1</th><th>C2</th><th>C3</th><th>C4</th><th>C5</th><th>Redação</th></tr></thead><tbody>'+
 rows.map(x=>'<tr><td><strong>'+managementInt(x.ranking)+'</strong></td><td><strong>'+esc(x.name)+'</strong><br><small>'+esc(x.username||'')+'</small></td>'+mgmtAnalyticsCells(x)+'</tr>').join('')+
 '</tbody></table></div>';
}
function managementClassDetailHtml(turma){
 const key=turma+'@@'+[...managementClassSelectedSims].sort().join('|')+'@@'+(managementDashboardFilters?.year||'');
 const data=managementClassDetailCache.get(key);
 if(!data)return '<div class="management-analytics-loading">Carregando simulados da turma…</div>';
 const rows=managementSafeArray(data.simulations);
 if(!rows.length)return '<div class="notice">Nenhum simulado encontrado para esta turma com a seleção atual.</div>';
 return '<div class="table-wrap management-nested-table"><table><thead>'+mgmtAnalyticsHead('Simulado')+'</thead><tbody>'+
 rows.map(x=>{
  const simKey=turma+'@@'+x.activityKey+'@@'+x.date;
  const open=managementSimulationOpen===simKey;
  const detail=managementStudentDetailCache.get(simKey);
  return '<tr class="management-drill-row'+(open?' open':'')+'" data-act="management-simulation-drill" data-turma="'+encodeURIComponent(turma)+'" data-activity-key="'+encodeURIComponent(x.activityKey)+'" data-date="'+esc(x.date)+'"><td><strong>'+esc(x.activity)+'</strong><br><small>'+esc(x.date)+'</small></td><td>'+managementInt(x.participants)+'</td><td>1</td>'+mgmtAnalyticsCells(x)+'</tr>'+
   (open?'<tr class="management-drill-detail"><td colspan="16">'+(detail?managementStudentRowsHtml(detail):'<div class="management-analytics-loading">Carregando alunos e ranking…</div>')+'</td></tr>':'');
 }).join('')+
 '</tbody></table></div>';
}
function managementClassAnalyticsTableHtml(data){
 const rows=managementSafeArray(data?.classes);
 if(!rows.length)return '<div class="notice">Nenhuma turma com resultados para os simulados selecionados.</div>';
 return '<div class="table-wrap management-analytics-main"><table><thead>'+mgmtAnalyticsHead('Turma')+'</thead><tbody>'+
 rows.map(x=>{
  const open=managementClassOpen===x.turma;
  return '<tr class="management-drill-row'+(open?' open':'')+'" data-act="management-class-drill" data-turma="'+encodeURIComponent(x.turma)+'"><td><strong>'+esc(x.turma)+'</strong></td><td>'+managementInt(x.participants)+'</td><td>'+managementInt(x.simulations)+'</td>'+mgmtAnalyticsCells(x)+'</tr>'+
  (open?'<tr class="management-drill-detail"><td colspan="16">'+managementClassDetailHtml(x.turma)+'</td></tr>':'');
 }).join('')+
 '</tbody></table></div>';
}
function managementClassAnalyticsSection(){
 if(!managementClassAnalyticsCache&&!managementClassAnalyticsLoading)queueMicrotask(()=>loadManagementClassAnalytics());
 if(managementClassAnalyticsLoading||!managementClassAnalyticsCache)return '<section class="card"><h2>Médias por turma</h2><p>Carregando análise das turmas…</p></section>';
 if(managementClassAnalyticsCache.error)return '<section class="card"><h2>Médias por turma</h2><div class="notice warning">'+esc(managementClassAnalyticsCache.error)+'</div></section>';
 return '<section class="card management-class-analytics"><h2>Médias por turma</h2><p class="micro">Nota ENEM = média de LC, CH, CN, MT e Redação. O bônus corresponde a 10%. A nota de Redação exibida é C1+C2+C3+C4+C5 pelas médias de competência.</p>'+
 managementSimulationSelectorHtml(managementClassAnalyticsCache)+managementClassAnalyticsTableHtml(managementClassAnalyticsCache)+'</section>';
}
const managementDashboardViewV3712Base=managementDashboardView;
managementDashboardView=function(){
 const base=managementDashboardViewV3712Base();
 if(!managementDashboardAllowed())return base;
 return base+managementClassAnalyticsSection();
};

acts['management-sims-clear']=()=>{
 managementClassSelectedSims.clear();
 document.querySelectorAll('[data-management-sim-token]').forEach(x=>x.checked=false);
 managementClassAnalyticsCache=null;managementClassDetailCache.clear();managementStudentDetailCache.clear();
 managementClassOpen='';managementSimulationOpen='';
 loadManagementClassAnalytics(true);
};
acts['management-sims-apply']=()=>{
 managementClassSelectedSims=new Set([...document.querySelectorAll('[data-management-sim-token]:checked')].map(x=>x.dataset.managementSimToken));
 managementClassAnalyticsCache=null;managementClassDetailCache.clear();managementStudentDetailCache.clear();
 managementClassOpen='';managementSimulationOpen='';
 loadManagementClassAnalytics(true);
};
acts['management-class-drill']=async el=>{
 const turma=decodeURIComponent(el?.dataset?.turma||'');
 if(!turma)return;
 if(managementClassOpen===turma){managementClassOpen='';managementSimulationOpen='';render();return;}
 managementClassOpen=turma;managementSimulationOpen='';render();
 try{await loadManagementClassDetail(turma);}catch(e){toast(e?.message||'Não foi possível abrir os simulados.',true);}
 render();
};
acts['management-simulation-drill']=async el=>{
 const turma=decodeURIComponent(el?.dataset?.turma||'');
 const activityKey=decodeURIComponent(el?.dataset?.activityKey||'');
 const date=el?.dataset?.date||'';
 const key=turma+'@@'+activityKey+'@@'+date;
 if(managementSimulationOpen===key){managementSimulationOpen='';render();return;}
 managementSimulationOpen=key;render();
 try{
  const data=await loadManagementStudentDetail(turma,activityKey,date);
  managementStudentDetailCache.set(key,data);
 }catch(e){toast(e?.message||'Não foi possível abrir os alunos.',true);}
 render();
};

const managementLoadV3712Base=loadManagementDashboard;
loadManagementDashboard=async function(force=false){
 const result=await managementLoadV3712Base(force);
 if(force){
  managementClassAnalyticsCache=null;managementClassDetailCache.clear();managementStudentDetailCache.clear();
  if(view==='home')queueMicrotask(()=>loadManagementClassAnalytics(true));
 }
 return result;
};
'''

CSS=r'''
/* === CLASS ENEM ANALYTICS V3.7.12 === */
.management-class-analytics{display:grid;gap:1rem}.management-multi-sims{border:1px solid var(--line);border-radius:14px;padding:.9rem;background:#fffafb}.management-multi-sims-head{display:flex;justify-content:space-between;gap:1rem;align-items:flex-start}.management-multi-sims-head p{margin:.25rem 0 0}.management-sim-checks{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:.45rem;margin-top:.75rem;max-height:220px;overflow:auto}.management-sim-checks label{display:flex;gap:.5rem;align-items:flex-start;border:1px solid var(--line);border-radius:10px;padding:.55rem;background:#fff}.management-sim-checks span{display:grid}.management-sim-checks small{color:var(--muted)}.management-analytics-main table,.management-nested-table table{min-width:1650px}.management-drill-row{cursor:pointer}.management-drill-row:hover,.management-drill-row.open{background:#fff6f8}.management-drill-detail>td{padding:.7rem!important;background:#fffafb}.management-nested-table{border:1px solid var(--line);border-radius:10px;background:#fff}.management-analytics-loading{padding:1rem;color:var(--muted)}.management-class-analytics th,.management-class-analytics td{white-space:nowrap}.management-class-analytics td:first-child,.management-class-analytics th:first-child{position:sticky;left:0;background:inherit;z-index:1}.management-class-analytics th:first-child{background:#fff}
@media(max-width:900px){.management-sim-checks{grid-template-columns:repeat(2,minmax(0,1fr))}.management-multi-sims-head{display:grid}}
@media(max-width:600px){.management-sim-checks{grid-template-columns:1fr}}
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
    source=re.sub(r'/static/student_summary\.js\?v=[^"\']+','/static/student_summary.js?v=3.7.12',source)
    html.write_text(source,encoding='utf-8')

    for verifier in ROOT.glob('verify_*.py'):
        source=verifier.read_text(encoding='utf-8')
        source=source.replace('/static/student_summary.js?v=3.7.11','/static/student_summary.js?v=3.7.12')
        source=source.replace('v3.7.11','v3.7.12')
        verifier.write_text(source,encoding='utf-8')

    site=ROOT/'site_version_release.py'
    if site.exists():
        source=site.read_text(encoding='utf-8').replace('PUBLIC_VERSION="3.7.11"','PUBLIC_VERSION="3.7.12"')
        site.write_text(source,encoding='utf-8')

    vsite=ROOT/'verify_site_version.py'
    if vsite.exists():
        source=vsite.read_text(encoding='utf-8').replace('v3.7.11','v3.7.12')
        vsite.write_text(source,encoding='utf-8')

    print('MEUCRONOGRAMA_CLASS_ENEM_ANALYTICS_READY: class averages, simulation drill-down, student ranking and multi-simulation selection installed.',flush=True)

if __name__=='__main__':
    main()
