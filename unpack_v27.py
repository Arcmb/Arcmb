"""Extract the verified Meu Cronograma 2.7 source extension.

No network, shell execution, credentials or user records are included.
"""
from pathlib import Path
import base64
import hashlib
import json
import lzma

ROOT = Path(__file__).resolve().parent
SHA256 = '5e1bda9301a40fbab1fce8adea798e43ffd68ce5d4a9091f58d99f0a6742f12a'
ALLOWED = {
    'model_data.py',
    'model_data_release.py',
    'verify_model_data.py',
    'finalize_v27.py',
    'static/model_data.js',
    'ATUALIZACAO_V27.md',
}


def unpack():
    parts = [ROOT / 'source' / f'v27-{i}.b64' for i in range(1, 6)]
    if not all(part.is_file() for part in parts):
        raise SystemExit('Incomplete v2.7 source package.')
    try:
        encoded = ''.join(part.read_text(encoding='ascii') for part in parts)
        blob = base64.b64decode(encoded, validate=True)
    except Exception as exc:
        raise SystemExit('Invalid v2.7 source encoding.') from exc
    if hashlib.sha256(blob).hexdigest() != SHA256:
        raise SystemExit('v2.7 source integrity failed.')
    decoder = lzma.LZMADecompressor(memlimit=256 * 1024 * 1024)
    raw = decoder.decompress(blob, max_length=200001)
    if len(raw) > 200000 or not decoder.eof or decoder.unused_data:
        raise SystemExit('v2.7 source package limit exceeded.')
    files = json.loads(raw)
    if not isinstance(files, dict) or set(files) != ALLOWED or not all(isinstance(v, str) for v in files.values()):
        raise SystemExit('Unexpected v2.7 files.')
    for name, text in files.items():
        path = ROOT / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding='utf-8')
    print('MEUCRONOGRAMA_V27_SOURCE_OK: 6 source files verified and extracted.')


if __name__ == '__main__':
    unpack()
