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
    compile(model,"model_data.py","exec")
    print("MEUCRONOGRAMA_TRI_IMPORT_STABILITY_CHECK_OK: single-parse confirm and guaranteed UI recovery passed.",flush=True)

if __name__=="__main__":
    main()
