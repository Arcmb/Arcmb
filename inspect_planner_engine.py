from pathlib import Path

path = Path(__file__).resolve().parent / 'planner.py'
text = path.read_text(encoding='utf-8').splitlines()
needles = ('def generate', 'def tasks', 'def task', 'score=', 'weeklyMin', 'difficulty', 'importance', 'subjectId', 'bonus')
printed = set()
print('PLANNER_ENGINE_INSPECT_BEGIN', flush=True)
for index, line in enumerate(text):
    if any(needle in line for needle in needles):
        start = max(0, index - 8)
        end = min(len(text), index + 18)
        key = (start, end)
        if key in printed:
            continue
        printed.add(key)
        print(f'PLANNER_ENGINE_RANGE {start + 1}-{end}', flush=True)
        for pos in range(start, end):
            print(f'{pos + 1:04d}: {text[pos]}', flush=True)
print('PLANNER_ENGINE_INSPECT_END', flush=True)
