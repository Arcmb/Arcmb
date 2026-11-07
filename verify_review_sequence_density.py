"""Verify chronological review numbering and compact matrix density."""
from pathlib import Path

ROOT=Path(__file__).resolve().parent


def require(value,message):
    if not value:raise RuntimeError(message)


def main():
    html=(ROOT/'static'/'app.html').read_text(encoding='utf-8')
    js=(ROOT/'static'/'review_table_page.js').read_text(encoding='utf-8')
    css=(ROOT/'static'/'style.css').read_text(encoding='utf-8')
    require('/static/review_table_page.js?v=5.4.0-layout4' in html,'Chronological review cache key is missing.')
    require('/static/style.css?v=5.1.0-layout4' in html,'Compact density stylesheet cache key is missing.')
    for marker in (
        'CHRONOLOGICAL REVIEW ORDER V4','reviewByDate','orderedReviews',
        'currentFeedback','currentSessions',"label:(index+1)+'ª revisão'",
        'startIndex=Math.max(stage+1,baseDates.length)'
    ):
        require(marker in js,'Missing chronological review marker: '+marker)
    require("completed.forEach(item=>{ordinal+=1" not in js,'Review ordinals are still assigned before chronological consolidation.')
    require('cycleGroups.sort' not in js,'Planned sessions are still numbered independently of due dates.')
    require('REVIEW MATRIX COMPACT DENSITY V4' in css,'Compact-density styles are missing.')
    for marker in ('min-height:38px!important','height:48px!important','padding:6px 7px!important','font-size:11px!important'):
        require(marker in css,'Missing compact-density marker: '+marker)
    print('MEUCRONOGRAMA_REVIEW_SEQUENCE_DENSITY_CHECK_OK: chronological numbering and compact row density passed.',flush=True)


if __name__=='__main__':main()
