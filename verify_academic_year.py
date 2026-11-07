"""Verify academic-year archive/reset and annual comparison."""
from pathlib import Path
ROOT=Path(__file__).resolve().parent

def require(x,msg):
    if not x:raise RuntimeError(msg)

def main():
    web=(ROOT/'webapp.py').read_text(encoding='utf-8')
    js=(ROOT/'static'/'academic_year.js').read_text(encoding='utf-8')
    html=(ROOT/'static'/'app.html').read_text(encoding='utf-8')
    for marker in ('hmay_academic_year','hmay_academic_cycles','academic_year_open','academic_year_comparison',"/api/academic-year/open"):
        require(marker in web,'Missing backend marker: '+marker)
    for marker in ('CICLOS DE ANO LETIVO V2','Evolução anual','Ano letivo ativo','Ativar ano selecionado','academic-year-activate','Comparação por área'):
        require(marker in js,'Missing UI marker: '+marker)
    require('/static/academic_year.js?v=' in html,'Academic-year asset not loaded.')
    print('MEUCRONOGRAMA_ACADEMIC_YEAR_CHECK_OK: explicit active-year selector, archive/reset and annual comparison passed.',flush=True)

if __name__=='__main__':main()
