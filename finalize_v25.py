"""Align legacy startup asset checks with the v2.5 release identity.
Functional import, catalogue, persistence and isolation assertions remain unchanged.
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def prepare():
    path = ROOT / 'verify_selective.py'
    text = path.read_text(encoding='utf-8')
    old = "require('v2.4'in source and '/static/selective.js'in source,'v2.3 assets missing.')"
    new = "require('v2.5'in source and '/static/selective.js'in source,'v2.5 assets missing.')"
    if text.count(old) == 1 and new not in text:
        path.write_text(text.replace(old, new, 1), encoding='utf-8')
    elif text.count(new) != 1 or old in text:
        raise RuntimeError('Unexpected selective release identity assertion.')
    print('MEUCRONOGRAMA_V25_VERIFIERS_READY: legacy release identity aligned; functional checks retained.')


if __name__ == '__main__':
    prepare()
