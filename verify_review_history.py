"""Verify the global review history interface before serving traffic."""
from pathlib import Path

ROOT=Path(__file__).resolve().parent


def require(value,message):
    if not value:raise RuntimeError(message)


def main():
    html=(ROOT/'static'/'app.html').read_text(encoding='utf-8')
    js=(ROOT/'static'/'review_history.js').read_text(encoding='utf-8')
    css=(ROOT/'static'/'style.css').read_text(encoding='utf-8')
    require('/static/review_history.js?v=5.1.0' in html,'Review-history asset is not loaded.')
    require(html.index('/static/study_schedule.js')<html.index('/static/review_history.js'),'Review history must load after study schedule.')
    require('GLOBAL REVIEW HISTORY V1' in js,'Review-history marker is missing.')
    require('Histórico e próximas revisões' in js and 'review-history-table' in js,'Global review table is missing.')
    require('Última revisão' in js and 'Próxima revisão' in js and 'Próximas projeções' in js,'Review date columns are missing.')
    require('reviewHistoryFeedback' in js and 'reviewHistoryProjectedDates' in js,'History/projection calculations are missing.')
    require("acts['review-history-export']" in js and "join(';')" in js,'Filtered CSV export is missing.')
    require('GLOBAL REVIEW HISTORY V1' in css and '.review-history-filters' in css,'Review-history styles are missing.')
    print('MEUCRONOGRAMA_REVIEW_HISTORY_CHECK_OK: global history, last/next dates, projections, filters and CSV export passed.',flush=True)


if __name__=='__main__':main()
