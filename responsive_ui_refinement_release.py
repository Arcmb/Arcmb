"""Install searchable student selection, responsive review tables and Qi logo delivery."""
from pathlib import Path
import re

ROOT=Path(__file__).resolve().parent
CSS_MARK='/* === RESPONSIVE UI SEARCH AND QI LOGO V1 === */'


def patch_static():
    static=ROOT/'static'
    assets=ROOT/'release_assets'
    (static/'responsive_ui_refinement.js').write_text((assets/'responsive_ui_refinement.js').read_text(encoding='utf-8'),encoding='utf-8')
    css_path=static/'style.css'
    css=css_path.read_text(encoding='utf-8')
    extra=(assets/'responsive_ui_refinement.css').read_text(encoding='utf-8')
    if CSS_MARK not in css:css=css.rstrip()+'\n\n'+extra.rstrip()+'\n'
    css_path.write_text(css,encoding='utf-8')
    for filename in ('app.html','login.html','setup.html'):
        path=static/filename
        if not path.exists():continue
        html=path.read_text(encoding='utf-8')
        html=re.sub(r'/static/qi-logo\.svg(?:\?v=[^"\']+)?','/static/qi-logo.svg?v=5.2.0',html)
        html=re.sub(r'/static/style\.css(?:\?v=[^"\']+)?','/static/style.css?v=5.1.0',html)
        if filename=='app.html':
            html=re.sub(r'<img\s+src="/static/qi-logo\.svg\?v=5\.2\.0"\s+alt="Qi Vestibulares"\s*>','<img src="/static/qi-logo.svg?v=5.2.0" alt="Qi Vestibulares" onerror="this.onerror=null;this.src=\'/static/icon.svg?v=5.2.0\'">',html)
            if '/static/responsive_ui_refinement.js' not in html:
                html=html.replace('</body>','<script src="/static/responsive_ui_refinement.js?v=5.2.1" defer></script>\n</body>',1)
        path.write_text(html,encoding='utf-8')


def patch_server():
    path=ROOT/'webapp.py'
    text=path.read_text(encoding='utf-8')
    anchor="'discipline_colors.js':'application/javascript; charset=utf-8'"
    if anchor not in text:anchor="'review_table_page.js':'application/javascript; charset=utf-8'"
    if anchor not in text:raise RuntimeError('Static asset anchor not found in webapp.py.')
    for mapping in (
        "'responsive_ui_refinement.js':'application/javascript; charset=utf-8'",
        "'qi-logo.svg':'image/svg+xml; charset=utf-8'",
        "'model_data.js':'application/javascript; charset=utf-8'",
    ):
        if mapping not in text:
            text=text.replace(anchor,anchor+','+mapping,1)
            anchor=mapping
    path.write_text(text,encoding='utf-8')


def main():
    patch_static();patch_server()
    print('MEUCRONOGRAMA_RESPONSIVE_UI_READY: student search, responsive review calendar and Qi logo delivery prepared.',flush=True)


if __name__=='__main__':main()
