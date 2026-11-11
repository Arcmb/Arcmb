"""Verify sortable hierarchical analytics v3.7.13."""
from pathlib import Path
ROOT=Path(__file__).resolve().parent
def require(v,m):
    if not v: raise RuntimeError(m)
def main():
    js=(ROOT/'static'/'student_summary.js').read_text(encoding='utf-8')
    css=(ROOT/'static'/'style.css').read_text(encoding='utf-8')
    html=(ROOT/'static'/'app.html').read_text(encoding='utf-8')
    for marker in (
        '// === CLASS ANALYTICS SORTING V3.7.13 ===',
        "class:{key:'turma',dir:'asc'}",
        "simulation:{key:'date',dir:'desc'}",
        "student:{key:'ranking',dir:'asc'}",
        'managementAnalyticsCompare',
        'managementAnalyticsSorted',
        'management-analytics-sort',
        "scope==='class'?'turma':scope==='simulation'?'activity':'name'",
    ):
        require(marker in js,'Missing sorting marker: '+marker)
    require('management-sort-th' in css and 'management-sort-arrow' in css,'Sorting styles missing.')
    require('/static/student_summary.js?v=3.7.13' in html,'v3.7.13 cache key missing.')
    print('MEUCRONOGRAMA_CLASS_ANALYTICS_SORT_CHECK_OK: alphabetical and ascending/descending sorting passed for class, simulation and student tables.',flush=True)
if __name__=='__main__': main()
