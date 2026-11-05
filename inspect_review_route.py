from pathlib import Path

ROOT=Path(__file__).resolve().parent
for name in ('webapp.py','model_data.py'):
    path=ROOT/name
    text=path.read_text(encoding='utf-8')
    print(f'REVIEW_ROUTE_INSPECT {name} len={len(text)}',flush=True)
    needles=('model_data','PATH_INFO','def __call__','def handle','review-errors','/api/model-data')
    for needle in needles:
        start=0
        hits=0
        while True:
            pos=text.find(needle,start)
            if pos<0 or hits>=12: break
            a=max(0,pos-450);b=min(len(text),pos+900)
            print(f'REVIEW_ROUTE_HIT {name} {needle!r} pos={pos}\n{text[a:b]}\n---',flush=True)
            start=pos+len(needle);hits+=1
