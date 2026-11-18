'use strict';
// Importação dedicada do arquivo de duas abas.
let resultImportDraft=null;
let resultImportLastSummary=null;

function resultImportFileBase64(file){
 return file.arrayBuffer().then(buffer=>{
  const bytes=new Uint8Array(buffer),step=0x8000;
  let binary='';
  for(let i=0;i<bytes.length;i+=step)binary+=String.fromCharCode(...bytes.subarray(i,i+step));
  return btoa(binary);
 });
}

function resultImportView(){
 if(!manages())return head('Importar resultados','Acesso reservado ao Master e à coordenação.');
 const completed=resultImportLastSummary?`<div class="notice"><strong>Importação concluída.</strong> ${resultImportLastSummary.new||0} resultado(s) novo(s) e ${resultImportLastSummary.updated||0} atualizado(s). O simulado já pode ser consultado em Exportar resultados.</div>`:'';
 return head('Importar resultados','Envie o Excel com DADOS DOS ALUNOS e DADOS DO SIMULADO. Não é necessário relacionar colunas manualmente.')+
 completed+
 `<div class="notice"><strong>Fluxo correto:</strong> selecionar o arquivo → conferir o simulado → vincular os alunos às contas → confirmar. As alternativas A–E serão comparadas automaticamente com o gabarito.</div>`+
 `<section class="card"><h2>Importar MODELO DADOS.xlsx</h2><p>O arquivo deve possuir exatamente as abas <strong>DADOS DOS ALUNOS</strong> e <strong>DADOS DO SIMULADO</strong>. Use a cópia salva somente com valores, sem fórmulas, macros, proteção ou vínculos externos.</p><label>Arquivo Excel preenchido (até 3 MB)<input id="result-import-file" type="file" accept=".xlsx"></label><p id="result-import-filename">${esc(resultImportDraft?.filename||'Nenhum arquivo selecionado.')}</p><div class="actions">${button('Ler e conferir arquivo','result-import-inspect','primary')}${button('Gerar novo modelo','result-import-model','secondary')}</div><div id="result-import-inspection">${resultImportDraft?.inspection?resultImportInspection(resultImportDraft.inspection):''}</div><div id="result-import-preview" class="workbook-preview">${resultImportDraft?.preview?resultImportPreview(resultImportDraft.preview):''}</div></section>`+
 `<details class="card"><summary>Outros formatos antigos</summary><p>Arquivos antigos com colunas personalizadas continuam disponíveis na página Desempenho. O arquivo atual de duas abas não deve ser enviado pelo mapeamento manual.</p></details>`;
}

function resultImportInspection(d){
 const warnings=(d.warnings||[]).map(x=>'<li>'+esc(x)+'</li>').join('');
 return `<hr><h3>Arquivo reconhecido</h3><p><strong>${d.rows}</strong> participantes · <strong>${d.mapRows}</strong> linhas no mapa · questões ${String(d.firstQuestion).padStart(2,'0')}–${String(d.lastQuestion).padStart(2,'0')}.</p><p><strong>Simulado:</strong> ${esc(d.title)} · <strong>Cores:</strong> ${(d.colors||[]).map(esc).join(', ')}</p><div class="form-grid">${input('Data de aplicação','result-import-date',resultImportDraft?.date||d.date||'','date','required')}${check('Substituir respostas/resultados existentes','result-import-replace',!!resultImportDraft?.replace)}${check('Substituir classificações existentes do mapa','result-import-replace-map',!!resultImportDraft?.replaceMap)}</div>${warnings?'<div class="notice warning"><strong>Conferências necessárias:</strong><ul>'+warnings+'</ul></div>':''}<p class="micro">O sistema recalcula acertos e percentuais pelas respostas e pelo gabarito. A coluna % ACERTOS da planilha, quando existir, é apenas informativa.</p>${resultImportBulkAccountsPanel()}${button('Vincular alunos e gerar prévia','result-import-preview','primary')}`;
}

function resultImportPayload(){
 if(!resultImportDraft?.file)throw new Error('Selecione o Excel preenchido.');
 const bindings=Object.fromEntries($$('[data-result-import-student]').map(e=>[e.dataset.resultImportStudent,e.value]));
 return {file:resultImportDraft.file,filename:resultImportDraft.filename,date:document.querySelector('[name=result-import-date]')?.value||resultImportDraft.date||'',replace:document.querySelector('[name=result-import-replace]')?.checked??resultImportDraft.replace??false,replaceMap:document.querySelector('[name=result-import-replace-map]')?.checked??resultImportDraft.replaceMap??false,mapping:Object.keys(bindings).length?bindings:resultImportDraft.mapping||{}};
}

