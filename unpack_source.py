"""Expand the checked, compressed source files used by this deployment.
No network access, shell execution, or credentials are needed.
"""
from pathlib import Path
import hashlib,json,lzma

ROOT=Path(__file__).resolve().parent
SHA256='69251ef48eac0f10816e103ef76bb25361448542009c51d27ba0bad1bcfbca16'
ALLOWED={'webapp.py','planner.py','requirements.txt','static/app.html','static/app.js','static/icon.svg','static/login.html','static/login.js','static/manifest.webmanifest','static/setup.html','static/style.css'}

def unpack():
    pieces=[ROOT/'source'/f'part{i}.xzpart'for i in (1,2,3)]
    if not all(p.is_file()for p in pieces):
        if (ROOT/'webapp.py').is_file()and (ROOT/'planner.py').is_file():
            print('Source files already available.');return
        raise SystemExit('Source package is incomplete.')
    blob=b''.join(p.read_bytes()for p in pieces)
    if hashlib.sha256(blob).hexdigest()!=SHA256:raise SystemExit('Source integrity check failed.')
    decompressor=lzma.LZMADecompressor()
    raw=decompressor.decompress(blob,max_length=1_000_001)
    if len(raw)>1_000_000 or not decompressor.eof:raise SystemExit('Source package exceeds limits.')
    files=json.loads(raw)
    if set(files)!=ALLOWED or not all(isinstance(v,str)for v in files.values()):raise SystemExit('Unexpected source package contents.')
    for name,text in files.items():
        target=ROOT/name
        target.parent.mkdir(parents=True,exist_ok=True)
        target.write_text(text,encoding='utf-8')
    print(f'Verified source package: {len(files)} files extracted.')

if __name__=='__main__':unpack()
