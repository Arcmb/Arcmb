"""Fix TRI/redaction confirmation latency, stuck-busy UI and persistent import audit."""
from pathlib import Path

ROOT = Path(__file__).resolve().parent
MARK = "# === TRI IMPORT STABILITY V1 ==="

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
"""
    new = """        if path == '/api/model-data/tri-preview':
            parsed, match, preview = _tri_preview(app, c, data)
            preview['unmatchedNames'] = match['unmatched'][:50]
            preview['conflictRows'] = match['conflicts'][:50]
            preview['withoutScoreNames'] = match['withoutScore'][:50]
            return app.reply(start, 200, preview)
        # === TRI IMPORT STABILITY V1 ===
        # Confirmation already parsed the workbook above. Reuse that parsed
        # payload instead of parsing the XLSX a second time.
        match = _tri_match(app, c, parsed, activity_key, applied_on)
        updated = unchanged = 0
"""
    if MARK not in text:
        if old not in text:
            raise RuntimeError("TRI confirm backend block was not found.")
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
    new = """// === TRI IMPORT STABILITY V1 ===
let triImportSaveSummary=null;
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
const triImportStatusBeforeSaveSummary=triImportStatus;
triImportStatus=function(){return triImportStatusBeforeSaveSummary()+triImportSavedSummaryHtml();};

acts['tri-import-confirm']=async()=>{
 const sim=triSelectedSimulation();if(!sim||!triImportPreviewData)throw new Error('Gere a conferência antes de confirmar.');
 if(!confirm(`Vincular as notas da aba ${triImportDraft.inspection.sheet} ao simulado ${sim.activity} de ${sim.date}?`))return;
 triImportBusy=true;render();
 try{
  const d=await api('/api/model-data/tri-confirm',{file:triImportDraft.file,filename:triImportDraft.filename,activityKey:sim.activityKey,date:sim.date});
  studentSummaryCache?.clear?.();
  if(typeof resultExportSimulations!=='undefined')resultExportSimulations=null;
  triImportPreviewData=null;
  triImportSaveSummary=d;
  toast(`Notas TRI e redação salvas: ${d.summary.updated} atualizada(s); ${d.summary.unchanged} sem mudança.`);
 }catch(error){
  const message=error?.message||'erro inesperado ao gravar as notas';
  toast('Não foi possível salvar as notas: '+message,true);
 }finally{
  triImportBusy=false;
  render();
 }
};
const triImportClearBeforeSummary=acts['tri-import-clear'];
acts['tri-import-clear']=()=>{triImportSaveSummary=null;return triImportClearBeforeSummary();};
document.addEventListener('change',event=>{if(event.target?.id==='tri-import-file')triImportSaveSummary=null;},true);
"""
    if "// === TRI IMPORT STABILITY V1 ===" not in text:
        if old not in text:
            raise RuntimeError("TRI confirm frontend handler was not found.")
        text = text.replace(old, new, 1)
    path.write_text(text, encoding="utf-8")

def main():
    patch_backend()
    patch_frontend()
    print("MEUCRONOGRAMA_TRI_IMPORT_STABILITY_READY: single-parse confirm, persistent audit summary and guaranteed UI recovery installed.", flush=True)

if __name__ == "__main__":
    main()
