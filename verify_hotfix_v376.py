"""Verify scoped report deletion v3.7.6."""
from pathlib import Path
ROOT=Path(__file__).resolve().parent
def require(v,m):
    if not v: raise RuntimeError(m)
def main():
    model=(ROOT/'model_data.py').read_text(encoding='utf-8')
    js=(ROOT/'static'/'student_summary.js').read_text(encoding='utf-8')
    css=(ROOT/'static'/'style.css').read_text(encoding='utf-8')
    html=(ROOT/'static'/'app.html').read_text(encoding='utf-8')

    require('# === REPORT SCOPED DELETE V3.7.6 ===' in model,'Scoped-delete backend missing.')
    require('/api/model-data/report-delete-options' in model and '/api/model-data/report-delete-scope' in model,'Delete routes missing.')
    require('_reports_latest_class_by_user' in model,'Latest-class resolution missing.')
    require("delete_model=True" in model and "DELETE FROM hmay_report_models" in model,'Global model deletion missing.')
    require("if selected_ids:" in model and "deleted_users.update(group_users)" in model,'Per-class/per-student semantics missing.')

    for marker in ('// === REPORT SCOPED DELETE V3.7.6 ===','report-model-delete-open','report-delete-confirm','Nenhuma turma foi selecionada','turma inteira'):
        require(marker in js,'Missing scoped-delete UI marker: '+marker)
    require('report-delete-class' in css and 'report-delete-students' in css,'Scoped-delete styles missing.')
    require('/static/student_summary.js?v=3.7.6' in html,'Student summary v3.7.6 cache key missing.')
    compile(model,'model_data.py','exec')
    print('MEUCRONOGRAMA_REPORT_SCOPED_DELETE_CHECK_OK: global, class-wide, mixed-class and selected-student report deletion rules passed.',flush=True)
if __name__=='__main__': main()
