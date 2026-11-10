"""Management dashboard for master/coordinator with aggregate simulation intelligence."""
from pathlib import Path
import re

ROOT=Path(__file__).resolve().parent
STATIC=ROOT/"static"
BACKEND_MARK="# === MANAGEMENT DASHBOARD V3.5 ==="
JS_MARK="// === MANAGEMENT DASHBOARD V3.5 ==="
CSS_MARK="/* === MANAGEMENT DASHBOARD V3.5 === */"

BACKEND=r'''
# === MANAGEMENT DASHBOARD V3.5 ===
_management_dashboard_original_handle = handle

def _mgmt_mean(values):
    vals=[]
    for value in values:
        try:
            if value is not None and value != '':
                vals.append(float(value))
        except Exception:
            pass
    return None if not vals else round(sum(vals)/len(vals),3)

def _mgmt_area_key(name):
    raw=F.norm(name or '')
    if raw in ('lc','linguagens') or 'lingu' in raw:
        return 'LC'
    if raw in ('ch','humanas') or 'human' in raw:
        return 'CH'
    if raw in ('cn','natureza') or 'nature' in raw:
        return 'CN'
    if raw in ('mt','matematica') or 'matem' in raw:
        return 'MT'
    return None

def _mgmt_dashboard_data(app,c,user,query):
    if user.get('role') not in ('master','coordenador'):
        raise ValueError('Painel gerencial exclusivo do Master e da coordenação.')

    requested_year=F.text((query or {}).get('year'),4)
    requested_turma=F.text((query or {}).get('turma'),160)
    requested_activity=F.text((query or {}).get('activityKey'),250)
    requested_date=F.text((query or {}).get('date'),40)

    active_students=app.db.execute(
        c,"SELECT COUNT(*) AS n FROM hmay_users WHERE role IN ('user','aluno') AND active=1"
    ).fetchone()['n']

    raw_rows=app.db.execute(
        c,
        """SELECT p.id,p.user_id,p.activity_key,p.activity,p.applied_on,p.metrics,p.metadata
           FROM hmay_performance p
           JOIN hmay_users u ON u.id=p.user_id
           WHERE u.role IN ('user','aluno') AND u.active=1
           ORDER BY p.applied_on,p.activity,u.name,u.username"""
    ).fetchall()

    turmas=set()
    years=set()
    sim_options={}
    prepared=[]
    for raw in raw_rows:
        row=dict(raw)
        metadata=_rx_json(row.get('metadata'))
        turma=F.text(metadata.get('TURMA'),160) or 'Sem turma'
        turmas.add(turma)
        date=F.text(row.get('applied_on'),40)
        if len(date)>=4:
            years.add(date[:4])
        sim_options[(row.get('activity_key',''),date)]={
            'activityKey':row.get('activity_key',''),
            'activity':row.get('activity',''),
            'date':date,
        }
        prepared.append((row,metadata,turma))

    exam_rows=app.db.execute(
        c,'SELECT id,title,applied_on,color FROM hmay_exams ORDER BY applied_on,title,color'
    ).fetchall()
    maps_count=0
    catalog_sims=set()
    for exam in exam_rows:
        date=F.text(exam['applied_on'],40)
        if requested_year and not date.startswith(requested_year):
            continue
        maps_count+=1
        catalog_sims.add((F.norm(exam['title']),date))

    filtered=[]
    for row,metadata,turma in prepared:
        date=F.text(row.get('applied_on'),40)
        if requested_year and not date.startswith(requested_year):
            continue
        if requested_turma and turma != requested_turma:
            continue
        if requested_activity and row.get('activity_key') != requested_activity:
            continue
        if requested_date and date != requested_date:
            continue
        filtered.append((row,metadata,turma))

    exam_cache={}
    participants=set()
    total_correct=total_marked=total_valid=0
    tri_general=[]
    redactions=[]
    areas={key:{'correct':0,'marked':0,'valid':0,'tri':[]} for key in ('LC','CH','CN','MT')}
    simulations={}
    classes={}

    for row,metadata,turma in filtered:
        exam_id=F.text(metadata.get('_exam_id'),160)
        if not exam_id:
            continue
        if exam_id not in exam_cache:
            exam_cache[exam_id]=E.get_exam(app,c,exam_id)
        exam=exam_cache.get(exam_id)
        if not exam:
            continue

        analysis=_rx_analyse(exam,_rx_json(row.get('metrics')),metadata)
        overall=analysis['overall']
        participants.add(row['user_id'])
        correct=max(0,int(overall.get('correct') or 0))
        marked=max(0,int(overall.get('marked') or 0))
        valid=max(0,int(overall.get('total') or 0))
        total_correct+=correct
        total_marked+=marked
        total_valid+=valid

        scores=_tri_scores_from_metadata(metadata)
        if scores.get('tri') is not None:
            tri_general.append(scores['tri'])
        if scores.get('redaction') is not None:
            redactions.append(scores['redaction'])

        skey=(row['activity_key'],row['applied_on'])
        sim=simulations.setdefault(skey,{
            'activityKey':row['activity_key'],'activity':row['activity'],'date':row['applied_on'],
            'participants':set(),'correct':0,'marked':0,'valid':0,
            'triGeneral':[],'lc':[],'ch':[],'cn':[],'mt':[],'redaction':[],
        })
        sim['participants'].add(row['user_id'])
        sim['correct']+=correct;sim['marked']+=marked;sim['valid']+=valid

        cls=classes.setdefault(turma,{
            'turma':turma,'participants':set(),'correct':0,'marked':0,'valid':0,
            'triGeneral':[],'redaction':[],
        })
        cls['participants'].add(row['user_id'])
        cls['correct']+=correct;cls['marked']+=marked;cls['valid']+=valid

        for key,value in (
            ('triGeneral',scores.get('tri')),('lc',scores.get('lc')),('ch',scores.get('ch')),
            ('cn',scores.get('cn')),('mt',scores.get('mt')),('redaction',scores.get('redaction'))
        ):
            if value is not None:
                sim[key].append(value)
        if scores.get('tri') is not None:
            cls['triGeneral'].append(scores['tri'])
        if scores.get('redaction') is not None:
            cls['redaction'].append(scores['redaction'])

        for item in analysis['groups'].get('Área',[]):
            key=_mgmt_area_key(item.get('name'))
            if not key:
                continue
            bucket=areas[key]
            bucket['correct']+=max(0,int(item.get('correct') or 0))
            bucket['marked']+=max(0,int(item.get('marked') or 0))
            bucket['valid']+=max(0,int(item.get('total') or 0))
        for area_key,score_key in (('LC','lc'),('CH','ch'),('CN','cn'),('MT','mt')):
            value=scores.get(score_key)
            if value is not None:
                areas[area_key]['tri'].append(value)

    sim_rows=[]
    for sim in simulations.values():
        sim_rows.append({
            'activityKey':sim['activityKey'],'activity':sim['activity'],'date':sim['date'],
            'participants':len(sim['participants']),'correct':sim['correct'],'valid':sim['valid'],
            'accuracy':None if not sim['marked'] else round(100*sim['correct']/sim['marked'],2),
            'triGeneral':_mgmt_mean(sim['triGeneral']),'lc':_mgmt_mean(sim['lc']),
            'ch':_mgmt_mean(sim['ch']),'cn':_mgmt_mean(sim['cn']),'mt':_mgmt_mean(sim['mt']),
            'redaction':_mgmt_mean(sim['redaction']),
        })
    sim_rows.sort(key=lambda x:(x['date'],F.norm(x['activity'])),reverse=True)

    class_rows=[]
    for cls in classes.values():
        class_rows.append({
            'turma':cls['turma'],'participants':len(cls['participants']),
            'correct':cls['correct'],'valid':cls['valid'],
            'accuracy':None if not cls['marked'] else round(100*cls['correct']/cls['marked'],2),
            'triGeneral':_mgmt_mean(cls['triGeneral']),'redaction':_mgmt_mean(cls['redaction']),
        })
    class_rows.sort(key=lambda x:(-(x['participants'] or 0),F.norm(x['turma'])))

    area_rows=[]
    for key,label in (('LC','Linguagens'),('CH','Humanas'),('CN','Natureza'),('MT','Matemática')):
        bucket=areas[key]
        area_rows.append({
            'key':key,'name':label,'correct':bucket['correct'],'valid':bucket['valid'],
            'accuracy':None if not bucket['marked'] else round(100*bucket['correct']/bucket['marked'],2),
            'tri':_mgmt_mean(bucket['tri']),
        })

    options=sorted(sim_options.values(),key=lambda x:(x['date'],F.norm(x['activity'])),reverse=True)
    return {
        'filters':{
            'years':sorted(years,reverse=True),
            'turmas':sorted(turmas,key=F.norm),
            'simulations':options,
            'selected':{
                'year':requested_year,'turma':requested_turma,
                'activityKey':requested_activity,'date':requested_date,
            },
        },
        'kpis':{
            'activeStudents':active_students,'participants':len(participants),
            'catalogSimulations':len(catalog_sims),'maps':maps_count,
            'simulationsWithResults':len(sim_rows),'participations':len(filtered),
            'correct':total_correct,'valid':total_valid,
            'accuracy':None if not total_marked else round(100*total_correct/total_marked,2),
            'triGeneral':_mgmt_mean(tri_general),'redaction':_mgmt_mean(redactions),
        },
        'areas':area_rows,'simulations':sim_rows,'classes':class_rows,
    }

def handle(app,c,user,path,method,data,query,start,HTTPError):
    if path == '/api/model-data/management-dashboard':
        if user.get('role') not in ('master','coordenador'):
            raise HTTPError(403,'Painel gerencial exclusivo do Master e da coordenação.')
        if method != 'GET':
            raise HTTPError(405,'Use GET para consultar o painel gerencial.')
        return app.reply(start,200,_mgmt_dashboard_data(app,c,user,query))
    return _management_dashboard_original_handle(app,c,user,path,method,data,query,start,HTTPError)
'''

