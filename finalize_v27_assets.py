"""Align the legacy selective-interface asset assertion with release 2.7.

This changes only the expected application version string. All functional
assertions in the deployment verifier remain active.
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def prepare():
    path = ROOT / 'verify_selective.py'
    text = path.read_text(encoding='utf-8')
    old = "require('v2.5'in source and '/static/selective.js'in source,'v2.5 assets missing.')"
    new = "require('v2.7'in source and '/static/selective.js'in source,'v2.7 assets missing.')"
    if text.count(old) == 1 and new not in text:
        path.write_text(text.replace(old, new, 1), encoding='utf-8')
    elif text.count(new) != 1 or old in text:
        raise RuntimeError('Unexpected selective-interface release assertion.')
    print('MEUCRONOGRAMA_V27_ASSET_CHECK_READY: legacy asset identity aligned; functional checks retained.')


if __name__ == '__main__':
    prepare()
