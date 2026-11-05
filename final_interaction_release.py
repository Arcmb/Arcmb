"""Finalize three interaction flows.

1. Export converted results through a JSON/base64 endpoint instead of relying on
   the legacy download helper.
2. Create student accounts in bounded chunks with real progress reporting and a
   single password hash per chunk.
3. Show an explicit control to return from an inspected student to the current
   Master/Coordinator account.
"""
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parent
STATIC = ROOT / 'static'

RETURN_JS = r'''"use strict";
// Explicit return from a managed account to the signed-in account.
function ownerReturnInstall(){
 const editing=[...document.querySelectorAll('.notice')].find(x=>/Você está editando a conta de/i.test(x.textContent||''));
 const old=document.querySelector('[data-owner-return-wrap]');
 if(!editing||!ME?.id||target===ME.id){if(old)old.remove();return;}
 if(editing.querySelector('[data-owner-return-wrap]'))return;
 const wrap=document.createElement('span');
 wrap.dataset.ownerReturnWrap='1';wrap.className='actions';wrap.style.display='inline-flex';wrap.style.marginLeft='.75rem';
 const control=document.createElement('button');control.type='button';control.className='secondary';
 control.dataset.act='return-owner';control.textContent='Voltar ao meu usuário';
 wrap.appendChild(control);editing.appendChild(wrap);
}

acts['return-owner']=async()=>{
 if(!ME?.id||target===ME.id)return;
 const open=acts['open-account'];
 if(typeof open==='function')await open({dataset:{id:ME.id}});
 else{target=ME.id;await load();view='home';render();}
};

document.addEventListener('DOMContentLoaded',ownerReturnInstall,{once:true});
window.addEventListener('load',ownerReturnInstall,{once:true});
new MutationObserver(ownerReturnInstall).observe(document.documentElement,{childList:true,subtree:true});
'''

