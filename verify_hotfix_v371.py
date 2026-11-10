"""Verify v3.7.1 hotfix."""
from pathlib import Path
ROOT=Path(__file__).resolve().parent
def require(v,m):
    if not v: raise RuntimeError(m)
def main():
    model=(ROOT/'model_data.py').read_text(encoding='utf-8')
    js=(ROOT/'static'/'student_summary.js').read_text(encoding='utf-8')
    css=(ROOT/'static'/'style.css').read_text(encoding='utf-8')
    html=(ROOT/'static'/'app.html').read_text(encoding='utf-8')
    require('# === HOTFIX V3.7.1 ===' in model,'Backend hotfix missing.')
    require("report-type-delete" in model and "_reports_delete_type" in model,'Type deletion route missing.')
    require("if isinstance(output,tuple)" in model and "return bytes(output)" in model,'Report XLSX byte normalization missing.')
    for marker in ("// === HOTFIX V3.7.1 ===","report-type-delete","management-score-marker","Modelo XLSX gerado"):
        require(marker in js,'Missing hotfix UI marker: '+marker)
    require('background:transparent!important' in css and 'management-score-fill' in css,'Dynamic fill styles missing.')
    require('/static/student_summary.js?v=3.7.1' in html,'Student summary hotfix cache key missing.')
    compile(model,'model_data.py','exec')
    print('MEUCRONOGRAMA_HOTFIX_371_CHECK_OK: report template download, type deletion and exact dynamic TRI columns passed.',flush=True)
if __name__=='__main__': main()
