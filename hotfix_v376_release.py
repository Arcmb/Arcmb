"""Hotfix v3.7.6: scoped deletion of student reports by class or selected students."""
from pathlib import Path
import re

ROOT=Path(__file__).resolve().parent
STATIC=ROOT/"static"
BACKEND_MARK="# === REPORT SCOPED DELETE V3.7.6 ==="
JS_MARK="// === REPORT SCOPED DELETE V3.7.6 ==="
CSS_MARK="/* === REPORT SCOPED DELETE V3.7.6 === */"

BACKEND=r'''
# === REPORT SCOPED DELETE V3.7.6 ===
_reports_handle_v376_base=handle

def _reports_latest_class_by_user(app,c,user_ids):
    if not user_ids:
        return {}
    lookup=_v36_class_lookup(app,c)
    placeholders=','.join('?' for _ in user_ids)
    rows=app.db.execute(
        c,
        'SELECT user_id,metadata,applied_on,updated_at FROM hmay_performance '
        'WHERE user_id IN ('+placeholders+') '
        'ORDER BY user_id,applied_on DESC,updated_at DESC',
        tuple(user_ids),
    ).fetchall()
    result={}
    for raw in rows:
        user_id=raw['user_id']
        if user_id in result:
            continue
        meta=_rx_json(raw['metadata'])
        raw_class=F.text(meta.get('TURMA'),160) or 'Sem turma'
        result[user_id]=lookup.get(F.norm(raw_class),raw_class)
    for user_id in user_ids:
        result.setdefault(user_id,'Sem turma')
    return result

def _reports_delete_options(app,c,model_id):
    _reports_ensure(app,c)
    model_id=F.text(model_id,160)
    model=app.db.execute(
        c,
        'SELECT m.id,m.title,m.activity,m.applied_on,t.name AS type_name '
        'FROM hmay_report_models m JOIN hmay_report_types t ON t.id=m.type_id '
        'WHERE m.id=?',
        (model_id,),
    ).fetchone()
    if not model:
        raise ValueError('Modelo de relatório não encontrado.')

    rows=app.db.execute(
        c,
        'SELECT r.user_id,u.name,u.username '
        'FROM hmay_student_reports r JOIN hmay_users u ON u.id=r.user_id '
        'WHERE r.model_id=? ORDER BY lower(u.name),lower(u.username)',
        (model_id,),
    ).fetchall()
    user_ids=[row['user_id'] for row in rows]
    class_by_user=_reports_latest_class_by_user(app,c,user_ids)

    groups={}
    for raw in rows:
        turma=class_by_user.get(raw['user_id'],'Sem turma')
        bucket=groups.setdefault(turma,[])
        bucket.append({
            'id':raw['user_id'],
            'name':raw['name'],
            'username':raw['username'],
        })

    classes=[
        {'name':name,'count':len(students),'students':students}
        for name,students in sorted(groups.items(),key=lambda item:F.norm(item[0]))
    ]
    return {
        'model':{
            'id':model['id'],'title':model['title'],'activity':model['activity'],
            'date':model['applied_on'],'type':model['type_name'],
        },
        'totalAssignments':len(rows),
        'classes':classes,
    }

def _reports_delete_scope(app,c,user,data):
    _reports_ensure(app,c)
    model_id=F.text(data.get('modelId'),160)
    if not model_id:
        raise ValueError('Modelo de relatório não informado.')
    model=app.db.execute(
        c,'SELECT id,title FROM hmay_report_models WHERE id=?',(model_id,)
    ).fetchone()
    if not model:
        raise ValueError('Modelo de relatório não encontrado.')

    options=_reports_delete_options(app,c,model_id)
    assignments={}
    for group in options['classes']:
        for student in group['students']:
            assignments[student['id']]=group['name']

    selections=data.get('selections')
    if not isinstance(selections,list):
        selections=[]

    deleted_users=set()
    delete_model=False

    if not selections:
        deleted_users=set(assignments.keys())
        delete_model=True
    else:
        for selection in selections:
            if not isinstance(selection,dict):
                continue
            turma=F.text(selection.get('turma'),160)
            if not turma:
                continue
            group_users={uid for uid,current_class in assignments.items() if current_class==turma}
            if not group_users:
                continue
            raw_ids=selection.get('userIds')
            selected_ids=[]
            if isinstance(raw_ids,list):
                selected_ids=[F.text(uid,160) for uid in raw_ids if F.text(uid,160)]
            if selected_ids:
                valid={uid for uid in selected_ids if uid in group_users}
                deleted_users.update(valid)
            else:
                deleted_users.update(group_users)

    deleted_count=0
    if deleted_users:
        ids=sorted(deleted_users)
        for offset in range(0,len(ids),300):
            chunk=ids[offset:offset+300]
            placeholders=','.join('?' for _ in chunk)
            params=[model_id]+chunk
            before=app.db.execute(
                c,
                'SELECT COUNT(*) AS n FROM hmay_student_reports '
                'WHERE model_id=? AND user_id IN ('+placeholders+')',
                tuple(params),
            ).fetchone()
            deleted_count+=int(before['n'] or 0)
            app.db.execute(
                c,
                'DELETE FROM hmay_student_reports WHERE model_id=? '
                'AND user_id IN ('+placeholders+')',
                tuple(params),
            )

    if delete_model:
        app.db.execute(c,'DELETE FROM hmay_report_models WHERE id=?',(model_id,))

    remaining=app.db.execute(
        c,'SELECT COUNT(*) AS n FROM hmay_student_reports WHERE model_id=?',(model_id,)
    ).fetchone()
    remaining_count=0 if delete_model else int(remaining['n'] or 0)

    app.event(c,user,user['id'],'student_report_scope_delete')
    return {
        'deletedAssignments':deleted_count,
        'remainingAssignments':remaining_count,
        'modelDeleted':delete_model,
        'modelTitle':model['title'],
        **_reports_admin_data(app,c),
    }

def handle(app,c,user,path,method,data,query,start,HTTPError):
    if path=='/api/model-data/report-delete-options':
        if user.get('role') not in ('master','coordenador'):
            raise HTTPError(403,'Acesso reservado ao Master e à coordenação.')
        if method!='POST':
            raise HTTPError(405,'Use POST para consultar o escopo de exclusão.')
        return app.reply(start,200,_reports_delete_options(app,c,data.get('modelId')))

    if path=='/api/model-data/report-delete-scope':
        if user.get('role') not in ('master','coordenador'):
            raise HTTPError(403,'Acesso reservado ao Master e à coordenação.')
        if method!='POST':
            raise HTTPError(405,'Use POST para excluir relatórios.')
        return app.reply(start,200,_reports_delete_scope(app,c,user,data))

    return _reports_handle_v376_base(app,c,user,path,method,data,query,start,HTTPError)
'''

