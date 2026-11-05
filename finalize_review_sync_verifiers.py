from pathlib import Path
import re

ROOT = Path(__file__).resolve().parent


def make_cache_checks_version_independent(text: str) -> str:
    """Keep functional asset checks without coupling them to a cache-bust number."""
    replacements = (
        (r"'/static/result_import\.js\?v=[^']+'", "'/static/result_import.js?v='"),
        (r'"/static/result_import\.js\?v=[^"]+"', '"/static/result_import.js?v="'),
        (r"'/static/app\.js\?v=[^']+'", "'/static/app.js?v='"),
        (r'"/static/app\.js\?v=[^"]+"', '"/static/app.js?v="'),
    )
    for pattern, replacement in replacements:
        text = re.sub(pattern, replacement, text)
    return text


def main():
    # Several historical verifiers asserted exact cache versions. The feature
    # changes the cache key intentionally, so all verifiers should check that
    # the asset is referenced, not a particular version string.
    updated = 0
    for verifier in ROOT.glob('verify_*.py'):
        text = verifier.read_text(encoding='utf-8')
        patched = make_cache_checks_version_independent(text)
        if verifier.name == 'verify_result_import.py':
            patched = re.sub(
                r"response = request\(app, '/static/result_import\.js', 'v=[^']+'\)",
                "response = request(app, '/static/result_import.js')",
                patched,
            )
        if patched != text:
            verifier.write_text(patched, encoding='utf-8')
            updated += 1

    html_path = ROOT / 'static' / 'app.html'
    html = html_path.read_text(encoding='utf-8')
    html = re.sub(r'/static/app\.js\?v[^\"\']*', '/static/app.js?v=2.9.4', html)
    html = re.sub(r'/static/result_import\.js\?v[^\"\']*', '/static/result_import.js?v=2.9.4', html)
    html_path.write_text(html, encoding='utf-8')

    print(
        'MEUCRONOGRAMA_REVIEW_SYNC_VERIFIERS_READY: '
        f'{updated} cache-coupled verifier(s) normalized; importer checks remain functional.',
        flush=True,
    )


if __name__ == '__main__':
    main()
