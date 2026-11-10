"""Hotfix v3.7.3: merge duplicate class registrations into an existing canonical class."""
from pathlib import Path
import re

ROOT=Path(__file__).resolve().parent
STATIC=ROOT/"static"
BACKEND_MARK="# === HOTFIX V3.7.3 ==="
JS_MARK="// === HOTFIX V3.7.3 ==="

BACKEND=r'''
# === HOTFIX V3.7.3 ===
_v373_save_class_base=_v36_save_class

def _v373_merge_classes(app,c,user,current,target,requested_aliases):
    rows=_v36_class_rows(app,c,False)
    merged_aliases=[]
    for value in (
        list(target.get('aliases') or [])
        + [current.get('name')]
        + list(current.get('aliases') or [])
        + list(requested_aliases or [])
    ):
        value=F.text(value,160)
        if value and F.norm(value)!=F.norm(target['name']):
            merged_aliases.append(value)
    merged_aliases=sorted(set(merged_aliases),key=F.norm)

    claimed={}
    for row in rows:
        if row['id'] in (current['id'],target['id']):
            continue
        claimed[F.norm(row['name'])]=row['name']
        for alias in row.get('aliases') or []:
            claimed[F.norm(alias)]=row['name']
    for alias in merged_aliases:
        owner=claimed.get(F.norm(alias))
        if owner:
            raise ValueError(
                f'Não é possível mesclar: o nome/alias "{alias}" já pertence à turma "{owner}".'
            )

    accepted=[current['name']]+list(current.get('aliases') or [])+list(requested_aliases or [])
    updated_results=_v372_update_performance_class(app,c,accepted,target['name'])
    stamp=P.now().isoformat()
    app.db.execute(
        c,
        'UPDATE hmay_classes SET aliases=?,active=1,updated_at=? WHERE id=?',
        (_v36_json.dumps(merged_aliases,ensure_ascii=False),stamp,target['id']),
    )
    app.db.execute(c,'DELETE FROM hmay_classes WHERE id=?',(current['id'],))
    _v36_dashboard_cache.clear()
    app.event(c,user,user['id'],'class_registry_merge')
    return {
        'id':target['id'],
        'name':target['name'],
        'aliases':merged_aliases,
        'active':True,
        'updatedResults':updated_results,
        'oldName':current['name'],
        'merged':True,
        'mergedFrom':current['name'],
        'mergedInto':target['name'],
    }

def _v36_save_class(app,c,user,data):
    rows=_v36_class_rows(app,c,False)
    class_id=F.text(data.get('id'),160)
    name=F.text(data.get('name'),160)
    if not name:
        raise ValueError('Informe o nome oficial da turma.')

    if class_id:
        current=next((row for row in rows if row['id']==class_id),None)
        if not current:
            raise ValueError('Turma não encontrada.')
        target=next(
            (row for row in rows if row['id']!=class_id and F.norm(row['name'])==F.norm(name)),
            None,
        )
        if target:
            aliases_raw=data.get('aliases')
            if isinstance(aliases_raw,str):
                requested_aliases=[
                    F.text(x,160) for x in _v36_re.split(r'[,;\n]+',aliases_raw)
                    if F.text(x,160)
                ]
            elif isinstance(aliases_raw,list):
                requested_aliases=[F.text(x,160) for x in aliases_raw if F.text(x,160)]
            else:
                requested_aliases=[]
            return _v373_merge_classes(app,c,user,current,target,requested_aliases)

    return _v373_save_class_base(app,c,user,data)
'''

JS=r'''
// === HOTFIX V3.7.3 ===
acts['class-registry-save']=async el=>{
 const id=el?.dataset?.classId||'';
 const name=document.querySelector('[data-class-name="'+CSS.escape(id)+'"]')?.value?.trim()||'';
 const aliases=document.querySelector('[data-class-aliases="'+CSS.escape(id)+'"]')?.value||'';
 const active=!!document.querySelector('[data-class-active="'+CSS.escape(id)+'"]')?.checked;
 const classes=classRegistryCache?.classes||[];
 const current=classes.find(x=>x.id===id);
 if(!name)throw new Error('Informe o nome oficial da turma.');

 const sameName=value=>String(value||'').trim().toLocaleLowerCase('pt-BR')===name.toLocaleLowerCase('pt-BR');
 const existing=classes.find(x=>x.id!==id&&sameName(x.name));

 let question='';
 if(existing){
  question='Mesclar a turma "'+(current?.name||'')+'" com a turma já existente "'+existing.name+'"? Todos os resultados vinculados serão atualizados para "'+existing.name+'" e a turma duplicada será removida.';
 }else if(current&&current.name!==name){
  question='Alterar a turma "'+current.name+'" para "'+name+'" e atualizar todos os registros vinculados?';
 }else{
  question='Normalizar as divergências desta turma para "'+name+'"?';
 }
 if(!confirm(question))return;

 const d=await api('/api/model-data/classes',{id,name,aliases,active});
 classRegistryCache={classes:d.classes||[],unregistered:d.unregistered||[]};
 managementDashboardCache=null;
 const saved=d.saved||{};
 const updated=Number(saved.updatedResults||0);
 if(saved.merged){
  toast('Turmas mescladas: "'+saved.mergedFrom+'" → "'+saved.mergedInto+'". '+updated+' registro(s) atualizado(s).');
 }else{
  toast('Turma salva. '+updated+' registro(s) histórico(s) atualizado(s).');
 }
 render();
};
'''

def main():
    model=ROOT/"model_data.py"
    text=model.read_text(encoding="utf-8")
    if BACKEND_MARK not in text:
        model.write_text(text.rstrip()+"\n\n"+BACKEND.strip()+"\n",encoding="utf-8")

    js=STATIC/"student_summary.js"
    text=js.read_text(encoding="utf-8")
    if JS_MARK not in text:
        js.write_text(text.rstrip()+"\n\n"+JS.strip()+"\n",encoding="utf-8")

    html=STATIC/"app.html"
    text=html.read_text(encoding="utf-8")
    text=re.sub(r'/static/student_summary\.js\?v=[^"\']+','/static/student_summary.js?v=3.7.3',text)
    html.write_text(text,encoding="utf-8")

    for verifier in ROOT.glob('verify_*.py'):
        source=verifier.read_text(encoding='utf-8')
        source=source.replace('/static/student_summary.js?v=3.7.2','/static/student_summary.js?v=3.7.3')
        verifier.write_text(source,encoding='utf-8')

    site=ROOT/'site_version_release.py'
    source=site.read_text(encoding='utf-8').replace('PUBLIC_VERSION="3.7.2"','PUBLIC_VERSION="3.7.3"')
    site.write_text(source,encoding='utf-8')
    vsite=ROOT/'verify_site_version.py'
    source=vsite.read_text(encoding='utf-8').replace('v3.7.2','v3.7.3')
    vsite.write_text(source,encoding='utf-8')

    print("MEUCRONOGRAMA_HOTFIX_373_READY: duplicate class names now merge into the existing canonical class with historical propagation.",flush=True)

if __name__=="__main__":
    main()
