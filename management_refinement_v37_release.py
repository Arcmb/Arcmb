"""Management refinement v3.7: sortable tables, exact TRI chart, max-by-area, and class correction."""
from pathlib import Path
import re

ROOT=Path(__file__).resolve().parent
STATIC=ROOT/"static"
BACKEND_MARK="# === MANAGEMENT REFINEMENT V3.7 ==="
JS_MARK="// === MANAGEMENT REFINEMENT V3.7 ==="
CSS_MARK="/* === MANAGEMENT REFINEMENT V3.7 === */"

BACKEND=r'''
# === MANAGEMENT REFINEMENT V3.7 ===
_v37_dashboard_base=_mgmt_dashboard_data
_v37_handle_base=handle

def _v37_filtered_metadata(app,c,query):
    conditions=["u.role IN ('user','aluno')","u.active=1"]
    args=[]
    year=F.text((query or {}).get('year'),4)
    activity=F.text((query or {}).get('activityKey'),250)
    date=F.text((query or {}).get('date'),40)
    turma=F.text((query or {}).get('turma'),160)
    if year:
        conditions.append('p.applied_on LIKE ?');args.append(year+'%')
    if activity:
        conditions.append('p.activity_key=?');args.append(activity)
    if date:
        conditions.append('p.applied_on=?');args.append(date)
    rows=app.db.execute(
        c,
        """SELECT p.metadata
           FROM hmay_performance p
           JOIN hmay_users u ON u.id=p.user_id
           WHERE """+' AND '.join(conditions),
        tuple(args),
    ).fetchall()
    lookup=_v36_class_lookup(app,c)
    result=[]
    for raw in rows:
        meta=_rx_json(raw['metadata'])
        raw_class=F.text(meta.get('TURMA'),160) or 'Sem turma'
        canonical=lookup.get(F.norm(raw_class),raw_class)
        if turma and canonical!=turma:
            continue
        result.append(meta)
    return result

def _mgmt_dashboard_data(app,c,user,query):
    result=_v37_dashboard_base(app,c,user,query)
    maxima={'LC':None,'CH':None,'CN':None,'MT':None,'RED':None}
    for meta in _v37_filtered_metadata(app,c,query):
        scores=_tri_scores_from_metadata(meta)
        for key,score_key in (('LC','lc'),('CH','ch'),('CN','cn'),('MT','mt'),('RED','redaction')):
            value=scores.get(score_key)
            if value is None:
                continue
            try:
                number=float(value)
            except Exception:
                continue
            if maxima[key] is None or number>maxima[key]:
                maxima[key]=number
    for area in result.get('areas',[]):
        area['maxTri']=maxima.get(area.get('key'))
    return result

def _v37_correct_class(app,c,user,source,target):
    source=F.text(source,160) or '(sem turma)'
    target=F.text(target,160)
    if not target:
        raise ValueError('Selecione a turma oficial de destino.')
    active={row['name'] for row in _v36_class_rows(app,c,True)}
    if target not in active:
        raise ValueError('A turma de destino não está ativa no cadastro.')
    rows=app.db.execute(c,'SELECT id,metadata FROM hmay_performance').fetchall()
    updates=[]
    for raw in rows:
        meta=_rx_json(raw['metadata'])
        current=F.text(meta.get('TURMA'),160) or '(sem turma)'
        if current!=source:
            continue
        meta['TURMA']=target
        updates.append((raw['id'],_v36_json.dumps(meta,ensure_ascii=False,separators=(',',':'))))
    if not updates:
        return {'source':source,'target':target,'updated':0}
    stamp=P.now().isoformat()
    for offset in range(0,len(updates),200):
        chunk=updates[offset:offset+200]
        cases=' '.join('WHEN ? THEN ?' for _ in chunk)
        placeholders=','.join('?' for _ in chunk)
        params=[]
        for row_id,meta_json in chunk:
            params.extend((row_id,meta_json))
        params.append(stamp)
        params.extend(row_id for row_id,_ in chunk)
        app.db.execute(
            c,
            'UPDATE hmay_performance SET metadata=CASE id '+cases+
            ' ELSE metadata END,version=version+1,updated_at=? WHERE id IN ('+placeholders+')',
            tuple(params),
        )
    _v36_dashboard_cache.clear()
    app.event(c,user,user['id'],'class_name_correction')
    return {'source':source,'target':target,'updated':len(updates)}

def handle(app,c,user,path,method,data,query,start,HTTPError):
    if path=='/api/model-data/class-correction':
        if user.get('role') not in ('master','coordenador'):
            raise HTTPError(403,'Correção de turmas exclusiva do Master e da coordenação.')
        if method!='POST':
            raise HTTPError(405,'Use POST para corrigir a turma.')
        result=_v37_correct_class(app,c,user,data.get('source'),data.get('target'))
        return app.reply(start,200,{**result,**_v36_class_payload(app,c)})
    return _v37_handle_base(app,c,user,path,method,data,query,start,HTTPError)
'''

