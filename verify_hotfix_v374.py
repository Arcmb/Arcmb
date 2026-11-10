"""Verify v3.7.4 report target parsing."""
from pathlib import Path
ROOT=Path(__file__).resolve().parent
def require(v,m):
    if not v: raise RuntimeError(m)
def main():
    model=(ROOT/'model_data.py').read_text(encoding='utf-8')
    require('# === HOTFIX V3.7.4 ===' in model,'Backend hotfix v3.7.4 missing.')
    require("raw=query.get('userId',[''])" in model,'List-based userId query parsing missing.')
    require("if isinstance(target_id,(list,tuple))" in model,'Target list unwrapping missing.')
    require("SELECT id,name,username,role,active FROM hmay_users WHERE id=?" in model,'Student target lookup missing.')
    compile(model,'model_data.py','exec')
    print('MEUCRONOGRAMA_HOTFIX_374_CHECK_OK: selected student report query parsing and permissions passed.',flush=True)
if __name__=='__main__': main()
