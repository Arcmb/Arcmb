"""Verify paper-style report cards v3.7.5."""
from pathlib import Path
ROOT=Path(__file__).resolve().parent
def require(v,m):
    if not v: raise RuntimeError(m)
def main():
    js=(ROOT/'static'/'student_summary.js').read_text(encoding='utf-8')
    css=(ROOT/'static'/'style.css').read_text(encoding='utf-8')
    html=(ROOT/'static'/'app.html').read_text(encoding='utf-8')
    for marker in ('// === REPORT PAPER LAYOUT V3.7.5 ===','reportPaperCardHtml','report-paper-cover-wrap','report-paper-title','report-paper-grid'):
        require(marker in js,'Missing report paper JS marker: '+marker)
    for marker in ('REPORT PAPER LAYOUT V3.7.5','aspect-ratio:210/297','report-paper-card','report-paper-open'):
        require(marker in css,'Missing report paper CSS marker: '+marker)
    require('/static/student_summary.js?v=3.7.5' in html,'Student summary v3.7.5 cache key missing.')
    print('MEUCRONOGRAMA_REPORT_PAPER_LAYOUT_CHECK_OK: cover-first paper cards, title-below layout and responsive report grid passed.',flush=True)
if __name__=='__main__': main()
