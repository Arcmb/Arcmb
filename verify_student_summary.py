from pathlib import Path

ROOT=Path(__file__).resolve().parent

def require(value,message):
    if not value: raise RuntimeError(message)

def main():
    bulk=(ROOT/'static'/'bulk_accounts_panel.js').read_text(encoding='utf-8')
    model=(ROOT/'model_data.py').read_text(encoding='utf-8')
    summary=(ROOT/'static'/'student_summary.js').read_text(encoding='utf-8')
    html=(ROOT/'static'/'app.html').read_text(encoding='utf-8')
    require("if(inspect)inspect.disabled=false" in bulk,'Bulk reader button is not enabled after file selection.')
    require("student_role') not in ('user', 'aluno')" in model,'Export list still excludes aluno role.')
    require("/api/model-data/student-summary" in model,'Student summary endpoint is missing.')
    require('Resumo individual' in summary and 'Desempenho acumulado por disciplina' in summary,'Student summary UI is incomplete.')
    require('/static/student_summary.js?v=3.3.0' in html,'Student summary asset is not loaded.')
    compile(model,'model_data.py','exec')
    print('MEUCRONOGRAMA_STUDENT_SUMMARY_CHECK_OK: reader enabled, aluno exports and individual summary passed.',flush=True)

if __name__=='__main__':
    main()
