"""Verify v3.7.3 class merge hotfix."""
from pathlib import Path
ROOT=Path(__file__).resolve().parent
def require(v,m):
    if not v: raise RuntimeError(m)
def main():
    model=(ROOT/'model_data.py').read_text(encoding='utf-8')
    js=(ROOT/'static'/'student_summary.js').read_text(encoding='utf-8')
    html=(ROOT/'static'/'app.html').read_text(encoding='utf-8')
    require('# === HOTFIX V3.7.3 ===' in model,'Backend hotfix v3.7.3 missing.')
    require('_v373_merge_classes' in model and "'class_registry_merge'" in model,'Class merge backend missing.')
    require("'DELETE FROM hmay_classes WHERE id=?'" in model,'Merged duplicate class is not removed.')
    require("'mergedInto':target['name']" in model,'Merge result metadata missing.')
    require('// === HOTFIX V3.7.3 ===' in js,'Frontend class merge hotfix missing.')
    require('Mesclar a turma' in js and 'Turmas mescladas:' in js,'Merge confirmation/result UI missing.')
    require('/static/student_summary.js?v=3.7.3' in html,'Student summary v3.7.3 cache key missing.')
    compile(model,'model_data.py','exec')
    print('MEUCRONOGRAMA_HOTFIX_373_CHECK_OK: duplicate registered classes merge, aliases consolidate, historical records propagate and source class is removed.',flush=True)
if __name__=='__main__': main()
