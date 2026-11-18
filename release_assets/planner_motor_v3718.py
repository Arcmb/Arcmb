
# === MOTOR V3.7.18 ===
# Decisões do responsável (18/11/2026):
# - Semana de domingo a sábado.
# - As revisões ocupam uma fração da semana que varia com a disponibilidade do aluno.
# - Prioridade às disciplinas com maior dificuldade; tópicos com mais erros primeiro.
# - Questão em branco conta como erro (comportamento já existente da sincronização).

_QI_DECLARED = {1: 1.65, 2: 1.35, 3: 1.0, 4: .78, 5: .60}


def _qi_review_share(weekly_capacity):
    """Fração máxima da semana para revisões na primeira rodada.

    Pouco tempo livre: as revisões de erros ocupam a maior parte (70%).
    Mais tempo livre: sobra mais espaço para estudo novo (60% e 50%).
    O que não for usado pelo estudo novo volta para as revisões na segunda rodada.
    """
    if weekly_capacity <= 300:
        return .70
    if weekly_capacity <= 600:
        return .60
    return .50


def _qi_review_cap(s, caps, td, used):
    future = sum(v for d, v in caps.items() if d >= td)
    weekly = max(0, min(future, s['weeklyGoal'] - used))
    return int(weekly * _qi_review_share(weekly))


def _qi_subject_weight(sub, subject_bonuses):
    declared = _QI_DECLARED.get(int(sub.get('priority', 3) or 3), 1.0)
    academic = max(1.0, min(1.25, float((subject_bonuses or {}).get(sub['id'], 1.0))))
    return declared * academic


def _qi_review_order(due, subjects, subject_bonuses, td):
    """Rodízio ponderado entre disciplinas: as de maior dificuldade recebem mais vezes.

    Dentro de cada disciplina: mais erros primeiro, depois a data-alvo mais antiga
    e a maior dificuldade. Sem empate pela ordem de cadastro das disciplinas.
    """
    by_subject = {}
    for c in due:
        by_subject.setdefault(c['subjectId'], []).append(c)
    for items in by_subject.values():
        items.sort(key=lambda x: (-int(x.get('errorCount', 0) or 0), x.get('nextDue', ''), -int(x.get('difficulty', 3) or 3), x.get('title', '')))
    subject_map = {x['id']: x for x in subjects}
    weights = {k: _qi_subject_weight(subject_map[k], subject_bonuses) if k in subject_map else 1.0 for k in by_subject}
    names = {k: str(subject_map.get(k, {}).get('name', '')) for k in by_subject}
    taken = {k: 0 for k in by_subject}
    ordered = []
    while any(by_subject.values()):
        key = min((k for k, v in by_subject.items() if v), key=lambda k: ((taken[k] + 1) / weights[k], -weights[k], names[k]))
        ordered.append(by_subject[key].pop(0))
        taken[key] += 1
    return ordered


def _qi_drop_conflicts(p, start, end, td, mins):
    """Remove apenas blocos planejados, não fixados e futuros que perderam a validade.

    Um bloco é inválido quando saiu da disponibilidade (bloqueio, compromisso, sono)
    ou passou a sobrepor outro bloco que permanece. Os demais ficam onde estão.
    """
    br = p['settings']['breakMin']
    week_items = [x for x in p['sessions'] if start <= x['date'] <= end and x['status'] != 'missed']
    movable = lambda x: x['status'] == 'planned' and not x.get('locked') and (x['date'] > td or x['date'] == td and x['start'] >= mins)
    keep = [x for x in week_items if not movable(x)]
    invalid = set()
    free_cache = {}
    for x in sorted([x for x in week_items if movable(x)], key=lambda x: (x['date'], x['start'])):
        if x['date'] not in free_cache:
            free_cache[x['date']] = free(p, x['date'])
        inside = any(a <= x['start'] < x['end'] <= b for a, b in free_cache[x['date']])
        clash = any(y['date'] == x['date'] and x['start'] < y['end'] + br and y['start'] - br < x['end'] for y in keep)
        if inside and not clash:
            keep.append(x)
        else:
            invalid.add(x['id'])
    if invalid:
        p['sessions'] = [x for x in p['sessions'] if x['id'] not in invalid]
    return invalid


def _qi_compact_pending(pending, caps, s, subjects, td, review_minutes):
    """Agrupa pendências repetitivas em mensagens que explicam a causa."""
    capacity = min(sum(v for d, v in caps.items() if d >= td), s['weeklyGoal'])
    out = []
    if capacity <= 0:
        out.append(dict(title='Horários livres', minutes=0, reason='Cadastre seus horários livres em Rotina e horários. Sem disponibilidade, o cronograma não tem onde encaixar estudos e revisões.'))
    reviews = [x for x in pending if str(x.get('reason', '')).startswith('Sem encaixe')]
    stale = [x for x in pending if str(x.get('reason', '')).startswith('Revisão anterior sem registro')]
    goals = [x for x in pending if str(x.get('reason', '')).startswith('Parte da meta')]
    other = [x for x in pending if x not in reviews and x not in stale and x not in goals]
    out.extend(other)
    if reviews and capacity > 0:
        out.append(dict(title=f'{len(reviews)} revisão(ões) aguardando horário', minutes=sum(int(x.get('minutes', 0) or 0) for x in reviews),
                        reason='A semana não comporta todas as revisões. As de disciplinas com maior dificuldade e com mais erros foram encaixadas primeiro; as demais entram nas próximas semanas.'))
    if stale:
        out.append(dict(title=f'{len(stale)} revisão(ões) passada(s) sem registro', minutes=sum(int(x.get('minutes', 0) or 0) for x in stale),
                        reason='Registre se foram feitas ou não antes de reagendar.'))
    if goals and capacity > 0:
        total_goal = sum(int(x.get('weeklyMin', 0) or 0) for x in subjects)
        missing = sum(int(x.get('minutes', 0) or 0) for x in goals)
        out.append(dict(title='Metas semanais acima do tempo livre', minutes=missing,
                        reason=f'As metas somam {total_goal} min e o tempo útil da semana é {capacity} min. A distribuição favoreceu as disciplinas com maior dificuldade.'))
    return out
