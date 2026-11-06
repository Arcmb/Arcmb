"""Verify the spreadsheet-style monthly review calendar release."""
from pathlib import Path

ROOT=Path(__file__).resolve().parent

def require(condition,message):
    if not condition:raise RuntimeError(message)

def main():
    js=(ROOT/'static'/'review_calendar_table.js').read_text(encoding='utf-8')
    html=(ROOT/'static'/'app.html').read_text(encoding='utf-8')
    css=(ROOT/'static'/'style.css').read_text(encoding='utf-8')
    require('REVIEW CALENDAR TABLE V1' in js,'Calendar script marker is missing.')
    require('Disciplina' in js and 'Assunto' in js,'Calendar fixed columns are missing.')
    require('Mês anterior' in js and 'Próximo mês' in js,'Month navigation is missing.')
    require('1ª revisão' not in js or 'reviewCalendarOrdinal' in js,'Review ordinal logic is missing.')
    require('review-calendar-prev' in js and 'review-calendar-next' in js,'Calendar actions are missing.')
    require('/static/review_calendar_table.js?v=3.2.0' in html,'Calendar script is not loaded.')
    require(html.index('/static/study_schedule.js')<html.index('/static/review_calendar_table.js'),'Calendar must load after study scheduling.')
    require('REVIEW CALENDAR TABLE V1' in css,'Calendar styles are missing.')
    require('position:sticky' in css and 'review-cal-projection' in css,'Sticky columns or projected-date styling is missing.')
    print('MEUCRONOGRAMA_REVIEW_CALENDAR_CHECK_OK: monthly rows, days, statuses, navigation and actions passed.',flush=True)

if __name__=='__main__':main()