RESULT_EXPORT_JS = r'''"use strict";
// Exportação coletiva robusta dos resultados convertidos.
let resultExportSimulations=null;
let resultExportLoading=false;
let resultExportSelected='';
let resultExportBusy=false;
let resultExportStatus='';
let resultExportStatusKind='';

async function loadResultExportSimulations(force=false){
 if(resultExportLoading)return;
 if(resultExportSimulations!==null&&!force)return;
 resultExportLoading=true;
 try{
  const data=await api('/api/model-data/simulations');
  resultExportSimulations=Array.isArray(data.simulations)?data.simulations:[];
  if(!resultExportSimulations.some(x=>x.id===resultExportSelected))resultExportSelected=resultExportSimulations[0]?.id||'';
 }finally{
  resultExportLoading=false;
  if(view==='result-export')render();
 }
}

function resultExportView(){
 if(!manages())return head('Exportar resultados','Acesso reservado ao Master e à coordenação.');
 if(resultExportSimulations===null&&!resultExportLoading)queueMicrotask(()=>loadResultExportSimulations());
 if(resultExportLoading||resultExportSimulations===null)return head('Exportar resultados','Resultados convertidos por simulado.')+'<section class="card">Carregando simulados importados…</section>';
 if(!resultExportSimulations.length)return head('Exportar resultados','Resultados convertidos por simulado.')+
  '<section class="card"><h2>Nenhum simulado importado</h2><p>Depois de confirmar uma importação, o simulado aparecerá aqui.</p><div class="actions">'+button('Atualizar lista','result-export-refresh','secondary')+'</div></section>';
 const selected=resultExportSimulations.find(x=>x.id===resultExportSelected)||resultExportSimulations[0];
 resultExportSelected=selected.id;
 const options=resultExportSimulations.map(x=>`<option value="${esc(x.id)}" ${x.id===selected.id?'selected':''}>${esc(x.activity)} · ${esc(x.date)} · ${x.participants} aluno(s)</option>`).join('');
 const status=resultExportStatus?`<div id="result-export-status" class="notice ${resultExportStatusKind}">${esc(resultExportStatus)}</div>`:'';
 return head('Exportar resultados','Escolha um simulado importado e baixe os resultados convertidos dos alunos.')+
 `<section class="card"><h2>Selecionar simulado</h2><label>Simulado<select name="result-export-simulation" ${resultExportBusy?'disabled':''}>${options}</select></label><div class="stats"><div class="stat"><strong>${selected.participants}</strong><span>aluno(s)</span></div><div class="stat"><strong>${esc(selected.date)}</strong><span>data de aplicação</span></div><div class="stat"><strong>${esc((selected.colors||[]).join(', ')||'—')}</strong><span>cores encontradas</span></div></div><div class="actions">${button(resultExportBusy?'Gerando Excel…':'Exportar resultados convertidos','result-export-download','primary',resultExportBusy?'disabled':'')}${button('Atualizar lista','result-export-refresh','secondary',resultExportBusy?'disabled':'')}</div>${status}<p class="micro">O Excel terá Resumo dos alunos, Por área, Por disciplina, Por tópico, Por assunto e Por habilidade. Habilidades iguais permanecem separadas por área.</p></section>`+
 `<section class="card"><h2>Regra utilizada</h2><p>Resposta igual ao gabarito = 1 acerto. Resposta diferente ou vazia = 0. Questão anulada ou sem gabarito fica fora do cálculo.</p><p>Nas questões 01–05 de Linguagens, o sistema utiliza a versão de Inglês ou Espanhol indicada para cada aluno.</p></section>`;
}

function resultExportSaveBase64(data){
 const encoded=String(data.content||'');
 if(!encoded)throw new Error('O servidor não retornou o conteúdo do Excel.');
 const raw=atob(encoded),bytes=new Uint8Array(raw.length);
 for(let i=0;i<raw.length;i++)bytes[i]=raw.charCodeAt(i);
 const url=URL.createObjectURL(new Blob([bytes],{type:data.mime||'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'}));
 const a=document.createElement('a');a.href=url;a.download=data.filename||'Resultados_convertidos.xlsx';
 document.body.appendChild(a);a.click();a.remove();setTimeout(()=>URL.revokeObjectURL(url),60000);
}

acts['result-export-refresh']=async()=>{if(resultExportBusy)return;resultExportSimulations=null;resultExportStatus='';await loadResultExportSimulations(true);};
acts['result-export-download']=async()=>{
 if(resultExportBusy)return;
 const selected=resultExportSimulations?.find(x=>x.id===resultExportSelected);
 if(!selected)throw new Error('Selecione um simulado.');
 resultExportBusy=true;resultExportStatus='Gerando as seis abas do Excel para '+selected.participants+' aluno(s)…';resultExportStatusKind='';render();
 try{
  const data=await api('/api/model-data/export-results-json',{activityKey:selected.activityKey,date:selected.date});
  resultExportSaveBase64(data);
  resultExportStatus='Excel gerado e enviado para a pasta de downloads do navegador.';resultExportStatusKind='success';
  toast('Resultados convertidos exportados.');
 }catch(err){resultExportStatus='Falha ao gerar o Excel: '+(err.message||'erro não identificado');resultExportStatusKind='danger';throw err;}
 finally{resultExportBusy=false;if(view==='result-export')render();}
};

document.addEventListener('change',event=>{
 if(event.target?.name!=='result-export-simulation')return;
 resultExportSelected=event.target.value;resultExportStatus='';render();
});
'''


def replace_once(text, old, new, label):
    if old not in text:
        raise RuntimeError(f'{label}: trecho esperado não encontrado.')
    return text.replace(old, new, 1)


