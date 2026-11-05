from pathlib import Path
ROOT=Path(__file__).resolve().parent
paths=[ROOT/'static'/'app.js', ROOT/'planner.py', ROOT/'webapp.py']
needles=('function reviewsView','reviewsView','nextDue','reviewIntervals','feedback','actualMin','kind===\'review\'','kind==\'review\'')
print('REVIEW_INSPECT_BEGIN', flush=True)
for path in paths:
    if not path.exists(): continue
    text=path.read_text(encoding='utf-8')
    for needle in needles:
        start=0
        n=0
        while True:
            pos=text.find(needle,start)
            if pos<0: break
            n+=1
            left=max(0,pos-1800); right=min(len(text),pos+4500)
            print(f'REVIEW_HIT file={path.name} needle={needle!r} pos={pos} #{n} :: '+text[left:right].replace('\n','\\n'), flush=True)
            start=pos+len(needle)
            if n>=5: break
print('REVIEW_INSPECT_END', flush=True)
