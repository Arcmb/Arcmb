"""Verify that the dedicated review page has a direct renderer bridge."""
from pathlib import Path

ROOT=Path(__file__).resolve().parent


def require(value,message):
    if not value:raise RuntimeError(message)


def main():
    html=(ROOT/'static'/'app.html').read_text(encoding='utf-8')
    guidance=(ROOT/'static'/'student_guidance.js').read_text(encoding='utf-8')
    page=(ROOT/'static'/'review_table_page.js').read_text(encoding='utf-8')
    require('/static/student_guidance.js?v=4.1.0' in html,'Review renderer cache key is missing.')
    require('/static/review_table_page.js?v=5.3.0' in html,'Review-table bridge cache key is missing.')
    require('globalThis.qiReviewOverviewHtml=qiReviewOverviewHtml' in guidance,'Consolidated review renderer is not exposed.')
    require('globalThis.qiReviewOverviewMonth' in guidance,'Review month navigator is not exposed.')
    for marker in ('REVIEW TABLE RUNTIME BRIDGE V1','qiReviewOverviewHtml','extractExistingTables','reviewTablesHtml','Tabela de revisões'):
        require(marker in page,'Missing runtime bridge marker: '+marker)
    require('A tabela mensal não pôde ser carregada' not in page,'Old calendar fallback remains in the dedicated page.')
    require('O histórico não pôde ser carregado' not in page,'Old history fallback remains in the dedicated page.')
    print('MEUCRONOGRAMA_REVIEW_TABLE_BRIDGE_CHECK_OK: direct consolidated rendering, month navigation and legacy extraction passed.',flush=True)


if __name__=='__main__':main()
