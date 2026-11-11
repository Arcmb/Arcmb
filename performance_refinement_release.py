"""Refine overview metrics, selected-TRI averages, latest disciplines and map date editing."""
from pathlib import Path
import re

ROOT=Path(__file__).resolve().parent
STATIC=ROOT/"static"
BACKEND_MARK="# === PERFORMANCE REFINEMENT V3.4 ==="
HOME_MARK="// === PERFORMANCE OVERVIEW V3.4 ==="
TRI_MARK="// === TRI AVERAGE V3.4 ==="
MAP_MARK="acts['exam-metadata-edit']"
CSS_MARK="/* === PERFORMANCE REFINEMENT V3.4 === */"

BACKEND=r'''
# === PERFORMANCE REFINEMENT V3.4 ===
_performance_refinement_original_handle = handle

import exam_metadata as _exam_metadata

def handle(app, c, user, path, method, data, query, start, HTTPError):
    if path == '/api/model-data/exam-edit-list':
        _rx_role_guard(user, HTTPError)
        if method != 'GET':
            raise HTTPError(405, 'Use GET para listar os mapas.')
        return app.reply(start, 200, {'exams': _exam_metadata.catalogue(app, c, user)})

    if path in ('/api/model-data/exam-date-update', '/api/model-data/exam-metadata-update'):
        _rx_role_guard(user, HTTPError)
        if method != 'POST':
            raise HTTPError(405, 'Use POST para editar o caderno.')
        result = _exam_metadata.update(app, c, user, data, HTTPError,
                                       date_only=path.endswith('/exam-date-update'))
        return app.reply(start, 200, result)

    return _performance_refinement_original_handle(app, c, user, path, method, data, query, start, HTTPError)
'''

HOME_JS=r'''
// === PERFORMANCE OVERVIEW V3.4 ===
function prLatestSimulation(d){
 const rows=[...(d?.simulations||[])];
 rows.sort((a,b)=>String(b?.date||'').localeCompare(String(a?.date||''))||String(a?.activity||'').localeCompare(String(b?.activity||''),'pt-BR'));
 return rows[0]||null;
}
function prFmt(value,digits=1){
 const n=Number(value);
 return value===null||value===undefined||value===''||!Number.isFinite(n)?'—':n.toLocaleString('pt-BR',{minimumFractionDigits:digits,maximumFractionDigits:digits});
}
function prLatestDisciplinesHtml(sim){
 const rows=[...(sim?.disciplines||[])].filter(x=>Number(x?.marked||0)>0);
 rows.sort((a,b)=>{
  const aa=a?.accuracy===null||a?.accuracy===undefined?999:Number(a.accuracy);
  const bb=b?.accuracy===null||b?.accuracy===undefined?999:Number(b.accuracy);
  return aa-bb||String(a?.name||'').localeCompare(String(b?.name||''),'pt-BR');
 });
 if(!rows.length)return '<div class="notice">O simulado mais recente ainda não possui divisão por disciplina disponível.</div>';
 return '<p class="micro">Todas as disciplinas de '+esc(sim.activity||'Simulado')+' · '+esc(sim.date||'')+'.</p>'+
  rows.map(x=>studentHomeBar(x,x.name)).join('');
}
const prDashboardBeforeV34=studentHomeDashboard;
studentHomeDashboard=function(){
 let html=prDashboardBeforeV34();
 const id=studentSummaryTarget();
 const d=studentSummaryCache.get(id);
 if(!d||d.error)return html;
 const p=d.performance||{};
 const latest=prLatestSimulation(d);
 if(!latest)return html;

 html=html.replace(
  /<strong>[^<]*<\/strong><span>acertos acumulados<\/span>/,
  '<strong>'+Number(p.correct||0)+'/'+Number(p.valid||0)+'</strong><span>acertos acumulados</span>'
 );

 const triGeneral=triHomeScore(latest,'general');
 if(triGeneral!==null&&!html.includes('<span>TRI geral mais recente</span>')){
  html=html.replace(
   /(<strong>[^<]*<\/strong><span>acertos acumulados<\/span><\/div>)/,
   '$1<div><strong>'+prFmt(triGeneral,1)+'</strong><span>TRI geral mais recente</span></div>'
  );
 }

 const redaction=triHomeScore(latest,'redaction');
 if(redaction!==null){
  const redAccuracy=Math.max(0,Math.min(100,redaction/10));
  const redRow=studentHomeBar({correct:Math.round(redaction),total:1000,accuracy:redAccuracy},'Redação');
  html=html.replace(
   /(<div class="student-home-block"><h3>Acertos\/TCT por área<\/h3>)([\s\S]*?)(<\/div><div class="student-home-block"><h3>Evolução da TRI geral<\/h3>)/,
   (all,start,body,end)=>start+body+redRow+end
  );
 }

 const disciplines=prLatestDisciplinesHtml(latest);
 html=html.replace(
  /<div class="student-home-block"><h3>Trilha de aprendizagem<\/h3>[\s\S]*?<\/div><div class="student-home-block"><h3>Execução da rotina<\/h3>/,
  '<div class="student-home-block"><h3>Trilha de aprendizagem</h3>'+disciplines+'</div><div class="student-home-block"><h3>Execução da rotina</h3>'
 );
 return html;
};
'''