JS=r'''
// === REPORT SCOPED DELETE V3.7.6 ===
let reportDeleteContext=null;

function reportModelsAdminHtml(models){
 const rows=(models||[]).map(m=>
  '<tr>'+
   '<td><strong>'+esc(m.type_name)+'</strong></td>'+
   '<td>'+esc(m.activity)+(m.applied_on?'<br><small>'+esc(m.applied_on)+'</small>':'')+'</td>'+
   '<td><input data-report-model-title="'+esc(m.id)+'" value="'+esc(m.title||'')+'"><textarea data-report-model-description="'+esc(m.id)+'" rows="2" placeholder="Descrição geral">'+esc(m.description||'')+'</textarea></td>'+
   '<td><div class="report-cover-edit">'+(m.cover?'<img src="'+esc(m.cover)+'" alt="Capa">':'')+'<input data-report-model-cover="'+esc(m.id)+'" value="'+esc(m.cover||'')+'" placeholder="URL da capa ou imagem enviada"><input type="file" accept="image/*" data-report-cover-file="'+esc(m.id)+'"></div></td>'+
   '<td>'+Number(m.assignments||0)+'</td>'+
   '<td><label class="check"><input type="checkbox" data-report-model-active="'+esc(m.id)+'"'+(m.active?' checked':'')+'> Ativo</label></td>'+
   '<td><div class="actions report-model-actions"><button type="button" class="secondary" data-act="report-model-save" data-model-id="'+esc(m.id)+'">Salvar</button><button type="button" class="secondary danger" data-act="report-model-delete-open" data-model-id="'+esc(m.id)+'" data-model-title="'+esc(m.title||m.activity||'Relatório')+'">Excluir</button></div></td>'+
  '</tr>'
 ).join('');
 return '<section class="card"><h2>Modelos cadastrados</h2><p>Título, descrição e capa são informações gerais replicadas a todos os alunos vinculados ao mesmo modelo.</p><div class="table-wrap"><table><thead><tr><th>Tipo</th><th>Atividade</th><th>Informações gerais</th><th>Capa</th><th>Alunos</th><th>Status</th><th>Ações</th></tr></thead><tbody>'+rows+'</tbody></table></div></section>';
}

function reportDeleteScopeHtml(data){
 const groups=data?.classes||[];
 const model=data?.model||{};
 const groupHtml=groups.map((group,index)=>
  '<section class="report-delete-class" data-report-delete-group="'+index+'">'+
   '<label class="report-delete-class-head"><input type="checkbox" data-report-delete-class="'+index+'" value="'+esc(group.name)+'"><span><strong>'+esc(group.name)+'</strong><small>'+Number(group.count||0)+' aluno(s) com este relatório</small></span></label>'+
   '<div class="report-delete-students" data-report-delete-students="'+index+'">'+
    group.students.map(student=>
     '<label><input type="checkbox" data-report-delete-student="'+index+'" value="'+esc(student.id)+'" disabled><span>'+esc(student.name)+'<small>'+esc(student.username||'')+'</small></span></label>'
    ).join('')+
   '</div>'+
  '</section>'
 ).join('');

 return '<div class="report-delete-scope">'+
  '<div class="notice warning"><strong>Excluir '+esc(model.title||'relatório')+'</strong><p>Se nenhuma turma for selecionada, o relatório será removido de todos os alunos e o modelo será excluído.</p></div>'+
  '<p><strong>'+Number(data?.totalAssignments||0)+'</strong> vínculo(s) atualmente cadastrado(s).</p>'+
  '<p class="micro">Ao selecionar uma turma: se nenhum aluno dela for marcado, o relatório será removido de toda a turma. Se marcar alunos, será removido somente desses alunos.</p>'+
  '<div class="report-delete-class-list">'+groupHtml+'</div>'+
  '<div class="actions"><button type="button" class="secondary" data-act="report-delete-cancel">Cancelar</button><button type="button" class="primary danger" data-act="report-delete-confirm">Excluir relatório</button></div>'+
 '</div>';
}

acts['report-model-delete-open']=async el=>{
 const modelId=el?.dataset?.modelId||'';
 if(!modelId)throw new Error('Modelo de relatório não informado.');
 const data=await api('/api/model-data/report-delete-options',{modelId});
 reportDeleteContext={modelId,data};
 modal('Excluir relatório',reportDeleteScopeHtml(data),null);
};

acts['report-delete-cancel']=()=>{reportDeleteContext=null;closeModal(true);};

acts['report-delete-confirm']=async()=>{
 if(!reportDeleteContext?.modelId)throw new Error('Nenhum relatório selecionado para exclusão.');
 const data=reportDeleteContext.data||{};
 const selectedClasses=[...document.querySelectorAll('[data-report-delete-class]:checked')];
 const selections=selectedClasses.map(input=>{
  const index=input.dataset.reportDeleteClass;
  const userIds=[...document.querySelectorAll('[data-report-delete-student="'+CSS.escape(index)+'"]:checked')].map(x=>x.value);
  return {turma:input.value,userIds};
 });

 let message='';
 if(!selections.length){
  message='Nenhuma turma foi selecionada. Isso excluirá o modelo "'+(data.model?.title||'Relatório')+'" e removerá o relatório de TODOS os '+Number(data.totalAssignments||0)+' aluno(s). Confirmar?';
 }else{
  const parts=selections.map(item=>item.turma+(item.userIds.length?' · '+item.userIds.length+' aluno(s) selecionado(s)':' · turma inteira'));
  message='Confirmar a exclusão neste escopo?\n\n'+parts.join('\n');
 }
 if(!confirm(message))return;

 const result=await api('/api/model-data/report-delete-scope',{
  modelId:reportDeleteContext.modelId,
  selections
 });
 reportDeleteContext=null;
 reportAdminCache={types:result.types||[],models:result.models||[]};
 studentReportsCache.clear();
 closeModal(true);
 render();
 toast(
  'Exclusão concluída: '+Number(result.deletedAssignments||0)+' vínculo(s) removido(s).'+
  (result.modelDeleted?' Modelo excluído.':' '+Number(result.remainingAssignments||0)+' vínculo(s) permanecem.')
 );
};

document.addEventListener('change',event=>{
 const el=event.target;
 if(!el?.matches('[data-report-delete-class]'))return;
 const index=el.dataset.reportDeleteClass;
 const students=document.querySelectorAll('[data-report-delete-student="'+CSS.escape(index)+'"]');
 students.forEach(input=>{
  input.disabled=!el.checked;
  if(!el.checked)input.checked=false;
 });
 const group=document.querySelector('[data-report-delete-group="'+CSS.escape(index)+'"]');
 if(group)group.classList.toggle('selected',el.checked);
},true);
'''