JS=r'''
// === MANAGEMENT REFINEMENT V3.7 ===
let managementClassSort={key:'turma',dir:'asc'};
let managementSimulationSort={key:'date',dir:'desc'};

function managementSortRows(rows,state){
 const copy=[...(rows||[])],dir=state.dir==='asc'?1:-1,key=state.key;
 copy.sort((a,b)=>{
  let av=a?.[key],bv=b?.[key];
  if(['participants','accuracy','triGeneral','redaction'].includes(key)){
   av=Number(av);bv=Number(bv);
   if(!Number.isFinite(av))av=-Infinity;
   if(!Number.isFinite(bv))bv=-Infinity;
   return (av-bv)*dir;
  }
  return String(av??'').localeCompare(String(bv??''),'pt-BR',{numeric:true,sensitivity:'base'})*dir;
 });
 return copy;
}
function managementSortButton(label,scope,key,state){
 const active=state.key===key,arrow=active?(state.dir==='asc'?' ↑':' ↓'):'';
 return '<button type="button" class="management-sort" data-act="management-sort" data-sort-scope="'+scope+'" data-sort-key="'+key+'">'+label+arrow+'</button>';
}
managementClassTable=function(rows){
 const sorted=managementSortRows(rows,managementClassSort);
 const body=sorted.map(x=>'<tr><td><strong>'+esc(x.turma||'Sem turma')+'</strong></td><td>'+managementInt(x.participants)+'</td><td>'+managementFmt(x.accuracy,1,'%')+'</td><td>'+managementFmt(x.triGeneral,1)+'</td><td>'+managementFmt(x.redaction,1)+'</td></tr>').join('');
 return body?'<div class="table-wrap"><table><thead><tr><th>'+managementSortButton('Turma','class','turma',managementClassSort)+'</th><th>'+managementSortButton('Participantes','class','participants',managementClassSort)+'</th><th>'+managementSortButton('% acertos','class','accuracy',managementClassSort)+'</th><th>'+managementSortButton('TRI geral','class','triGeneral',managementClassSort)+'</th><th>'+managementSortButton('Redação','class','redaction',managementClassSort)+'</th></tr></thead><tbody>'+body+'</tbody></table></div>':'<div class="notice">Sem turmas para os filtros selecionados.</div>';
};
managementSimulationTable=function(rows){
 const sorted=managementSortRows(rows,managementSimulationSort);
 const body=sorted.map(x=>'<tr><td><strong>'+esc(x.activity||'Simulado')+'</strong><br><small>'+esc(x.date||'')+'</small></td><td>'+managementInt(x.participants)+'</td><td>'+managementFmt(x.accuracy,1,'%')+'</td><td>'+managementFmt(x.triGeneral,1)+'</td><td>'+managementFmt(x.lc,1)+'</td><td>'+managementFmt(x.ch,1)+'</td><td>'+managementFmt(x.cn,1)+'</td><td>'+managementFmt(x.mt,1)+'</td><td>'+managementFmt(x.redaction,1)+'</td></tr>').join('');
 return body?'<div class="table-wrap"><table><thead><tr><th>'+managementSortButton('Simulado','simulation','activity',managementSimulationSort)+'</th><th>'+managementSortButton('Participantes','simulation','participants',managementSimulationSort)+'</th><th>'+managementSortButton('% acertos','simulation','accuracy',managementSimulationSort)+'</th><th>'+managementSortButton('TRI geral','simulation','triGeneral',managementSimulationSort)+'</th><th>LC</th><th>CH</th><th>CN</th><th>MT</th><th>Redação</th></tr></thead><tbody>'+body+'</tbody></table></div>':'<div class="notice">Sem resultados para listar.</div>';
};
acts['management-sort']=el=>{
 const scope=el?.dataset?.sortScope,key=el?.dataset?.sortKey;
 const state=scope==='simulation'?managementSimulationSort:managementClassSort;
 if(state.key===key)state.dir=state.dir==='asc'?'desc':'asc';else{state.key=key;state.dir=key==='turma'||key==='activity'?'asc':'desc';}
 render();
};

managementSimulationChart=function(rows){
 const ordered=[...(rows||[])].sort((a,b)=>String(a.date||'').localeCompare(String(b.date||'')));
 if(!ordered.length)return '<div class="notice">Nenhum simulado com resultados nos filtros selecionados.</div>';
 const cols=ordered.map(x=>{
  const tri=Number(x.triGeneral),hasTri=Number.isFinite(tri),height=hasTri?Math.max(0,Math.min(100,tri/10)):0;
  return '<div class="management-score-col"><div class="management-score-plot"><span class="management-score-value">'+(hasTri?managementFmt(tri,1):'—')+'</span><div class="management-score-track"><span class="management-score-fill" style="height:'+height+'%"></span></div></div><strong>'+esc(x.activity||'Simulado')+'</strong><small>'+esc(x.date||'')+'</small><em>'+managementInt(x.participants)+' participantes · % acertos '+managementFmt(x.accuracy,1,'%')+'</em></div>';
 }).join('');
 return '<div class="management-score-chart"><div class="management-scale"><span>1000</span><span>750</span><span>500</span><span>250</span><span>0</span></div><div class="management-score-columns">'+cols+'</div></div><p class="micro">A altura da coluna corresponde exatamente à nota TRI geral média na escala de 0 a 1000.</p>';
};

managementAreaHtml=function(rows){
 if(!(rows||[]).length)return '<div class="notice">Sem dados de área para os filtros selecionados.</div>';
 return '<div class="management-area-grid">'+rows.map(x=>{
  const tri=Number(x.tri),max=Number(x.maxTri),hasTri=Number.isFinite(tri),hasMax=Number.isFinite(max)&&max>0;
  const width=hasTri&&hasMax?Math.max(0,Math.min(100,100*tri/max)):0;
  const tct=x.accuracy===null||x.accuracy===undefined?'':('<span>% acertos '+managementFmt(x.accuracy,1,'%')+'</span>');
  return '<article><div class="management-area-title"><strong>'+esc(x.name)+'</strong><span>Média '+(hasTri?managementFmt(tri,1):'—')+(hasMax?' · Máxima '+managementFmt(max,1):'')+'</span></div><div class="management-bar tri-scale"><span style="width:'+width+'%"></span></div><div class="management-area-meta">'+tct+'<span>'+(hasMax?'Preenchimento relativo à maior nota observada':'Sem nota máxima disponível')+'</span></div></article>';
 }).join('')+'</div>';
};

function classRegistryPendingHtml(){
 const missing=classRegistryCache?.unregistered||[],classes=(classRegistryCache?.classes||[]).filter(x=>x.active);
 if(!missing.length)return '<div class="notice success">Nenhuma pendência de turma encontrada.</div>';
 return '<div class="class-pending-list">'+missing.map((x,index)=>'<div class="class-pending-row"><div><strong>'+esc(x.name)+'</strong><small>'+managementInt(x.records)+' registro(s) afetado(s)</small></div><label>Correção<select data-class-pending-target="'+index+'"><option value="">Selecione a turma oficial</option>'+classes.map(c=>'<option value="'+esc(c.name)+'">'+esc(c.name)+'</option>').join('')+'</select></label><button type="button" class="primary" data-act="class-pending-correct" data-source="'+encodeURIComponent(x.name)+'" data-index="'+index+'">Confirmar correção</button></div>').join('')+'</div>';
}
classRegistryPanel=function(){
 if(!classRegistryCache&&!classRegistryLoading)queueMicrotask(()=>loadClassRegistry());
 if(classRegistryLoading||!classRegistryCache)return '<section class="card"><h2>Cadastro de turmas</h2><p>Carregando…</p></section>';
 if(classRegistryCache.error)return '<section class="card"><h2>Cadastro de turmas</h2><div class="notice warning">'+esc(classRegistryCache.error)+'</div></section>';
 const rows=(classRegistryCache.classes||[]).map(x=>'<tr><td><strong>'+esc(x.name)+'</strong></td><td><div class="class-correction-cell"><input data-class-name="'+esc(x.id)+'" value="'+esc(x.name)+'" aria-label="Correção do nome oficial"><small>Aliases: '+esc((x.aliases||[]).join('; ')||'nenhum')+'</small><input data-class-aliases="'+esc(x.id)+'" value="'+esc((x.aliases||[]).join('; '))+'" placeholder="Aliases separados por ;"></div></td><td><label class="check"><input type="checkbox" data-class-active="'+esc(x.id)+'"'+(x.active?' checked':'')+'> Ativa</label></td><td><button type="button" class="secondary" data-act="class-registry-save" data-class-id="'+esc(x.id)+'">Salvar</button></td></tr>').join('');
 return '<section class="card class-registry-card"><h2>Cadastro de turmas</h2><p>Use o nome oficial e, quando necessário, aliases autorizados. Pendências pontuais podem ser corrigidas diretamente abaixo.</p><div class="class-new-grid"><label>Nova turma<input id="class-new-name" placeholder="Ex.: Qi Med 01"></label><label>Aliases autorizados<input id="class-new-aliases" placeholder="Ex.: 01 Qi Med 01; MED 01"></label><button type="button" class="primary" data-act="class-registry-new">Cadastrar turma</button></div><h3>Pendências encontradas</h3>'+classRegistryPendingHtml()+'<div class="table-wrap"><table><thead><tr><th>Cadastrada</th><th>Correção</th><th>Ativa</th><th>Salvar</th></tr></thead><tbody>'+rows+'</tbody></table></div></section>';
};
acts['class-pending-correct']=async el=>{
 const index=Number(el?.dataset?.index),source=decodeURIComponent(el?.dataset?.source||''),select=document.querySelector('[data-class-pending-target="'+index+'"]'),target=select?.value||'';
 if(!target)throw new Error('Selecione a turma oficial para corrigir a pendência.');
 if(!confirm('Corrigir "'+source+'" para "'+target+'" em todos os registros afetados?'))return;
 const d=await api('/api/model-data/class-correction',{source,target});
 classRegistryCache={classes:d.classes||[],unregistered:d.unregistered||[]};managementDashboardCache=null;
 toast('Correção concluída: '+Number(d.updated||0)+' registro(s) atualizados.');
 render();
};
'''