function resultImportPreview(d){
 const s=d.summary,warnings=(s.warnings||[]).map(x=>'<li>'+esc(x)+'</li>').join('');
 return `<hr><h3>Conferência antes de salvar</h3><p><strong>${esc(s.title)}</strong> · ${br(s.date)} · cores: ${(s.colors||[]).map(esc).join(', ')}</p><p>${s.linked} alunos vinculados; ${s.new} resultados novos; ${s.updated} atualizados; ${s.unchanged} sem mudança; ${s.conflicts} divergências preservadas, salvo substituição marcada.</p><p>Mapas: ${s.map.total} questões/versões · ${s.map.new} novas · ${s.map.updated} atualizadas · ${s.map.conflicts} divergências.</p>${warnings?'<div class="notice warning"><ul>'+warnings+'</ul></div>':''}<div class="table-wrap"><table><thead><tr><th>Aluno do arquivo</th><th>Turma</th><th>Cor</th><th>Conta no site</th></tr></thead><tbody>${d.students.map(x=>`<tr><td>${esc(x.name)}</td><td>${esc(x.group)}</td><td>${esc(x.color)}</td><td><select data-result-import-student="${esc(x.key)}"><option value="">Não importar este aluno</option>${d.accounts.map(a=>`<option value="${esc(a.id)}" ${d.mapping[x.key]===a.id?'selected':''}>${esc(a.name)} (${esc(a.username)})</option>`).join('')}</select></td></tr>`).join('')}</tbody></table></div>${s.unresolved?check('Ignorar alunos sem vínculo e importar somente os vinculados','result-import-skip',false):''}${(d.sample||[]).map(x=>'<details><summary>Prévia detalhada de '+esc(x.name)+'</summary>'+workbookAnalysis(x.analysis)+'</details>').join('')}<div class="actions">${button('Atualizar prévia','result-import-preview')}${button('Confirmar importação','result-import-confirm','primary')}</div><p id="result-import-token-state" role="status">Nenhum dado foi gravado até a confirmação.</p>`;
}

acts['result-import-model']=()=>{view='result-model';render();window.scrollTo(0,0);};
acts['model-to-results']=()=>{view='result-import';render();window.scrollTo(0,0);};
acts['result-import-inspect']=async()=>{
 if(!resultImportDraft?.file)throw new Error('Selecione o Excel preenchido.');
 const d=await api('/api/model-data/inspect',{file:resultImportDraft.file,filename:resultImportDraft.filename,date:resultImportDraft.date||''});
 resultImportDraft={...resultImportDraft,inspection:d,date:d.date||resultImportDraft.date||'',token:null,preview:null,mapping:{}};
 $('#result-import-inspection').innerHTML=resultImportInspection(d);$('#result-import-preview').innerHTML='';
};
acts['result-import-preview']=async()=>{
 const p=resultImportPayload(),d=await api('/api/model-data/preview',p);
 resultImportDraft={...p,inspection:resultImportDraft.inspection,preview:d,token:d.token,mapping:d.mapping};
 $('#result-import-preview').innerHTML=resultImportPreview(d);
};
acts['result-import-confirm']=async()=>{
 if(!resultImportDraft?.token)throw new Error('Atualize a prévia após alterar opções ou vínculos.');
 const p=resultImportPayload();p.token=resultImportDraft.token;p.skipUnmapped=document.querySelector('[name=result-import-skip]')?.checked||false;
 if(!confirm('Converter as alternativas pelo gabarito e salvar os resultados nas contas vinculadas?'))return;
 const d=await api('/api/model-data/confirm',p);
 const syncIds=[...new Set(Object.values(p.mapping||{}).filter(Boolean))];
 try{if(syncIds.length)await api('/api/model-data/review-errors-sync-batch',{targetIds:syncIds});}catch(err){console.warn('Falha ao sincronizar revisões de erros',err);}
 resultImportLastSummary=d.summary||{};resultImportDraft=null;
 if(typeof resultExportSimulations!=='undefined')resultExportSimulations=null;
 render();toast('Importação concluída: '+(d.summary.new||0)+' resultados novos; '+(d.summary.updated||0)+' atualizados.');
};

document.addEventListener('change',async e=>{
 if(e.target.id!=='result-import-file')return;
 const file=e.target.files?.[0];e.target.value='';if(!file)return;
 try{
  if(!/\.xlsx$/i.test(file.name))throw new Error('Selecione um arquivo .xlsx.');
  if(file.size>3000000)throw new Error('O arquivo excede o limite de 3 MB.');
  const encoded=await resultImportFileBase64(file);
  resultImportDraft={file:encoded,filename:file.name,date:'',replace:false,replaceMap:false,inspection:null,preview:null,token:null,mapping:{}};
  resultImportLastSummary=null;resultImportBulkResult=null;resultImportBulkPassword='';
  const name=$('#result-import-filename');if(name)name.textContent=file.name;
  const inspection=$('#result-import-inspection');if(inspection)inspection.innerHTML='';
  const preview=$('#result-import-preview');if(preview)preview.innerHTML='';
  toast('Arquivo selecionado. Clique em Ler e conferir arquivo.');
 }catch(err){toast(err.message,true);}
});