def patch_export_backend():
    path = ROOT / 'model_data.py'
    source = path.read_text(encoding='utf-8')
    marker = "    if path == '/api/model-data/export-results' and method == 'POST':\n"
    if "'/api/model-data/export-results-json'" not in source:
        route = """    if path == '/api/model-data/export-results-json' and method == 'POST':
        _rx_role_guard(user, HTTPError)
        activity_key = F.text(data.get('activityKey'), 250)
        applied_on = F.text(data.get('date'), 40)
        if not activity_key or not applied_on:
            raise ValueError('Selecione um simulado para exportar.')
        blob, mime = result_export_workbook(app, c, user, activity_key, applied_on)
        title_row = app.db.execute(
            c, 'SELECT activity FROM hmay_performance WHERE activity_key=? AND applied_on=? ORDER BY activity LIMIT 1',
            (activity_key, applied_on),
        ).fetchone()
        title = title_row['activity'] if title_row else 'simulado'
        filename = re.sub(r'[^A-Za-z0-9_-]+', '_', title).strip('_') or 'simulado'
        import base64 as _result_export_base64
        app.event(c, user, user['id'], 'model_data_results_export')
        return app.reply(start, 200, {
            'filename': f'Resultados_convertidos_{filename}_{applied_on}.xlsx',
            'mime': mime,
            'content': _result_export_base64.b64encode(blob).decode('ascii'),
        })
"""
        source = replace_once(source, marker, route + marker, 'rota JSON da exportação')
    path.write_text(source, encoding='utf-8')


def patch_bulk_backend():
    path = ROOT / 'webapp.py'
    source = path.read_text(encoding='utf-8')
    if 'password_digest = password_hash(password)' not in source:
        source = replace_once(
            source,
            "    password = valid_password(provisional_password)\n",
            "    password = valid_password(provisional_password)\n    password_digest = password_hash(password)\n",
            'hash único por lote',
        )
        source = replace_once(
            source,
            "            (target_id, login, name, password_hash(password), 'aluno', 1, 1, stamp),\n",
            "            (target_id, login, name, password_digest, 'aluno', 1, 1, stamp),\n",
            'uso do hash único',
        )
    if "'nextOffset': next_offset" not in source:
        old = """                try:
                    result = bulk_create_student_accounts(
                        self, c, user, parsed.get('students', []), data.get('password')
                    )
                except PermissionError as exc:
                    raise HTTPError(403, str(exc))
                return self.reply(start,200,result)
"""
        new = """                all_students = parsed.get('students', [])
                try:
                    offset = max(0, int(data.get('offset', 0) or 0))
                    raw_limit = data.get('limit')
                    limit = len(all_students) if raw_limit in (None, '') else max(1, min(50, int(raw_limit)))
                except (TypeError, ValueError):
                    raise ValueError('Intervalo do lote inválido.')
                selected_students = all_students[offset:offset + limit]
                try:
                    result = bulk_create_student_accounts(
                        self, c, user, selected_students, data.get('password')
                    )
                except PermissionError as exc:
                    raise HTTPError(403, str(exc))
                processed = len(selected_students)
                next_offset = min(len(all_students), offset + processed)
                result['batch'] = {
                    'offset': offset, 'processed': processed,
                    'nextOffset': next_offset, 'total': len(all_students),
                    'done': next_offset >= len(all_students),
                }
                return self.reply(start,200,result)
"""
        source = replace_once(source, old, new, 'cadastro paginado')
    mime_anchor = "'bulk_accounts_panel.js':'application/javascript; charset=utf-8'"
    if "'return_to_owner.js':'application/javascript; charset=utf-8'" not in source:
        source = replace_once(source, mime_anchor, mime_anchor + ",'return_to_owner.js':'application/javascript; charset=utf-8'", 'MIME do retorno')
    path.write_text(source, encoding='utf-8')


