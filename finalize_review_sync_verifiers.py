from pathlib import Path
import re

ROOT = Path(__file__).resolve().parent


def main():
    verifier = ROOT / 'verify_result_import.py'
    text = verifier.read_text(encoding='utf-8')

    text = re.sub(
        r"require\('/static/result_import\.js\?v=[^']+' in html, 'Result importer asset is missing from app\.html\.'\)",
        "require('/static/result_import.js?v=' in html, 'Result importer asset is missing from app.html.')",
        text,
    )
    text = re.sub(
        r"response = request\(app, '/static/result_import\.js', 'v=[^']+'\)",
        "response = request(app, '/static/result_import.js')",
        text,
    )
    verifier.write_text(text, encoding='utf-8')

    html_path = ROOT / 'static' / 'app.html'
    html = html_path.read_text(encoding='utf-8')
    html = re.sub(r'/static/app\.js\?v=[^\"\']+', '/static/app.js?v=2.9.4', html)
    html = re.sub(r'/static/result_import\.js\?v=[^\"\']+', '/static/result_import.js?v=2.9.4', html)
    html_path.write_text(html, encoding='utf-8')

    print('MEUCRONOGRAMA_REVIEW_SYNC_VERIFIERS_READY: cache-independent importer check prepared.', flush=True)


if __name__ == '__main__':
    main()
