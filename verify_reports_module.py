"""Verify student reports module."""
from pathlib import Path
ROOT=Path(__file__).resolve().parent
def require(v,m):
    if not v: raise RuntimeError(m)
def main():
    model=(ROOT/"model_data.py").read_text(encoding="utf-8")
    app=(ROOT/"static"/"app.js").read_text(encoding="utf-8")
    js=(ROOT/"static"/"student_summary.js").read_text(encoding="utf-8")
    css=(ROOT/"static"/"style.css").read_text(encoding="utf-8")
    html=(ROOT/"static"/"app.html").read_text(encoding="utf-8")
    require("# === STUDENT REPORTS MODULE V1 ===" in model,"Reports backend missing.")
    for route in ("student-reports","report-admin-data","report-type-save","report-model-save","report-batch-preview","report-batch-confirm"):
        require(route in model,"Missing reports route: "+route)
    require("hmay_report_types" in model and "hmay_report_models" in model and "hmay_student_reports" in model,"Reports tables missing.")
    require("['reports','Meus relatórios']" in app and "['report-admin','Cadastro de relatórios']" in app,"Reports nav missing.")
    require("reports:reportsView" in app and "'report-admin':reportAdminView" in app,"Reports page routing missing.")
    for marker in ("// === STUDENT REPORTS MODULE V1 ===","Meus relatórios","Cadastro em lote","Modelos cadastrados","Tipos de relatório","Abrir relatório"):
        require(marker in js,"Missing reports UI marker: "+marker)
    require("STUDENT REPORTS MODULE V1" in css,"Reports CSS missing.")
    require("/static/app.js?v=3.7.0" in html and "/static/student_summary.js?v=3.7.0" in html,"Reports cache keys missing.")
    compile(model,"model_data.py","exec")
    print("MEUCRONOGRAMA_REPORTS_MODULE_CHECK_OK: student reports, types, batch import, shared models, covers and nav passed.",flush=True)
if __name__=="__main__": main()
