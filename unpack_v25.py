"""Extract the reviewed v2.5 area-workbook extension.
The source parts are LZMA-compressed and Base64-encoded, not encrypted.
"""
from pathlib import Path
import base64, hashlib, json, lzma

ROOT=Path(__file__).resolve().parent
SHA256='5b29f7bbe2ee5dfda302e2b98b2985258d156ab5ae5d4161b72df88b1d48da9e'
ALLOWED={'static/area_tabs.js', 'tests/test_area_tabs.py', 'area_tabs_release.py', 'verify_area_tabs.py', 'area_workbook.py'}


def unpack():
    parts=[ROOT/'source'/f'v25-{i}.b64' for i in range(1,5)]
    if not all(p.is_file() for p in parts):
        raise RuntimeError('Incomplete v2.5 source package.')
    encoded=''.join(p.read_text(encoding='ascii').strip() for p in parts)
    blob=base64.b64decode(encoded,validate=True)
    if hashlib.sha256(blob).hexdigest()!=SHA256:
        raise RuntimeError('v2.5 source integrity check failed.')
    decoder=lzma.LZMADecompressor(memlimit=64*1024*1024)
    raw=decoder.decompress(blob,max_length=300001)
    if len(raw)>300000 or not decoder.eof or decoder.unused_data:
        raise RuntimeError('v2.5 source exceeds limits.')
    files=json.loads(raw)
    if not isinstance(files,dict) or set(files)!=ALLOWED or not all(isinstance(v,str) for v in files.values()):
        raise RuntimeError('Unexpected v2.5 source paths.')
    for name,text in files.items():
        path=ROOT/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_text(text,encoding='utf-8')
    print(f'MEUCRONOGRAMA_V25_SOURCE_OK: {len(files)} source files verified and extracted.')


if __name__=='__main__':unpack()
