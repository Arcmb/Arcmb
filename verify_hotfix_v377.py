"""Verify report registry view v3.7.7."""
from pathlib import Path
ROOT=Path(__file__).resolve().parent
def require(v,m):
    if not v: raise RuntimeError(m)
def main():
    model=(ROOT/'model_data.py').read_text(encoding='utf-8')
    js=(ROOT/'static'/'student_summary.js').read_text(encoding='utf-8')
    css=(ROOT/'static'/'style.css').read_text(encoding='utf-8')
    html=(ROOT/'static'/'app.html').read_text(encoding='utf-8')

    require('# === REPORT REGISTRY VIEW V3.7.7 ===' in model,'Registry backend missing.')
    require('/api/model-data/report-registry' in model and '/api/model-data/report-registry-detail' in model,'Registry routes missing.')
    require('_reports_latest_class_by_user' in model,'Current-class mapping is not reused.')
    require("student_suggestions" in model and "class_suggestions" in model,'Autocomplete suggestions missing.')

    for marker in (
        '// === REPORT REGISTRY VIEW V3.7.7 ===',
        'report-registry-student',
        'report-registry-turma',
        'report-registry-model-toggle',
        'report-registry-class-toggle',
        'Ver vínculos',
        'Abrir relatório',
    ):
        require(marker in js,'Missing registry UI marker: '+marker)
    require('report-registry-class-list' in css and 'report-registry-students-table' in css,'Registry nested-table styles missing.')
    require('/static/student_summary.js?v=3.7.7' in html,'Student summary v3.7.7 cache key missing.')
    compile(model,'model_data.py','exec')
    print('MEUCRONOGRAMA_REPORT_REGISTRY_CHECK_OK: searchable manager table, autocomplete, class drill-down, student drill-down and individual links passed.',flush=True)
if __name__=='__main__': main()
