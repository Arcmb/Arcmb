"""Install simple per-tab tutorials and a final Guia de Uso tab."""
from pathlib import Path
import re

ROOT=Path(__file__).resolve().parent
STATIC=ROOT/'static'
ASSETS=ROOT/'release_assets'
CSS_MARK='/* === GUIA DE USO E TUTORIAIS V1 === */'
CSS=r'''
/* === GUIA DE USO E TUTORIAIS V1 === */
.use-guide-overlay{position:fixed;inset:0;z-index:9999;display:none;align-items:center;justify-content:center;padding:18px;background:rgba(49,24,30,.48);backdrop-filter:blur(3px)}
.use-guide-overlay.open{display:flex}.use-guide-dialog{width:min(520px,100%);background:#fff;border:1px solid var(--line);border-radius:20px;box-shadow:0 24px 70px rgba(71,25,35,.25);padding:22px}.use-guide-top{display:flex;justify-content:space-between;align-items:center;gap:12px}.use-guide-kicker{font-size:11px;font-weight:800;letter-spacing:.12em;color:var(--primary)}.use-guide-close{border:0;background:#fae9ec;color:#8f3545;width:34px;height:34px;border-radius:10px;font-size:22px}.use-guide-dialog h2{margin:.35rem 0 1rem}.use-guide-text{font-size:1.05rem;line-height:1.65;min-height:82px}.use-guide-progress{display:flex;gap:6px;margin-bottom:14px}.use-guide-progress span{height:6px;flex:1;border-radius:999px;background:#eee1e4}.use-guide-progress span.active,.use-guide-progress span.done{background:var(--primary)}.use-guide-never{display:flex;gap:8px;align-items:center;margin:12px 0;color:var(--muted);font-size:.9rem}.use-guide-actions{display:flex;justify-content:space-between;gap:10px;align-items:center;flex-wrap:wrap}.use-guide-actions>div{display:flex;gap:8px}.use-guide-page{margin-top:1rem}.use-guide-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:12px}.use-guide-card{border:1px solid var(--line);border-radius:15px;padding:14px;background:#fff;display:flex;justify-content:space-between;gap:14px;align-items:center}.use-guide-card h3{margin:0 0 5px}.use-guide-card p{margin:0;color:var(--muted);font-size:.88rem;line-height:1.45}.use-guide-context{white-space:nowrap}.guide-use-nav-button span:first-child{display:inline-grid;place-items:center;width:20px;height:20px;border-radius:50%;border:1px solid currentColor;font-weight:900}.account-search-control{position:relative}.account-search-results{display:none;position:absolute;left:0;right:0;top:calc(100% + 5px);z-index:1200;max-height:280px;overflow:auto;background:#fff;border:1px solid var(--line);border-radius:12px;box-shadow:0 14px 34px rgba(72,28,38,.16);padding:5px}.account-search-results.open{display:grid}.account-search-result{border:0;background:#fff;color:var(--ink);text-align:left;padding:9px 10px;border-radius:8px;cursor:pointer}.account-search-result:hover,.account-search-result:focus{background:#fae9ec;outline:0}
@media(max-width:680px){.use-guide-grid{grid-template-columns:1fr}.use-guide-actions{align-items:stretch}.use-guide-actions>div{margin-left:auto}.use-guide-card{align-items:flex-start;flex-direction:column}.use-guide-card button{width:100%}}
'''

def main():
    (STATIC/'use_guide.js').write_text((ASSETS/'use_guide.js').read_text(encoding='utf-8'),encoding='utf-8')
    css_path=STATIC/'style.css';css=css_path.read_text(encoding='utf-8')
    if CSS_MARK not in css:css=css.rstrip()+'\n\n'+CSS.strip()+'\n'
    css_path.write_text(css,encoding='utf-8')
    html_path=STATIC/'app.html';html=html_path.read_text(encoding='utf-8')
    html=re.sub(r'/static/responsive_ui_refinement\.js\?v=[^"\']+','/static/responsive_ui_refinement.js?v=5.3.0',html)
    if '/static/use_guide.js' not in html:html=html.replace('</body>','<script src="/static/use_guide.js?v=1.0.0" defer></script>\n</body>',1)
    html_path.write_text(html,encoding='utf-8')
    web=ROOT/'webapp.py';text=web.read_text(encoding='utf-8')
    anchor="'responsive_ui_refinement.js':'application/javascript; charset=utf-8'"
    mapping="'use_guide.js':'application/javascript; charset=utf-8'"
    if mapping not in text:
        if anchor not in text:raise RuntimeError('Responsive asset MIME anchor not found.')
        text=text.replace(anchor,anchor+','+mapping,1)
    web.write_text(text,encoding='utf-8')
    print('MEUCRONOGRAMA_USE_GUIDE_READY: per-tab tutorials, contextual help and final Guia de Uso installed.',flush=True)

if __name__=='__main__':main()