CSS=r'''
/* === MANAGEMENT REFINEMENT V3.7 === */
.management-sort{border:0;background:transparent;padding:0;font:inherit;font-weight:800;color:inherit;cursor:pointer;text-transform:none}.management-score-chart{height:320px}.management-score-columns{align-items:stretch}.management-score-col{height:100%;grid-template-rows:minmax(0,1fr) auto auto auto}.management-score-plot{height:100%;display:grid;grid-template-rows:auto minmax(0,1fr);gap:.25rem;justify-items:center;width:54px}.management-score-track{position:relative;height:100%;min-height:210px;width:32px;background:#f3e0e4;border-radius:8px 8px 3px 3px;overflow:hidden}.management-score-fill{position:absolute;bottom:0;left:0;right:0;background:linear-gradient(180deg,#db8d99,#b65362);border-radius:7px 7px 2px 2px}.class-pending-list{display:grid;gap:.6rem}.class-pending-row{display:grid;grid-template-columns:minmax(180px,1fr) minmax(240px,1.5fr) auto;gap:.7rem;align-items:end;padding:.75rem;border:1px solid #f0cf91;background:#fff5df;border-radius:12px}.class-pending-row>div{display:grid;gap:.2rem}.class-pending-row small{color:var(--muted)}.class-correction-cell{display:grid;gap:.25rem}.class-correction-cell small{color:var(--muted)}
@media(max-width:800px){.class-pending-row{grid-template-columns:1fr}}
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
    text=re.sub(r'/static/student_summary\.js\?v=[^"\']+','/static/student_summary.js?v=3.7.0',text)
    html.write_text(text,encoding="utf-8")
    print("MEUCRONOGRAMA_MANAGEMENT_REFINEMENT_V37_READY: sortable tables, exact 0-1000 TRI positioning, area maxima and class correction workflow installed.",flush=True)

if __name__=="__main__":
    main()