TRI_JS=r'''
// === TRI AVERAGE V3.4 ===
function triDashboardAverage(rows,key){
 const values=(rows||[]).map(sim=>triDashboardScore(sim,key)).filter(value=>value!==null);
 if(!values.length)return null;
 return values.reduce((sum,value)=>sum+value,0)/values.length;
}
function triDashboardAverageCards(rows){
 const metrics=[
  ['general','TRI geral',1],['lc','Linguagens',1],['ch','Humanas',1],
  ['cn','Natureza',1],['mt','Matemática',1],['redaction','Redação',1]
 ];
 return '<div class="tri-dashboard-score-grid">'+metrics.map(item=>{
  const value=triDashboardAverage(rows,item[0]);
  return '<div><strong>'+triDashFormat(value,item[2])+'</strong><span>'+item[1]+'</span></div>';
 }).join('')+'</div>';
}
triStudentPanel=function(d){
 const simulations=(d?.simulations||[]).filter(triDashboardHasTri);
 if(!simulations.length)return '<section class="card student-tri-panel"><p class="eyebrow">Escala TRI</p><h3>Notas TRI</h3><div class="notice">Ainda não há notas TRI importadas para este aluno.</div></section>';
 const selected=triDashboardSelected(simulations);
 const latest=triDashboardSort(simulations,false)[0]||null;
 const filter=triDashboardFilterHtml(simulations);
 let selectedBlock='<div class="notice warning">Selecione ao menos um simulado para calcular as médias e a evolução.</div>';
 if(selected.length){
  selectedBlock=
   '<div class="tri-dashboard-current"><div><p class="eyebrow">Média dos simulados selecionados</p><h3>'+selected.length+' simulado(s) na média</h3><p class="micro">Cada área usa apenas as notas disponíveis entre os simulados marcados.</p></div>'+
   triDashboardAverageCards(selected)+'</div>'+
   triDashboardComparison(selected)+triDashboardEvolution(selected);
 }
 const latestBlock=latest?
  '<section class="tri-dashboard-latest"><div><p class="eyebrow">Último simulado realizado</p><h3>'+esc(latest.activity||'Simulado')+'</h3><p>'+esc(latest.date||'')+(latest.color?' · prova '+esc(latest.color):'')+'</p></div>'+triDashboardMetricCards(latest)+'</section>':'';
 return '<section class="card student-tri-panel tri-dashboard-panel"><div class="tri-dashboard-title"><div><p class="eyebrow">Escala TRI</p><h2>Notas e evolução TRI</h2></div></div>'+
  latestBlock+filter+selectedBlock+triDashboardRedactionHistory(simulations)+
  '<p class="micro">TRI e acertos/TCT são indicadores diferentes. As médias e gráficos consideram somente os simulados selecionados acima.</p></section>';
};
'''

MAP_JS = (ROOT/'release_assets'/'exam_metadata.js').read_text(encoding='utf-8')

CSS=r'''
/* === PERFORMANCE REFINEMENT V3.4 === */
.tri-dashboard-latest{display:grid;gap:.75rem;padding:.9rem;border:1px solid var(--line);border-radius:14px;background:#fffafb}.tri-dashboard-latest h3{margin:.1rem 0}.exam-date-edit-card{display:grid;gap:.7rem}.exam-date-edit-row{display:grid;grid-template-columns:minmax(220px,1fr) minmax(180px,240px) auto;gap:.8rem;align-items:end;padding:.8rem 0;border-top:1px solid var(--line)}.exam-date-edit-row:first-of-type{border-top:0}.exam-date-edit-row>div{display:grid;gap:.2rem}.exam-date-edit-row small{color:var(--muted)}.exam-date-edit-row label{display:grid;gap:.3rem}.student-home-kpis{grid-template-columns:repeat(3,minmax(0,1fr))}
@media(max-width:850px){.exam-date-edit-row{grid-template-columns:1fr}.student-home-kpis{grid-template-columns:repeat(2,minmax(0,1fr))}}
@media(max-width:560px){.student-home-kpis{grid-template-columns:1fr}}
'''

