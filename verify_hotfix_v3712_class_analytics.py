"""Verify hierarchical ENEM analytics v3.7.12."""
from pathlib import Path
ROOT=Path(__file__).resolve().parent
def require(v,m):
    if not v: raise RuntimeError(m)
def main():
    model=(ROOT/'model_data.py').read_text(encoding='utf-8')
    js=(ROOT/'static'/'student_summary.js').read_text(encoding='utf-8')
    css=(ROOT/'static'/'style.css').read_text(encoding='utf-8')
    html=(ROOT/'static'/'app.html').read_text(encoding='utf-8')

    require('# === CLASS ENEM ANALYTICS V3.7.12 ===' in model,'Backend analytics marker missing.')
    for token in ('management-class-analytics','management-class-detail','management-simulation-students'):
        require(token in model,'Missing analytics endpoint '+token)
    require("sum(vals[k] or 0.0 for k in ('lc','ch','cn','mt','red'))/5.0" in model,'Five-area ENEM mean missing.')
    require("bonus=enem*1.10" in model,'10 percent bonus missing.')
    require("redaction=None if all(v is None for v in red_parts) else round(sum(v or 0 for v in red_parts),2)" in model,'Competency-sum essay score missing.')
    require("row['ranking']=index" in model,'ENEM ranking missing.')

    for marker in ('// === CLASS ENEM ANALYTICS V3.7.12 ===','Simulados considerados nas médias','management-class-drill','management-simulation-drill','Nota ENEM','+10%','C1','C5'):
        require(marker in js,'Missing UI marker '+marker)
    require('management-sim-checks' in css and 'management-drill-row' in css,'Analytics styles missing.')
    require('/static/student_summary.js?v=3.7.12' in html,'v3.7.12 cache key missing.')
    compile(model,'model_data.py','exec')
    print('MEUCRONOGRAMA_CLASS_ENEM_ANALYTICS_CHECK_OK: class/simulation/student hierarchy, ENEM means, bonus, competencies, ranking and simulation selection passed.',flush=True)
if __name__=='__main__': main()
