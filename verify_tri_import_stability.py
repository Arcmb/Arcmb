"""Verify TRI/redaction import stability V2."""
from pathlib import Path

ROOT=Path(__file__).resolve().parent

def require(value,message):
    if not value:
        raise RuntimeError(message)

def main():
    model=(ROOT/"model_data.py").read_text(encoding="utf-8")
    js=(ROOT/"static"/"tri_scores.js").read_text(encoding="utf-8")
    html=(ROOT/"static"/"app.html").read_text(encoding="utf-8")
    css=(ROOT/"static"/"style.css").read_text(encoding="utf-8")

    require("# === TRI IMPORT STABILITY V2 ===" in model, "Backend V2 marker missing.")
    require("pending_updates = []" in model, "Batch update collection missing.")
    require("TRI_IMPORT_BATCH_SIZE = 80" in model, "TRI batch size missing.")
    require("CASE id " in model and "MEUCRONOGRAMA_TRI_IMPORT_BATCH_DONE" in model, "Batch SQL/progress log missing.")
    require("match = _tri_match(app, c, parsed, activity_key, applied_on)" in model, "Confirm does not reuse parsed workbook.")
    require("'issues': {" in model and "unmatchedNames" in model and "withoutScoreNames" in model, "Persistent issue payload missing.")

    require("// === TRI IMPORT STABILITY V2 ===" in js, "Frontend V2 marker missing.")
    for label in ("1. Arquivo lido","2. Alunos vinculados","3. Envio ao servidor","4. Gravação das notas","5. Finalização"):
        require(label in js, "Missing progress label: "+label)
    require("triImportProcess.state='saving'" in js, "Saving-stage transition missing.")
    require("triImportProcess={state:'done'" in js, "Completion stage missing.")
    require("Não foi possível salvar as notas:" in js, "Visible save error missing.")
    stable=js[js.find("// === TRI IMPORT STABILITY V2 ==="):]
    require("triImportBusy=true;render();" not in stable, "Full-page redraw still happens before request.")
    require("saveButton.disabled=true" in stable, "Direct saving button state missing.")
    require("Resultado da última importação" in js, "Persistent audit summary missing.")

    require("/static/tri_scores.js?v=3.7.14" in html, "TRI cache key is not aligned with token flow.")
    require("TRI IMPORT PROCESS V2" in css, "Progress styles missing.")
    compile(model,"model_data.py","exec")
    print("MEUCRONOGRAMA_TRI_IMPORT_STABILITY_V2_CHECK_OK: batch save, 5-step progress, audit and cache bust passed.",flush=True)

if __name__=="__main__":
    main()
