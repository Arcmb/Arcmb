"""Enhance TRI dashboards with simulation filters, area evolution and essay history."""
from pathlib import Path
import re

ROOT=Path(__file__).resolve().parent
STATIC=ROOT/"static"
BACKEND_MARK="# === TRI DASHBOARD V3.3 ==="
TRI_JS_MARK="// === TRI DASHBOARD V3.3 ==="
HOME_JS_MARK="// === TRI HOME DASHBOARD V3.3 ==="
CSS_MARK="/* === TRI DASHBOARD V3.3 === */"

BACKEND = r'''
# === TRI DASHBOARD V3.3 ===
_tri_dashboard_original_summary = student_summary

def student_summary(app, c, user, target):
    result = _tri_dashboard_original_summary(app, c, user, target)
    metadata_by_simulation = _tri_simulation_metadata(app, c, target['id'])
    for simulation in result.get('simulations', []):
        metadata = metadata_by_simulation.get(
            (F.norm(simulation.get('activity')), simulation.get('date')),
            {},
        )
        scores = _tri_scores_from_metadata(metadata)
        simulation['triScores'] = {
            'ranking': scores.get('ranking'),
            'general': scores.get('tri'),
            'bonus': scores.get('triBonus'),
            'lc': scores.get('lc'),
            'ch': scores.get('ch'),
            'cn': scores.get('cn'),
            'mt': scores.get('mt'),
            'redaction': scores.get('redaction'),
        }
    return result
'''

