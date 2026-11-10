"""Refine overview metrics, selected-TRI averages, latest disciplines and map date editing."""
from pathlib import Path
import re

ROOT=Path(__file__).resolve().parent
STATIC=ROOT/"static"
BACKEND_MARK="# === PERFORMANCE REFINEMENT V3.4 ==="
HOME_MARK="// === PERFORMANCE OVERVIEW V3.4 ==="
TRI_MARK="// === TRI AVERAGE V3.4 ==="
MAP_MARK="// === EXAM DATE EDIT V3.4 ==="
CSS_MARK="/* === PERFORMANCE REFINEMENT V3.4 === */"

BACKEND=r'''
# === PERFORMANCE REFINEMENT V3.4 ===
_performance_refinement_original_handle = handle

def _pr_exam_edit_list(app, c):
    exams = app.db.execute(
        c,
        'SELECT id,title,applied_on,color,version,updated_at FROM hmay_exams ORDER BY applied_on DESC,title,color'
    ).fetchall()
    rows = app.db.execute(
        c,
        'SELECT id,metadata FROM hmay_performance'
    ).fetchall()
    linked = {}
    for raw in rows:
        item = dict(raw)
        metadata = _rx_json(item.get('metadata'))
        exam_id = F.text(metadata.get('_exam_id'), 160)
        if exam_id:
            linked[exam_id] = linked.get(exam_id, 0) + 1
    return [
        {
            'id': row['id'],
            'title': row['title'],
            'date': row['applied_on'],
            'color': row['color'],
            'version': row['version'],
            'linkedResults': linked.get(row['id'], 0),
        }
        for row in exams
    ]

def _pr_update_exam_date(app, c, user, exam_id, new_date):
    exam_id = F.text(exam_id, 160)
    new_date = F.date_value(new_date)
    if not exam_id or not new_date:
        raise ValueError('Informe o mapa e uma nova data válida.')

    exam_row = app.db.execute(
        c,
        'SELECT id,title,applied_on,color FROM hmay_exams WHERE id=?',
        (exam_id,),
    ).fetchone()
    if not exam_row:
        raise ValueError('Mapa não encontrado.')
    exam = dict(exam_row)
    old_date = exam['applied_on']
    if old_date == new_date:
        return {'examId': exam_id, 'oldDate': old_date, 'newDate': new_date, 'updatedResults': 0, 'unchanged': True}

    duplicate = app.db.execute(
        c,
        'SELECT id FROM hmay_exams WHERE id<>? AND title=? AND applied_on=? AND color=? LIMIT 1',
        (exam_id, exam['title'], new_date, exam['color']),
    ).fetchone()
    if duplicate:
        raise ValueError('Já existe um mapa com o mesmo simulado, cor e nova data.')

    candidates = app.db.execute(
        c,
        'SELECT id,user_id,activity_key,applied_on,metadata FROM hmay_performance WHERE metadata LIKE ?',
        ('%' + exam_id + '%',),
    ).fetchall()
    linked = []
    for raw in candidates:
        item = dict(raw)
        if F.text(_rx_json(item.get('metadata')).get('_exam_id'), 160) == exam_id:
            linked.append(item)

    existing_rows = app.db.execute(
        c,
        'SELECT id,user_id,activity_key FROM hmay_performance WHERE applied_on=?',
        (new_date,),
    ).fetchall()
    existing = {(row['user_id'], row['activity_key']): row['id'] for row in existing_rows}
    for row in linked:
        other_id = existing.get((row['user_id'], row['activity_key']))
        if other_id and other_id != row['id']:
            raise ValueError('A nova data criaria resultado duplicado para pelo menos um aluno. A alteração foi cancelada.')

    stamp = P.now().isoformat()
    app.db.execute(
        c,
        'UPDATE hmay_exams SET applied_on=?,version=version+1,updated_at=? WHERE id=?',
        (new_date, stamp, exam_id),
    )
    for offset in range(0, len(linked), 300):
        chunk = linked[offset:offset+300]
        if not chunk:
            continue
        placeholders = ','.join('?' for _ in chunk)
        params = [new_date, stamp] + [row['id'] for row in chunk]
        app.db.execute(
            c,
            'UPDATE hmay_performance SET applied_on=?,version=version+1,updated_at=? WHERE id IN (' + placeholders + ')',
            tuple(params),
        )
    app.event(c, user, user['id'], 'exam_date_update')
    print(
        f'MEUCRONOGRAMA_EXAM_DATE_UPDATED exam={exam_id} old={old_date} new={new_date} results={len(linked)}',
        flush=True,
    )
    return {
        'examId': exam_id,
        'title': exam['title'],
        'color': exam['color'],
        'oldDate': old_date,
        'newDate': new_date,
        'updatedResults': len(linked),
        'unchanged': False,
    }

def handle(app, c, user, path, method, data, query, start, HTTPError):
    if path == '/api/model-data/exam-edit-list':
        _rx_role_guard(user, HTTPError)
        if method != 'GET':
            raise HTTPError(405, 'Use GET para listar os mapas.')
        return app.reply(start, 200, {'exams': _pr_exam_edit_list(app, c)})

    if path == '/api/model-data/exam-date-update':
        _rx_role_guard(user, HTTPError)
        if method != 'POST':
            raise HTTPError(405, 'Use POST para atualizar a data.')
        result = _pr_update_exam_date(
            app, c, user,
            data.get('examId'),
            data.get('date'),
        )
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

MAP_JS=r'''
// === EXAM DATE EDIT V3.4 ===
let examEditCache=null;
let examEditLoading=false;
async function loadExamEditCache(force=false){
 if(!manages()||examEditLoading||(!force&&examEditCache))return;
 examEditLoading=true;
 try{
  const data=await api('/api/model-data/exam-edit-list');
  examEditCache=data?.exams||[];
 }catch(error){
  examEditCache={error:error?.message||'Não foi possível carregar os mapas.'};
 }finally{
  examEditLoading=false;
  if(view==='exams'&&typeof render==='function')render();
 }
}
function examEditPanel(){
 if(!manages())return '';
 if(!examEditCache&&!examEditLoading)queueMicrotask(()=>loadExamEditCache());
 if(examEditLoading||!examEditCache)return '<section class="card"><h2>Editar dados dos mapas</h2><p>Carregando mapas…</p></section>';
 if(examEditCache?.error)return '<section class="card"><h2>Editar dados dos mapas</h2><div class="notice warning">'+esc(examEditCache.error)+'</div></section>';
 const rows=(examEditCache||[]).map(exam=>
  '<div class="exam-date-edit-row"><div><strong>'+esc(exam.title||'Simulado')+'</strong><small>'+esc(exam.color||'')+' · '+Number(exam.linkedResults||0)+' resultado(s) vinculado(s)</small></div>'+
  '<label>Data de aplicação<input type="date" data-exam-date-input="'+esc(exam.id)+'" value="'+esc(exam.date||'')+'"></label>'+
  '<button type="button" class="secondary" data-act="exam-date-save" data-exam-id="'+esc(exam.id)+'">Salvar data</button></div>'
 ).join('');
 return '<section class="card exam-date-edit-card"><h2>Editar dados dos mapas</h2><p>Corrigir a data aqui também atualiza os resultados já vinculados ao mesmo mapa. Nenhuma nota, resposta ou redação é recalculada.</p>'+rows+'</section>';
}
const examDateOriginalExamsView=examsView;
examsView=function(){
 const base=examDateOriginalExamsView();
 return base+examEditPanel();
};
acts['exam-date-save']=async(buttonEl)=>{
 const examId=buttonEl?.dataset?.examId||'';
 const input=document.querySelector('[data-exam-date-input="'+CSS.escape(examId)+'"]');
 const date=input?.value||'';
 if(!examId||!date)throw new Error('Informe uma data válida.');
 if(!confirm('Atualizar a data deste mapa e de todos os resultados vinculados para '+date+'?'))return;
 buttonEl.disabled=true;
 const oldText=buttonEl.textContent;
 buttonEl.textContent='Salvando…';
 try{
  const result=await api('/api/model-data/exam-date-update',{examId,date});
  examEditCache=null;
  if(typeof studentSummaryCache!=='undefined')studentSummaryCache?.clear?.();
  if(typeof resultExportSimulations!=='undefined')resultExportSimulations=null;
  toast('Data atualizada: '+result.updatedResults+' resultado(s) vinculado(s) ajustado(s).');
  await loadExamEditCache(true);
 }finally{
  buttonEl.disabled=false;
  buttonEl.textContent=oldText;
 }
};
'''

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

    home=STATIC/"student_summary.js"
    text=home.read_text(encoding="utf-8")
    if HOME_MARK not in text:
        home.write_text(text.rstrip()+"\n\n"+HOME_JS.strip()+"\n",encoding="utf-8")

    tri=STATIC/"tri_scores.js"
    text=tri.read_text(encoding="utf-8")
    if TRI_MARK not in text:
        tri.write_text(text.rstrip()+"\n\n"+TRI_JS.strip()+"\n",encoding="utf-8")

    appjs=STATIC/"app.js"
    text=appjs.read_text(encoding="utf-8")
    if MAP_MARK not in text:
        appjs.write_text(text.rstrip()+"\n\n"+MAP_JS.strip()+"\n",encoding="utf-8")

    css=STATIC/"style.css"
    text=css.read_text(encoding="utf-8")
    if CSS_MARK not in text:
        css.write_text(text.rstrip()+"\n\n"+CSS.strip()+"\n",encoding="utf-8")

    html=STATIC/"app.html"
    text=html.read_text(encoding="utf-8")
    text=re.sub(r'/static/app\.js\?v=[^"\']+','/static/app.js?v=3.4.0',text)
    text=re.sub(r'/static/student_summary\.js\?v=[^"\']+','/static/student_summary.js?v=3.4.0',text)
    text=re.sub(r'/static/tri_scores\.js\?v=[^"\']+','/static/tri_scores.js?v=3.4.0',text)
    html.write_text(text,encoding="utf-8")

    print("MEUCRONOGRAMA_PERFORMANCE_REFINEMENT_READY: overview totals/TRI, latest disciplines, selected TRI averages and safe exam-date editing installed.",flush=True)

if __name__=="__main__":
    main()
