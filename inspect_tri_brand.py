from pathlib import Path
import re

ROOT=Path(__file__).resolve().parent
print('TRI_BRAND_INSPECT_BEGIN',flush=True)
for rel in ('static/tri_scores.js','model_data.py','static/app.html','static/login.html','static/setup.html','static/style.css','static/icon.svg','static/manifest.webmanifest'):
    p=ROOT/rel
    if not p.exists():
        print('TRI_BRAND_MISSING',rel,flush=True);continue
    text=p.read_text(encoding='utf-8')
    print(f'TRI_BRAND_FILE {rel} len={len(text)}',flush=True)
    if rel=='model_data.py':
        defs=re.findall(r'^def (_tri_[A-Za-z0-9_]+)\(',text,re.M)
        print('TRI_BACKEND_DEFS :: '+','.join(defs),flush=True)
        needles=('def _tri_detect_table','def _tri_extract','def _tri_row','def _tri_inspect','def _tri_preview','def _tri_confirm','scores =','redaction','tri-inspect','tri-preview','tri-confirm')
    elif rel=='static/tri_scores.js':
        needles=('function triImportStatus','function triImportPreviewHtml','function triImportCard','acts[\'tri-import-confirm\']','function triStudentPanel')
    else:
        needles=('class="logo"','theme-color',':root{','aside{','login-body','manifest')
    for needle in needles:
        pos=text.find(needle)
        if pos>=0:
            snippet=text[max(0,pos-1300):min(len(text),pos+6000)].replace('\n','\\n')
            print(f'TRI_BRAND_HIT file={rel} needle={needle!r} pos={pos} :: {snippet}',flush=True)
print('TRI_BRAND_INSPECT_END',flush=True)