TRI_JS = r'''
// === TRI DASHBOARD V3.3 ===
let triDashboardSelectedKeys=null;
let triDashboardAvailableKeys=[];
let triDashboardSelectionOwner=null;

function triDashNumber(value){
 const n=Number(value);
 return value===null||value===undefined||value===''||!Number.isFinite(n)?null:n;
}
function triDashFormat(value,digits=1){
 const n=triDashNumber(value);
 return n===null?'—':n.toLocaleString('pt-BR',{minimumFractionDigits:digits,maximumFractionDigits:digits});
}
function triDashboardKey(sim){
 return String(sim?.activity||'')+'@@'+String(sim?.date||'');
}
function triDashboardSort(simulations,ascending=false){
 const rows=[...(simulations||[])];
 rows.sort((a,b)=>{
  const date=String(a?.date||'').localeCompare(String(b?.date||''));
  if(date)return ascending?date:-date;
  const name=String(a?.activity||'').localeCompare(String(b?.activity||''),'pt-BR');
  return ascending?name:-name;
 });
 return rows;
}
function triDashboardScore(sim,key){
 const scores=sim?.triScores||{};
 let value=scores[key];
 if((value===null||value===undefined||value==='')&&key==='redaction')value=sim?.redaction?.score;
 return triDashNumber(value);
}
function triDashboardHasTri(sim){
 return ['general','lc','ch','cn','mt','redaction'].some(key=>triDashboardScore(sim,key)!==null);
}
function triDashboardEnsureSelection(simulations){
 const owner=typeof studentSummaryTarget==='function'?studentSummaryTarget():'';
 const keys=(simulations||[]).map(triDashboardKey);
 const valid=new Set(keys);
 if(triDashboardSelectionOwner!==owner){
  triDashboardSelectionOwner=owner;
  triDashboardSelectedKeys=null;
 }
 if(!(triDashboardSelectedKeys instanceof Set))triDashboardSelectedKeys=new Set(keys);
 else triDashboardSelectedKeys=new Set([...triDashboardSelectedKeys].filter(key=>valid.has(key)));
 triDashboardAvailableKeys=keys;
}
function triDashboardSelected(simulations){
 triDashboardEnsureSelection(simulations);
 return (simulations||[]).filter(sim=>triDashboardSelectedKeys.has(triDashboardKey(sim)));
}
function triDashboardFilterHtml(simulations){
 triDashboardEnsureSelection(simulations);
 const allChecked=triDashboardAvailableKeys.length>0&&triDashboardSelectedKeys.size===triDashboardAvailableKeys.length;
 const items=triDashboardSort(simulations,false).map(sim=>{
  const key=triDashboardKey(sim),checked=triDashboardSelectedKeys.has(key)?' checked':'';
  return '<label class="tri-dashboard-filter-item"><input type="checkbox" data-tri-dashboard-key="'+encodeURIComponent(key)+'"'+checked+'><span><strong>'+esc(sim.activity||'Simulado')+'</strong><small>'+esc(sim.date||'')+'</small></span></label>';
 }).join('');
 return '<section class="tri-dashboard-filter"><div class="tri-dashboard-filter-head"><div><h4>Simulados exibidos</h4><p class="micro">Selecione um, vários ou todos. Isso permite comparar apenas provas com parametrizações compatíveis.</p></div><label class="tri-dashboard-all"><input type="checkbox" data-tri-dashboard-all'+(allChecked?' checked':'')+'> Todos</label></div><div class="tri-dashboard-filter-grid">'+items+'</div></section>';
}
function triDashboardMetricCards(sim){
 const metrics=[
  ['general','TRI geral'],['lc','Linguagens'],['ch','Humanas'],
  ['cn','Natureza'],['mt','Matemática'],['redaction','Redação']
 ];
 return '<div class="tri-dashboard-score-grid">'+metrics.map(item=>{
  const value=triDashboardScore(sim,item[0]);
  return '<div><strong>'+triDashFormat(value,item[0]==='redaction'?0:1)+'</strong><span>'+item[1]+'</span></div>';
 }).join('')+'</div>';
}
function triDashboardComparison(rows){
 const body=triDashboardSort(rows,true).map(sim=>
  '<tr><td><strong>'+esc(sim.activity||'Simulado')+'</strong><br><small>'+esc(sim.date||'')+'</small></td>'+
  '<td>'+triDashFormat(triDashboardScore(sim,'general'))+'</td>'+
  '<td>'+triDashFormat(triDashboardScore(sim,'lc'))+'</td>'+
  '<td>'+triDashFormat(triDashboardScore(sim,'ch'))+'</td>'+
  '<td>'+triDashFormat(triDashboardScore(sim,'cn'))+'</td>'+
  '<td>'+triDashFormat(triDashboardScore(sim,'mt'))+'</td>'+
  '<td>'+triDashFormat(triDashboardScore(sim,'redaction'),0)+'</td></tr>'
 ).join('');
 return '<div class="tri-dashboard-comparison"><h4>Notas dos simulados selecionados</h4><div class="table-wrap"><table><thead><tr><th>Simulado</th><th>TRI geral</th><th>LC</th><th>CH</th><th>CN</th><th>MT</th><th>Redação</th></tr></thead><tbody>'+body+'</tbody></table></div></div>';
}
function triDashboardSeries(rows,key,label,digits=1){
 const ordered=triDashboardSort(rows,true).filter(sim=>triDashboardScore(sim,key)!==null);
 if(!ordered.length)return '<article class="tri-dashboard-series"><h4>'+esc(label)+'</h4><div class="notice">Sem nota TRI importada para esta série.</div></article>';
 const bars=ordered.map(sim=>{
  const value=triDashboardScore(sim,key);
  const height=Math.max(5,Math.min(100,(value/1000)*100));
  return '<div class="tri-dashboard-series-item" title="'+esc((sim.activity||'Simulado')+' · '+(sim.date||''))+'">'+
   '<span class="tri-dashboard-series-value">'+triDashFormat(value,digits)+'</span>'+
   '<div class="tri-dashboard-series-track"><span style="height:'+height+'%"></span></div>'+
   '<small>'+esc(sim.activity||'Simulado')+'</small><em>'+esc(sim.date||'')+'</em></div>';
 }).join('');
 return '<article class="tri-dashboard-series"><h4>'+esc(label)+'</h4><div class="tri-dashboard-series-chart">'+bars+'</div></article>';
}
function triDashboardEvolution(rows){
 const metrics=[
  ['general','TRI geral',1],['lc','Linguagens',1],['ch','Humanas',1],
  ['cn','Natureza',1],['mt','Matemática',1],['redaction','Redação',0]
 ];
 return '<section class="tri-dashboard-evolution"><h4>Evolução TRI por área</h4><p class="micro">A ordem é determinada pela data de aplicação. Cada coluna usa o nome real do simulado.</p><div class="tri-dashboard-evolution-grid">'+metrics.map(item=>triDashboardSeries(rows,item[0],item[1],item[2])).join('')+'</div></section>';
}
function triDashboardRedactionValue(sim,key){
 const red=sim?.redaction||{};
 if(key==='score'){
  const value=triDashNumber(red.score);
  return value===null?triDashboardScore(sim,'redaction'):value;
 }
 return key==='theme'?String(red.theme||''):triDashNumber(red[key]);
}
function triDashboardRedactionHistory(simulations){
 const rows=triDashboardSort(simulations,false).filter(sim=>{
  const red=sim?.redaction||{};
  return triDashboardRedactionValue(sim,'score')!==null||String(red.theme||'').trim()||['c1','c2','c3','c4','c5'].some(k=>triDashboardRedactionValue(sim,k)!==null);
 });
 if(!rows.length)return '<section class="tri-redaction-history"><h4>Histórico de redações</h4><div class="notice">Ainda não há redações importadas para este aluno.</div></section>';
 const body=rows.map(sim=>
  '<tr><td><strong>'+esc(sim.activity||'Simulado')+'</strong><br><small>'+esc(sim.date||'')+'</small></td>'+
  '<td>'+esc(triDashboardRedactionValue(sim,'theme')||'—')+'</td>'+
  '<td><strong>'+triDashFormat(triDashboardRedactionValue(sim,'score'),0)+'</strong></td>'+
  ['c1','c2','c3','c4','c5'].map(k=>'<td>'+triDashFormat(triDashboardRedactionValue(sim,k),0)+'</td>').join('')+
  '</tr>'
 ).join('');
 return '<section class="tri-redaction-history"><h4>Histórico de redações</h4><p class="micro">Redações em ordem da aplicação mais recente para a mais antiga.</p><div class="table-wrap"><table><thead><tr><th>Simulado</th><th>Tema</th><th>Nota</th><th>C1</th><th>C2</th><th>C3</th><th>C4</th><th>C5</th></tr></thead><tbody>'+body+'</tbody></table></div></section>';
}

triStudentPanel=function(d){
 const simulations=(d?.simulations||[]).filter(triDashboardHasTri);
 if(!simulations.length)return '<section class="card student-tri-panel"><p class="eyebrow">Escala TRI</p><h3>Notas TRI</h3><div class="notice">Ainda não há notas TRI importadas para este aluno.</div></section>';
 const selected=triDashboardSelected(simulations);
 const latest=triDashboardSort(selected,false)[0]||null;
 const filter=triDashboardFilterHtml(simulations);
 const selectedBlock=latest?
  '<div class="tri-dashboard-current"><div><p class="eyebrow">Simulado em destaque</p><h3>'+esc(latest.activity||'Simulado')+'</h3><p>'+esc(latest.date||'')+(latest.color?' · prova '+esc(latest.color):'')+'</p></div>'+triDashboardMetricCards(latest)+'</div>'+
  triDashboardComparison(selected)+triDashboardEvolution(selected):
  '<div class="notice warning">Selecione ao menos um simulado para visualizar as notas.</div>';
 return '<section class="card student-tri-panel tri-dashboard-panel"><div class="tri-dashboard-title"><div><p class="eyebrow">Escala TRI</p><h2>Notas e evolução TRI</h2></div></div>'+filter+selectedBlock+triDashboardRedactionHistory(simulations)+'<p class="micro">TRI e acertos/TCT são indicadores diferentes. Use a seleção acima para evitar comparar simulados com parametrizações incompatíveis.</p></section>';
};

document.addEventListener('change',event=>{
 const target=event.target;
 if(!target)return;
 if(target.matches('[data-tri-dashboard-all]')){
  triDashboardSelectedKeys=target.checked?new Set(triDashboardAvailableKeys):new Set();
  if(typeof render==='function')render();
  return;
 }
 if(target.matches('[data-tri-dashboard-key]')){
  if(!(triDashboardSelectedKeys instanceof Set))triDashboardSelectedKeys=new Set(triDashboardAvailableKeys);
  const key=decodeURIComponent(target.dataset.triDashboardKey||'');
  if(target.checked)triDashboardSelectedKeys.add(key);else triDashboardSelectedKeys.delete(key);
  if(typeof render==='function')render();
 }
},true);
'''

