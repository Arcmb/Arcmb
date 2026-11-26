"use strict";
// Cadastro em lote centralizado no Painel Master/Coordenação.
let bulkAccountsDraft=null;
let bulkAccountsResult=null;
let bulkAccountsPassword='';
let bulkAccountsStage=0;
let bulkAccountsStatus='Selecione um arquivo Excel.';
let bulkAccountsStatusKind='';
let bulkAccountsBusy=false;
let bulkAccountsExactProgress=null;

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
 const stageProgress=[0,25,50,80,100][Math.max(0,Math.min(4,bulkAccountsStage))];
 const progress=bulkAccountsExactProgress===null?stageProgress:Math.max(0,Math.min(100,bulkAccountsExactProgress));
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
 return `<section class="card bulk-accounts-panel" data-bulk-accounts-panel id="bulk-accounts-panel"><h2>Cadastro de alunos em lote</h2><p>Use o mesmo Excel de resultados, com a aba <strong>DADOS DOS ALUNOS</strong>. As contas existentes são preservadas e os nomes ausentes são cadastrados como <strong>Aluno</strong>. A senha provisória vale <strong>7 dias</strong>.</p>${bulkAccountsProgressHtml()}<label>Arquivo Excel<input id="bulk-accounts-file" type="file" accept=".xlsx"></label><p id="bulk-accounts-filename" class="micro">${esc(fileName)}</p><div class="actions">${button('Ler e conferir arquivo','bulk-accounts-inspect','secondary',bulkAccountsDraft?.file&&!bulkAccountsBusy?'':'disabled')}${button('Limpar','bulk-accounts-reset','secondary',bulkAccountsBusy?'disabled':'')}</div><div id="bulk-accounts-inspection">${bulkAccountsInspectionHtml()}</div><label>Senha provisória comum para as novas contas<div class="bulk-password-row"><input id="bulk-accounts-password" name="bulk-accounts-password" type="password" minlength="8" maxlength="128" autocomplete="new-password" placeholder="Digite de 8 a 128 caracteres"><button type="button" class="secondary" data-act="bulk-accounts-toggle-password" aria-label="Mostrar senha provisória">Mostrar</button></div></label><p class="micro">A senha será aplicada somente às contas novas. Cada aluno deverá alterá-la no primeiro acesso.</p><div class="actions">${button(bulkAccountsBusy?'Processando…':'Criar contas ausentes','bulk-accounts-create','primary',inspected&&!bulkAccountsBusy?'':'disabled')}${button('?','bulk-accounts-help','secondary','aria-label="Explicar cadastro em lote" title="Explicar cadastro em lote"')}</div><div id="bulk-accounts-result">${bulkAccountsResultHtml()}</div></section>`;
}

function bulkAccountsInsertPanel(html){
 if(!html||html.includes('data-bulk-accounts-panel'))return html;
 const panel=bulkAccountsPanel();
 const markers=['<div class="card">','<section class="card">'];
 for(const marker of markers){if(html.includes(marker))return html.replace(marker,panel+marker);}
 return html+panel;
}

function bulkAccountsSetStatus(stage,message,kind='',exact=null){
 bulkAccountsStage=stage;bulkAccountsStatus=message;bulkAccountsStatusKind=kind;bulkAccountsExactProgress=exact;
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

function bulkAccountsMergeResult(total,part){
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
   for(const student of part.created||[]){
    const history=await chooseHistory(student.name,part.historyYear,student.historyCandidates||[]);
    if(history.historySource)await api('/api/history/link-profile',{target:student.id,...history});
   }
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

acts['bulk-accounts-download']=()=>{
 const rows=bulkAccountsResult?.created||[];
 if(!rows.length)throw new Error('Nenhuma conta nova foi criada neste lote.');
 if(!bulkAccountsPassword)throw new Error('A senha provisória não está mais disponível nesta sessão.');
 csv('Acessos_provisorios_alunos.csv', [['Nome','Login','Senha provisória','Troca obrigatória no primeiro acesso','Válida até'],...rows.map(x=>[x.name,x.username,bulkAccountsPassword,'SIM',new Date(Date.now()+7*864e5).toLocaleDateString('pt-BR')])]);
};

acts['bulk-accounts-return-import']=()=>{view='result-import';render();window.scrollTo(0,0);};
acts['bulk-accounts-reset']=()=>{bulkAccountsDraft=null;bulkAccountsResult=null;bulkAccountsPassword='';bulkAccountsBusy=false;bulkAccountsStage=0;bulkAccountsExactProgress=null;bulkAccountsStatus='Selecione um arquivo Excel.';bulkAccountsStatusKind='';render();};

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
  const inspect=document.querySelector('[data-act="bulk-accounts-inspect"]');if(inspect)inspect.disabled=false;
  bulkAccountsSetStatus(1,'Arquivo selecionado. Clique em Ler e conferir arquivo.','success');
 }catch(err){bulkAccountsSetStatus(0,err.message||'Arquivo inválido.','error');toast(err.message,true);}
});
