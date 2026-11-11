"""Verify strict A-E import normalization v3.7.9."""
from pathlib import Path
ROOT=Path(__file__).resolve().parent

def require(value,message):
    if not value:
        raise RuntimeError(message)

def main():
    model=(ROOT/'model_data.py').read_text(encoding='utf-8')
    require('# === STRICT A-E IMPORT V3.7.9 ===' in model,'Strict A-E marker missing.')
    block=model[model.index('# === STRICT A-E IMPORT V3.7.9 ===')-80:model.index('# === STRICT A-E IMPORT V3.7.9 ===')+350]
    require("if text in ('A', 'B', 'C', 'D', 'E'):" in block,'Exact A-E whitelist missing.')
    require('return text' in block and 'return 0' in block,'Strict valid/error returns missing.')
    require("text = str(value).strip().upper()" in block,'Case normalization missing.')
    compile(model,'model_data.py','exec')
    print(
        'MEUCRONOGRAMA_STRICT_AE_IMPORT_CHECK_OK: A-E whitelist and universal non-A-E error conversion passed.',
        flush=True,
    )

if __name__=='__main__':
    main()
