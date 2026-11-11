"""Hotfix v3.7.13: sortable hierarchical ENEM analytics tables."""
from pathlib import Path
import re

ROOT=Path(__file__).resolve().parent
STATIC=ROOT/'static'
JS_MARK='// === CLASS ANALYTICS SORTING V3.7.13 ==='
CSS_MARK='/* === CLASS ANALYTICS SORTING V3.7.13 === */'

JS=r'''
// === CLASS ANALYTICS SORTING V3.7.13 ===
let managementAnalyticsSort={
 class:{key:'turma',dir:'asc'},
 simulation:{key:'date',dir:'desc'},
 student:{key:'ranking',dir:'asc'},
};

const managementAnalyticsColumns=[
 ['participants','Participantes'],
 ['simulations','Simulados'],
 ['enem','Nota ENEM'],
 ['bonus','+10%'],
 ['accuracy','Acertos'],
 ['lcAccuracy','LC'],
 ['chAccuracy','CH'],
 ['cnAccuracy','CN'],
 ['mtAccuracy','MT'],
 ['c1','C1'],['c2','C2'],['c3','C3'],['c4','C4'],['c5','C5'],
 ['redaction','Redação'],
];

function managementAnalyticsCompare(a,b,key,dir){
 const av=a?.[key],bv=b?.[key];
 const factor=dir==='desc'?-1:1;
 const aEmpty=av===null||av===undefined||av==='';
 const bEmpty=bv===null||bv===undefined||bv==='';
 if(aEmpty&&bEmpty)return 0;
 if(aEmpty)return 1;
 if(bEmpty)return -1;
 if(typeof av==='number'||typeof bv==='number'){
  const an=Number(av),bn=Number(bv);
  if(Number.isFinite(an)&&Number.isFinite(bn))return (an-bn)*factor;
 }
 return String(av).localeCompare(String(bv),'pt-BR',{sensitivity:'base',numeric:true})*factor;
}
function managementAnalyticsSorted(rows,scope){
 const sort=managementAnalyticsSort[scope]||{key:'',dir:'asc'};
 return [...managementSafeArray(rows)].sort((a,b)=>{
  const primary=managementAnalyticsCompare(a,b,sort.key,sort.dir);
  if(primary)return primary;
  const fallbackKey=scope==='class'?'turma':scope==='simulation'?'activity':'name';
  return managementAnalyticsCompare(a,b,fallbackKey,'asc');
 });
}
function managementSortTh(label,scope,key){
 const sort=managementAnalyticsSort[scope]||{};
 const active=sort.key===key;
 const arrow=active?(sort.dir==='asc'?'▲':'▼'):'↕';
 const title=active
  ?(sort.dir==='asc'?'Ordem crescente. Clique para decrescente.':'Ordem decrescente. Clique para crescente.')
  :'Clique para ordenar.';
 return '<th class="management-sort-th'+(active?' active':'')+'"><button type="button" data-act="management-analytics-sort" data-sort-scope="'+scope+'" data-sort-key="'+key+'" title="'+title+'"><span>'+label+'</span><span class="management-sort-arrow">'+arrow+'</span></button></th>';
}
function managementAnalyticsHead(first,scope='class'){
 const firstKey=scope==='class'?'turma':scope==='simulation'?'activity':'name';
 return '<tr>'+managementSortTh(first,scope,firstKey)+
  managementAnalyticsColumns.map(([key,label])=>managementSortTh(label,scope,key)).join('')+
 '</tr>';
}
function managementStudentRowsHtml(data){
 const rows=managementAnalyticsSorted(data?.students,'student');
 if(!rows.length)return '<div class="notice">Nenhum aluno encontrado neste simulado.</div>';
 return '<div class="table-wrap management-nested-table"><table><thead><tr>'+
  managementSortTh('Ranking','student','ranking')+
  managementSortTh('Aluno','student','name')+
  managementAnalyticsColumns.filter(([key])=>key!=='participants'&&key!=='simulations').map(([key,label])=>managementSortTh(label,'student',key)).join('')+
  '</tr></thead><tbody>'+
  rows.map(x=>'<tr><td><strong>'+managementInt(x.ranking)+'</strong></td><td><strong>'+esc(x.name)+'</strong><br><small>'+esc(x.username||'')+'</small></td>'+mgmtAnalyticsCells(x)+'</tr>').join('')+
 '</tbody></table></div>';
}
function managementClassDetailHtml(turma){
 const key=turma+'@@'+[...managementClassSelectedSims].sort().join('|')+'@@'+(managementDashboardFilters?.year||'');
 const data=managementClassDetailCache.get(key);
 if(!data)return '<div class="management-analytics-loading">Carregando simulados da turma…</div>';
 const rows=managementAnalyticsSorted(data.simulations,'simulation');
 if(!rows.length)return '<div class="notice">Nenhum simulado encontrado para esta turma com a seleção atual.</div>';
 return '<div class="table-wrap management-nested-table"><table><thead>'+managementAnalyticsHead('Simulado','simulation')+'</thead><tbody>'+
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
 const rows=managementAnalyticsSorted(data?.classes,'class');
 if(!rows.length)return '<div class="notice">Nenhuma turma com resultados para os simulados selecionados.</div>';
 return '<div class="table-wrap management-analytics-main"><table><thead>'+managementAnalyticsHead('Turma','class')+'</thead><tbody>'+
 rows.map(x=>{
  const open=managementClassOpen===x.turma;
  return '<tr class="management-drill-row'+(open?' open':'')+'" data-act="management-class-drill" data-turma="'+encodeURIComponent(x.turma)+'"><td><strong>'+esc(x.turma)+'</strong></td><td>'+managementInt(x.participants)+'</td><td>'+managementInt(x.simulations)+'</td>'+mgmtAnalyticsCells(x)+'</tr>'+
  (open?'<tr class="management-drill-detail"><td colspan="16">'+managementClassDetailHtml(x.turma)+'</td></tr>':'');
 }).join('')+
 '</tbody></table></div>';
}
acts['management-analytics-sort']=el=>{
 const scope=el?.dataset?.sortScope||'';
 const key=el?.dataset?.sortKey||'';
 if(!managementAnalyticsSort[scope]||!key)return;
 const current=managementAnalyticsSort[scope];
 if(current.key===key)current.dir=current.dir==='asc'?'desc':'asc';
 else{
  current.key=key;
  current.dir=['turma','activity','name'].includes(key)?'asc':'desc';
 }
 render();
};
'''

