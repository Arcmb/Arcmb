from pathlib import Path

ROOT = Path(__file__).resolve().parent


def main():
    path = ROOT / 'verify_result_import.py'
    source = path.read_text(encoding='utf-8')
    old = "/static/result_import.js?v=2.8.4"
    new = "/static/result_import.js?v=2.8.5"
    if old in source:
        source = source.replace(old, new)
        path.write_text(source, encoding='utf-8')
    if new not in path.read_text(encoding='utf-8'):
        raise RuntimeError('Result-import verifier cache key was not aligned to 2.8.5.')
    print('MEUCRONOGRAMA_BULK_STUDENT_FINALIZED: result-import verifier aligned to cache key 2.8.5.', flush=True)


if __name__ == '__main__':
    main()
