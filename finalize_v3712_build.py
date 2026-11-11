"""Final cache/version guard for v3.7.12."""
from pathlib import Path
import re

ROOT=Path(__file__).resolve().parent
TARGET='3.7.12'

def normalize(text):
    text=re.sub(r'3\.7\.12\d+', TARGET, text)
    return text

def main():
    html=ROOT/'static'/'app.html'
    source=normalize(html.read_text(encoding='utf-8'))
    html.write_text(source,encoding='utf-8')

    for verifier in ROOT.glob('verify_*.py'):
        source=normalize(verifier.read_text(encoding='utf-8'))
        verifier.write_text(source,encoding='utf-8')

    print('MEUCRONOGRAMA_V3712_FINAL_GUARD_READY: malformed v3.7.12x cache assertions normalized.',flush=True)

if __name__=='__main__':
    main()
