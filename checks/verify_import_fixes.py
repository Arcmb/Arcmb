"""Correção de divergências das importações na interface (v3.17.0), num SQLite temporário."""
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tests'))


def main():
    html = (ROOT / 'static' / 'app.html').read_text(encoding='utf-8')
    js = (ROOT / 'static' / 'import_fixes.js').read_text(encoding='utf-8')
    web = (ROOT / 'webapp.py').read_text(encoding='utf-8')
    assert '/static/import_fixes.js?v=' in html, 'Janela de correção não carregada.'
    assert "'import_fixes.js'" in web, 'import_fixes.js não liberado no servidor.'
    assert 'importFixOpen' in js and 'importFixStore' in js, 'Janela de correção incompleta.'
    suite = unittest.defaultTestLoader.loadTestsFromName('test_import_fixes')
    result = unittest.TextTestRunner(verbosity=0, stream=open('/dev/null', 'w')).run(suite)
    if not result.wasSuccessful():
        for _, trace in result.failures + result.errors:
            print(trace, flush=True)
        raise SystemExit(1)
    print('MEUCRONOGRAMA_V3170_IMPORT_FIXES_CHECK_OK: respostas, gabarito, notas TRI, mapa avulso, turmas e correções passed.', flush=True)


if __name__ == '__main__':
    main()
