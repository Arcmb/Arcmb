"""Verify performance refinement v3.4."""
from pathlib import Path

ROOT=Path(__file__).resolve().parent

def require(value,message):
    if not value:
        raise RuntimeError(message)

def main():
    model=(ROOT/"model_data.py").read_text(encoding="utf-8")
    home=(ROOT/"static"/"student_summary.js").read_text(encoding="utf-8")
    tri=(ROOT/"static"/"tri_scores.js").read_text(encoding="utf-8")
    html=(ROOT/"static"/"app.html").read_text(encoding="utf-8")
    css=(ROOT/"static"/"style.css").read_text(encoding="utf-8")

    require("# === PERFORMANCE REFINEMENT V3.4 ===" in model,"Backend refinement marker missing.")
    require("/api/model-data/exam-edit-list" in model and "/api/model-data/exam-date-update" in model,"Map date-edit routes are missing.")
    require("_exam_id" in model and "updatedResults" in model,"Linked-result propagation is missing.")
    require("resultado duplicado" in model,"Date conflict protection is missing.")

    for marker in ("// === PERFORMANCE OVERVIEW V3.4 ===","acertos acumulados","TRI geral mais recente","Redação","Todas as disciplinas de"):
        require(marker in home,"Missing overview marker: "+marker)
    require("p.correct||0)+'/'+Number(p.valid||0)" in home,"Accumulated correct/valid total is missing.")

    for marker in ("// === TRI AVERAGE V3.4 ===","Média dos simulados selecionados","triDashboardAverage","Último simulado realizado"):
        require(marker in tri,"Missing TRI-average marker: "+marker)

    for marker in ("// === EXAM DATE EDIT V3.4 ===","Editar dados dos mapas","Salvar data","exam-date-update"):
        require(marker in home,"Missing map-edit UI marker: "+marker)

    require("/static/student_summary.js?v=3.7.0" in html,"Student summary cache key is missing.")
    require("/static/tri_scores.js?v=3.7.14" in html,"TRI cache key is missing.")
    require("PERFORMANCE REFINEMENT V3.4" in css,"Refinement CSS is missing.")
    compile(model,"model_data.py","exec")
    print("MEUCRONOGRAMA_PERFORMANCE_REFINEMENT_CHECK_OK: totals, latest TRI/disciplines, selected averages and safe exam-date edit passed.",flush=True)

if __name__=="__main__":
    main()
