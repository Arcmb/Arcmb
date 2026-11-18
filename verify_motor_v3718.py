"""Verificação da v3.7.18 sem banco: motor em perfis sintéticos na memória."""
from pathlib import Path
import copy, datetime as dt, sys

ROOT = Path(__file__).resolve().parent


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def main():
    import planner as P
    require('# === MOTOR V3.7.18 ===' in (ROOT / 'planner.py').read_text(encoding='utf-8'), 'Motor patch missing.')
    require('getDay());/*v3718*/' in (ROOT / 'static' / 'app.js').read_text(encoding='utf-8'), 'Sunday week UI patch missing.')
    require(P.date(P.week('2026-11-25')).weekday() == 6 and P.week('2026-11-22') == '2026-11-22', 'Week must start on Sunday.')
    sunday = P.week(P.add(P.today(), 7))
    now = dt.datetime.combine(P.date(sunday), dt.time(6, 0), tzinfo=P.TZ)
    p = P.default_profile('Verificação motor')
    p['availability'] = [dict(day=i, status='available', ranges=[dict(start='19:00', end='21:00')]) for i in range(7)]
    p['subjects'] = [dict(id=f's{i}', name=n, kind='study', action='Estudar e praticar', weeklyMin=90, difficulty=3, importance=3,
                          priority=2, priorityManual=True, examDate='', active=True) for i, n in enumerate(('Química', 'Matemática', 'Física'))]
    for i in range(3):
        for j in range(6):
            p['contents'].append(dict(id=f'c{i}{j}', subjectId=f's{i}', title=f'T{j}', topic='', notes='', material='', status='studied',
                                      paused=False, studyMinutes=0, reviewMinutes=20, difficulty=3, studiedOn=P.add(sunday, -30),
                                      studiedTime='12:00', nextDue=P.add(sunday, -5), stage=0, errorCount=1))
    P.validate(p)
    out = P.generate(copy.deepcopy(p), sunday, current=now)
    reviewed = {s['subjectId'] for s in out['sessions'] if s['kind'] == 'review'}
    require(reviewed == {'s0', 's1', 's2'}, 'Reviews must rotate across all disciplines.')
    require(len(out['pending']) <= 4, 'Pending items must be grouped.')
    blocked = copy.deepcopy(out)
    wed = P.add(sunday, 3)
    blocked['exceptions'].append(dict(id='blk', date=wed, start='19:00', end='21:00', title='Bloqueio'))
    before = {s['id'] for s in blocked['sessions']}
    on_wed = {s['id'] for s in blocked['sessions'] if s['date'] == wed and s['status'] == 'planned'}
    fixed = P.generate(blocked, sunday, current=now, mode='fill')
    require(not any(s['date'] == wed and s['status'] == 'planned' for s in fixed['sessions']), 'Fill mode must remove conflicting blocks.')
    kept = before & {s['id'] for s in fixed['sessions']}
    require(kept == before - on_wed, 'Fill mode must keep every still-valid block in place.')
    print('MEUCRONOGRAMA_V3718_MOTOR_CHECK_OK: Sunday week, review rotation, grouped pending and minimal conflict repair passed.', flush=True)


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        print('MEUCRONOGRAMA_V3718_MOTOR_CHECK_FAILED:', exc, flush=True)
        sys.exit(1)
