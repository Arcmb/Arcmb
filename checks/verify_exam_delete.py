"""Exclusão de notas, respostas e gabarito de um simulado (v3.15.0), num SQLite temporário."""
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tests'))


def main():
    model = (ROOT / 'model_data.py').read_text(encoding='utf-8')
    js = (ROOT / 'static' / 'student_summary.js').read_text(encoding='utf-8')
    for route in ('/api/model-data/exam-delete-preview', '/api/model-data/exam-delete'):
        assert route in model and route in js, 'Rota de exclusão ausente: ' + route
    assert "acts['exam-delete']" in js, 'Botão de exclusão ausente.'
    suite = unittest.defaultTestLoader.loadTestsFromName('test_exam_delete')
    result = unittest.TextTestRunner(verbosity=0, stream=open('/dev/null', 'w')).run(suite)
    if not result.wasSuccessful():
        for _, trace in result.failures + result.errors:
            print(trace, flush=True)
        raise SystemExit(1)
    print('MEUCRONOGRAMA_V3150_EXAM_DELETE_CHECK_OK: notas, respostas, gabarito, revisões, alcance e confirmação passed.', flush=True)


if __name__ == '__main__':
    main()
