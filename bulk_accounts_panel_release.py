"""Centralize bulk student-account creation in the account administration panel.

The existing secure backend route is reused. This release adds:
- a Master/Coordinator panel for reading DADOS DOS ALUNOS;
- provisional-password visibility control;
- explicit progress stages;
- automatic refresh and return to the result import flow.
"""
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parent
STATIC = ROOT / 'static'
JS_NAME = 'bulk_accounts_panel.js'
JS_URL = '/static/bulk_accounts_panel.js?v=2.8.6'
JS_MIME = "'bulk_accounts_panel.js':'application/javascript; charset=utf-8'"
CSS_MARKER = '/* MEU CRONOGRAMA: PAINEL DE CONTAS EM LOTE */'

JS_SOURCE = r'''"use strict";
// Cadastro em lote centralizado no Painel Master/Coordenação.
let bulkAccountsDraft=null;
let bulkAccountsResult=null;
let bulkAccountsPassword='';
let bulkAccountsStage=0;
let bulkAccountsStatus='Selecione um arquivo Excel.';
let bulkAccountsStatusKind='';
let bulkAccountsBusy=false;

function bulkAccountsFileBase64(file){
 return file.arrayBuffer().then(buffer=>{
  const bytes=new Uint8Array(buffer),step=0x8000;
  let binary='';
  for(let i=0;i<bytes.length;i+=step)binary+=String.fromCharCode(...bytes.subarray(i,i+step));
  return btoa(binary);
 });
}

function bulkAccountsProgressHtml(){
 const labels=['Selecionar arquivo','Conferir alunos','Criar contas','Atualizar painel','Concluído'];
 const progress=[0,25,50,80,100][Math.max(0,Math.min(4,bulkAccountsStage))];
 return `<div class="bulk-account-progress-wrap"><div class="bulk-account-progress-bar" aria-hidden="true"><span style="width:${progress}%"></span></div><ol class="bulk-account-progress">${labels.map((label,index)=>`<li class="${index<bulkAccountsStage?'done':index===bulkAccountsStage?'current':'pending'}"><span>${index+1}</span>${esc(label)}</li>`).join('')}</ol><p id="bulk-accounts-status" class="bulk-account-status ${bulkAccountsStatusKind}" role="status" aria-live="polite">${esc(bulkAccountsStatus)}</p></div>`;
}

function bulkAccountsInspectionHtml(){
 const d=bulkAccountsDraft?.inspection;
 if(!d)return '<p class="micro">O arquivo ainda não foi conferido.</p>';
 return `<div class="notice"><strong>Arquivo reconhecido.</strong><p>${d.rows||0} participante(s) · ${d.mapRows||0} linha(s) no mapa · questões ${String(d.firstQuestion||0).padStart(2,'0')}–${String(d.lastQuestion||0).padStart(2,'0')}.</p><p><strong>Simulado:</strong> ${esc(d.title||'Não informado')} · <strong>Cores:</strong> ${(d.colors||[]).map(esc).join(', ')||'não informadas'}</p></div>`;
}

function bulkAccountsResultHtml(){
 const r=bulkAccountsResult;
 if(!r)return '';
 const s=r.summary||{};
 const created=(r.created||[]).slice(0,20).map(x=>`<li>${esc(x.name)} — <strong>${esc(x.username)}</strong></li>`).join('');
 const conflicts=(r.conflicts||[]).slice(0,20).map(x=>`<li><strong>${esc(x.name)}</strong>: ${esc(x.reason)}</li>`).join('');
 return `<div class="notice ${s.conflicts?'warning':''}"><strong>${s.created||0} conta(s) criada(s); ${s.existing||0} já existente(s); ${s.conflicts||0} conflito(s).</strong>${s.duplicateRows?`<p>${s.duplicateRows} linha(s) repetida(s) foram ignoradas.</p>`:''}${created?`<details><summary>Logins criados</summary><ul>${created}</ul>${(r.created||[]).length>20?`<p class="micro">Mais ${(r.created||[]).length-20} conta(s) constam na lista para download.</p>`:''}</details>`:''}${conflicts?`<details open><summary>Conflitos que exigem revisão</summary><ul>${conflicts}</ul>${(r.conflicts||[]).length>20?`<p class="micro">Mais ${(r.conflicts||[]).length-20} conflito(s) não exibido(s).</p>`:''}</details>`:''}<div class="actions">${(r.created||[]).length?button('Baixar lista de acessos','bulk-accounts-download','secondary'):''}${bulkAccountsDraft?.fromResultImport?button('Voltar à importação de resultados','bulk-accounts-return-import','primary'):''}${button('Iniciar outro lote','bulk-accounts-reset','secondary')}</div></div>`;
}

function bulkAccountsPanel(){
 if(!manages())return '';
 const inspected=!!bulkAccountsDraft?.inspection;
 const fileName=bulkAccountsDraft?.filename||'Nenhum arquivo selecionado.';
 return `<section class="card bulk-accounts-panel" data-bulk-accounts-panel id="bulk-accounts-panel"><h2>Cadastro de alunos em lote</h2><p>Use o mesmo Excel de resultados, com a aba <strong>DADOS DOS ALUNOS</strong>. As contas existentes são preservadas e os nomes ausentes são cadastrados como <strong>Aluno</strong>.</p>${bulkAccountsProgressHtml()}<label>Arquivo Excel<input id="bulk-accounts-file" type="file" accept=".xlsx"></label><p id="bulk-accounts-filename" class="micro">${esc(fileName)}</p><div class="actions">${button('Ler e conferir arquivo','bulk-accounts-inspect','secondary',bulkAccountsDraft?.file&&!bulkAccountsBusy?'':'disabled')}${button('Limpar','bulk-accounts-reset','secondary',bulkAccountsBusy?'disabled':'')}</div><div id="bulk-accounts-inspection">${bulkAccountsInspectionHtml()}</div><label>Senha provisória comum para as novas contas<div class="bulk-password-row"><input id="bulk-accounts-password" name="bulk-accounts-password" type="password" minlength="8" maxlength="128" autocomplete="new-password" placeholder="Digite de 8 a 128 caracteres"><button type="button" class="secondary" data-act="bulk-accounts-toggle-password" aria-label="Mostrar senha provisória">Mostrar</button></div></label><p class="micro">A senha será aplicada somente às contas novas. Cada aluno deverá alterá-la no primeiro acesso.</p><div class="actions">${button(bulkAccountsBusy?'Processando…':'Criar contas ausentes','bulk-accounts-create','primary',inspected&&!bulkAccountsBusy?'':'disabled')}${button('?','bulk-accounts-help','secondary','aria-label="Explicar cadastro em lote" title="Explicar cadastro em lote"')}</div><div id="bulk-accounts-result">${bulkAccountsResultHtml()}</div></section>`;
}

function bulkAccountsInsertPanel(html){
 if(!html||html.includes('data-bulk-accounts-panel'))return html;
 const panel=bulkAccountsPanel();
 const markers=['<div class="card">','<section class="card">'];
 for(const marker of markers){if(html.includes(marker))return html.replace(marker,panel+marker);}
 return html+panel;
}

function bulkAccountsSetStatus(stage,message,kind=''){
 bulkAccountsStage=stage;bulkAccountsStatus=message;bulkAccountsStatusKind=kind;
 const wrap=document.querySelector('#bulk-accounts-panel .bulk-account-progress-wrap');
 if(wrap)wrap.outerHTML=bulkAccountsProgressHtml();
}

const bulkAccountsOriginalAccountsView=accountsView;
accountsView=function(){return bulkAccountsInsertPanel(bulkAccountsOriginalAccountsView());};
if(typeof coordinatorView==='function'){
 const bulkAccountsOriginalCoordinatorView=coordinatorView;
 coordinatorView=function(){return bulkAccountsInsertPanel(bulkAccountsOriginalCoordinatorView());};
}

// O importador passa a apontar para o cadastro centralizado, evitando dois fluxos concorrentes.
if(typeof resultImportBulkAccountsPanel==='function'){
 resultImportBulkAccountsPanel=function(){
  return `<section class="card" style="margin-top:1rem"><h3>Contas dos alunos</h3><p>O cadastro em lote foi centralizado no Painel Master/Coordenação. O arquivo selecionado pode ser encaminhado para lá sem nova seleção.</p><div class="actions">${button('Abrir cadastro em lote','bulk-accounts-open','primary')}</div></section>`;
 };
}

acts['bulk-accounts-open']=()=>{
 if(typeof resultImportDraft!=='undefined'&&resultImportDraft?.file){
  bulkAccountsDraft={file:resultImportDraft.file,filename:resultImportDraft.filename,date:resultImportDraft.date||resultImportDraft.inspection?.date||'',inspection:resultImportDraft.inspection||null,fromResultImport:true};
  bulkAccountsStage=bulkAccountsDraft.inspection?2:1;
  bulkAccountsStatus=bulkAccountsDraft.inspection?'Arquivo já conferido. Defina a senha e crie as contas ausentes.':'Arquivo recebido da importação. Clique em Ler e conferir arquivo.';
  bulkAccountsStatusKind='';bulkAccountsResult=null;
 }
 view='accounts';render();window.scrollTo(0,0);
 setTimeout(()=>document.getElementById('bulk-accounts-panel')?.scrollIntoView({behavior:'smooth',block:'start'}),50);
};

acts['bulk-accounts-toggle-password']=el=>{
 const field=document.getElementById('bulk-accounts-password');if(!field)return;
 const show=field.type==='password';field.type=show?'text':'password';
 el.textContent=show?'Ocultar':'Mostrar';el.setAttribute('aria-label',show?'Ocultar senha provisória':'Mostrar senha provisória');
};

acts['bulk-accounts-help']=()=>modal('Cadastro de alunos em lote','<p><strong>Etapa 1:</strong> selecione o Excel que contém DADOS DOS ALUNOS.</p><p><strong>Etapa 2:</strong> confira a quantidade de participantes reconhecidos.</p><p><strong>Etapa 3:</strong> defina a senha provisória e crie apenas as contas ausentes.</p><p><strong>Etapa 4:</strong> o sistema atualiza a lista de contas e, quando o arquivo veio da importação de resultados, refaz o vínculo pelos nomes.</p><p>Contas existentes não são alteradas. O login da planilha é usado quando válido; caso esteja vazio, um login é gerado automaticamente.</p>',null);

acts['bulk-accounts-inspect']=async()=>{
 if(!bulkAccountsDraft?.file)throw new Error('Selecione o arquivo Excel.');
 bulkAccountsBusy=true;bulkAccountsSetStatus(1,'Lendo e validando as abas do arquivo…');
 try{
  const d=await api('/api/model-data/inspect',{file:bulkAccountsDraft.file,filename:bulkAccountsDraft.filename,date:bulkAccountsDraft.date||''});
  bulkAccountsDraft={...bulkAccountsDraft,inspection:d,date:d.date||bulkAccountsDraft.date||''};
  bulkAccountsResult=null;
  const box=document.getElementById('bulk-accounts-inspection');if(box)box.innerHTML=bulkAccountsInspectionHtml();
  const create=document.querySelector('[data-act="bulk-accounts-create"]');if(create)create.disabled=false;
  bulkAccountsSetStatus(2,`${d.rows||0} participante(s) reconhecido(s). Defina a senha provisória e prossiga.`,'success');
 }catch(err){bulkAccountsSetStatus(1,err.message||'Não foi possível conferir o arquivo.','error');throw err;}
 finally{bulkAccountsBusy=false;}
};

acts['bulk-accounts-create']=async()=>{
 if(!bulkAccountsDraft?.inspection)throw new Error('Leia e confira o arquivo antes de criar as contas.');
 const field=document.getElementById('bulk-accounts-password');const password=field?.value||'';
 if(password.length<8||password.length>128)throw new Error('A senha provisória deve ter de 8 a 128 caracteres.');
 const rows=bulkAccountsDraft.inspection.rows||0;
 if(!confirm(`Criar somente as contas de Aluno ausentes entre ${rows} participante(s)?`))return;
 bulkAccountsBusy=true;bulkAccountsPassword=password;bulkAccountsSetStatus(2,'Preparando o cadastro seguro…');
 const create=document.querySelector('[data-act="bulk-accounts-create"]');if(create){create.disabled=true;create.textContent='Processando…';}
 try{
  bulkAccountsSetStatus(3,`Criando as contas ausentes entre ${rows} participante(s)…`);
  const result=await api('/api/accounts/bulk-from-results',{file:bulkAccountsDraft.file,filename:bulkAccountsDraft.filename,date:bulkAccountsDraft.date||'',password});
  bulkAccountsResult=result;
  bulkAccountsSetStatus(4,'Contas processadas. Atualizando o painel e os vínculos…');
  try{await refreshAccounts();}catch(_){/* A criação já foi confirmada no servidor. */}
  if(typeof resultImportDraft!=='undefined'&&resultImportDraft?.file===bulkAccountsDraft.file){
   const p={file:resultImportDraft.file,filename:resultImportDraft.filename,date:resultImportDraft.date||resultImportDraft.inspection?.date||bulkAccountsDraft.date||'',replace:resultImportDraft.replace||false,replaceMap:resultImportDraft.replaceMap||false,mapping:{}};
   try{
    const preview=await api('/api/model-data/preview',p);
    resultImportDraft={...p,inspection:resultImportDraft.inspection||bulkAccountsDraft.inspection,preview,token:preview.token,mapping:preview.mapping};
   }catch(_){/* O usuário poderá gerar a prévia novamente na página de importação. */}
  }
  if(field)field.value='';
  bulkAccountsBusy=false;bulkAccountsStage=4;bulkAccountsStatus=`Concluído: ${result.summary?.created||0} conta(s) criada(s), ${result.summary?.existing||0} já existente(s) e ${result.summary?.conflicts||0} conflito(s).`;bulkAccountsStatusKind=result.summary?.conflicts?'warning':'success';
  render();
  toast(`${result.summary?.created||0} conta(s) criada(s).`);
 }catch(err){bulkAccountsBusy=false;bulkAccountsSetStatus(2,err.message||'Não foi possível criar as contas.','error');if(create){create.disabled=false;create.textContent='Criar contas ausentes';}throw err;}
};

acts['bulk-accounts-download']=()=>{
 const rows=bulkAccountsResult?.created||[];
 if(!rows.length)throw new Error('Nenhuma conta nova foi criada neste lote.');
 if(!bulkAccountsPassword)throw new Error('A senha provisória não está mais disponível nesta sessão.');
 csv('Acessos_provisorios_alunos.csv', [['Nome','Login','Senha provisória','Troca obrigatória no primeiro acesso'],...rows.map(x=>[x.name,x.username,bulkAccountsPassword,'SIM'])]);
};

acts['bulk-accounts-return-import']=()=>{view='result-import';render();window.scrollTo(0,0);};
acts['bulk-accounts-reset']=()=>{bulkAccountsDraft=null;bulkAccountsResult=null;bulkAccountsPassword='';bulkAccountsBusy=false;bulkAccountsStage=0;bulkAccountsStatus='Selecione um arquivo Excel.';bulkAccountsStatusKind='';render();};

document.addEventListener('change',async event=>{
 if(event.target.id!=='bulk-accounts-file')return;
 const file=event.target.files?.[0];event.target.value='';if(!file)return;
 try{
  if(!/\.xlsx$/i.test(file.name))throw new Error('Selecione um arquivo .xlsx.');
  if(file.size>3000000)throw new Error('O arquivo excede o limite de 3 MB.');
  bulkAccountsSetStatus(0,'Preparando o arquivo selecionado…');
  const encoded=await bulkAccountsFileBase64(file);
  bulkAccountsDraft={file:encoded,filename:file.name,date:'',inspection:null,fromResultImport:false};bulkAccountsResult=null;bulkAccountsPassword='';
  const name=document.getElementById('bulk-accounts-filename');if(name)name.textContent=file.name;
  const inspection=document.getElementById('bulk-accounts-inspection');if(inspection)inspection.innerHTML=bulkAccountsInspectionHtml();
  const create=document.querySelector('[data-act="bulk-accounts-create"]');if(create)create.disabled=true;
  bulkAccountsSetStatus(1,'Arquivo selecionado. Clique em Ler e conferir arquivo.','success');
 }catch(err){bulkAccountsSetStatus(0,err.message||'Arquivo inválido.','error');toast(err.message,true);}
});
'''