CSS=r'''
/* === REPORT SCOPED DELETE V3.7.6 === */
.report-model-actions{display:flex;gap:.45rem;flex-wrap:wrap}.report-delete-scope{display:grid;gap:.9rem;min-width:min(760px,82vw)}.report-delete-class-list{display:grid;gap:.65rem;max-height:52vh;overflow:auto;padding-right:.25rem}.report-delete-class{border:1px solid var(--line);border-radius:12px;padding:.7rem;background:#fff}.report-delete-class.selected{border-color:#d6919c;background:#fffafb}.report-delete-class-head{display:flex;gap:.65rem;align-items:center;font-weight:700}.report-delete-class-head span{display:grid}.report-delete-class-head small{font-weight:400;color:var(--muted)}.report-delete-students{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:.35rem .75rem;margin-top:.65rem;padding-top:.6rem;border-top:1px solid var(--line)}.report-delete-students label{display:flex;gap:.45rem;align-items:flex-start;padding:.35rem;border-radius:8px}.report-delete-students label:has(input:disabled){opacity:.45}.report-delete-students span{display:grid;font-size:.8rem}.report-delete-students small{color:var(--muted)}.primary.danger{background:#a53d4e;color:#fff;border-color:#a53d4e}
@media(max-width:700px){.report-delete-scope{min-width:0}.report-delete-students{grid-template-columns:1fr}}
'''

