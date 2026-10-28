"""Keep the existing workbook startup check aligned with release 2.4.1.

All functional assertions remain unchanged. A mismatched or unexpected verifier
fails the build instead of silently disabling release identity validation.
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def prepare():
    path = ROOT / 'verify_workbook.py'
    text = path.read_text(encoding='utf-8')
    old = "require(staff.request('/readyz')['data'].get('version')=='2.4','Release identity mismatch.')"
    new = "require(staff.request('/readyz')['data'].get('version')=='2.4.1','Release identity mismatch.')"
    if text.count(old) == 1 and new not in text:
        path.write_text(text.replace(old, new, 1), encoding='utf-8')
    elif text.count(new) != 1 or old in text:
        raise RuntimeError('Unexpected workbook release identity assertion.')
    print('MEUCRONOGRAMA_V241_VERIFIERS_READY: exact release identity aligned; functional checks retained.')


if __name__ == '__main__':
    prepare()
