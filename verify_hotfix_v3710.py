"""Verify non-A-E exam-key import rule v3.7.10."""
from pathlib import Path
import model_data as M

ROOT=Path(__file__).resolve().parent

def require(value,message):
    if not value:
        raise RuntimeError(message)

def main():
    model=(ROOT/'model_data.py').read_text(encoding='utf-8')
    require('# === NON-AE GABARITO AS ERROR V3.7.10 ===' in model,'v3.7.10 marker missing.')
    require("item['answer'] = '#ERRO#'" in model,'Forced-error sentinel missing.')
    require('pass  # v3.7.10: non-A-E gabarito is normalized as error instead of blocking import' in model,'Old blocking validator was not disabled.')
    require(M._answer('A','Resposta')=='A','A must remain valid.')
    require(M._answer('E','Resposta')=='E','E must remain valid.')
    for value in ('x','X/X','A/A','A|A','A | A','A/B','B|C','ANULADA','',None,0,1,'*','.'):
        require(M._answer(value,'Resposta')==0,repr(value)+' must be student error zero.')
    print('MEUCRONOGRAMA_NON_AE_GABARITO_CHECK_OK: non-A-E gabarito no longer blocks import and non-A-E student responses remain errors.',flush=True)

if __name__=='__main__':
    main()
