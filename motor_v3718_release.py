"""v3.7.18: melhorias do motor de estudos.

- Semana de domingo a sábado (planner.week e agenda).
- Revisões: rodízio ponderado entre disciplinas (maior dificuldade recebe mais vezes),
  tópicos com mais erros primeiro e cota da semana que varia com a disponibilidade.
- Peso das disciplinas sem contagem dupla de importância e dificuldade.
- Modo completar remove e reencaixa apenas os blocos que perderam a validade.
- Pendências agrupadas com a causa (sem horário livre, metas acima do tempo, revisões).
- Prioridade acadêmica restrita ao ano letivo ativo, quando definido.
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parent
MARK = '# === MOTOR V3.7.18 ==='


def patch(text, old, new, label):
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f'{label}: esperado 1 trecho, encontrado {count}.')
    return text.replace(old, new, 1)


def patch_planner():
    path = ROOT / 'planner.py'
    text = path.read_text(encoding='utf-8')
    if MARK in text:
        return
    text = patch(text, "def week(value): return add(value,-date(value).weekday())",
                 "def week(value): return add(value,-((date(value).weekday()+1)%7))  # domingo a sábado (v3.7.18)", 'week')
    text = patch(text, "    kept=[x for x in p['sessions']if start<=x['date']<=end and x['status']!='missed'];used=",
                 "    _qi_drop_conflicts(p,start,end,td,mins)\n"
                 "    kept=[x for x in p['sessions']if start<=x['date']<=end and x['status']!='missed'];used=", 'conflicts')
    text = patch(text, "    def place(task,duration):\n",
                 "    _qi_rev=dict(used=0,cap=10**9);_qi_deferred=[];_qi_failed=set()\n    def place(task,duration):\n", 'review state')
    text = patch(text,
                 "if d<task.get('earliest',td) or day_used[d]+duration>caps[d] or used+duration>s['weeklyGoal']:continue",
                 "if d<task.get('earliest',td) or day_used[d]+duration>caps[d] or used+duration>s['weeklyGoal'] or (task['kind']=='review' and _qi_rev['used']+duration>_qi_rev['cap']):continue",
                 'review cap check')
    text = patch(text, "day_used[d]+=duration;used+=duration;slots[d]=",
                 "day_used[d]+=duration;used+=duration;_qi_rev['used']+=duration*(task['kind']=='review');slots[d]=", 'review cap count')
    text = patch(text,
                 "    due.sort(key=lambda x:(subject_priority.get(x['subjectId'],3),(date(x['nextDue'])-date(td)).days,-x['difficulty']))\n",
                 "    due=_qi_review_order(due,subjects,subject_bonuses,td);_qi_rev['cap']=_qi_review_cap(s,caps,td,used)\n", 'review order')
    text = patch(text, "            placed=place(task,min(duration,240))\n",
                 "            placed=False if (_qi_deferred and _qi_deferred[-1][0].get('reviewCycleId')==cycle) else place(task,min(duration,240))\n",
                 'review chain')
    text = patch(text,
                 "            if not placed:pending.append(dict(title=title,minutes=duration,reason='Sem encaixe após a data-alvo, preservando pausas, disponibilidade e limites.'))\n",
                 "            if not placed:_qi_deferred.append((task,min(duration,240),dict(title=title,minutes=duration,reason='Sem encaixe após a data-alvo, preservando pausas, disponibilidade e limites.')))\n",
                 'review defer')
    text = patch(text,
                 "weights.append(max(1,sub['weeklyMin'])*(1+.10*(diff-3)+.06*(sub['importance']-3)+.15*urgency)*academic*declared)",
                 "weights.append(max(1,sub['weeklyMin'])*(1+.10*(diff-sub['difficulty'])+.15*urgency)*academic*declared)",
                 'weights')
    text = patch(text, "    p['sessions']+=created;p['sessions'].sort(key=lambda x:(x['date'],x['start']))\n",
                 "    _qi_rev['cap']=10**9;_qi_last={}\n"
                 "    for _qi_task,_qi_dur,_qi_pend in _qi_deferred:\n"
                 "        _qi_cycle=_qi_task.get('reviewCycleId')\n"
                 "        if _qi_cycle in _qi_failed:pending.append(_qi_pend);continue\n"
                 "        if _qi_cycle in _qi_last:_qi_task.update(earliest=_qi_last[_qi_cycle]['date'],notBeforeDate=_qi_last[_qi_cycle]['date'],notBeforeMin=_qi_last[_qi_cycle]['end']+br)\n"
                 "        _qi_placed=place(_qi_task,_qi_dur)\n"
                 "        if _qi_placed:_qi_last[_qi_cycle]=_qi_placed\n"
                 "        else:pending.append(_qi_pend);_qi_failed.add(_qi_cycle)\n"
                 "    p['sessions']+=created;p['sessions'].sort(key=lambda x:(x['date'],x['start']))\n",
                 'review second pass')
    text = patch(text, "    p['pending']=pending;p['planMeta']=",
                 "    p['pending']=_qi_compact_pending(pending,caps,s,subjects,td,0);p['planMeta']=", 'pending')
    text = text.rstrip('\n') + '\n' + (ROOT / 'release_assets' / 'planner_motor_v3718.py').read_text(encoding='utf-8')
    path.write_text(text, encoding='utf-8')


def patch_adaptive():
    path = ROOT / 'adaptive.py'
    text = path.read_text(encoding='utf-8')
    if MARK in text:
        return
    text = patch(text, "    cutoff = P.date(P.add(P.today(), -365))\n",
                 "    cutoff = P.date(P.add(P.today(), -365))\n    _qi_year = _qi_active_year(app, c, target)\n", 'year lookup')
    text = patch(text, "        if applied < cutoff:\n",
                 "        if applied < cutoff or (_qi_year and applied.year != _qi_year):\n", 'year filter')
    text = text.rstrip('\n') + '\n\n' + MARK + '\n' + (
        "def _qi_active_year(app, c, target):\n"
        "    \"\"\"Ano letivo ativo do aluno; None quando nunca foi definido.\"\"\"\n"
        "    try:\n"
        "        row = app.db.execute(c, 'SELECT active_year FROM hmay_academic_year WHERE user_id=?', (target,)).fetchone()\n"
        "    except Exception:\n"
        "        return None\n"
        "    try:\n"
        "        return int(row['active_year']) if row else None\n"
        "    except (KeyError, TypeError, ValueError):\n"
        "        return None\n")
    path.write_text(text, encoding='utf-8')


def patch_app_js():
    path = ROOT / 'static' / 'app.js'
    text = path.read_text(encoding='utf-8')
    if 'getDay());/*v3718*/' in text:
        return
    text = patch(text, "const weekOf=s=>add(s,-((date(s).getDay()+6)%7));", "const weekOf=s=>add(s,-date(s).getDay());/*v3718*/", 'weekOf')
    text = patch(text, "${days[i]} <small>", "${days[(i+6)%7]} <small>", 'agenda list label')
    text = patch(text, ">${days[i]}<br>", ">${days[(i+6)%7]}<br>", 'agenda grid label')
    path.write_text(text, encoding='utf-8')


def main():
    patch_planner()
    patch_adaptive()
    patch_app_js()
    print('MEUCRONOGRAMA_V3718_MOTOR_READY: Sunday weeks, weighted review rotation, availability-based review share, minimal conflict repair.', flush=True)


if __name__ == '__main__':
    main()
