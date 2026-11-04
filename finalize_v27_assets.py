"""Align the legacy selective-interface asset assertion with release 2.7.

This changes only the expected application version string. All functional
assertions in the deployment verifier remain active.
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def prepare():
    path = ROOT / 'verify_selective.py'
    text = path.read_text(encoding='utf-8')
    lines = text.splitlines()
    matches = [
        index for index, line in enumerate(lines)
        if 'require(' in line and '/static/selective.js' in line and 'assets missing' in line
    ]
    if len(matches) != 1:
        raise RuntimeError('Unexpected selective-interface release assertion.')
    index = matches[0]
    indent = lines[index][:len(lines[index]) - len(lines[index].lstrip())]
    lines[index] = indent + "require('v2.7'in source and '/static/selective.js'in source,'v2.7 assets missing.')"
    path.write_text('\n'.join(lines) + ('\n' if text.endswith('\n') else ''), encoding='utf-8')
    print('MEUCRONOGRAMA_V27_ASSET_CHECK_READY: legacy asset identity aligned; functional checks retained.')


if __name__ == '__main__':
    prepare()
