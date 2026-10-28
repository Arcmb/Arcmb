"""Extract the transparent, checksum-verified v2.3 source extension.

Only the listed UTF-8 source files are written. No network access, shell commands,
credentials or user data are involved. This package is not encrypted.
"""
from pathlib import Path
import hashlib
import json
import lzma

ROOT = Path(__file__).resolve().parent
SHA256 = '2e04252bfb2150231dad36ff9e73fe248cc658021b6b3726973bf6c492cc4fa1'
ALLOWED = {
    'questions_v23.py', 'templates_v23.py', 'selective.py', 'exams.py',
    'enhance_release.py', 'verify_selective.py', 'static/selective.js',
    'tests/test_v23.py', 'tests/check_v23_interface.py',
}


def unpack():
    paths = [ROOT / 'source' / f'v23-{n}.xzpart' for n in (1, 2)]
    if not all(path.is_file() for path in paths):
        raise SystemExit('The v2.3 source package is incomplete.')
    blob = b''.join(path.read_bytes() for path in paths)
    if hashlib.sha256(blob).hexdigest() != SHA256:
        raise SystemExit('The v2.3 source integrity check failed.')
    decoder = lzma.LZMADecompressor(memlimit=64 * 1024 * 1024)
    raw = decoder.decompress(blob, max_length=200_001)
    if len(raw) > 200_000 or not decoder.eof or decoder.unused_data:
        raise SystemExit('The v2.3 source package exceeds limits.')
    files = json.loads(raw)
    if (not isinstance(files, dict) or set(files) != ALLOWED
            or not all(isinstance(value, str) for value in files.values())):
        raise SystemExit('Unexpected v2.3 source package contents.')
    for name, text in files.items():
        destination = ROOT / name
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(text, encoding='utf-8')
    print('MEUCRONOGRAMA_V23_SOURCE_OK: 9 source files verified and extracted.')


if __name__ == '__main__':
    unpack()
