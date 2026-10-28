"""Extract the reviewed v2.4.1 extension; no network or credentials."""
from pathlib import Path
import hashlib,json,lzma
ROOT=Path(__file__).resolve().parent
SHA256='703cd411807e406994cec5bcfb52e0a7356300d56c9f9e57bc0a222ed3fe82ac'
ALLOWED={'tests/check_coordinator_interface.py', 'static/coordinator_accounts.js', 'tests/test_coordinator_creation.py', 'tests/check_routine_interface.py', 'static/routine_entries.js', 'verify_coordinator.py', 'routine_release.py', 'routine_entries.py', 'tests/test_routine_entries.py', 'coordinator_release.py'}


def unpack():
    blob=b''.join((ROOT/'source'/f'v241-{i}.xzpart').read_bytes() for i in (1,2,3))
    if hashlib.sha256(blob).hexdigest()!=SHA256:
        raise RuntimeError('v2.4.1 source integrity check failed.')
    decoder=lzma.LZMADecompressor()
    raw=decoder.decompress(blob,max_length=1_000_001)
    if len(raw)>1_000_000 or not decoder.eof or decoder.unused_data:
        raise RuntimeError('v2.4.1 source exceeds limits.')
    files=json.loads(raw)
    if not isinstance(files,dict) or set(files)!=ALLOWED or not all(isinstance(v,str) for v in files.values()):
        raise RuntimeError('Unexpected v2.4.1 source paths.')
    for name,text in files.items():
        target=ROOT/name
        target.parent.mkdir(parents=True,exist_ok=True)
        target.write_text(text,encoding='utf-8')
    print('MEUCRONOGRAMA_V241_SOURCE_OK: 10 source files verified and extracted.')


if __name__=='__main__':unpack()
