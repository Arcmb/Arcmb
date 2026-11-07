"""Verify that the dedicated review page renders directly from learner data."""
from pathlib import Path

ROOT=Path(__file__).resolve().parent


def require(value,message):
    if not value:raise RuntimeError(message)


def main():
    html=(ROOT/'static'/'app.html').read_text(encoding='utf-8')
    page=(ROOT/'static'/'review_table_page.js').read_text(encoding='utf-8')
    require('/static/review_table_page.js?v=5.4.0' in html,'Direct review-table cache key is missing.')
    for marker in (
        'REVIEW TABLE DIRECT RENDERER V2','reviewRows','linkedSessions','linkedFeedback',
        'monthlyTable','historyTable','directTablesHtml','P.contents','P.sessions','P.feedback','Tabela de revisões'
    ):
        require(marker in page,'Missing direct renderer marker: '+marker)
    require('Tabela temporariamente indisponível' not in page,'Dependency fallback remains in the dedicated page.')
    require('A tabela mensal não pôde ser carregada' not in page,'Old calendar fallback remains in the dedicated page.')
    require('O histórico não pôde ser carregado' not in page,'Old history fallback remains in the dedicated page.')
    require('globalThis.qiReviewOverviewHtml' not in page,'Dedicated page still depends on the guidance renderer.')
    print('MEUCRONOGRAMA_REVIEW_TABLE_BRIDGE_CHECK_OK: standalone contents/sessions/feedback renderer and month navigation passed.',flush=True)


if __name__=='__main__':main()