CSS_SOURCE = r'''
/* MEU CRONOGRAMA: PAINEL DE CONTAS EM LOTE */
.bulk-password-row{display:grid;grid-template-columns:minmax(0,1fr) auto;gap:.55rem;align-items:center}
.bulk-password-row input{min-width:0}
.bulk-account-progress-wrap{margin:1rem 0;padding:1rem;border:1px solid var(--border,#ddd);border-radius:14px;background:rgba(255,255,255,.45)}
.bulk-account-progress-bar{height:.45rem;border-radius:999px;background:rgba(80,65,145,.13);overflow:hidden;margin-bottom:.8rem}
.bulk-account-progress-bar span{display:block;height:100%;background:var(--primary,#6553b5);transition:width .25s ease}
.bulk-account-progress{display:grid;grid-template-columns:repeat(5,minmax(0,1fr));gap:.45rem;list-style:none;padding:0;margin:0}
.bulk-account-progress li{font-size:.78rem;line-height:1.25;color:var(--muted,#6c6880);display:flex;align-items:center;gap:.35rem;min-width:0}
.bulk-account-progress li span{display:inline-grid;place-items:center;flex:0 0 1.45rem;height:1.45rem;border-radius:999px;background:rgba(80,65,145,.12);font-weight:700}
.bulk-account-progress li.done,.bulk-account-progress li.current{color:var(--text,#1e1935);font-weight:650}
.bulk-account-progress li.done span,.bulk-account-progress li.current span{background:var(--primary,#6553b5);color:#fff}
.bulk-account-status{margin:.8rem 0 0;font-weight:600}
.bulk-account-status.error{color:#a52828}.bulk-account-status.warning{color:#805b00}.bulk-account-status.success{color:#1b6b45}
@media(max-width:760px){.bulk-account-progress{grid-template-columns:1fr}.bulk-password-row{grid-template-columns:1fr}.bulk-password-row button{width:100%}}
'''


