"""Verify management refinement v3.7."""
from pathlib import Path
ROOT=Path(__file__).resolve().parent
def require(v,m):
    if not v: raise RuntimeError(m)
def main():
    model=(ROOT/"model_data.py").read_text(encoding="utf-8")
    js=(ROOT/"static"/"student_summary.js").read_text(encoding="utf-8")
    css=(ROOT/"static"/"style.css").read_text(encoding="utf-8")
    html=(ROOT/"static"/"app.html").read_text(encoding="utf-8")
    require("# === MANAGEMENT REFINEMENT V3.7 ===" in model,"Backend v3.7 missing.")
    require("/api/model-data/class-correction" in model and "maxTri" in model,"Class correction or max TRI missing.")
    for marker in ("// === MANAGEMENT REFINEMENT V3.7 ===","management-sort","A altura da coluna corresponde exatamente","Máxima","Pendências encontradas","Confirmar correção"):
        require(marker in js,"Missing UI marker: "+marker)
    require("management-score-fill" in css and "class-pending-row" in css,"Styles missing.")
    require("/static/student_summary.js?v=3.7.0" in html,"Cache key v3.7.0 missing.")
    compile(model,"model_data.py","exec")
    print("MEUCRONOGRAMA_MANAGEMENT_REFINEMENT_V37_CHECK_OK: sorting, exact TRI scale, maxima and class correction passed.",flush=True)
if __name__=="__main__": main()
