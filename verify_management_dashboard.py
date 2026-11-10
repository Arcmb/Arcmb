"""Verify management dashboard v3.5."""
from pathlib import Path
ROOT=Path(__file__).resolve().parent
def require(value,message):
    if not value: raise RuntimeError(message)
def main():
    model=(ROOT/"model_data.py").read_text(encoding="utf-8")
    js=(ROOT/"static"/"student_summary.js").read_text(encoding="utf-8")
    css=(ROOT/"static"/"style.css").read_text(encoding="utf-8")
    html=(ROOT/"static"/"app.html").read_text(encoding="utf-8")
    require("# === MANAGEMENT DASHBOARD V3.5 ===" in model,"Management backend marker missing.")
    require("/api/model-data/management-dashboard" in model,"Management endpoint missing.")
    require("('master','coordenador')" in model,"Management role guard missing.")
    for marker in ("// === MANAGEMENT DASHBOARD V3.5 ===","Painel de bordo da coordenação","Resumo geral","Médias por área","Resumo por simulado","Resumo por turma","management-turma","management-simulation"):
        require(marker in js,"Missing management UI marker: "+marker)
    require("['master','coordenador'].includes(ME.role)" in js,"Master/coordinator frontend guard missing.")
    require("/static/student_summary.js?v=3.6.0" in html,"Management asset cache key missing.")
    require("MANAGEMENT DASHBOARD V3.5" in css,"Management CSS marker missing.")
    compile(model,"model_data.py","exec")
    print("MEUCRONOGRAMA_MANAGEMENT_DASHBOARD_CHECK_OK: master/coordinator aggregate dashboard, filters, KPIs, area/simulation/class analytics passed.",flush=True)
if __name__=="__main__": main()
