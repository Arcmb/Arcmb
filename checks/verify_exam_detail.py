"""Consulta de um caderno: gabarito, notas e respostas (v3.16.0), num SQLite temporário."""
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tests'))


def main():
    model = (ROOT / 'model_data.py').read_text(encoding='utf-8')
    js = (ROOT / 'static' / 'student_summary.js').read_text(encoding='utf-8')
    assert '/api/model-data/exam-detail' in model and '/api/model-data/exam-detail' in js, 'Rota de consulta ausente.'
    assert "acts['exam-detail']" in js and 'exam-detail-title' in js, 'Clique no simulado ausente.'
    suite = unittest.defaultTestLoader.loadTestsFromName('test_exam_detail')
    result = unittest.TextTestRunner(verbosity=0, stream=open('/dev/null', 'w')).run(suite)
    if not result.wasSuccessful():
        for _, trace in result.failures + result.errors:
            print(trace, flush=True)
        raise SystemExit(1)
    print('MEUCRONOGRAMA_V3160_EXAM_DETAIL_CHECK_OK: gabarito, notas, respostas, permissões e busca passed.', flush=True)


if __name__ == '__main__':
    main()
