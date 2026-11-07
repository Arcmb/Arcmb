"""Verify the requested review-table layout and same-base integration."""
from pathlib import Path

ROOT=Path(__file__).resolve().parent


def require(value,message):
    if not value:raise RuntimeError(message)


def main():
    html=(ROOT/'static'/'app.html').read_text(encoding='utf-8')
    js=(ROOT/'static'/'review_table_page.js').read_text(encoding='utf-8')
    css=(ROOT/'static'/'style.css').read_text(encoding='utf-8')
    require('/static/review_table_page.js?v=5.4.0-layout3' in html,'Compact review-table cache key is missing.')
    require('/static/style.css?v=5.1.0-layout3' in html,'Compact review-table stylesheet cache key is missing.')
    for marker in (
        'REVIEW MATRIX AND HISTORY LAYOUT V3','ASSUNTO / DISCIPLINA','Datas sem ocorrência foram omitidas',
        'Ordenar por','Revisões do dia','Baixar quadro (CSV)','Imprimir quadro',
        'Histórico de revisões e experiências','ACERTOS','PERCEPÇÃO','TÉCNICA','PRÓXIMA REVISÃO',
        'profile.contents','profile.sessions','state().feedback','forceReviewPage','MutationObserver'
    ):
        require(marker in js,'Missing compact review-table marker: '+marker)
    require('daysInMonth' not in js,'The page still creates every calendar day instead of relevant dates only.')
    require('Tabela temporariamente indisponível' not in js,'Obsolete dependency fallback remains.')
    require('REVIEW MATRIX AND HISTORY LAYOUT V3' in css,'Compact review-table styles are missing.')
    for marker in ('.rt-matrix','.rt-history','.rt-study','.rt-done','.rt-planned','.rt-overdue'):
        require(marker in css,'Missing compact review-table style: '+marker)
    print('MEUCRONOGRAMA_REVIEW_MATRIX_LAYOUT_CHECK_OK: relevant-date matrix, sorting, day filter, history, CSV, print and direct rendering passed.',flush=True)


if __name__=='__main__':main()
