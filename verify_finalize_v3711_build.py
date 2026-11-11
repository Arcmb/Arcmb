"""Final functional checks for v3.7.11 management filters."""
from pathlib import Path
import model_data as M

ROOT=Path(__file__).resolve().parent

def require(v,m):
    if not v: raise RuntimeError(m)

def main():
    html=(ROOT/'static'/'app.html').read_text(encoding='utf-8')
    require('/static/student_summary.js?v=3.7.11' in html,'Final student-summary cache key is not v3.7.11.')
    require('3.7.111' not in html,'Malformed public version remains in HTML.')

    require(M._v3711_query_scalar({'turma':['Enem Fit']},'turma',160)=='Enem Fit','Turma list query was not unwrapped.')
    require(M._v3711_query_scalar({'year':['2026']},'year',4)=='2026','Year list query was not unwrapped.')
    require(M._v3711_query_scalar({'activityKey':['abc']},'activityKey',250)=='abc','Simulation list query was not unwrapped.')
    require(M._v3711_query_scalar({},'turma',160)=='','Empty turma filter must remain empty.')

    print('MEUCRONOGRAMA_V3711_FINAL_GUARD_CHECK_OK: final version key and list-based management filters passed.',flush=True)

if __name__=='__main__': main()
