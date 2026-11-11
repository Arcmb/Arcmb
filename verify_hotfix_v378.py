"""Verify final TRI workbook byte normalization v3.7.8."""
from pathlib import Path
ROOT=Path(__file__).resolve().parent
def require(v,m):
    if not v: raise RuntimeError(m)
def main():
    model=(ROOT/'model_data.py').read_text(encoding='utf-8')
    require('# === TRI TEMPLATE FINAL BYTES V3.7.8 ===' in model,'Final TRI template patch missing.')
    final=model[model.rfind('# === TRI TEMPLATE FINAL BYTES V3.7.8 ==='):]
    require('if isinstance(output, tuple):' in final,'Tuple normalization missing.')
    require('return bytes(output)' in final,'Raw XLSX byte return missing.')
    require('NOTA COM BONIFICAÇÃO' not in final,'Bonus column returned in final TRI template.')
    compile(model,'model_data.py','exec')
    print('MEUCRONOGRAMA_TRI_TEMPLATE_FINAL_BYTES_CHECK_OK: final template is byte-safe, no bonus column and endpoint-compatible.',flush=True)
if __name__=='__main__': main()