JS=r'''
// === MANAGEMENT DASHBOARD V3.5 ===
let managementDashboardCache=null;
let managementDashboardLoading=false;
let managementDashboardFilters={year:'',turma:'',activityKey:'',date:''};

function managementDashboardAllowed(){return typeof ME!=='undefined'&&ME&&['master','coordenador'].includes(ME.role);}
function managementFmt(value,digits=1,suffix=''){const n=Number(value);return value===null||value===undefined||value===''||!Number.isFinite(n)?'—':n.toLocaleString('pt-BR',{minimumFractionDigits:digits,maximumFractionDigits:digits})+suffix;}
function managementInt(value){const n=Number(value);return Number.isFinite(n)?Math.round(n).toLocaleString('pt-BR'):'0';}
async function loadManagementDashboard(force=false){
 if(!managementDashboardAllowed()||managementDashboardLoading||(!force&&managementDashboardCache))return;
 managementDashboardLoading=true;
 try{
  const q=new URLSearchParams();
  Object.entries(managementDashboardFilters).forEach(([key,value])=>{if(value)q.set(key,value);});
  managementDashboardCache=await api('/api/model-data/management-dashboard'+(q.toString()?'?'+q.toString():''));
 }catch(error){managementDashboardCache={error:error?.message||'Não foi possível carregar o painel gerencial.'};}
 finally{managementDashboardLoading=false;if(view==='home'&&typeof render==='function')render();}
}
function managementSelect(label,id,value,options){
 return '<label>'+label+'<select id="'+id+'"><option value="">Todos</option>'+options.map(opt=>{const raw=typeof opt==='string'?opt:opt.value,text=typeof opt==='string'?opt:opt.label;return '<option value="'+esc(raw)+'"'+(String(raw)===String(value||'')?' selected':'')+'>'+esc(text)+'</option>';}).join('')+'</select></label>';
}
function managementFiltersHtml(d){
 const f=d?.filters||{},s=f.selected||{};
 const sims=(f.simulations||[]).map(x=>({value:(x.activityKey||'')+'@@'+(x.date||''),label:(x.activity||'Simulado')+' · '+(x.date||'')}));
 const selected=(s.activityKey||s.date)?(s.activityKey||'')+'@@'+(s.date||''):'';
 return '<section class="management-filter-card"><div class="management-filter-grid">'+managementSelect('Ano','management-year',s.year||'',f.years||[])+managementSelect('Turma','management-turma',s.turma||'',f.turmas||[])+managementSelect('Simulado','management-simulation',selected,sims)+'</div><div class="actions"><button type="button" class="secondary" data-act="management-dashboard-refresh">Atualizar painel</button></div></section>';
}
function managementKpisHtml(k){
 const cards=[[managementInt(k.activeStudents),'alunos ativos'],[managementInt(k.participants),'alunos com participação'],[managementInt(k.catalogSimulations),'simulados cadastrados'],[managementInt(k.maps),'mapas cadastrados'],[managementInt(k.simulationsWithResults),'simulados com resultados'],[managementInt(k.participations),'participações registradas'],[managementFmt(k.accuracy,1,'%'),'aproveitamento TCT'],[managementFmt(k.triGeneral,1),'TRI geral média'],[managementFmt(k.redaction,1),'Redação média']];
 return '<div class="management-kpi-grid">'+cards.map(([v,l])=>'<div><strong>'+v+'</strong><span>'+l+'</span></div>').join('')+'</div>';
}
function managementAreaHtml(rows){
 if(!(rows||[]).length)return '<div class="notice">Sem dados de área para os filtros selecionados.</div>';
 return '<div class="management-area-grid">'+rows.map(x=>{const width=Math.max(0,Math.min(100,Number(x.accuracy||0)));return '<article><div class="management-area-title"><strong>'+esc(x.name)+'</strong><span>'+managementFmt(x.accuracy,1,'%')+'</span></div><div class="management-bar"><span style="width:'+width+'%"></span></div><div class="management-area-meta"><span>'+managementInt(x.correct)+'/'+managementInt(x.valid)+' acertos</span><span>TRI média '+managementFmt(x.tri,1)+'</span></div></article>';}).join('')+'</div>';
}
function managementSimulationChart(rows){
 const ordered=[...(rows||[])].sort((a,b)=>String(a.date||'').localeCompare(String(b.date||'')));
 if(!ordered.length)return '<div class="notice">Nenhum simulado com resultados nos filtros selecionados.</div>';
 return '<div class="management-sim-chart">'+ordered.map(x=>{const acc=Math.max(4,Math.min(100,Number(x.accuracy||0))),tri=Math.max(4,Math.min(100,Number(x.triGeneral||0)/10));return '<div class="management-sim-col" title="'+esc((x.activity||'Simulado')+' · '+(x.date||''))+'"><div class="management-dual-bars"><span class="tct" style="height:'+acc+'%"></span><span class="tri" style="height:'+tri+'%"></span></div><strong>'+esc(x.activity||'Simulado')+'</strong><small>'+esc(x.date||'')+'</small><em>'+managementInt(x.participants)+' participantes</em></div>';}).join('')+'</div><div class="management-legend"><span><i class="tct"></i>TCT %</span><span><i class="tri"></i>TRI geral ÷ 10</span></div>';
}
function managementSimulationTable(rows){
 const body=(rows||[]).map(x=>'<tr><td><strong>'+esc(x.activity||'Simulado')+'</strong><br><small>'+esc(x.date||'')+'</small></td><td>'+managementInt(x.participants)+'</td><td>'+managementInt(x.correct)+'/'+managementInt(x.valid)+'</td><td>'+managementFmt(x.accuracy,1,'%')+'</td><td>'+managementFmt(x.triGeneral,1)+'</td><td>'+managementFmt(x.lc,1)+'</td><td>'+managementFmt(x.ch,1)+'</td><td>'+managementFmt(x.cn,1)+'</td><td>'+managementFmt(x.mt,1)+'</td><td>'+managementFmt(x.redaction,1)+'</td></tr>').join('');
 return body?'<div class="table-wrap"><table><thead><tr><th>Simulado</th><th>Participantes</th><th>Acertos</th><th>TCT</th><th>TRI geral</th><th>LC</th><th>CH</th><th>CN</th><th>MT</th><th>Redação</th></tr></thead><tbody>'+body+'</tbody></table></div>':'<div class="notice">Sem resultados para listar.</div>';
}
function managementClassTable(rows){
 const body=(rows||[]).map(x=>'<tr><td><strong>'+esc(x.turma||'Sem turma')+'</strong></td><td>'+managementInt(x.participants)+'</td><td>'+managementInt(x.correct)+'/'+managementInt(x.valid)+'</td><td>'+managementFmt(x.accuracy,1,'%')+'</td><td>'+managementFmt(x.triGeneral,1)+'</td><td>'+managementFmt(x.redaction,1)+'</td></tr>').join('');
 return body?'<div class="table-wrap"><table><thead><tr><th>Turma</th><th>Participantes</th><th>Acertos</th><th>TCT</th><th>TRI geral</th><th>Redação</th></tr></thead><tbody>'+body+'</tbody></table></div>':'<div class="notice">Sem turmas para os filtros selecionados.</div>';
}
function managementDashboardView(){
 if(!managementDashboardCache&&!managementDashboardLoading)queueMicrotask(()=>loadManagementDashboard());
 if(managementDashboardLoading||!managementDashboardCache)return '<section class="card management-dashboard"><h2>Painel de bordo da coordenação</h2><p>Carregando indicadores gerais…</p></section>';
 const d=managementDashboardCache;
 if(d?.error)return '<section class="card management-dashboard"><h2>Painel de bordo da coordenação</h2><div class="notice warning">'+esc(d.error)+'</div><button type="button" class="secondary" data-act="management-dashboard-refresh">Tentar novamente</button></section>';
 return '<section class="management-dashboard"><div class="card management-hero"><div><p class="eyebrow">VISÃO GERENCIAL</p><h1>Painel de bordo da coordenação</h1><p>Simulados, participação, TCT, TRI, redação e turmas em uma única visão operacional.</p></div><div class="actions"><button type="button" class="secondary" data-act="management-go-import">Importar resultados</button><button type="button" class="secondary" data-act="management-go-exams">Mapas de questões</button><button type="button" class="primary" data-act="management-dashboard-refresh">Atualizar</button></div></div>'+managementFiltersHtml(d)+'<section class="card"><h2>Resumo geral</h2>'+managementKpisHtml(d.kpis||{})+'</section><section class="card"><h2>Médias por área</h2><p class="micro">TCT e TRI calculados com os participantes dos filtros selecionados.</p>'+managementAreaHtml(d.areas||[])+'</section><section class="card"><h2>Evolução dos simulados</h2>'+managementSimulationChart(d.simulations||[])+'</section><section class="card"><h2>Resumo por simulado</h2>'+managementSimulationTable(d.simulations||[])+'</section><section class="card"><h2>Resumo por turma</h2>'+managementClassTable(d.classes||[])+'</section></section>';
}
const managementOriginalHomeView=homeView;
homeView=function(){if(managementDashboardAllowed())return managementDashboardView();return managementOriginalHomeView();};
acts['management-dashboard-refresh']=async()=>{managementDashboardCache=null;await loadManagementDashboard(true);};
acts['management-go-import']=()=>{view='result-import';render();window.scrollTo(0,0);};
acts['management-go-exams']=()=>{view='exams';render();window.scrollTo(0,0);};
document.addEventListener('change',event=>{const el=event.target;if(!managementDashboardAllowed()||!el)return;if(el.id==='management-year'){managementDashboardFilters.year=el.value||'';managementDashboardCache=null;loadManagementDashboard(true);}if(el.id==='management-turma'){managementDashboardFilters.turma=el.value||'';managementDashboardCache=null;loadManagementDashboard(true);}if(el.id==='management-simulation'){const parts=(el.value||'').split('@@');managementDashboardFilters.activityKey=parts[0]||'';managementDashboardFilters.date=parts[1]||'';managementDashboardCache=null;loadManagementDashboard(true);}},true);
'''

