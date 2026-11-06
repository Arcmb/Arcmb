from pathlib import Path
import re

ROOT=Path(__file__).resolve().parent
print('TRI_BRAND_INSPECT_BEGIN',flush=True)
for rel in ('static/app.js','model_data.py','webapp.py','static/app.html','static/style.css'):
    p=ROOT/rel
    if not p.exists():
        print('TRI_BRAND_MISSING',rel,flush=True);continue
    text=p.read_text(encoding='utf-8')
    print(f'TRI_BRAND_FILE {rel} len={len(text)}',flush=True)
    needles=('Importar Ranking e notas TRI','Ler Ranking Geral','Ranking Geral','triRanking','tri-score','/api/tri','TRI LING','C1','logo','brand','sidebar','--primary','--accent',"class=\"logo\"")
    for needle in needles:
        pos=text.find(needle)
        if pos>=0:
            snippet=text[max(0,pos-2200):min(len(text),pos+7000)].replace('\n','\\n')
            print(f'TRI_BRAND_HIT file={rel} needle={needle!r} pos={pos} :: {snippet}',flush=True)
print('TRI_BRAND_INSPECT_END',flush=True)