// === MEU CRONOGRAMA: CADASTRO EM LOTE DE ALUNOS ===
let resultImportBulkResult=null;
let resultImportBulkPassword='';

function resultImportBulkResultHtml(){
 const r=resultImportBulkResult;
 if(!r)return '';
 const s=r.summary||{};
 const conflicts=(r.conflicts||[]).slice(0,20).map(x=>`<li><strong>${esc(x.name)}</strong>: ${esc(x.reason)}</li>`).join('');
 const more=(r.conflicts||[]).length>20?`<p class="micro">Mais ${(r.conflicts||[]).length-20} conflito(s) não exibido(s).</p>`:'';
 return `<div class="notice ${s.conflicts?'warning':''}"><strong>${s.created||0} conta(s) criada(s); ${s.existing||0} já existente(s); ${s.conflicts||0} conflito(s).</strong>${s.duplicateRows?`<p>${s.duplicateRows} linha(s) repetida(s) no arquivo foram ignoradas.</p>`:''}${conflicts?`<ul>${conflicts}</ul>${more}`:''}${(r.created||[]).length?`<div class="actions">${button('Baixar lista de acessos','result-import-bulk-download','secondary')}</div><p class="micro">O arquivo de acessos contém a senha provisória comum definida nesta tela. Trate-o como informação confidencial.</p>`:''}</div>`;
}

function resultImportBulkAccountsPanel(){
 return `<section class="card" style="margin-top:1rem"><h3>Cadastrar contas ausentes em lote</h3><p>O sistema usa os nomes da aba <strong>DADOS DOS ALUNOS</strong>. Contas existentes são preservadas; para novos alunos, o login da planilha será usado ou será gerado automaticamente.</p><div class="form-grid">${input('Senha provisória comum para os novos alunos','result-import-bulk-password','','password','required minlength="8" maxlength="128" autocomplete="new-password"')}</div><div class="actions">${button('Criar contas ausentes e vincular','result-import-bulk-create','primary')}${button('?','result-import-bulk-help','secondary','aria-label="Explicar cadastro em lote" title="Explicar cadastro em lote"')}</div><p class="micro">Todos os novos usuários serão do perfil Aluno, ativos e obrigados a trocar a senha no primeiro acesso.</p><div id="result-import-bulk-output">${resultImportBulkResultHtml()}</div></section>`;
}

acts['result-import-bulk-help']=()=>modal(
 'Cadastro de alunos em lote',
 '<p>O arquivo atual será lido novamente. Para cada nome que ainda não possuir uma conta de Aluno, o sistema criará uma conta ativa.</p><p>Se a coluna LOGIN estiver preenchida, ela será usada. Quando estiver vazia, o login será gerado a partir do primeiro e do último nome, com numeração automática em caso de repetição.</p><p>A senha provisória é comum ao lote e deve ter pelo menos 8 caracteres. Cada aluno será obrigado a trocá-la no primeiro acesso.</p>',
 null
);

acts['result-import-bulk-create']=async()=>{
 if(!resultImportDraft?.file)throw new Error('Selecione e leia o arquivo antes de cadastrar os alunos.');
 const field=document.querySelector('[name=result-import-bulk-password]');
 const password=field?.value||'';
 if(password.length<8||password.length>128)throw new Error('A senha provisória deve ter de 8 a 128 caracteres.');
 const rows=resultImportDraft.inspection?.rows||0;
 if(!confirm(`Criar as contas de Aluno ausentes entre ${rows} participante(s), usando a senha provisória informada?`))return;
 const base=resultImportPayload();
 const result=await api('/api/accounts/bulk-from-results',{
  file:base.file,filename:base.filename,date:base.date,password
 });
 resultImportBulkResult=result;
 resultImportBulkPassword=password;
 if(field)field.value='';
 const inspection=resultImportDraft.inspection;
 const previewPayload={...base,mapping:{}};
 const preview=await api('/api/model-data/preview',previewPayload);
 resultImportDraft={...previewPayload,inspection,preview,token:preview.token,mapping:preview.mapping};
 const inspectionBox=$('#result-import-inspection');if(inspectionBox)inspectionBox.innerHTML=resultImportInspection(inspection);
 const previewBox=$('#result-import-preview');if(previewBox)previewBox.innerHTML=resultImportPreview(preview);
 toast(`${result.summary.created||0} conta(s) criada(s). ${preview.summary.linked||0} aluno(s) vinculado(s) na nova prévia.`);
};