CSS=r'''
/* === MANAGEMENT DASHBOARD V3.5 === */
.management-dashboard{display:grid;gap:1rem}.management-hero{display:flex;justify-content:space-between;gap:1rem;align-items:flex-start}.management-hero h1{margin:.1rem 0 .4rem;font-size:1.8rem}.management-filter-card{border:1px solid var(--line);border-radius:16px;background:#fff;padding:1rem;display:grid;gap:.7rem}.management-filter-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:.7rem}.management-kpi-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:.7rem}.management-kpi-grid>div{border:1px solid var(--line);border-radius:14px;padding:1rem;background:#fffafb;display:grid;gap:.2rem}.management-kpi-grid strong{font-size:1.45rem;color:#9f4351}.management-kpi-grid span{font-size:.78rem;color:var(--muted)}.management-area-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:.8rem}.management-area-grid article{border:1px solid var(--line);border-radius:14px;padding:.9rem}.management-area-title,.management-area-meta{display:flex;justify-content:space-between;gap:.8rem}.management-area-meta{font-size:.75rem;color:var(--muted);margin-top:.35rem}.management-bar{height:9px;background:#f3e0e4;border-radius:999px;overflow:hidden;margin-top:.5rem}.management-bar span{display:block;height:100%;background:linear-gradient(90deg,#b65362,#db8d99);border-radius:inherit}.management-sim-chart{height:260px;display:flex;align-items:flex-end;gap:1rem;overflow-x:auto;padding:1rem .4rem .4rem;border-bottom:1px solid var(--line)}.management-sim-col{height:100%;min-width:120px;display:grid;grid-template-rows:1fr auto auto auto;gap:.2rem;justify-items:center;text-align:center}.management-dual-bars{height:100%;width:56px;display:flex;gap:6px;align-items:flex-end}.management-dual-bars span{width:25px;min-height:5px;border-radius:7px 7px 2px 2px}.management-dual-bars .tct{background:#b65362}.management-dual-bars .tri{background:#7a5f98}.management-sim-col strong{max-width:120px;line-height:1.1}.management-sim-col small,.management-sim-col em{font-size:.68rem;color:var(--muted);font-style:normal}.management-legend{display:flex;gap:1rem;margin-top:.6rem;font-size:.75rem;color:var(--muted)}.management-legend span{display:flex;align-items:center;gap:.35rem}.management-legend i{width:12px;height:12px;border-radius:3px}.management-legend i.tct{background:#b65362}.management-legend i.tri{background:#7a5f98}
@media(max-width:900px){.management-hero{display:grid}.management-filter-grid,.management-kpi-grid{grid-template-columns:repeat(2,minmax(0,1fr))}.management-area-grid{grid-template-columns:1fr}}
@media(max-width:560px){.management-filter-grid,.management-kpi-grid{grid-template-columns:1fr}}
'''

def main():
    model=ROOT/"model_data.py"
    text=model.read_text(encoding="utf-8")
    if BACKEND_MARK not in text:
        model.write_text(text.rstrip()+"\n\n"+BACKEND.strip()+"\n",encoding="utf-8")
    js=STATIC/"student_summary.js"
    text=js.read_text(encoding="utf-8")
    if JS_MARK not in text:
        js.write_text(text.rstrip()+"\n\n"+JS.strip()+"\n",encoding="utf-8")
    css=STATIC/"style.css"
    text=css.read_text(encoding="utf-8")
    if CSS_MARK not in text:
        css.write_text(text.rstrip()+"\n\n"+CSS.strip()+"\n",encoding="utf-8")
    html=STATIC/"app.html"
    text=html.read_text(encoding="utf-8")
    text=re.sub(r'/static/student_summary\.js\?v=[^"\']+','/static/student_summary.js?v=3.5.0',text)
    html.write_text(text,encoding="utf-8")
    print("MEUCRONOGRAMA_MANAGEMENT_DASHBOARD_READY: master/coordinator aggregate dashboard with filters, KPIs, area averages and simulation/class tables installed.",flush=True)

if __name__=="__main__":
    main()