def insert_js_mime(source: str) -> str:
    if JS_MIME in source:
        return source
    entries = list(re.finditer(r"'[^'\n]+\.js'\s*:\s*'application/javascript; charset=utf-8'", source))
    if not entries:
        raise RuntimeError('JavaScript static MIME allowlist was not found.')
    anchor = entries[-1]
    return source[:anchor.end()] + ',' + JS_MIME + source[anchor.end():]


def prepare():
    STATIC.mkdir(parents=True, exist_ok=True)
    (STATIC / JS_NAME).write_text(JS_SOURCE, encoding='utf-8')

    css_path = STATIC / 'style.css'
    css = css_path.read_text(encoding='utf-8')
    if CSS_MARKER not in css:
        css += '\n' + CSS_SOURCE + '\n'
    css_path.write_text(css, encoding='utf-8')

    html_path = STATIC / 'app.html'
    html = html_path.read_text(encoding='utf-8')
    if JS_URL not in html:
        html = html.replace('</body>', f'<script src="{JS_URL}" defer></script>\n</body>', 1)
    html_path.write_text(html, encoding='utf-8')

    webapp_path = ROOT / 'webapp.py'
    webapp_path.write_text(insert_js_mime(webapp_path.read_text(encoding='utf-8')), encoding='utf-8')
    print('MEUCRONOGRAMA_BULK_ACCOUNTS_PANEL_READY: master/coordinator panel, password visibility and progress stages prepared.', flush=True)


if __name__ == '__main__':
    prepare()
