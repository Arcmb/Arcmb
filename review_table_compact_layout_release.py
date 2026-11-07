"""Install the compact review matrix requested for Meu Cronograma.

The page contains only:
- one matrix with subject/discipline in rows and relevant dates in columns;
- ordering and date/discipline filters;
- CSV and print actions;
- one review-history table fed by the same P.contents/P.sessions/P.feedback base.

It also adds a direct click/mutation fallback so the page is rendered even if an
older render wrapper falls through to the home screen.
"""
from pathlib import Path
import re

ROOT=Path(__file__).resolve().parent
CSS_MARK='/* === REVIEW MATRIX AND HISTORY LAYOUT V3 === */'


def main():
    static=ROOT/'static'
    assets=ROOT/'release_assets'
    js=(assets/'review_table_layout_v3.js').read_text(encoding='utf-8')
    css_extra=(assets/'review_table_layout_v3.css').read_text(encoding='utf-8')
    (static/'review_table_page.js').write_text(js,encoding='utf-8')

    css_path=static/'style.css'
    css=css_path.read_text(encoding='utf-8')
    if CSS_MARK not in css:
        css=css.rstrip()+'\n\n'+css_extra.rstrip()+'\n'
    css_path.write_text(css,encoding='utf-8')

    html_path=static/'app.html'
    html=html_path.read_text(encoding='utf-8')
    html=re.sub(r'/static/review_table_page\.js\?v=[^"\']+','/static/review_table_page.js?v=5.4.0-layout3',html)
    html=re.sub(r'/static/style\.css\?v=[^"\']+','/static/style.css?v=5.1.0-layout3',html)
    html_path.write_text(html,encoding='utf-8')
    print('MEUCRONOGRAMA_REVIEW_MATRIX_LAYOUT_READY: relevant-date matrix, filters, history, CSV and print installed.',flush=True)


if __name__=='__main__':main()
