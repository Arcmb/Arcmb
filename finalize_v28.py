"""Align the v2.7 disposable scoring check with the definitive language map."""
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parent


def prepare():
    path = ROOT / 'verify_model_data.py'
    text = path.read_text(encoding='utf-8')
    replacement = """            maps = []
            english_keys = ['A', 'B', 'D', 'ANULADA']
            spanish_keys = ['E', 'D', 'C', 'ANULADA']
            for question in range(1, 5):
                maps.append([title, date, color, question, 'LC', 'Inglês', 'Leitura', 'Texto', 'H01', 'Inglês', english_keys[question - 1]])
                maps.append([title, date, color, question, 'LC', 'Espanhol', 'Leitura', 'Texto', 'H02', 'Espanhol', spanish_keys[question - 1]])
"""
    text, changed = re.subn(
        r"            maps = \[\[.*?\n            blob, _ =",
        replacement + "            blob, _ =",
        text,
        count=1,
        flags=re.S,
    )
    if changed != 1:
        raise RuntimeError('Amostra do verificador v2.7 não encontrada.')
    path.write_text(text, encoding='utf-8')
    print('MEUCRONOGRAMA_V28_LEGACY_CHECK_READY: old scoring sample now contains English and Spanish variants.')


if __name__ == '__main__':
    prepare()
