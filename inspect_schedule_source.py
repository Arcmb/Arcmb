from pathlib import Path

ROOT=Path(__file__).resolve().parent
print('SCHEDULE_INSPECT_BEGIN',flush=True)
checks={
 'planner.py':[
  'def initial(', 'def validate(', 'def generate(', "weights.append", 'def fixed_on(', 'def week(', 'def feedback(', 'def evidence('
 ],
 'static/app.js':[
  'function subjectsView', "'add-subject'", "'edit-subject'", 'function weekView', 'function homeView', 'function reviewsView', 'function routineView', 'Disciplinas e metas', 'Quadro semanal'
 ],
 'static/adaptive.js':[
  'function mappingView', 'function adaptive', 'preview', 'profile', 'academicPriorityHtml'
 ],
 'adaptive.py':[
  'QUESTIONS=', 'def suggestions(', 'def handle(', 'academic_priority'
 ]
}
for rel,needles in checks.items():
 p=ROOT/rel
 if not p.exists():
  print('SCHEDULE_MISSING',rel,flush=True);continue
 text=p.read_text(encoding='utf-8')
 print(f'SCHEDULE_FILE {rel} len={len(text)}',flush=True)
 for needle in needles:
  pos=text.find(needle)
  if pos>=0:
   snippet=text[max(0,pos-2200):min(len(text),pos+9000)].replace('\n','\\n')
   print(f'SCHEDULE_HIT file={rel} needle={needle!r} pos={pos} :: {snippet}',flush=True)
print('SCHEDULE_INSPECT_END',flush=True)
