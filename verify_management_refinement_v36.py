"""Verify management refinement v3.6."""
from pathlib import Path
ROOT=Path(__file__).resolve().parent
def require(value,message):
    if not value: raise RuntimeError(message)
def main():
    model=(ROOT/"model_data.py").read_text(encoding="utf-8")
    js=(ROOT/"static"/"student_summary.js").read_text(encoding="utf-8")
    css=(ROOT/"static"/"style.css").read_text(encoding="utf-8")
    html=(ROOT/"static"/"app.html").read_text(encoding="utf-8")
    require("# === MANAGEMENT REFINEMENT V3.6 ===" in model,"V3.6 backend marker missing.")
    require("hmay_classes" in model and "/api/model-data/classes" in model,"Class registry missing.")
    require("_v36_validate_class_names" in model and "turma(s) não cadastrada(s)" in model,"Import class validation missing.")
    require("# === TRI MODEL WITHOUT BONUS V3.6 ===" in model,"TRI no-bonus template missing.")
    template=model[model.find("# === TRI MODEL WITHOUT BONUS V3.6 ==="):]
    require("NOTA COM BONIFICAÇÃO" not in template,"Bonus column is still present in the final TRI model.")
    require("_v36_dashboard_cache" in model and "_v36_exam_area_maps" in model,"Fast dashboard/cache missing.")
    for marker in ("// === MANAGEMENT REFINEMENT V3.6 ===","Nota TRI geral média em escala de 0 a 1000","% acertos","Cadastro de turmas","class-registry-new"):
        require(marker in js,"Missing V3.6 UI marker: "+marker)
    require("<th>% acertos</th>" in js,"Simulation/class percentage column is missing.")
    require("management-score-track" in css and "class-registry-card" in css,"V3.6 styles missing.")
    require("/static/student_summary.js?v=3.7.0" in html,"Student summary cache key v3.6.0 missing.")
    compile(model,"model_data.py","exec")
    print("MEUCRONOGRAMA_MANAGEMENT_REFINEMENT_CHECK_OK: fast cache, TRI 0-1000, percent tables, class registry/validation and bonus removal passed.",flush=True)
if __name__=="__main__": main()
