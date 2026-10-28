"""Extract checked UTF-8 source for the v2.4 single-workbook extension.
No network, shell execution, credentials or user records. Not encrypted.
"""
from pathlib import Path
import hashlib, json, lzma
ROOT=Path(__file__).resolve().parent
SHA256='844e39d2f11ce424a0c05c91b81dbf7b5fb532d1532c4b75bf7c06bf020627d4'
ALLOWED={'unified.py','unified_release.py','static/import_wizard.js','verify_workbook.py'}
def unpack():
    parts=[ROOT/'source'/f'v24-{i}.xzpart' for i in (1,2,3)]
    if not all(p.is_file()for p in parts):raise SystemExit('Incomplete v2.4 source package.')
    blob=b''.join(p.read_bytes()for p in parts)
    if hashlib.sha256(blob).hexdigest()!=SHA256:raise SystemExit('v2.4 source integrity failed.')
    decoder=lzma.LZMADecompressor(memlimit=64*1024*1024)
    raw=decoder.decompress(blob,max_length=200001)
    if len(raw)>200000 or not decoder.eof or decoder.unused_data:raise SystemExit('v2.4 package limit exceeded.')
    files=json.loads(raw)
    if not isinstance(files,dict)or set(files)!=ALLOWED or not all(isinstance(v,str)for v in files.values()):raise SystemExit('Unexpected v2.4 files.')
    for name,text in files.items():
        path=ROOT/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_text(text,encoding='utf-8')
    print('MEUCRONOGRAMA_V24_SOURCE_OK: 4 source files verified and extracted.')
if __name__=='__main__':unpack()
