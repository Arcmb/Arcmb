"""Verify the use guide, simple tutorials and single student selector."""
from pathlib import Path
ROOT=Path(__file__).resolve().parent

def require(value,message):
    if not value:raise RuntimeError(message)

def main():
    js=(ROOT/'static'/'use_guide.js').read_text(encoding='utf-8')
    app=(ROOT/'static'/'app.html').read_text(encoding='utf-8')
    responsive=(ROOT/'static'/'responsive_ui_refinement.js').read_text(encoding='utf-8')
    css=(ROOT/'static'/'style.css').read_text(encoding='utf-8')
    for marker in ('Guia de Uso','Pular tutorial','Não exibir novamente','? Ajuda','Próxima','Anterior'):
        require(marker in js,'Missing tutorial marker: '+marker)
    require('/static/use_guide.js?v=' in app,'Use-guide asset is not loaded.')
    require("wrap.style.display='none'" in responsive,'Native student selector was not hidden.')
    require('account-search-results' in responsive and 'Digite o nome do aluno' in responsive,'Single autocomplete student search is missing.')
    require('GUIA DE USO E TUTORIAIS V1' in css,'Use-guide styles are missing.')
    print('MEUCRONOGRAMA_USE_GUIDE_CHECK_OK: tutorials, guide tab and single student autocomplete passed.',flush=True)

if __name__=='__main__':main()
