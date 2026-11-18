"""Structured weekly routine. Reuses commitments; no schema or account changes."""
from __future__ import annotations
import copy
import re
import planner as P


def save_table(profile, data):
    if not isinstance(data, dict):
        raise ValueError('Dados da rotina inválidos.')
    if set(data) - {'settings', 'availability', 'entries', 'days', 'recurrence', 'anchor'}:
        raise ValueError('Campo não permitido na rotina.')
    if not isinstance(data.get('settings'), dict) or not isinstance(data.get('availability'), list):
        raise ValueError('Informe disponibilidade e limites da rotina.')
    result = copy.deepcopy(profile)
    if set(data['settings']) - set(result['settings']):
        raise ValueError('Configuração de rotina não reconhecida.')
    result['settings'].update(data['settings'])
    result['availability'] = copy.deepcopy(data['availability'])
    P.validate(result)
    for item in result['availability']:
        if item['status'] != 'available':
            continue
        intervals = sorted((P.minute(r['start']), P.minute(r['end'])) for r in item['ranges'])
        if not intervals:
            raise ValueError(P.DAY_NAMES[item['day']] + ': informe pelo menos um horário livre ou selecione Não informado.')
        if any(a2 < b1 for (_, b1), (a2, _) in zip(intervals, intervals[1:])):
            raise ValueError(P.DAY_NAMES[item['day']] + ': há horários livres sobrepostos. Revise início e término.')
    entries = data.get('entries', [])
    if not isinstance(entries, list) or len(entries) > 50:
        raise ValueError('Cadastre até 50 atividades por vez.')
    clean = []
    for number, row in enumerate(entries, 1):
        if not isinstance(row, dict) or set(row) - {'start', 'end', 'title'}:
            raise ValueError(f'Atividade {number}: registro inválido.')
        if any(not isinstance(row.get(k, ''), str) for k in ('start', 'end', 'title')):
            raise ValueError(f'Atividade {number}: horário e atividade precisam ser textos.')
        start, end, title = (row.get(k, '').strip() for k in ('start', 'end', 'title'))
        if not any((start, end, title)):
            continue
        if not start or not end or not title:
            raise ValueError(f'Atividade {number}: preencha horário de início, horário de término e atividade.')
        if len(title) > 250:
            raise ValueError(f'Atividade {number}: descreva a atividade em até 250 caracteres.')
        if not re.fullmatch(r'\d{2}:\d{2}', start) or not re.fullmatch(r'\d{2}:\d{2}', end):
            raise ValueError(f'Atividade {number}: use horários no formato HH:MM.')
        if P.minute(end) <= P.minute(start):
            raise ValueError(f'Atividade {number}: o término precisa ser depois do início. Para atravessar a meia-noite, use Compromisso detalhado.')
        clean.append({'start': start, 'end': end, 'title': title})
    added = 0
    if clean:
        recurrence = data.get('recurrence', 'weekly')
        if recurrence not in ('weekly', 'biweekly', 'once'):
            raise ValueError('Selecione uma repetição válida para as atividades.')
        anchor = data.get('anchor')
        try:
            if not isinstance(anchor, str) or len(anchor) != 10:
                raise ValueError()
            P.date(anchor)
        except (ValueError, TypeError):
            raise ValueError('Informe a data inicial ou a data da atividade.') from None
        days = data.get('days', [])
        if recurrence == 'once':
            days = [P.date(anchor).weekday()]
        elif (not isinstance(days, list) or not 1 <= len(days) <= 7 or
              any(type(d) is not int or not 0 <= d <= 6 for d in days) or len(set(days)) != len(days)):
            raise ValueError('Marque os dias em que essas atividades acontecem.')
        days = sorted(days)
        def same(existing, entry):
            return (existing['title'].strip().casefold() == entry['title'].casefold() and
                    existing['start'] == entry['start'] and existing['end'] == entry['end'] and
                    existing['recurrence'] == recurrence and existing['anchor'] == anchor and
                    sorted(existing['days']) == days and not existing.get('until'))
        for entry in clean:
            if any(same(x, entry) for x in result['fixed']):
                continue
            result['fixed'].append(dict(entry, id=P.uid(), category='Rotina', before=0, after=0,
                                        recurrence=recurrence, days=days, anchor=anchor, until=''))
            added += 1
    if result.get('planMeta'):
        result['planMeta']['dirty'] = True
    P.audit(result, 'routine_table', f'Rotina salva: {added} atividade(s) acrescentada(s); disponibilidade e limites conferidos. Horários de estudo existentes preservados.')
    return P.validate(result)
