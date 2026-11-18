"""Verificação da v3.9.0 em memória (sem gravar no banco)."""
from pathlib import Path
import copy, datetime as dt, sys

ROOT = Path(__file__).resolve().parent


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def main():
    import motor_profiles as M
    import planner as P
    cfg = copy.deepcopy(M.DEFAULT_CONFIG)
    sig = lambda media, acc, rec, n=3: {'sims': n, 'media': media, 'accuracy': acc, 'recurrence': rec, 'errors': 10, 'recurrentErrors': int(rec * 10)}
    require(M.classify(sig(780, .8, .1), cfg)[0] == 'precisao', '760+ com pouca recorrência deve ser Precisão.')
    require(M.classify(sig(780, .8, .3), cfg)[0] == 'intensiva', 'Recorrência alta deve ser Revisão Intensiva.')
    require(M.classify(sig(600, .5, .1), cfg)[0] == 'base', 'Média abaixo de 650 deve ser Base Sólida.')
    require(M.classify(sig(700, .65, .1), cfg)[0] == 'pratica', 'Faixa intermediária deve ser Prática Ativa.')
    require(M.classify({'sims': 0}, cfg)[0] is None, 'Sem simulado completo não classifica.')
    st = M._default_state()
    st, _ = M.advance(st, 'pratica', 2, 'r')
    require(st['current'] == 'pratica', 'Primeira classificação deve ser aplicada.')
    st, _ = M.advance(st, 'base', 3, 'r')
    require(st['current'] == 'pratica', 'Um simulado isolado não deve trocar o perfil.')
    st, _ = M.advance(st, 'base', 4, 'r')
    require(st['current'] == 'base', 'Dois simulados seguidos devem trocar o perfil.')
    manual = dict(st, mode='manual', current='precisao')
    manual, _ = M.advance(manual, 'pratica', 5, 'r')
    manual, _ = M.advance(manual, 'pratica', 6, 'r')
    require(manual['current'] == 'precisao', 'Escolha manual deve ser respeitada.')
    try:
        M.validate_config({'thresholds': {'base': 800, 'high': 700}})
        raise RuntimeError('Configuração incoerente aceita.')
    except ValueError:
        pass
    sunday = P.week(P.add(P.today(), 7))
    now = dt.datetime.combine(P.date(sunday), dt.time(6, 0), tzinfo=P.TZ)
    p = P.default_profile('Verificação perfis')
    p['availability'] = [dict(day=i, status='available', ranges=[dict(start='19:00', end='21:00')]) for i in range(7)]
    p['subjects'] = [dict(id='s1', name='Química', kind='study', action='Estudar', weeklyMin=90, difficulty=3, importance=3, priority=2, priorityManual=True, examDate='', active=True)]
    p['contents'] = [dict(id='c1', subjectId='s1', title='T', topic='', notes='', material='', status='studied', paused=False, studyMinutes=0, reviewMinutes=30,
                          difficulty=3, studiedOn=P.add(sunday, -30), studiedTime='12:00', nextDue=P.add(sunday, -2), stage=0)]
    P.validate(p)
    q = copy.deepcopy(p)
    q['settings']['motorProfile'] = {'key': 'pratica', 'reviewPlan': 'exercise_only', 'theoryMin': 5, 'exerciseMin': 25, 'reviewShare': .6}
    out = P.generate(q, sunday, current=now)
    parts = {s.get('reviewPart') for s in out['sessions'] if s.get('reviewContentId') == 'c1'}
    require(parts == {'exercise'}, 'Perfil Prática Ativa deve gerar só exercícios.')
    q['contents'][0]['reviewPrefsCustom'] = True
    q['sessions'] = []
    out = P.generate(q, sunday, current=now)
    parts = {s.get('reviewPart') for s in out['sessions'] if s.get('reviewContentId') == 'c1'}
    require(parts == {'theory', 'exercise'}, 'Ajuste manual do aluno deve prevalecer sobre o perfil.')
    print('MEUCRONOGRAMA_V390_MOTOR_PROFILES_CHECK_OK: classification, two-simulation migration, manual override and plan application passed.', flush=True)


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        print('MEUCRONOGRAMA_V390_MOTOR_PROFILES_CHECK_FAILED:', exc, flush=True)
        sys.exit(1)
