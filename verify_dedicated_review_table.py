"""Verify the dedicated review-table page and final Qi branding."""
from pathlib import Path

ROOT=Path(__file__).resolve().parent


def require(condition,message):
    if not condition:raise RuntimeError(message)


def main():
    html=(ROOT/'static'/'app.html').read_text(encoding='utf-8')
    js=(ROOT/'static'/'review_table_page.js').read_text(encoding='utf-8')
    css=(ROOT/'static'/'style.css').read_text(encoding='utf-8')
    logo=(ROOT/'static'/'qi-logo.svg').read_text(encoding='utf-8')
    webapp=(ROOT/'webapp.py').read_text(encoding='utf-8')

    require('/static/review_table_page.js?v=5.4.0' in html,'Standalone review-table asset is not loaded last.')
    require('/static/qi-logo.svg?v=5.2.0' in html,'Final Qi logo cache key is missing.')
    require("['review-table','Tabela de revisões']" in js,'Dedicated navigation entry is missing.')
    require("view==='review-table'" in js and 'reviewTableView' in js,'Dedicated review-table rendering is missing.')
    for marker in ('REVIEW TABLE DIRECT RENDERER V2','reviewRows','linkedSessions','monthlyTable','historyTable','directTablesHtml'):
        require(marker in js,'Standalone review renderer is missing: '+marker)
    require('.review-calendar-card,.review-history-global,.qi-review-overview' in js,'Duplicate tables are not removed from Minhas revisões.')
    require('Tabela temporariamente indisponível' not in js,'Old dependency fallback remains in the page.')
    require('DEDICATED REVIEW TABLE PAGE V1' in css and 'background:#fff!important' in css,'Final white background and review-page CSS are missing.')
    require('<circle' in logo and '#e00613' in logo and 'stroke="#fff"' in logo,'Qi logo does not match the required red-circle/white-symbol identity.')
    require("'review_table_page.js':'application/javascript; charset=utf-8'" in webapp,'Dedicated review-table asset is not served.')
    require("'qi-logo.svg':'image/svg+xml; charset=utf-8'" in webapp,'Qi logo asset is not served.')
    print('MEUCRONOGRAMA_DEDICATED_REVIEW_TABLE_CHECK_OK: dedicated tab, standalone monthly/history rendering, no duplicates and Qi logo passed.',flush=True)

if __name__=='__main__':main()