def main():
    model=ROOT/"model_data.py"
    text=model.read_text(encoding="utf-8")
    if BACKEND_MARK not in text:
        model.write_text(text.rstrip()+"\n\n"+BACKEND.strip()+"\n",encoding="utf-8")

    # The workbook and map modules are unpacked by earlier release steps.
    modules = {
        model: [
            ("'md_' + identity[:32]", "_exam_metadata.available_import_id(app, c, 'md_' + identity[:32])"),
            ("app.db.execute(c, 'SELECT id FROM hmay_exams WHERE identity_key=?', (identity,)).fetchone()",
             "_exam_metadata.find_import_map(app, c, spec['title'], spec['date'], spec['color'])"),
            ("color=spec['color'], area='', items=items", "color=spec['color'], area=old['area'] if old else '', items=items"),
        ],
        ROOT/'unified.py': [
            ("'wb_'+identity[:32]", "_exam_metadata.available_import_id(app, c, 'wb_' + identity[:32])"),
            ("app.db.execute(c,'SELECT id FROM hmay_exams WHERE identity_key=?',(identity,)).fetchone()",
             "_exam_metadata.find_import_map(app, c, values['title'], values['date'], values['color'])"),
        ],
        ROOT/'exams.py': [],
    }
    keys = {model:"exam['identity_key']", ROOT/'unified.py':"p['identity']", ROOT/'exams.py':"identity"}
    for module, replacements in modules.items():
        source=module.read_text(encoding='utf-8')
        for old, new in replacements:
            if new in source:
                continue
            if source.count(old)!=1:
                raise RuntimeError(f'Expected one map import expression in {module.name}: {old}')
            source=source.replace(old,new)
        call=f"_exam_metadata.release_obsolete_key(app, c, {keys[module]})"
        if call not in source:
            source,count=re.subn(r"^( +)(cur\s*=\s*(?:app\.)?db.execute\(c,\s*'INSERT INTO hmay_exams)",
                                 lambda m:m[1]+call+'\n'+m[0],source,count=1,flags=re.M)
            if count!=1:
                raise RuntimeError(f'Expected the map insertion in {module.name}.')
        if 'import exam_metadata as _exam_metadata' not in source:
            source += '\nimport exam_metadata as _exam_metadata\n'
        module.write_text(source,encoding='utf-8')

    selective=STATIC/'selective.js'
    source=selective.read_text(encoding='utf-8')
    replacement='const seq=++examSeq;queueMicrotask(()=>loadExamMapList(seq));'
    if replacement not in source:
        source,count=re.subn(r"const seq=\+\+examSeq;queueMicrotask\(async\(\)=>\{try\{const d=await api\('/api/exams'\);[^\n]+",
                             replacement,source,count=1)
        if count!=1:
            raise RuntimeError('The main exam catalogue view was not found.')
        selective.write_text(source,encoding='utf-8')

    home=STATIC/"student_summary.js"
    text=home.read_text(encoding="utf-8")
    if HOME_MARK not in text:
        text=text.rstrip()+"\n\n"+HOME_JS.strip()+"\n"
    if MAP_MARK not in text:
        text=text.rstrip()+"\n\n"+MAP_JS.strip()+"\n"
    home.write_text(text,encoding="utf-8")

    tri=STATIC/"tri_scores.js"
    text=tri.read_text(encoding="utf-8")
    if TRI_MARK not in text:
        tri.write_text(text.rstrip()+"\n\n"+TRI_JS.strip()+"\n",encoding="utf-8")

    css=STATIC/"style.css"
    text=css.read_text(encoding="utf-8")
    if CSS_MARK not in text:
        css.write_text(text.rstrip()+"\n\n"+CSS.strip()+"\n",encoding="utf-8")

    html=STATIC/"app.html"
    text=html.read_text(encoding="utf-8")
    text=re.sub(r'/static/student_summary\.js\?v=[^"\']+','/static/student_summary.js?v=3.4.0',text)
    text=re.sub(r'/static/tri_scores\.js\?v=[^"\']+','/static/tri_scores.js?v=3.7.14',text)
    html.write_text(text,encoding="utf-8")

    print("MEUCRONOGRAMA_PERFORMANCE_REFINEMENT_READY: overview totals/TRI, latest disciplines, selected TRI averages and safe exam-date editing installed.",flush=True)

if __name__=="__main__":
    main()
