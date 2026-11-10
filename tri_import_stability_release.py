"""Harden TRI/redaction import: batch persistence, visible stages, cache bust and audit."""
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parent
MARK = "# === TRI IMPORT STABILITY V2 ==="

def patch_backend():
    path = ROOT / "model_data.py"
    text = path.read_text(encoding="utf-8")

    old = """        parsed, match, preview = _tri_preview(app, c, data)
        if path == '/api/model-data/tri-preview':
            preview['unmatchedNames'] = match['unmatched'][:50]
            preview['conflictRows'] = match['conflicts'][:50]
            preview['withoutScoreNames'] = match['withoutScore'][:50]
            return app.reply(start, 200, preview)
        updated = unchanged = 0
        for pair in match['matched']:
            metadata = _rx_json(pair['target'].get('metadata'))
            if _tri_apply_metadata(metadata, pair['source']['scores'], parsed['sheet'], user):
                app.db.execute(
                    c, 'UPDATE hmay_performance SET metadata=?,updated_at=? WHERE id=?',
                    (json.dumps(metadata, ensure_ascii=False, separators=(',', ':')), P.now().isoformat(), pair['target']['id']),
                )
                updated += 1
            else:
                unchanged += 1
        app.event(c, user, user['id'], 'tri_scores_import')
"""

    new = """        if path == '/api/model-data/tri-preview':
            parsed, match, preview = _tri_preview(app, c, data)
            preview['unmatchedNames'] = match['unmatched'][:50]
            preview['conflictRows'] = match['conflicts'][:50]
            preview['withoutScoreNames'] = match['withoutScore'][:50]
            return app.reply(start, 200, preview)

        # === TRI IMPORT STABILITY V2 ===
        # The workbook was parsed above. Reuse it and persist changed rows in
        # small SQL batches instead of one network round-trip per student.
        match = _tri_match(app, c, parsed, activity_key, applied_on)
        pending_updates = []
        unchanged = 0
        for pair in match['matched']:
            metadata = _rx_json(pair['target'].get('metadata'))
            if _tri_apply_metadata(metadata, pair['source']['scores'], parsed['sheet'], user):
                pending_updates.append((
                    pair['target']['id'],
                    json.dumps(metadata, ensure_ascii=False, separators=(',', ':')),
                ))
            else:
                unchanged += 1

        TRI_IMPORT_BATCH_SIZE = 80
        updated = 0
        total_pending = len(pending_updates)
        print(
            f'MEUCRONOGRAMA_TRI_IMPORT_START matched={len(match["matched"])} pending={total_pending} unchanged={unchanged}',
            flush=True,
        )
        stamp = P.now().isoformat()
        for offset in range(0, total_pending, TRI_IMPORT_BATCH_SIZE):
            chunk = pending_updates[offset:offset + TRI_IMPORT_BATCH_SIZE]
            cases = ' '.join('WHEN ? THEN ?' for _ in chunk)
            placeholders = ','.join('?' for _ in chunk)
            params = []
            for row_id, metadata_json in chunk:
                params.extend((row_id, metadata_json))
            params.append(stamp)
            params.extend(row_id for row_id, _ in chunk)
            sql = (
                'UPDATE hmay_performance SET metadata=CASE id ' + cases +
                ' ELSE metadata END,updated_at=? WHERE id IN (' + placeholders + ')'
            )
            app.db.execute(c, sql, tuple(params))
            updated += len(chunk)
            print(
                f'MEUCRONOGRAMA_TRI_IMPORT_BATCH_DONE updated={updated}/{total_pending}',
                flush=True,
            )

        app.event(c, user, user['id'], 'tri_scores_import')
        print(
            f'MEUCRONOGRAMA_TRI_IMPORT_DONE updated={updated} unchanged={unchanged} matched={len(match["matched"])}',
            flush=True,
        )
"""

    if MARK not in text:
        if old not in text:
            raise RuntimeError("TRI confirmation persistence block was not found.")
        text = text.replace(old, new, 1)

    old_reply = """                'conflicts': len(match['conflicts']), 'withoutScore': len(match['withoutScore']),
            }
        })"""
    new_reply = """                'conflicts': len(match['conflicts']), 'withoutScore': len(match['withoutScore']),
            },
            'issues': {
                'unmatchedNames': match['unmatched'][:100],
                'conflictRows': match['conflicts'][:100],
                'withoutScoreNames': match['withoutScore'][:100],
            }
        })"""
    if "'issues': {" not in text:
        if old_reply not in text:
            raise RuntimeError("TRI confirm response block was not found.")
        text = text.replace(old_reply, new_reply, 1)

    path.write_text(text, encoding="utf-8")

