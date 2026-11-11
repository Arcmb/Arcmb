"""Verify result-import live status v3.7.10."""
from pathlib import Path
ROOT=Path(__file__).resolve().parent

def require(v,m):
    if not v: raise RuntimeError(m)

def main():
    js=(ROOT/'static'/'result_import.js').read_text(encoding='utf-8')
    css=(ROOT/'static'/'style.css').read_text(encoding='utf-8')
    html=(ROOT/'static'/'app.html').read_text(encoding='utf-8')

    for marker in (
        '// === RESULT IMPORT LIVE STATUS V3.7.10 ===',
        'resultImportSetLiveStatus',
        'Preparando ',
        'Enviando ',
        'Servidor processando ',
        'Confirmando a gravação',
        'resultado(s) processado(s)',
    ):
        require(marker in js,'Missing result-import status marker: '+marker)

    require("api('/api/model-data/confirm',p)" in js,'Existing confirm endpoint was changed or removed.')
    require('result-import-live-bar' in css,'Progress styles missing.')
    require('/static/result_import.js?v=2.9.5' in html,'Result-import cache key not updated.')
    print('MEUCRONOGRAMA_RESULT_IMPORT_STATUS_CHECK_OK: total-aware staged messages and final summary passed.',flush=True)

if __name__=='__main__': main()