acts['result-import-bulk-download']=()=>{
 const rows=resultImportBulkResult?.created||[];
 if(!rows.length)throw new Error('Nenhuma conta nova foi criada neste lote.');
 if(!resultImportBulkPassword)throw new Error('A senha provisória não está mais disponível nesta sessão.');
 csv('Acessos_provisorios_alunos.csv',[
  ['Nome','Login','Senha provisória','Troca obrigatória no primeiro acesso'],
  ...rows.map(x=>[x.name,x.username,resultImportBulkPassword,'SIM'])
 ]);
};

// === RESULT IMPORT LIVE STATUS V3.7.10 ===
let resultImportLiveTimer=null;

function resultImportLiveStatusHtml(stage,total,message,kind=''){
 const pct={prepare:12,sending:34,processing:68,confirming:88,done:100,error:100}[stage]??0;
 const done=stage==='done',error=stage==='error';
 return '<div class="result-import-live-status '+(kind||'')+'" aria-live="polite">'+
  '<div class="result-import-live-head"><strong>'+esc(message)+'</strong><span>'+Number(total||0)+' resultado(s)</span></div>'+
  '<div class="result-import-live-bar '+(error?'error':'')+'"><span style="width:'+pct+'%"></span></div>'+
  '<p class="micro">'+(
   done?'Importação confirmada pelo servidor.':
   error?'A importação não foi concluída.':
   'Aguarde a confirmação do servidor antes de sair desta página.'
  )+'</p>'+
 '</div>';
}

function resultImportSetLiveStatus(stage,total,message,kind=''){
 const el=document.getElementById('result-import-token-state');
 if(el)el.innerHTML=resultImportLiveStatusHtml(stage,total,message,kind);
}

acts['result-import-confirm']=async()=>{
 if(!resultImportDraft?.token)throw new Error('Atualize a prévia após alterar opções ou vínculos.');
 const p=resultImportPayload();
 p.token=resultImportDraft.token;
 p.skipUnmapped=document.querySelector('[name=result-import-skip]')?.checked||false;
 const summary=resultImportDraft?.preview?.summary||{};
 const total=Number(summary.linked||summary.new+summary.updated+summary.unchanged||resultImportDraft?.inspection?.rows||0);
 if(!confirm('Converter as alternativas pelo gabarito e salvar '+total+' resultado(s) nas contas vinculadas?'))return;

 const button=document.querySelector('[data-act="result-import-confirm"]');
 if(button){button.disabled=true;button.textContent='Importando…';}
 clearTimeout(resultImportLiveTimer);
 resultImportSetLiveStatus('prepare',total,'Preparando '+total+' resultado(s) para cadastro…');

 try{
  await new Promise(resolve=>setTimeout(resolve,180));
  resultImportSetLiveStatus('sending',total,'Enviando '+total+' resultado(s) ao servidor…');
  resultImportLiveTimer=setTimeout(()=>{
   resultImportSetLiveStatus('processing',total,'Servidor processando '+total+' resultado(s)…');
   resultImportLiveTimer=setTimeout(()=>{
    resultImportSetLiveStatus('confirming',total,'Confirmando a gravação dos resultados…');
   },1800);
  },900);

  const d=await api('/api/model-data/confirm',p);
  clearTimeout(resultImportLiveTimer);

  const s=d.summary||{};
  const processed=Number(
   s.processed ?? s.linked ??
   ((Number(s.new||0)+Number(s.updated||0)+Number(s.unchanged||0)) || total)
  );
  resultImportSetLiveStatus(
   'done',processed,
   'Concluído: '+processed+' resultado(s) processado(s) — '+Number(s.new||0)+' novo(s), '+Number(s.updated||0)+' atualizado(s)'+(Number(s.unchanged||0)?', '+Number(s.unchanged||0)+' sem mudança':'')+'.',
   'success'
  );

  resultImportLastSummary=s;
  if(typeof resultExportSimulations!=='undefined')resultExportSimulations=null;

  await new Promise(resolve=>setTimeout(resolve,750));
  resultImportDraft=null;
  render();
  toast('Importação concluída: '+Number(s.new||0)+' resultado(s) novo(s) e '+Number(s.updated||0)+' atualizado(s).');
 }catch(error){
  clearTimeout(resultImportLiveTimer);
  resultImportSetLiveStatus('error',total,error?.message||'Falha ao processar os resultados.','error');
  if(button){button.disabled=false;button.textContent='Confirmar importação';}
  throw error;
 }
};
