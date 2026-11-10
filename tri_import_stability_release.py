"""Fix TRI/redaction confirmation latency and stuck-busy UI."""
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
acts['tri-import-confirm']=async()=>{
 const sim=triSelectedSimulation();if(!sim||!triImportPreviewData)throw new Error('Gere a conferência antes de confirmar.');
 if(!confirm(`Vincular as notas da aba ${triImportDraft.inspection.sheet} ao simulado ${sim.activity} de ${sim.date}?`))return;
 triImportBusy=true;render();
 try{
  const d=await api('/api/model-data/tri-confirm',{file:triImportDraft.file,filename:triImportDraft.filename,activityKey:sim.activityKey,date:sim.date});
  studentSummaryCache?.clear?.();
  if(typeof resultExportSimulations!=='undefined')resultExportSimulations=null;
  triImportPreviewData=null;
  toast(`Notas TRI e redação salvas: ${d.summary.updated} atualizada(s); ${d.summary.unchanged} sem mudança.`);
 }catch(error){
  const message=error?.message||'erro inesperado ao gravar as notas';
  toast('Não foi possível salvar as notas: '+message,true);
 }finally{
  triImportBusy=false;
  render();
 }
};
"""
    if "// === TRI IMPORT STABILITY V1 ===" not in text:
        if old not in text:
            raise RuntimeError("TRI confirm frontend handler was not found.")
        text = text.replace(old, new, 1)
    path.write_text(text, encoding="utf-8")

def main():
    patch_backend()
    patch_frontend()
    print("MEUCRONOGRAMA_TRI_IMPORT_STABILITY_READY: confirm reuses parsed XLSX and UI always exits saving state.", flush=True)

if __name__ == "__main__":
    main()
