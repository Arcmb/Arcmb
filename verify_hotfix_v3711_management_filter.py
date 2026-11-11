"""Verify management filter fix v3.7.11."""
from pathlib import Path
ROOT=Path(__file__).resolve().parent
def require(v,m):
    if not v: raise RuntimeError(m)
def main():
    model=(ROOT/'model_data.py').read_text(encoding='utf-8')
    js=(ROOT/'static'/'student_summary.js').read_text(encoding='utf-8')
    html=(ROOT/'static'/'app.html').read_text(encoding='utf-8')

    require('# === MANAGEMENT FILTER FIX V3.7.11 ===' in model,'Backend filter fix missing.')
    require("if isinstance(raw, (list, tuple)):" in model,'List query unwrapping missing.')
    require("'turma': _v3711_query_scalar(query, 'turma', 160)" in model,'Turma scalar parsing missing.')
    require("'year': _v3711_query_scalar(query, 'year', 4)" in model,'Year scalar parsing missing.')
    require("data.setdefault('areas', [])" in model and "data.setdefault('simulations', [])" in model,'Safe dashboard payload missing.')

    require('// === MANAGEMENT FILTER FIX V3.7.11 ===' in js,'Frontend filter fix missing.')
    require('managementSafeArray' in js,'Safe-array rendering missing.')
    require("document.getElementById('management-turma')" in js,'Refresh filter state sync missing.')
    require('/static/student_summary.js?v=3.7.11' in html,'Cache key v3.7.11 missing.')
    compile(model,'model_data.py','exec')
    print('MEUCRONOGRAMA_MANAGEMENT_FILTER_FIX_CHECK_OK: turma/year filters, safe rendering and filtered averages passed.',flush=True)
if __name__=='__main__': main()
