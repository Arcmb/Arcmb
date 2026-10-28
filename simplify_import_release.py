"""Apply the model-first UI after the existing v2.3 build, without data migrations."""
from pathlib import Path
ROOT=Path(__file__).resolve().parent

def change(s,old,new):
    if s.count(old)!=1:raise RuntimeError('Unexpected source for model-first UI: '+old[:80])
    return s.replace(old,new)

def prepare():
    p=ROOT/'webapp.py';s=p.read_text(encoding='utf-8')
    s=change(s,"'selective.js':'application/javascript; charset=utf-8'", "'selective.js':'application/javascript; charset=utf-8','import_wizard.js':'application/javascript; charset=utf-8'")
    s=change(s,"ready=True,version='2.3'","ready=True,version='2.3.1'")
    p.write_text(s,encoding='utf-8')
    p=ROOT/'static/app.html';s=p.read_text(encoding='utf-8')
    s=change(s,'<script src="/static/selective.js?v=2.3" defer></script>','<script src="/static/selective.js?v=2.3" defer></script><script src="/static/import_wizard.js?v=2.3.1" defer></script>')
    s=s.replace('v2.3</','v2.3.1</').replace('?v=2.3"','?v=2.3.1"')
    p.write_text(s,encoding='utf-8')
    p=ROOT/'static/app.js';s=p.read_text(encoding='utf-8')
    s=change(s,"['performance','Desempenho'],['exams','Simulados e questões']", "['result-model','Modelo de resultados'],['performance','Desempenho'],['exams','Mapa de questões']")
    s=change(s,"navItems.filter(x=>x[0]!=='exams'||manages())","navItems.filter(x=>!['exams','result-model'].includes(x[0])||manages())")
    s=change(s,'mapping:mappingView,exams:examsView};',"mapping:mappingView,exams:examsView,'result-model':resultModelView};")
    p.write_text(s,encoding='utf-8')
    p=ROOT/'static/style.css';s=p.read_text(encoding='utf-8')
    s+='''\n/* v2.3.1 — checkbox-first results template */
.model-layout{display:grid;grid-template-columns:minmax(0,1.7fr) minmax(260px,1fr);gap:20px;align-items:start}.model-summary{position:sticky;top:100px}.model-summary ol{max-height:38vh;overflow:auto;padding-left:24px;overflow-wrap:anywhere}.model-summary .actions{margin-top:16px}.model-summary button{width:100%;white-space:normal}.model-field-table{width:100%;table-layout:fixed}.model-field-table th:first-child{width:78px}.model-field-table td{padding:9px 12px;vertical-align:middle;overflow-wrap:anywhere}.model-field-table td label{display:inline;cursor:pointer;font-weight:500;line-height:1.6}.model-field-table td .tag{margin-left:10px}.model-field-table input[type=checkbox]{width:22px;height:22px;margin:0;accent-color:#6652a4;cursor:pointer}.model-tick{text-align:center}.model-selected{background:#f1edfa}.model-group-title{display:flex;flex-wrap:wrap;align-items:center;justify-content:space-between;gap:10px}.model-group-title h2{margin:0}.model-group .actions{margin:12px 0}.model-range,.model-custom{display:flex;align-items:end;gap:10px;flex-wrap:wrap;margin:14px 0}.model-range label{max-width:135px}.model-custom label{flex:1;min-width:170px}.model-main-actions{margin:18px 0}.model-entry{border-left:4px solid #6652a4}.model-advanced{margin:16px 0}.model-advanced summary{cursor:pointer;padding:12px;background:#f1edfa;border-radius:10px}.model-layout>*{min-width:0}@media(max-width:960px){.model-layout{grid-template-columns:1fr}.model-summary{position:static;order:-1}.model-summary ol{max-height:145px}}@media(max-width:480px){.model-field-table th:first-child{width:55px}.model-field-table td{padding:9px 6px}.model-field-table td .tag{display:block;margin:4px 0}.model-group-title{display:block}.model-group .actions button{font-size:.82rem}.model-range button,.model-custom button{width:100%}}\n'''
    p.write_text(s,encoding='utf-8')
    print('MEUCRONOGRAMA_MODEL_FIRST_OK: visible checkboxes before file generation; existing data preserved.')

if __name__=='__main__':prepare()
