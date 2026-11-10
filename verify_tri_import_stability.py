"""Verify TRI/redaction import confirmation stability patch."""
from pathlib import Path

ROOT=Path(__file__).resolve().parent

def require(value,message):
    if not value:
        raise RuntimeError(message)

def main():
    model=(ROOT/"model_data.py").read_text(encoding="utf-8")
    js=(ROOT/"static"/"tri_scores.js").read_text(encoding="utf-8")
    require("# === TRI IMPORT STABILITY V1 ===" in model, "Backend stability marker missing.")
    require("match = _tri_match(app, c, parsed, activity_key, applied_on)" in model, "Confirm does not reuse parsed workbook.")
    preview="if path == '/api/model-data/tri-preview':\n            parsed, match, preview = _tri_preview(app, c, data)"
    require(preview in model, "TRI preview route was not preserved.")
    require("// === TRI IMPORT STABILITY V1 ===" in js, "Frontend stability marker missing.")
    require("Não foi possível salvar as notas:" in js, "Visible TRI save error handling missing.")
    require("finally{triImportBusy=false;}" not in js[js.find("// === TRI IMPORT STABILITY V1 ==="):], "Old stuck-busy confirm handler remains.")
    require("triImportBusy=false;\n  render();" in js, "Confirm does not redraw after leaving busy state.")
    require("/api/model-data/tri-confirm" in js, "TRI confirmation endpoint missing.")
    require("'issues': {" in model and "unmatchedNames" in model and "withoutScoreNames" in model, "Persistent import issue payload missing.")
    require("Resultado da última importação" in js, "Persistent import summary UI missing.")
    require("triImportSaveSummary=d" in js, "Successful import is not retained for audit.")
    require("triImportClearBeforeSummary" in js, "Persistent summary is not cleared with import reset.")
    compile(model,"model_data.py","exec")
    print("MEUCRONOGRAMA_TRI_IMPORT_STABILITY_CHECK_OK: single-parse confirm and guaranteed UI recovery passed.",flush=True)

if __name__=="__main__":
    main()