def patch_bulk_ui():
    path = STATIC / 'bulk_accounts_panel.js'
    source = path.read_text(encoding='utf-8')
    if 'bulkAccountsExactProgress' not in source:
        source = replace_once(source, "let bulkAccountsBusy=false;\n", "let bulkAccountsBusy=false;\nlet bulkAccountsExactProgress=null;\n", 'estado do progresso')
        source = replace_once(source, " const progress=[0,25,50,80,100][Math.max(0,Math.min(4,bulkAccountsStage))];\n", " const stageProgress=[0,25,50,80,100][Math.max(0,Math.min(4,bulkAccountsStage))];\n const progress=bulkAccountsExactProgress===null?stageProgress:Math.max(0,Math.min(100,bulkAccountsExactProgress));\n", 'barra real')
        source = replace_once(source, "function bulkAccountsSetStatus(stage,message,kind=''){\n bulkAccountsStage=stage;bulkAccountsStatus=message;bulkAccountsStatusKind=kind;\n", "function bulkAccountsSetStatus(stage,message,kind='',exact=null){\n bulkAccountsStage=stage;bulkAccountsStatus=message;bulkAccountsStatusKind=kind;bulkAccountsExactProgress=exact;\n", 'status percentual')
    pattern = re.compile(r"acts\['bulk-accounts-create'\]=async\(\)=>\{.*?\n\};\n\nacts\['bulk-accounts-download'\]", re.S)
    if 'Perfis processados:' not in source:
        replacement = r'''function bulkAccountsMergeResult(total,part){
 const merged=total||{created:[],existing:[],conflicts:[],duplicateRows:0,summary:{rows:0,uniqueNames:0,created:0,existing:0,conflicts:0,duplicateRows:0}};
 merged.created.push(...(part.created||[]));merged.existing.push(...(part.existing||[]));merged.conflicts.push(...(part.conflicts||[]));
 merged.duplicateRows+=(part.duplicateRows||0);merged.summary.rows=part.batch?.total||merged.summary.rows||0;merged.summary.uniqueNames=merged.summary.rows;
 merged.summary.created=merged.created.length;merged.summary.existing=merged.existing.length;merged.summary.conflicts=merged.conflicts.length;merged.summary.duplicateRows=merged.duplicateRows;
 return merged;
}

acts['bulk-accounts-create']=async()=>{
 if(!bulkAccountsDraft?.inspection)throw new Error('Leia e confira o arquivo antes de criar as contas.');
 const field=document.getElementById('bulk-accounts-password');const password=field?.value||'';
 if(password.length<8||password.length>128)throw new Error('A senha provisória deve ter de 8 a 128 caracteres.');
 const rows=bulkAccountsDraft.inspection.rows||0;
 if(!confirm(`Criar somente as contas de Aluno ausentes entre ${rows} participante(s)?`))return;
 bulkAccountsBusy=true;bulkAccountsPassword=password;bulkAccountsResult=null;
 const create=document.querySelector('[data-act="bulk-accounts-create"]');if(create){create.disabled=true;create.textContent='Processando…';}
 try{
  const chunkSize=25;let offset=0;let aggregate=null;
  bulkAccountsSetStatus(2,`Preparando ${rows} perfil(is) para cadastro…`,'',0);
  while(offset<rows){
   const end=Math.min(rows,offset+chunkSize);
   bulkAccountsSetStatus(2,`Criando perfis ${offset+1} a ${end} de ${rows}…`,'',Math.round(100*offset/Math.max(rows,1)));
   const part=await api('/api/accounts/bulk-from-results',{file:bulkAccountsDraft.file,filename:bulkAccountsDraft.filename,date:bulkAccountsDraft.date||'',password,offset,limit:chunkSize});
   aggregate=bulkAccountsMergeResult(aggregate,part);
   const next=Number(part.batch?.nextOffset);offset=Number.isFinite(next)&&next>offset?next:end;
   bulkAccountsResult=aggregate;
   const output=document.getElementById('bulk-accounts-result');if(output)output.innerHTML=bulkAccountsResultHtml();
   bulkAccountsSetStatus(2,`Perfis processados: ${offset}/${rows} — ${aggregate.summary.created} criado(s), ${aggregate.summary.existing} existente(s), ${aggregate.summary.conflicts} conflito(s).`,'',Math.round(100*offset/Math.max(rows,1)));
   await new Promise(resolve=>setTimeout(resolve,0));
  }
  bulkAccountsResult=aggregate||bulkAccountsMergeResult(null,{batch:{total:rows}});
  bulkAccountsSetStatus(3,'Todos os perfis foram processados. Atualizando a lista de contas e os vínculos…','',100);
  try{await refreshAccounts();}catch(_){}
  if(typeof resultImportDraft!=='undefined'&&resultImportDraft?.file===bulkAccountsDraft.file){
   const p={file:resultImportDraft.file,filename:resultImportDraft.filename,date:resultImportDraft.date||resultImportDraft.inspection?.date||bulkAccountsDraft.date||'',replace:resultImportDraft.replace||false,replaceMap:resultImportDraft.replaceMap||false,mapping:{}};
   try{const preview=await api('/api/model-data/preview',p);resultImportDraft={...p,inspection:resultImportDraft.inspection||bulkAccountsDraft.inspection,preview,token:preview.token,mapping:preview.mapping};}catch(_){}
  }
  if(field)field.value='';bulkAccountsBusy=false;bulkAccountsStage=4;bulkAccountsExactProgress=100;
  bulkAccountsStatus=`Concluído: ${bulkAccountsResult.summary.created||0} conta(s) criada(s), ${bulkAccountsResult.summary.existing||0} já existente(s) e ${bulkAccountsResult.summary.conflicts||0} conflito(s).`;
  bulkAccountsStatusKind=bulkAccountsResult.summary.conflicts?'warning':'success';render();toast(`${bulkAccountsResult.summary.created||0} conta(s) criada(s).`);
 }catch(err){bulkAccountsBusy=false;bulkAccountsSetStatus(2,err.message||'Não foi possível criar as contas.','error');if(create){create.disabled=false;create.textContent='Criar contas ausentes';}throw err;}
};

acts['bulk-accounts-download']'''
        source, count = pattern.subn(replacement, source, count=1)
        if count != 1:
            raise RuntimeError('Ação de cadastro em lote não encontrada.')
    source = source.replace("bulkAccountsBusy=false;bulkAccountsStage=0;bulkAccountsStatus='Selecione um arquivo Excel.';bulkAccountsStatusKind='';render();", "bulkAccountsBusy=false;bulkAccountsStage=0;bulkAccountsExactProgress=null;bulkAccountsStatus='Selecione um arquivo Excel.';bulkAccountsStatusKind='';render();")
    path.write_text(source, encoding='utf-8')


def patch_assets():
    (STATIC / 'result_export.js').write_text(RESULT_EXPORT_JS, encoding='utf-8')
    (STATIC / 'return_to_owner.js').write_text(RETURN_JS, encoding='utf-8')
    html_path = STATIC / 'app.html'
    html = html_path.read_text(encoding='utf-8')
    html = html.replace('/static/result_export.js?v=2.8.3', '/static/result_export.js?v=2.8.9')
    html = html.replace('/static/bulk_accounts_panel.js?v=2.8.6', '/static/bulk_accounts_panel.js?v=2.8.9')
    if '/static/return_to_owner.js?v=2.8.9' not in html:
        html = html.replace('</body>', '<script src="/static/return_to_owner.js?v=2.8.9" defer></script>\n</body>')
    html_path.write_text(html, encoding='utf-8')


def main():
    patch_export_backend()
    patch_bulk_backend()
    patch_bulk_ui()
    patch_assets()
    print('MEUCRONOGRAMA_FINAL_INTERACTIONS_READY: robust Excel export, real bulk progress and owner return prepared.')


if __name__ == '__main__':
    main()
