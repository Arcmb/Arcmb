"""Production verification for the student academic home dashboard."""
from pathlib import Path
ROOT=Path(__file__).resolve().parent
def require(condition,message):
    if not condition: raise RuntimeError(message)
def main():
    js=(ROOT/'static'/'student_summary.js').read_text(encoding='utf-8')
    css=(ROOT/'static'/'style.css').read_text(encoding='utf-8')
    html=(ROOT/'static'/'app.html').read_text(encoding='utf-8')
    model=(ROOT/'model_data.py').read_text(encoding='utf-8')
    for marker in ['TRAJETÓRIA ACADÊMICA NA VISÃO GERAL','Meu desempenho e progresso','Evolução nos simulados','Trilha de aprendizagem','Execução da rotina',"view==='performance'||view==='home'",'studentHomeOriginalHomeView']:
        require(marker in js,'Missing student-home marker: '+marker)
    require('MEU CRONOGRAMA: TRAJETÓRIA ACADÊMICA NA VISÃO GERAL' in css,'Student-home CSS is missing.')
    require('/static/student_summary.js?v=3.4.0' in html,'Student-home cache key is missing.')
    require('# === MEU CRONOGRAMA: TRAJETÓRIA ACADÊMICA NA VISÃO GERAL ===' in model,'Student-home backend extension is missing.')
    print('MEUCRONOGRAMA_STUDENT_HOME_CHECK_OK: dashboard base and v3.4 asset passed.',flush=True)
if __name__=='__main__': main()
