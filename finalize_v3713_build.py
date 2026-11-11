"""Final cache/version guard for v3.7.13."""
from pathlib import Path
import re
ROOT=Path(__file__).resolve().parent
TARGET='3.7.13'
def normalize(text):
    return re.sub(r'3\.7\.13\d+',TARGET,text)
def main():
    html=ROOT/'static'/'app.html'
    html.write_text(normalize(html.read_text(encoding='utf-8')),encoding='utf-8')
    for verifier in ROOT.glob('verify_*.py'):
        verifier.write_text(normalize(verifier.read_text(encoding='utf-8')),encoding='utf-8')
    print('MEUCRONOGRAMA_V3713_FINAL_GUARD_READY: malformed v3.7.13x version assertions normalized.',flush=True)
if __name__=='__main__': main()