HOME_JS = r'''
// === TRI HOME DASHBOARD V3.3 ===
function triHomeScore(sim,key){
 const scores=sim?.triScores||{};
 const raw=key==='redaction'?(scores.redaction??sim?.redaction?.score):scores[key];
 const n=Number(raw);
 return raw===null||raw===undefined||raw===''||!Number.isFinite(n)?null:n;
}
function triHomeSorted(simulations,ascending=true){
 const rows=[...(simulations||[])];
 rows.sort((a,b)=>{
  const date=String(a?.date||'').localeCompare(String(b?.date||''));
  if(date)return ascending?date:-date;
  const name=String(a?.activity||'').localeCompare(String(b?.activity||''),'pt-BR');
  return ascending?name:-name;
 });
 return rows;
}
function triHomeFmt(value,digits=1){
 const n=Number(value);
 return value===null||value===undefined||value===''||!Number.isFinite(n)?'—':n.toLocaleString('pt-BR',{minimumFractionDigits:digits,maximumFractionDigits:digits});
}
studentHomeEvolution=function(simulations){
 const rows=triHomeSorted(simulations,true).filter(sim=>triHomeScore(sim,'general')!==null);
 if(!rows.length)return '<div class="notice">As notas TRI aparecerão aqui depois da importação.</div>';
 const bars=rows.map(sim=>{
  const value=triHomeScore(sim,'general'),height=Math.max(5,Math.min(100,(value/1000)*100));
  return '<div class="student-home-evolution-item tri-home-evolution-item" title="'+esc((sim.activity||'Simulado')+' · '+(sim.date||''))+'">'+
   '<span class="student-home-evolution-value">'+triHomeFmt(value,0)+'</span>'+
   '<div class="student-home-evolution-track tri-track"><span style="height:'+height+'%"></span></div>'+
   '<small>'+esc(sim.activity||'Simulado')+'</small><em>'+esc(sim.date||'')+'</em></div>';
 }).join('');
 return '<div class="student-home-evolution tri-home-evolution">'+bars+'</div><p class="micro">TRI geral em ordem cronológica pela data de aplicação.</p>';
};

const triHomeOriginalDashboardV33=studentHomeDashboard;
studentHomeDashboard=function(){
 let base=triHomeOriginalDashboardV33();
 base=base.replace('<h3>Desempenho por área</h3>','<h3>Acertos/TCT por área</h3>');
 base=base.replace('<h3>Evolução nos simulados</h3>','<h3>Evolução da TRI geral</h3>');
 const id=studentSummaryTarget();
 const d=studentSummaryCache.get(id);
 if(!d||d.error)return base;
 const latest=triHomeSorted((d.simulations||[]).filter(sim=>['lc','ch','cn','mt','redaction'].some(k=>triHomeScore(sim,k)!==null)),false)[0];
 if(!latest)return base;
 const metrics=[
  ['general','TRI geral',1],['lc','Linguagens',1],['ch','Humanas',1],
  ['cn','Natureza',1],['mt','Matemática',1],['redaction','Redação',0]
 ];
 const cards=metrics.map(item=>'<div><strong>'+triHomeFmt(triHomeScore(latest,item[0]),item[2])+'</strong><span>'+item[1]+'</span></div>').join('');
 const block='<div class="student-home-columns tri-home-tri-columns"><div class="student-home-block tri-home-tri-block"><div class="tri-home-tri-head"><div><h3>TRI por área</h3><p class="micro">'+esc(latest.activity||'Simulado')+' · '+esc(latest.date||'')+'</p></div></div><div class="student-home-mini-stats tri-home-tri-grid">'+cards+'</div></div></div>';
 const marker='<div class="student-home-columns"><div class="student-home-block"><h3>Trilha de aprendizagem</h3>';
 return base.includes(marker)?base.replace(marker,block+marker):base+block;
};
'''