def main():
    model=ROOT/'model_data.py'
    source=model.read_text(encoding='utf-8')
    if BACKEND_MARK not in source:
        model.write_text(source.rstrip()+"\n\n"+BACKEND.strip()+"\n",encoding='utf-8')

    js=STATIC/'student_summary.js'
    source=js.read_text(encoding='utf-8')
    if JS_MARK not in source:
        js.write_text(source.rstrip()+"\n\n"+JS.strip()+"\n",encoding='utf-8')

    css=STATIC/'style.css'
    source=css.read_text(encoding='utf-8')
    if CSS_MARK not in source:
        css.write_text(source.rstrip()+"\n\n"+CSS.strip()+"\n",encoding='utf-8')

    html=STATIC/'app.html'
    source=html.read_text(encoding='utf-8')
    source=re.sub(r'/static/student_summary\.js\?v=[^"\']+','/static/student_summary.js?v=3.7.6',source)
    html.write_text(source,encoding='utf-8')

    for verifier in ROOT.glob('verify_*.py'):
        source=verifier.read_text(encoding='utf-8')
        source=source.replace('/static/student_summary.js?v=3.7.5','/static/student_summary.js?v=3.7.6')
        source=source.replace('/static/student_summary.js?v=3.7.4','/static/student_summary.js?v=3.7.6')
        verifier.write_text(source,encoding='utf-8')

    site=ROOT/'site_version_release.py'
    source=site.read_text(encoding='utf-8').replace('PUBLIC_VERSION="3.7.5"','PUBLIC_VERSION="3.7.6"')
    site.write_text(source,encoding='utf-8')

    vsite=ROOT/'verify_site_version.py'
    source=vsite.read_text(encoding='utf-8').replace('v3.7.5','v3.7.6')
    vsite.write_text(source,encoding='utf-8')

    print("MEUCRONOGRAMA_REPORT_SCOPED_DELETE_READY: report models can be deleted globally, by current class, or by selected students.",flush=True)

if __name__=='__main__':
    main()