def patch_frontend():
    path = ROOT / "static" / "tri_scores.js"
    text = path.read_text(encoding="utf-8")

    old = """acts['tri-import-confirm']=async()=>{
 const sim=triSelectedSimulation();if(!sim||!triImportPreviewData)throw new Error('Gere a conferência antes de confirmar.');
 if(!confirm(`Vincular as notas da aba ${triImportDraft.inspection.sheet} ao simulado ${sim.activity} de ${sim.date}?`))return;
 triImportBusy=true;render();try{const d=await api('/api/model-data/tri-confirm',{file:triImportDraft.file,filename:triImportDraft.filename,activityKey:sim.activityKey,date:sim.date});studentSummaryCache?.clear?.();if(typeof resultExportSimulations!=='undefined')resultExportSimulations=null;triImportPreviewData=null;toast(`Notas TRI vinculadas: ${d.summary.updated} atualizada(s); ${d.summary.unchanged} sem mudança.`);render();}finally{triImportBusy=false;}
};
"""

    new = """// === TRI IMPORT STABILITY V2 ===
let triImportSaveSummary=null;
let triImportProcess=null;
let triImportProcessTimer=null;

function triImportIssueName(x){
 if(typeof x==='string')return x;
 return x?.name||x?.student_name||x?.target?.student_name||x?.source?.name||'Registro não identificado';
}
function triImportSavedSummaryHtml(){
 const d=triImportSaveSummary;if(!d)return '';
 const s=d.summary||{},issues=d.issues||{};
 const blocks=[
  ['Não encontrados',issues.unmatchedNames||[]],
  ['Conflitos de nome',issues.conflictRows||[]],
  ['Sem nota no arquivo',issues.withoutScoreNames||[]]
 ].filter(x=>x[1].length);
 const detail=blocks.map(([title,values])=>'<div class="tri-import-issue"><strong>'+esc(title)+' ('+values.length+')</strong><ul>'+values.map(v=>'<li>'+esc(triImportIssueName(v))+'</li>').join('')+'</ul></div>').join('');
 return '<section class="notice '+((s.unmatched||s.conflicts||s.withoutScore)?'warning':'success')+' tri-import-result"><h3>Resultado da última importação</h3><div class="student-home-mini-stats"><div><strong>'+Number(s.updated||0)+'</strong><span>atualizados</span></div><div><strong>'+Number(s.unchanged||0)+'</strong><span>sem alteração</span></div><div><strong>'+Number(s.unmatched||0)+'</strong><span>não encontrados</span></div><div><strong>'+Number(s.conflicts||0)+'</strong><span>conflitos</span></div><div><strong>'+Number(s.withoutScore||0)+'</strong><span>sem nota</span></div></div>'+detail+'</section>';
}
function triImportProcessHtml(){
 const p=triImportProcess;
 const inspection=triImportDraft?.inspection;
 const preview=triImportPreviewData;
 if(!inspection&&!p)return '<div id="tri-import-process"></div>';
 const matched=p?.matched??preview?.matched??0;
 const students=p?.students??preview?.students??0;
 const state=p?.state||'preview';
 const done=n=>state==='done'||(state==='saving'&&n<=3)||(state==='sending'&&n<=2)||(state==='preview'&&n<=2);
 const active=n=>(state==='sending'&&n===3)||(state==='saving'&&n===4)||(state==='done'&&n===5)||(state==='error'&&n===5);
 const cls=n=>done(n)?'done':active(n)?(state==='error'?'error':'active'):'pending';
 const icon=n=>done(n)?'✓':active(n)?(state==='error'?'!':'…'):String(n);
 const note3=state==='sending'?'Enviando o arquivo e os vínculos para o servidor.':'Dados preparados para envio.';
 const note4=state==='saving'?'Servidor processando e gravando as notas no banco.':'Aguardando a etapa de gravação.';
 const note5=state==='done'?'Gravação confirmada pelo servidor.':state==='error'?'A operação não foi concluída. Veja a mensagem de erro.':'Aguardando confirmação final.';
 return '<section class="tri-import-process-card"><h3>Etapas da importação</h3>'+
  '<div class="tri-import-step '+cls(1)+'"><span>'+icon(1)+'</span><div><strong>1. Arquivo lido</strong><small>'+esc(inspection?.sheet||'Planilha reconhecida')+'</small></div></div>'+
  '<div class="tri-import-step '+cls(2)+'"><span>'+icon(2)+'</span><div><strong>2. Alunos vinculados</strong><small>'+matched+'/'+students+' aluno(s) vinculados ao simulado.</small></div></div>'+
  '<div class="tri-import-step '+cls(3)+'"><span>'+icon(3)+'</span><div><strong>3. Envio ao servidor</strong><small>'+note3+'</small></div></div>'+
  '<div class="tri-import-step '+cls(4)+'"><span>'+icon(4)+'</span><div><strong>4. Gravação das notas</strong><small>'+note4+'</small></div></div>'+
  '<div class="tri-import-step '+cls(5)+'"><span>'+icon(5)+'</span><div><strong>5. Finalização</strong><small>'+note5+'</small></div></div>'+
  '</section>';
}
function triImportUpdateProcessDom(){
 const el=document.getElementById('tri-import-process');
 if(el)el.innerHTML=triImportProcessHtml();
}
const triImportStatusBeforeStability=triImportStatus;
triImportStatus=function(){
 return triImportStatusBeforeStability()+'<div id="tri-import-process">'+triImportProcessHtml()+'</div>'+triImportSavedSummaryHtml();
};

acts['tri-import-preview']=async()=>{
 const sim=triSelectedSimulation();if(!sim)throw new Error('Selecione o simulado que receberá as notas.');
 triImportDraft.simulationId=sim.id;triImportBusy=true;
 try{
  triImportPreviewData=await api('/api/model-data/tri-preview',{file:triImportDraft.file,filename:triImportDraft.filename,activityKey:sim.activityKey,date:sim.date});
  triImportProcess={state:'preview',matched:triImportPreviewData.matched||0,students:triImportPreviewData.students||0};
  render();
 }finally{triImportBusy=false;}
};

acts['tri-import-confirm']=async()=>{
 const sim=triSelectedSimulation();if(!sim||!triImportPreviewData)throw new Error('Gere a conferência antes de confirmar.');
 if(!confirm(`Vincular as notas da aba ${triImportDraft.inspection.sheet} ao simulado ${sim.activity} de ${sim.date}?`))return;
 triImportBusy=true;
 triImportProcess={state:'sending',matched:triImportPreviewData.matched||0,students:triImportPreviewData.students||0};
 triImportUpdateProcessDom();
 const saveButton=document.querySelector('[data-act="tri-import-confirm"]');
 if(saveButton){saveButton.disabled=true;saveButton.textContent='Salvando notas…';}
 clearTimeout(triImportProcessTimer);
 triImportProcessTimer=setTimeout(()=>{
  if(triImportBusy&&triImportProcess){
   triImportProcess.state='saving';
   triImportUpdateProcessDom();
  }
 },700);
 try{
  const d=await api('/api/model-data/tri-confirm',{file:triImportDraft.file,filename:triImportDraft.filename,activityKey:sim.activityKey,date:sim.date});
  studentSummaryCache?.clear?.();
  if(typeof resultExportSimulations!=='undefined')resultExportSimulations=null;
  triImportSaveSummary=d;
  triImportProcess={state:'done',matched:d.summary?.matched||triImportProcess?.matched||0,students:triImportProcess?.students||0};
  triImportPreviewData=null;
  toast(`Notas TRI e redação salvas: ${d.summary.updated} atualizada(s); ${d.summary.unchanged} sem mudança.`);
 }catch(error){
  const message=error?.message||'erro inesperado ao gravar as notas';
  triImportProcess={...(triImportProcess||{}),state:'error'};
  toast('Não foi possível salvar as notas: '+message,true);
 }finally{
  clearTimeout(triImportProcessTimer);
  triImportBusy=false;
  render();
 }
};
const triImportClearBeforeStability=acts['tri-import-clear'];
acts['tri-import-clear']=()=>{
 clearTimeout(triImportProcessTimer);
 triImportSaveSummary=null;triImportProcess=null;
 return triImportClearBeforeStability();
};
document.addEventListener('change',event=>{
 if(event.target?.id==='tri-import-file'){
  clearTimeout(triImportProcessTimer);
  triImportSaveSummary=null;triImportProcess=null;
 }
},true);
"""

    if MARK.replace("#","//") not in text:
        if old not in text:
            raise RuntimeError("TRI base confirm handler was not found.")
        text = text.replace(old, new, 1)

    path.write_text(text, encoding="utf-8")

    html_path = ROOT / "static" / "app.html"
    html = html_path.read_text(encoding="utf-8")
    html = re.sub(r'/static/tri_scores\.js\?v=[^"\']+', '/static/tri_scores.js?v=3.2.0', html)
    html_path.write_text(html, encoding="utf-8")

    css_path = ROOT / "static" / "style.css"
    css = css_path.read_text(encoding="utf-8")
    css_marker = "/* === TRI IMPORT PROCESS V2 === */"
    css_extra = r"""
/* === TRI IMPORT PROCESS V2 === */
.tri-import-process-card{margin-top:.85rem;padding:.85rem;border:1px solid var(--line);border-radius:14px;background:#fff}
.tri-import-process-card h3{margin:0 0 .7rem}.tri-import-step{display:grid;grid-template-columns:30px 1fr;gap:.65rem;align-items:start;padding:.55rem 0;border-top:1px solid var(--line)}
.tri-import-step:first-of-type{border-top:0}.tri-import-step>span{width:26px;height:26px;border-radius:50%;display:grid;place-items:center;font-weight:800;background:#f3e8ea;color:var(--muted)}
.tri-import-step div{display:grid;gap:.12rem}.tri-import-step small{color:var(--muted)}.tri-import-step.done>span{background:#e1f1e9;color:#2f6b4d}.tri-import-step.active>span{background:#fff0d4;color:#805b11}.tri-import-step.error>span{background:#f8dce2;color:#8c2f42}.tri-import-step.pending{opacity:.62}
.tri-import-result{margin-top:.85rem}.tri-import-issue{margin-top:.65rem}.tri-import-issue ul{margin:.35rem 0 0;padding-left:1.2rem;max-height:180px;overflow:auto}
"""
    if css_marker not in css:
        css = css.rstrip() + "\n\n" + css_extra.strip() + "\n"
    css_path.write_text(css, encoding="utf-8")

def main():
    patch_backend()
    patch_frontend()
    print(
        "MEUCRONOGRAMA_TRI_IMPORT_STABILITY_V2_READY: batch persistence, 5-step progress UI and tri_scores cache bust installed.",
        flush=True,
    )

if __name__ == "__main__":
    main()