CSS = r'''
/* === TRI DASHBOARD V3.3 === */
.tri-dashboard-panel{display:grid;gap:1rem}.tri-dashboard-filter{border:1px solid var(--line);border-radius:14px;padding:.9rem;background:#fff}.tri-dashboard-filter-head{display:flex;justify-content:space-between;gap:1rem;align-items:flex-start}.tri-dashboard-filter-head h4{margin:0 0 .25rem}.tri-dashboard-all{display:flex;align-items:center;gap:.4rem;font-weight:700;white-space:nowrap}.tri-dashboard-filter-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:.5rem;margin-top:.7rem}.tri-dashboard-filter-item{display:flex;align-items:center;gap:.55rem;padding:.55rem .65rem;border:1px solid var(--line);border-radius:10px;background:#fffafb}.tri-dashboard-filter-item span{display:grid}.tri-dashboard-filter-item small{color:var(--muted)}.tri-dashboard-current{display:grid;gap:1rem}.tri-dashboard-current h3{margin:.1rem 0}.tri-dashboard-score-grid{display:grid;grid-template-columns:repeat(6,minmax(0,1fr));gap:.55rem}.tri-dashboard-score-grid>div,.tri-home-tri-grid>div{border:1px solid #e2ddef;border-radius:14px;padding:.85rem;background:#fff;display:grid;gap:.2rem}.tri-dashboard-score-grid strong,.tri-home-tri-grid strong{font-size:1.3rem;color:#9f4351}.tri-dashboard-score-grid span,.tri-home-tri-grid span{font-size:.78rem;color:var(--muted)}.tri-dashboard-comparison h4,.tri-dashboard-evolution>h4,.tri-redaction-history h4{margin-bottom:.45rem}.tri-dashboard-evolution-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:1rem}.tri-dashboard-series{border:1px solid var(--line);border-radius:14px;padding:.85rem;min-width:0}.tri-dashboard-series h4{margin:0 0 .5rem}.tri-dashboard-series-chart{height:220px;display:flex;align-items:flex-end;gap:.75rem;overflow-x:auto;padding:.55rem .3rem .2rem;border-bottom:1px solid var(--line)}.tri-dashboard-series-item{height:100%;min-width:110px;display:grid;grid-template-rows:auto 1fr auto auto;gap:.25rem;justify-items:center;text-align:center}.tri-dashboard-series-value{font-size:.78rem;font-weight:700}.tri-dashboard-series-track{height:100%;width:28px;background:#f3e0e4;border-radius:9px 9px 3px 3px;display:flex;align-items:flex-end;overflow:hidden}.tri-dashboard-series-track span{width:100%;background:linear-gradient(180deg,#db8d99,#b65362);border-radius:8px 8px 2px 2px}.tri-dashboard-series-item small{max-width:110px;white-space:normal;line-height:1.15;font-weight:700}.tri-dashboard-series-item em{font-size:.68rem;color:var(--muted);font-style:normal}.tri-redaction-history{padding-top:.8rem;border-top:1px solid var(--line)}.tri-redaction-history td:nth-child(n+3){text-align:center}.tri-home-evolution-item{min-width:105px}.tri-home-evolution-item small{max-width:105px;white-space:normal;text-align:center;line-height:1.1;font-weight:700}.tri-home-evolution-item em{font-size:.65rem;color:var(--muted);font-style:normal;text-align:center}.tri-home-evolution{gap:.7rem}.tri-home-tri-columns{grid-template-columns:1fr}.tri-home-tri-grid{grid-template-columns:repeat(6,minmax(0,1fr))}.tri-home-tri-head h3{margin:0}.tri-home-tri-head p{margin:.2rem 0 .7rem}
@media(max-width:1000px){.tri-dashboard-score-grid,.tri-home-tri-grid{grid-template-columns:repeat(3,minmax(0,1fr))}.tri-dashboard-evolution-grid{grid-template-columns:1fr}}
@media(max-width:620px){.tri-dashboard-filter-head{display:grid}.tri-dashboard-score-grid,.tri-home-tri-grid{grid-template-columns:repeat(2,minmax(0,1fr))}.tri-dashboard-series-item{min-width:88px}.tri-dashboard-series-item small{max-width:88px}}
'''

