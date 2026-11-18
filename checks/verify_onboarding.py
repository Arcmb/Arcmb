"""Verificação da v3.14.0 (primeiro acesso guiado). Não usa o banco."""
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def main():
    import planner as P
    html = (ROOT / 'static' / 'app.html').read_text(encoding='utf-8')
    js = (ROOT / 'static' / 'onboarding.js').read_text(encoding='utf-8')
    require('/static/onboarding.js' in html, 'Tela de primeiro acesso ausente.')
    require('style=' not in js, 'A política de segurança bloqueia estilo inline: use qi_extras.css.')
    require('qiOnboardingPending' in (ROOT / 'static' / 'use_guide.js').read_text(encoding='utf-8'), 'O guia rápido precisa esperar o primeiro acesso.')
    p = P.default_profile('Teste')
    s = dict(p['settings'], preferred='noite', onboardedAt='2026-11-18', onboardingGoal='Medicina', weeklyGoal=300)
    av = [dict(day=d, status='available' if d < 5 else 'unavailable', ranges=[dict(start='19:00', end='22:30')] if d < 5 else []) for d in range(7)]
    p = P.validate(P.action(p, 'routine', dict(settings=s, availability=av)))
    require(p['settings']['onboardedAt'] == '2026-11-18', 'O primeiro acesso precisa ficar registrado nas configurações.')
    print('MEUCRONOGRAMA_V3140_ONBOARDING_CHECK_OK', flush=True)


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        print('MEUCRONOGRAMA_V3140_ONBOARDING_CHECK_FAILED:', exc, flush=True)
        sys.exit(1)