CSS=r'''
/* === CLASS ANALYTICS SORTING V3.7.13 === */
.management-sort-th{padding:0!important}.management-sort-th>button{width:100%;display:flex;align-items:center;justify-content:space-between;gap:.35rem;padding:.65rem .55rem;border:0;background:transparent;color:inherit;font:inherit;font-weight:700;text-transform:uppercase;letter-spacing:.03em;cursor:pointer;white-space:nowrap}.management-sort-th>button:hover,.management-sort-th.active>button{background:#fff1f3;color:#9f3346}.management-sort-arrow{font-size:.72rem;opacity:.75}.management-sort-th.active .management-sort-arrow{opacity:1}.management-class-analytics thead th{vertical-align:middle}
'''

def main():
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
    source=re.sub(r'/static/student_summary\.js\?v=[^"\']+','/static/student_summary.js?v=3.7.13',source)
    html.write_text(source,encoding='utf-8')

    for verifier in ROOT.glob('verify_*.py'):
        source=verifier.read_text(encoding='utf-8')
        source=source.replace('/static/student_summary.js?v=3.7.12','/static/student_summary.js?v=3.7.13')
        verifier.write_text(source,encoding='utf-8')

    site=ROOT/'site_version_release.py'
    if site.exists():
        source=site.read_text(encoding='utf-8').replace('PUBLIC_VERSION="3.7.12"','PUBLIC_VERSION="3.7.13"')
        site.write_text(source,encoding='utf-8')

    vsite=ROOT/'verify_site_version.py'
    if vsite.exists():
        source=vsite.read_text(encoding='utf-8').replace('v3.7.12','v3.7.13')
        vsite.write_text(source,encoding='utf-8')

    print('MEUCRONOGRAMA_CLASS_ANALYTICS_SORT_READY: class, simulation and student tables are sortable alphabetically and numerically.',flush=True)

if __name__=='__main__':
    main()