def main():
    model=ROOT/"model_data.py"
    text=model.read_text(encoding="utf-8")
    if BACKEND_MARK not in text:
        model.write_text(text.rstrip()+"\n\n"+BACKEND.strip()+"\n",encoding="utf-8")

    tri_js=STATIC/"tri_scores.js"
    text=tri_js.read_text(encoding="utf-8")
    if TRI_JS_MARK not in text:
        tri_js.write_text(text.rstrip()+"\n\n"+TRI_JS.strip()+"\n",encoding="utf-8")

    home_js=STATIC/"student_summary.js"
    text=home_js.read_text(encoding="utf-8")
    if HOME_JS_MARK not in text:
        home_js.write_text(text.rstrip()+"\n\n"+HOME_JS.strip()+"\n",encoding="utf-8")

    css=STATIC/"style.css"
    text=css.read_text(encoding="utf-8")
    if CSS_MARK not in text:
        css.write_text(text.rstrip()+"\n\n"+CSS.strip()+"\n",encoding="utf-8")

    html=STATIC/"app.html"
    text=html.read_text(encoding="utf-8")
    text=re.sub(r'/static/tri_scores\.js\?v=[^"\']+','/static/tri_scores.js?v=3.3.0',text)
    text=re.sub(r'/static/student_summary\.js\?v=[^"\']+','/static/student_summary.js?v=3.3.0',text)
    html.write_text(text,encoding="utf-8")

    print("MEUCRONOGRAMA_TRI_DASHBOARD_READY: TRI area cards, chronological named evolution, selectable simulations and essay history installed.",flush=True)

if __name__=="__main__":
    main()
