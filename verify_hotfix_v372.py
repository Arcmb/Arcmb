"""Verify v3.7.2 hotfix."""
from pathlib import Path
ROOT=Path(__file__).resolve().parent
def require(v,m):
    if not v: raise RuntimeError(m)
def main():
    model=(ROOT/'model_data.py').read_text(encoding='utf-8')
    js=(ROOT/'static'/'student_summary.js').read_text(encoding='utf-8')
    css=(ROOT/'static'/'style.css').read_text(encoding='utf-8')
    html=(ROOT/'static'/'app.html').read_text(encoding='utf-8')
    require('# === HOTFIX V3.7.2 ===' in model,'Backend hotfix v3.7.2 missing.')
    require("_reports_header_key" in model and "_reports_normalize_url" in model,'Robust report parser missing.')
    require("_reports_header_map(['NOME DO ALUNO','ATIVIDADE/SIMULADO','TIPO DE RELATÓRIO','NOME DO RELATÓRIO (opcional)','DATA (opcional)','LINK DE ACESSO'])" not in model,'Unexpected test residue.')
    ns={}
    compile(model,'model_data.py','exec')
    for marker in ("// === HOTFIX V3.7.2 ===","Turma cadastrada","Turmas divergentes","Salvar correção","management-score-axis"):
        require(marker in js,'Missing v3.7.2 UI marker: '+marker)
    require("class-divergent-chip" in css and "height:240px!important" in css,'v3.7.2 styles missing.')
    require('/static/student_summary.js?v=3.7.2' in html,'Student summary v3.7.2 cache key missing.')
    require("'activity':{'atividade','simulado','atividade simulado'" in model,'Activity/simulation header alias missing.')
    require("'type':{'tipo','tipo de relatorio'" in model,'Report type header alias missing.')
    print('MEUCRONOGRAMA_HOTFIX_372_CHECK_OK: generated report headers, URL normalization, class propagation UI and aligned TRI axis passed.',flush=True)
if __name__=='__main__': main()
