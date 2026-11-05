from pathlib import Path
ROOT=Path(__file__).resolve().parent
paths=[ROOT/'static'/'app.js', ROOT/'planner.py']
needles=(
 "function reviewsView","feedback-content","Registrar revisão","function feedback",
 "actualMin","confidence","help","modalForm","feedbackForm","feedback-form","reason"
)
print('REVIEW_INSPECT_BEGIN', flush=True)
for path in paths:
    if not path.exists(): continue
    text=path.read_text(encoding='utf-8')
    for needle in needles:
        pos=text.find(needle)
        if pos<0: continue
        left=max(0,pos-1200); right=min(len(text),pos+6500)
        print(f'REVIEW_HIT file={path.name} needle={needle!r} pos={pos} :: '+text[left:right].replace('\n','\\n'), flush=True)
print('REVIEW_INSPECT_END', flush=True)
