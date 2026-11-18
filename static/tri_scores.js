"use strict";
// Importação opcional de Ranking/Ranking Geral e exibição das notas TRI.
let triImportDraft=null,triImportBusy=false,triImportPreviewData=null;

function triFileBase64(file){
 if(typeof resultImportFileBase64==='function')return resultImportFileBase64(file);
 return file.arrayBuffer().then(buffer=>{const bytes=new Uint8Array(buffer),step=0x8000;let binary='';for(let i=0;i<bytes.length;i+=step)binary+=String.fromCharCode(...bytes.subarray(i,i+step));return btoa(binary);});
}
function triScore(value){const n=Number(value);return Number.isFinite(n)?n:null;}
function triFormat(value,digits=1){const n=triScore(value);return n===null?'—':n.toLocaleString('pt-BR',{minimumFractionDigits:digits,maximumFractionDigits:digits});}
function triSelectedSimulation(){const id=document.querySelector('[name=tri-import-simulation]')?.value||triImportDraft?.simulationId||'';return (triImportDraft?.simulations||[]).find(x=>x.id===id)||null;}
function triColumnsText(columns){return Object.entries(columns||{}).map(([key,value])=>`<span class="student-home-chip"><strong>${esc(value)}</strong></span>`).join('');}
function triImportStatus(){
 if(!triImportDraft?.inspection)return '';
 const d=triImportDraft.inspection,options=(d.simulations||[]).map(x=>`<option value="${esc(x.id)}" ${(triImportDraft.simulationId||d.simulations?.[0]?.id)===x.id?'selected':''}>${esc(x.activity)} · ${esc(x.date)} · ${x.participants} aluno(s)</option>`).join('');
 const sample=(d.sample||[]).slice(0,8).map(x=>`<tr><td>${esc(x.name)}</td><td>${triFormat(x.scores?.tri)}</td><td>${triFormat(x.scores?.lc)}</td><td>${triFormat(x.scores?.ch)}</td><td>${triFormat(x.scores?.cn)}</td><td>${triFormat(x.scores?.mt)}</td><td>${triFormat(x.scores?.redaction,0)}</td></tr>`).join('');
 return `<hr><h3>Aba reconhecida: ${esc(d.sheet)}</h3><p><strong>${d.rows}</strong> linha(s) com nota · cabeçalho na linha ${d.headerRow}.</p><div class="student-home-chips">${triColumnsText(d.columns)}</div><label>Vincular ao simulado<select name="tri-import-simulation">${options}</select></label><p class="micro">${esc(d.notice||'')}</p>${sample?`<div class="table-wrap"><table><thead><tr><th>Aluno</th><th>TRI geral</th><th>Linguagens</th><th>Humanas</th><th>Natureza</th><th>Matemática</th><th>Redação</th></tr></thead><tbody>${sample}</tbody></table></div>`:''}<div class="actions">${button('Conferir vínculos das notas','tri-import-preview','primary')}</div><div id="tri-import-preview">${triImportPreviewData?triImportPreviewHtml(triImportPreviewData):''}</div>`;
}
function triImportPreviewHtml(d){
 const sample=(d.sample||[]).map(x=>`<tr><td>${esc(x.name)}</td><td>${esc(x.login||'')}</td><td>${triFormat(x.tri)}</td><td>${triFormat(x.lc)}</td><td>${triFormat(x.ch)}</td><td>${x.changed?'Atualizar':'Sem mudança'}</td></tr>`).join('');
 const warnings=[];if(d.unmatched)warnings.push(`${d.unmatched} nome(s) do ranking não encontrados no simulado.`);if(d.conflicts)warnings.push(`${d.conflicts} conflito(s) de nomes repetidos.`);if(d.withoutScore)warnings.push(`${d.withoutScore} aluno(s) do simulado sem linha de nota no ranking.`);
 return `<div class="notice ${warnings.length?'warning':'success'}"><strong>${d.matched}/${d.students}</strong> aluno(s) vinculados · ${d.changed} atualização(ões) · ${d.unchanged} sem mudança.${warnings.length?'<br>'+warnings.map(esc).join(' '):''}</div>${sample?`<div class="table-wrap"><table><thead><tr><th>Aluno</th><th>Login</th><th>TRI geral</th><th>TRI LC</th><th>TRI CH</th><th>Situação</th></tr></thead><tbody>${sample}</tbody></table></div>`:''}<div class="actions">${button(triImportBusy?'Salvando notas…':'Confirmar vínculo das notas TRI','tri-import-confirm','primary',triImportBusy?'disabled':'')}</div>`;
}
function triImportCard(){
 if(!manages())return '';
 return `<section class="card"><h2>Importar Ranking e notas TRI <button type="button" class="help-button" data-act="tri-import-help" aria-label="Explicar notas TRI">?</button></h2><p>Selecione o Excel original que contém uma aba <strong>Ranking Geral</strong> ou <strong>Ranking</strong>. O sistema procura RANKING, TRI, TRI LING, TRI HUM, TRI NAT, TRI MAT e RED e vincula pelos nomes dos alunos.</p><label>Arquivo de ranking (.xlsx, até 8 MB)<input id="tri-import-file" type="file" accept=".xlsx"></label><p id="tri-import-filename">${esc(triImportDraft?.filename||'Nenhum arquivo selecionado.')}</p><div class="actions">${button('Ler Ranking Geral','tri-import-inspect','primary')}${button('Limpar','tri-import-clear','secondary')}</div><div id="tri-import-status">${triImportStatus()}</div></section>`;
}

if(typeof resultImportView==='function'){
 const triOriginalResultImportView=resultImportView;
 resultImportView=function(){return triOriginalResultImportView()+triImportCard();};
}

acts['tri-import-help']=()=>modal('Notas TRI por simulado','<p><strong>TCT/acertos</strong> continuam sendo calculados pelas respostas e pelo gabarito.</p><p><strong>TRI</strong> é importada separadamente da aba Ranking/Ranking Geral e fica vinculada ao mesmo aluno, simulado e data.</p><p>O motor matemático usa prioritariamente os erros por disciplina, tópico, assunto e habilidade. A nota TRI é exibida na trajetória e na exportação, sem duplicar o peso dos mesmos acertos.</p>',null);
acts['tri-import-clear']=()=>{triImportDraft=null;triImportPreviewData=null;render();};
acts['tri-import-inspect']=async()=>{
 if(!triImportDraft?.file)throw new Error('Selecione o Excel de ranking.');
 triImportBusy=true;try{const d=await api('/api/model-data/tri-inspect',{file:triImportDraft.file,filename:triImportDraft.filename});triImportDraft={...triImportDraft,inspection:d,simulations:d.simulations||[],simulationId:d.simulations?.[0]?.id||''};triImportPreviewData=null;}finally{triImportBusy=false;render();}
};
acts['tri-import-preview']=async()=>{
 const sim=triSelectedSimulation();if(!sim)throw new Error('Selecione o simulado que receberá as notas.');
 triImportDraft.simulationId=sim.id;triImportBusy=true;try{triImportPreviewData=await api('/api/model-data/tri-preview',{file:triImportDraft.file,filename:triImportDraft.filename,activityKey:sim.activityKey,date:sim.date});render();}finally{triImportBusy=false;}
};
// === TRI IMPORT STABILITY V2 ===
let triImportSaveSummary=null;
let triImportProcess=null;
let triImportProcessTimer=null;

function triImportIssueName(x){
 if(typeof x==='string')return x;
 return x?.name||x?.student_name||x?.target?.student_name||x?.source?.name||'Registro não identificado';
}
function triImportSavedSummaryHtml(){
 const d=triImportSaveSummary;if(!d)return '';
 const s=d.summary||{},issues=d.issues||{};
 const blocks=[
  ['Não encontrados',issues.unmatchedNames||[]],
  ['Conflitos de nome',issues.conflictRows||[]],
  ['Sem nota no arquivo',issues.withoutScoreNames||[]]
 ].filter(x=>x[1].length);
 const detail=blocks.map(([title,values])=>'<div class="tri-import-issue"><strong>'+esc(title)+' ('+values.length+')</strong><ul>'+values.map(v=>'<li>'+esc(triImportIssueName(v))+'</li>').join('')+'</ul></div>').join('');
 return '<section class="notice '+((s.unmatched||s.conflicts||s.withoutScore)?'warning':'success')+' tri-import-result"><h3>Resultado da última importação</h3><div class="student-home-mini-stats"><div><strong>'+Number(s.updated||0)+'</strong><span>atualizados</span></div><div><strong>'+Number(s.unchanged||0)+'</strong><span>sem alteração</span></div><div><strong>'+Number(s.unmatched||0)+'</strong><span>não encontrados</span></div><div><strong>'+Number(s.conflicts||0)+'</strong><span>conflitos</span></div><div><strong>'+Number(s.withoutScore||0)+'</strong><span>sem nota</span></div></div>'+detail+'</section>';
}
function triImportProcessHtml(){
 const p=triImportProcess;
 const inspection=triImportDraft?.inspection;
 const preview=triImportPreviewData;
 if(!inspection&&!p)return '<div id="tri-import-process"></div>';
 const matched=p?.matched??preview?.matched??0;
 const students=p?.students??preview?.students??0;
 const state=p?.state||'preview';
 const done=n=>state==='done'||(state==='saving'&&n<=3)||(state==='sending'&&n<=2)||(state==='preview'&&n<=2);
 const active=n=>(state==='sending'&&n===3)||(state==='saving'&&n===4)||(state==='done'&&n===5)||(state==='error'&&n===5);
 const cls=n=>done(n)?'done':active(n)?(state==='error'?'error':'active'):'pending';
 const icon=n=>done(n)?'✓':active(n)?(state==='error'?'!':'…'):String(n);
 const note3=state==='sending'?'Enviando o arquivo e os vínculos para o servidor.':'Dados preparados para envio.';
 const note4=state==='saving'?'Servidor processando e gravando as notas no banco.':'Aguardando a etapa de gravação.';
 const note5=state==='done'?'Gravação confirmada pelo servidor.':state==='error'?'A operação não foi concluída. Veja a mensagem de erro.':'Aguardando confirmação final.';
 return '<section class="tri-import-process-card"><h3>Etapas da importação</h3>'+
  '<div class="tri-import-step '+cls(1)+'"><span>'+icon(1)+'</span><div><strong>1. Arquivo lido</strong><small>'+esc(inspection?.sheet||'Planilha reconhecida')+'</small></div></div>'+
  '<div class="tri-import-step '+cls(2)+'"><span>'+icon(2)+'</span><div><strong>2. Alunos vinculados</strong><small>'+matched+'/'+students+' aluno(s) vinculados ao simulado.</small></div></div>'+
  '<div class="tri-import-step '+cls(3)+'"><span>'+icon(3)+'</span><div><strong>3. Envio ao servidor</strong><small>'+note3+'</small></div></div>'+
  '<div class="tri-import-step '+cls(4)+'"><span>'+icon(4)+'</span><div><strong>4. Gravação das notas</strong><small>'+note4+'</small></div></div>'+
  '<div class="tri-import-step '+cls(5)+'"><span>'+icon(5)+'</span><div><strong>5. Finalização</strong><small>'+note5+'</small></div></div>'+
  '</section>';
}
function triImportUpdateProcessDom(){
 const el=document.getElementById('tri-import-process');
 if(el)el.innerHTML=triImportProcessHtml();
}
const triImportStatusBeforeStability=triImportStatus;
triImportStatus=function(){
 return triImportStatusBeforeStability()+'<div id="tri-import-process">'+triImportProcessHtml()+'</div>'+triImportSavedSummaryHtml();
};

acts['tri-import-preview']=async()=>{
 const sim=triSelectedSimulation();if(!sim)throw new Error('Selecione o simulado que receberá as notas.');
 triImportDraft.simulationId=sim.id;triImportBusy=true;
 try{
  triImportPreviewData=await api('/api/model-data/tri-preview',{file:triImportDraft.file,filename:triImportDraft.filename,activityKey:sim.activityKey,date:sim.date});
  triImportProcess={state:'preview',matched:triImportPreviewData.matched||0,students:triImportPreviewData.students||0};
  render();
 }finally{triImportBusy=false;}
};

acts['tri-import-confirm']=async()=>{
 const sim=triSelectedSimulation();if(!sim||!triImportPreviewData)throw new Error('Gere a conferência antes de confirmar.');
 if(!confirm(`Vincular as notas da aba ${triImportDraft.inspection.sheet} ao simulado ${sim.activity} de ${sim.date}?`))return;
 triImportBusy=true;
 triImportProcess={state:'sending',matched:triImportPreviewData.matched||0,students:triImportPreviewData.students||0};
 triImportUpdateProcessDom();
 const saveButton=document.querySelector('[data-act="tri-import-confirm"]');
 if(saveButton){saveButton.disabled=true;saveButton.textContent='Salvando notas…';}
 clearTimeout(triImportProcessTimer);
 triImportProcessTimer=setTimeout(()=>{
  if(triImportBusy&&triImportProcess){
   triImportProcess.state='saving';
   triImportUpdateProcessDom();
  }
 },700);
 try{
  const d=await api('/api/model-data/tri-confirm',{file:triImportDraft.file,filename:triImportDraft.filename,activityKey:sim.activityKey,date:sim.date});
  studentSummaryCache?.clear?.();
  if(typeof resultExportSimulations!=='undefined')resultExportSimulations=null;
  triImportSaveSummary=d;
  triImportProcess={state:'done',matched:d.summary?.matched||triImportProcess?.matched||0,students:triImportProcess?.students||0};
  triImportPreviewData=null;
  toast(`Notas TRI e redação salvas: ${d.summary.updated} atualizada(s); ${d.summary.unchanged} sem mudança.`);
 }catch(error){
  const message=error?.message||'erro inesperado ao gravar as notas';
  triImportProcess={...(triImportProcess||{}),state:'error'};
  toast('Não foi possível salvar as notas: '+message,true);
 }finally{
  clearTimeout(triImportProcessTimer);
  triImportBusy=false;
  render();
 }
};
const triImportClearBeforeStability=acts['tri-import-clear'];
acts['tri-import-clear']=()=>{
 clearTimeout(triImportProcessTimer);
 triImportSaveSummary=null;triImportProcess=null;
 return triImportClearBeforeStability();
};
document.addEventListener('change',event=>{
 if(event.target?.id==='tri-import-file'){
  clearTimeout(triImportProcessTimer);
  triImportSaveSummary=null;triImportProcess=null;
 }
},true);

document.addEventListener('change',async event=>{
 if(event.target?.id==='tri-import-file'){
  const file=event.target.files?.[0];event.target.value='';if(!file)return;
  try{if(!/\.xlsx$/i.test(file.name))throw new Error('Selecione um arquivo .xlsx.');if(file.size>8000000)throw new Error('O arquivo excede 8 MB.');const encoded=await triFileBase64(file);triImportDraft={file:encoded,filename:file.name,inspection:null,simulations:[],simulationId:''};triImportPreviewData=null;render();toast('Arquivo de ranking selecionado. Clique em Ler Ranking Geral.');}catch(error){toast(error.message,true);}
 }
 if(event.target?.name==='tri-import-simulation'&&triImportDraft){triImportDraft.simulationId=event.target.value;triImportPreviewData=null;render();}
});

function triStudentPanel(d){
 const latest=(d?.simulations||[])[0],summary=d?.tri||{};
 if(!latest)return '';
 const areas=(latest.triByArea||[]).filter(x=>triScore(x.score)!==null);
 if(triScore(latest.tri)===null&&!areas.length)return `<div class="student-tri-panel notice"><strong>Nota TRI ainda não vinculada.</strong> Os acertos/TCT já estão disponíveis. O Master ou Coordenador pode importar a aba Ranking Geral na página Importar resultados.</div>`;
 const areaCards=areas.map(x=>`<div><strong>${triFormat(x.score)}</strong><span>${esc(x.name)}</span></div>`).join('');
 const evolution=(summary.evolution||[]).map((x,index)=>{const height=Math.max(5,Math.min(100,studentHomeNumber(x.score)/10));return `<div class="student-home-evolution-item" title="${esc(x.activity||'Simulado')} · ${esc(x.date||'')} · TRI ${triFormat(x.score)}"><span class="student-home-evolution-value">${triFormat(x.score,0)}</span><div class="student-home-evolution-track tri-track"><span style="height:${height}%"></span></div><small>${index+1}º</small></div>`;}).join('');
 return `<div class="student-tri-panel"><div class="student-tri-head"><div><p class="eyebrow">Escala TRI</p><h3>Nota do simulado</h3></div><div class="student-tri-main"><strong>${triFormat(latest.tri)}</strong><span>TRI geral${triScore(latest.ranking)!==null?' · ranking '+triFormat(latest.ranking,0):''}</span></div></div><div class="student-home-mini-stats tri-area-grid">${areaCards}</div>${evolution?`<h4>Evolução da nota TRI</h4><div class="student-home-evolution">${evolution}</div>`:''}<p class="micro">TCT/acertos e TRI são indicadores diferentes: os acertos mostram o domínio dos itens; a TRI mantém a nota informada no ranking do simulado.</p></div>`;
}

if(typeof studentHomeDashboard==='function'){
 const triOriginalStudentHomeDashboard=studentHomeDashboard;
 studentHomeDashboard=function(){const base=triOriginalStudentHomeDashboard();const d=studentSummaryCache.get(studentSummaryTarget());const panel=triStudentPanel(d);return panel?base.replace('<p class="micro student-home-footnote">',panel+'<p class="micro student-home-footnote">'):base;};
}
if(typeof studentSummaryPanel==='function'){
 const triOriginalStudentSummaryPanel=studentSummaryPanel;
 studentSummaryPanel=function(){const base=triOriginalStudentSummaryPanel();const d=studentSummaryCache.get(studentSummaryTarget());const panel=triStudentPanel(d);return panel?base+`<section class="card">${panel}</section>`:base;};
}


// === QI TRI E REDACAO V1 ===
function qiTriDownloadBase64(filename,mime,encoded){
 const binary=atob(encoded),bytes=new Uint8Array(binary.length);
 for(let i=0;i<binary.length;i++)bytes[i]=binary.charCodeAt(i);
 const url=URL.createObjectURL(new Blob([bytes],{type:mime}));
 const a=document.createElement('a');a.href=url;a.download=filename;document.body.appendChild(a);a.click();a.remove();setTimeout(()=>URL.revokeObjectURL(url),1500);
}
function triImportCard(){
 if(!manages())return '';
 return `<section class="card"><h2>Importar TRI e Redação <button type="button" class="help-button" data-act="tri-import-help" aria-label="Explicar notas TRI e redação">?</button></h2><p>Importe ranking, TRI geral e por área, tema da redação, competências C1–C5 e nota total. O arquivo atualiza somente essas notas; respostas, acertos e mapa de questões são preservados.</p><fieldset class="tri-import-controls" ${triImportBusy?'disabled':''}><div class="actions">${button('Gerar modelo TRI + Redação','tri-import-template','secondary')}</div><label>Arquivo de notas (.xlsx, até 8 MB)<input id="tri-import-file" type="file" accept=".xlsx"></label><p id="tri-import-filename">${esc(triImportDraft?.filename||'Nenhum arquivo selecionado.')}</p><div class="actions">${button('Ler notas TRI/Redação','tri-import-inspect','primary')}${button('Limpar','tri-import-clear','secondary')}</div><div id="tri-import-status">${triImportStatus()}</div></fieldset><div class="actions">${button('Consultar notas no banco','tri-coverage','secondary')}</div><div id="tri-coverage">${triCoverageHtml()}</div></section>`;
}
function triImportStatus(){
 if(!triImportDraft?.inspection)return '';
 const d=triImportDraft.inspection,options=(d.simulations||[]).map(x=>`<option value="${esc(x.id)}" ${(triImportDraft.simulationId||d.simulations?.[0]?.id)===x.id?'selected':''}>${esc(x.activity)} · ${esc(x.date)} · ${x.participants} aluno(s)</option>`).join('');
 const sample=(d.sample||[]).slice(0,8).map(x=>`<tr><td>${esc(x.name)}</td><td>${triFormat(x.scores?.tri)}</td><td>${triFormat(x.scores?.lc)}</td><td>${triFormat(x.scores?.ch)}</td><td>${triFormat(x.scores?.cn)}</td><td>${triFormat(x.scores?.mt)}</td><td>${triFormat(x.scores?.redaction,0)}</td><td>${triFormat(x.scores?.c1,0)}</td><td>${triFormat(x.scores?.c2,0)}</td><td>${triFormat(x.scores?.c3,0)}</td><td>${triFormat(x.scores?.c4,0)}</td><td>${triFormat(x.scores?.c5,0)}</td></tr>`).join('');
 return `<hr><h3>Aba reconhecida: ${esc(d.sheet)}</h3><p><strong>${d.rows}</strong> linha(s) com nota · cabeçalho na linha ${d.headerRow}.</p><div class="student-home-chips">${triColumnsText(d.columns)}</div><label>Vincular ao simulado<select name="tri-import-simulation">${options}</select></label><p class="micro">${esc(d.notice||'')}</p>${sample?`<div class="table-wrap"><table><thead><tr><th>Aluno</th><th>TRI geral</th><th>LC</th><th>CH</th><th>CN</th><th>MT</th><th>Redação</th><th>C1</th><th>C2</th><th>C3</th><th>C4</th><th>C5</th></tr></thead><tbody>${sample}</tbody></table></div>`:''}<div class="actions">${button('Conferir vínculos das notas','tri-import-preview','primary')}</div><div id="tri-import-preview">${triImportPreviewData?triImportPreviewHtml(triImportPreviewData):''}</div>`;
}
function triImportPreviewHtml(d){
 const sample=(d.sample||[]).map(x=>`<tr><td>${esc(x.name)}</td><td>${esc(x.login||'')}</td><td>${triFormat(x.tri)}</td><td>${triFormat(x.lc)}</td><td>${triFormat(x.ch)}</td><td>${triFormat(x.cn)}</td><td>${triFormat(x.mt)}</td><td>${triFormat(x.redaction,0)}</td><td>${triFormat(x.c1,0)}</td><td>${triFormat(x.c2,0)}</td><td>${triFormat(x.c3,0)}</td><td>${triFormat(x.c4,0)}</td><td>${triFormat(x.c5,0)}</td><td>${x.changed?'Atualizar':'Sem mudança'}</td></tr>`).join('');
 const warnings=[];if(d.unmatched)warnings.push(`${d.unmatched} nome(s) não encontrados no simulado.`);if(d.conflicts)warnings.push(`${d.conflicts} conflito(s) de nomes repetidos.`);if(d.withoutScore)warnings.push(`${d.withoutScore} aluno(s) sem linha de nota.`);
 return `<div class="notice ${warnings.length?'warning':'success'}"><strong>${d.matched}/${d.students}</strong> aluno(s) vinculados · ${d.changed} atualização(ões) · ${d.unchanged} sem mudança.${warnings.length?'<br>'+warnings.map(esc).join(' '):''}</div>${sample?`<div class="table-wrap"><table><thead><tr><th>Aluno</th><th>Login</th><th>TRI</th><th>LC</th><th>CH</th><th>CN</th><th>MT</th><th>Redação</th><th>C1</th><th>C2</th><th>C3</th><th>C4</th><th>C5</th><th>Situação</th></tr></thead><tbody>${sample}</tbody></table></div>`:''}<div class="actions">${button(triImportBusy?'Salvando notas…':triImportProcess?.state==='error'?'Retomar envio':'Confirmar vínculo das notas','tri-import-confirm','primary',triImportBusy?'disabled':'')}</div>`;
}
acts['tri-import-template']=async()=>{const d=await api('/api/model-data/tri-template',{});qiTriDownloadBase64(d.filename,d.mime,d.file);toast('Modelo TRI e Redação gerado.');};
acts['tri-import-help']=()=>modal('TRI e Redação por simulado','<p><strong>TCT/acertos</strong> continuam sendo calculados pelas respostas e pelo gabarito.</p><p><strong>TRI</strong>, ranking e redação são importados separadamente e vinculados ao mesmo aluno e simulado.</p><p>C1–C5 aceitam valores de 0 a 200. A nota total aceita 0 a 1000; se ficar vazia e as cinco competências estiverem completas, o sistema calcula a soma.</p><p>Campos vazios preservam o valor já salvo.</p>',null);
const qiOriginalTriStudentPanel=triStudentPanel;
triStudentPanel=function(d){
 let base=qiOriginalTriStudentPanel(d),latest=(d?.simulations||[])[0],red=latest?.redaction||{};
 const values=['c1','c2','c3','c4','c5'].map(k=>triScore(red[k]));
 if(!base||(!red.theme&&values.every(v=>v===null)))return base;
 const cards=values.map((v,i)=>`<div><strong>${v===null?'—':triFormat(v,0)}</strong><span>C${i+1}</span></div>`).join('');
 const block=`<div class="qi-redaction-detail"><h4>Redação</h4>${red.theme?`<p><strong>Tema:</strong> ${esc(red.theme)}</p>`:''}<div class="student-home-mini-stats qi-redaction-grid">${cards}</div></div>`;
 return base.replace('<p class="micro">TCT/acertos',block+'<p class="micro">TCT/acertos');
};

// === TRI IMPORT TOKEN V1 ===
function triPercent(count,total){
 if(!total)return '0%';
 const value=count===total?100:Math.min(99.9,Math.round(1000*count/total)/10);
 return value.toLocaleString('pt-BR')+'%';
}

let triCoverage=null;
let triCoverageLoading=false;
function triCoverageHtml(){
 if(!triCoverage)return '';
 if(triCoverage.error)return '<p role="alert">'+esc(triCoverage.error)+'</p>';
 if(!triCoverage.length)return '<p>Nenhum simulado com resultados cadastrados.</p>';
 const rows=triCoverage.map(row=>'<tr><td>'+esc(row.activity)+'</td><td>'+esc(br(row.date))+'</td><td>'+row.total+'</td><td>'+row.saved+'</td><td>'+triPercent(row.saved,row.total)+'</td></tr>').join('');
 return '<div class="table-wrap"><table><caption>Alunos com importação de notas TRI/Redação registrada no banco</caption><thead><tr><th>Simulado</th><th>Aplicação</th><th>Participantes</th><th>Com notas importadas</th><th>% do simulado</th></tr></thead><tbody>'+rows+'</tbody></table></div>';
}
async function triLoadCoverage(){
 if(triCoverageLoading)return;
 triCoverageLoading=true;
 try{triCoverage=(await api('/api/model-data/tri-coverage')).simulations;}
 catch(error){triCoverage={error:error.message};}
 finally{
  triCoverageLoading=false;
  const el=document.getElementById('tri-coverage');
  if(el)el.innerHTML=triCoverageHtml();
 }
}
acts['tri-coverage']=triLoadCoverage;

acts['tri-import-preview']=async()=>{
 if(triImportBusy)return;
 const sim=triSelectedSimulation();
 if(!sim)throw new Error('Selecione o simulado que receberá as notas.');
 triImportDraft.simulationId=sim.id;
 triImportPreviewData=null;
 triImportProcess=null;
 triImportSaveSummary=null;
 triImportBusy=true;
 render();
 try{
  const preview=await api('/api/model-data/tri-preview',{
   file:triImportDraft.file,filename:triImportDraft.filename,
   activityKey:sim.activityKey,date:sim.date,batchMode:true
  });
  if(!Array.isArray(preview.batches)||preview.batches.some(b=>!b.importToken||!Number.isInteger(b.count)||b.count<1)||
     preview.batches.reduce((n,b)=>n+b.count,0)!==preview.matched){
   throw new Error('O servidor não confirmou os lotes desta prévia. Confira os vínculos novamente.');
  }
  triImportPreviewData=preview;
  triImportProcess={state:'preview',matched:preview.matched,students:preview.students,
   received:0,verified:0,updated:0,unchanged:0,nextBatch:0};
 }finally{
  triImportBusy=false;
  render();
 }
};

function triImportProcessHtml(){
 const p=triImportProcess;
 if(!triImportDraft?.inspection||!p)return '';
 const step=(n,label,note,complete,active=false,failed=false)=>{
  const cls=failed?'error':complete?'done':active?'active':'pending';
  const icon=failed?'!':complete?'✓':active?'…':String(n);
  return '<div class="tri-import-step '+cls+'"><span>'+icon+'</span><div><strong>'+n+'. '+label+'</strong><small>'+note+'</small></div></div>';
 };
 const total=p.matched;
 const meter=(count,label)=>{
  const text=count+' de '+total+' ('+triPercent(count,total)+')';
  return text+'<progress aria-label="'+label+'" aria-valuetext="'+text+'" value="'+count+'" max="'+Math.max(total,1)+'"></progress>';
 };
 const done=p.state==='done';
 let message='Aguardando confirmação da gravação.';
 if(!total)message='Nenhum resultado vinculado para enviar.';
 if(done)message=p.verified+' confirmados no banco. '+p.updated+' atualizados e '+p.unchanged+' já conferiam com a planilha.';
 if(p.state==='error')message=esc(p.error)+' Confira os totais acima. Use Retomar envio ou faça uma nova conferência se a prévia expirou.';
 return '<section class="tri-import-process-card"><h3>Etapas da importação</h3>'+
  step(1,'Arquivo lido',esc(triImportDraft.inspection.sheet||'Planilha reconhecida'),true)+
  step(2,'Alunos vinculados',p.matched+' de '+p.students+' alunos do simulado.',true)+
  step(3,'Envio ao servidor','Recebidos pelo servidor: '+meter(p.received,'Resultados recebidos pelo servidor'),total>0&&p.received===total,p.state==='sending',p.state==='error'&&p.stage===3)+
  step(4,'Gravação das notas','Confirmados no banco: '+meter(p.verified,'Resultados confirmados no banco'),done,p.state==='saving',p.state==='error'&&p.stage===4)+
  step(5,'Finalização',message,done)+'</section>';
}

acts['tri-import-confirm']=async()=>{
 if(triImportBusy)return;
 const sim=triSelectedSimulation(),preview=triImportPreviewData,p=triImportProcess;
 if(!sim||!preview||!p||sim.id!==triImportDraft.simulationId)throw new Error('Confira os vínculos antes de enviar.');
 if(!p.matched)throw new Error('Não há resultados vinculados para enviar.');
 if(!confirm('Salvar as notas conferidas de '+sim.activity+' ('+br(sim.date)+')?'))return;
 triImportBusy=true;
 p.state='sending';
 render();
 try{
  while(p.nextBatch<preview.batches.length){
   const {importToken,count}=preview.batches[p.nextBatch];
   p.stage=3;
   p.state='sending';
   triImportUpdateProcessDom();
   const receipt=await api('/api/model-data/tri-confirm-prepare',{importToken});
   if(!receipt.ready||receipt.receivedRecords!==count)throw new Error('O servidor não confirmou o recebimento do lote.');
   p.received=p.verified+count;
   p.stage=4;
   p.state='saving';
   triImportUpdateProcessDom();
   const result=await api('/api/model-data/tri-confirm',{importToken});
   const {updated,unchanged}=result.summary||{};
   if(result.verifiedRecords!==count||!Number.isInteger(updated)||!Number.isInteger(unchanged)||
      updated<0||unchanged<0||updated+unchanged!==count){
    throw new Error('Falta a confirmação da gravação deste lote.');
   }
   p.verified+=count;
   p.updated+=updated;
   p.unchanged+=unchanged;
   p.nextBatch++;
   triImportUpdateProcessDom();
  }
  p.state='done';
  triImportSaveSummary={summary:{updated:p.updated,unchanged:p.unchanged,unmatched:preview.unmatched,
   conflicts:preview.conflicts,withoutScore:preview.withoutScore},issues:preview};
  triImportPreviewData=null;
  toast('Importação concluída: '+p.verified+' resultados confirmados no banco.');
 }catch(error){
  p.state='error';
  p.error=error.message||'A conexão foi interrompida.';
  toast(p.error,true);
 }finally{
  triImportBusy=false;
  if(p.verified){
   if(typeof studentSummaryCache!=='undefined')studentSummaryCache?.clear?.();
   if(typeof resultExportSimulations!=='undefined')resultExportSimulations=null;
   if(typeof managementDashboardCache!=='undefined')managementDashboardCache=null;
   if(typeof managementClassAnalyticsCache!=='undefined'){
    managementClassAnalyticsCache=null;
    managementClassDetailCache.clear();
    managementStudentDetailCache.clear();
   }
  }
  render();
  if(triCoverage)await triLoadCoverage();
 }
};

document.addEventListener('change',event=>{
 if(event.target?.name==='tri-import-simulation'){
  triImportProcess=null;
  triImportSaveSummary=null;
 }
},true);

// === TRI DASHBOARD V3.3 ===
let triDashboardSelectedKeys=null;
let triDashboardAvailableKeys=[];
let triDashboardSelectionOwner=null;

function triDashNumber(value){
 const n=Number(value);
 return value===null||value===undefined||value===''||!Number.isFinite(n)?null:n;
}
function triDashFormat(value,digits=1){
 const n=triDashNumber(value);
 return n===null?'—':n.toLocaleString('pt-BR',{minimumFractionDigits:digits,maximumFractionDigits:digits});
}
function triDashboardKey(sim){
 return String(sim?.activity||'')+'@@'+String(sim?.date||'');
}
function triDashboardSort(simulations,ascending=false){
 const rows=[...(simulations||[])];
 rows.sort((a,b)=>{
  const date=String(a?.date||'').localeCompare(String(b?.date||''));
  if(date)return ascending?date:-date;
  const name=String(a?.activity||'').localeCompare(String(b?.activity||''),'pt-BR');
  return ascending?name:-name;
 });
 return rows;
}
function triDashboardScore(sim,key){
 const scores=sim?.triScores||{};
 let value=scores[key];
 if((value===null||value===undefined||value==='')&&key==='redaction')value=sim?.redaction?.score;
 return triDashNumber(value);
}
function triDashboardHasTri(sim){
 return ['general','lc','ch','cn','mt','redaction'].some(key=>triDashboardScore(sim,key)!==null);
}
function triDashboardEnsureSelection(simulations){
 const owner=typeof studentSummaryTarget==='function'?studentSummaryTarget():'';
 const keys=(simulations||[]).map(triDashboardKey);
 const valid=new Set(keys);
 if(triDashboardSelectionOwner!==owner){
  triDashboardSelectionOwner=owner;
  triDashboardSelectedKeys=null;
 }
 if(!(triDashboardSelectedKeys instanceof Set))triDashboardSelectedKeys=new Set(keys);
 else triDashboardSelectedKeys=new Set([...triDashboardSelectedKeys].filter(key=>valid.has(key)));
 triDashboardAvailableKeys=keys;
}
function triDashboardSelected(simulations){
 triDashboardEnsureSelection(simulations);
 return (simulations||[]).filter(sim=>triDashboardSelectedKeys.has(triDashboardKey(sim)));
}
function triDashboardFilterHtml(simulations){
 triDashboardEnsureSelection(simulations);
 const allChecked=triDashboardAvailableKeys.length>0&&triDashboardSelectedKeys.size===triDashboardAvailableKeys.length;
 const items=triDashboardSort(simulations,false).map(sim=>{
  const key=triDashboardKey(sim),checked=triDashboardSelectedKeys.has(key)?' checked':'';
  return '<label class="tri-dashboard-filter-item"><input type="checkbox" data-tri-dashboard-key="'+encodeURIComponent(key)+'"'+checked+'><span><strong>'+esc(sim.activity||'Simulado')+'</strong><small>'+esc(sim.date||'')+'</small></span></label>';
 }).join('');
 return '<section class="tri-dashboard-filter"><div class="tri-dashboard-filter-head"><div><h4>Simulados exibidos</h4><p class="micro">Selecione um, vários ou todos. Isso permite comparar apenas provas com parametrizações compatíveis.</p></div><label class="tri-dashboard-all"><input type="checkbox" data-tri-dashboard-all'+(allChecked?' checked':'')+'> Todos</label></div><div class="tri-dashboard-filter-grid">'+items+'</div></section>';
}
function triDashboardMetricCards(sim){
 const metrics=[
  ['general','TRI geral'],['lc','Linguagens'],['ch','Humanas'],
  ['cn','Natureza'],['mt','Matemática'],['redaction','Redação']
 ];
 return '<div class="tri-dashboard-score-grid">'+metrics.map(item=>{
  const value=triDashboardScore(sim,item[0]);
  return '<div><strong>'+triDashFormat(value,item[0]==='redaction'?0:1)+'</strong><span>'+item[1]+'</span></div>';
 }).join('')+'</div>';
}
function triDashboardComparison(rows){
 const body=triDashboardSort(rows,true).map(sim=>
  '<tr><td><strong>'+esc(sim.activity||'Simulado')+'</strong><br><small>'+esc(sim.date||'')+'</small></td>'+
  '<td>'+triDashFormat(triDashboardScore(sim,'general'))+'</td>'+
  '<td>'+triDashFormat(triDashboardScore(sim,'lc'))+'</td>'+
  '<td>'+triDashFormat(triDashboardScore(sim,'ch'))+'</td>'+
  '<td>'+triDashFormat(triDashboardScore(sim,'cn'))+'</td>'+
  '<td>'+triDashFormat(triDashboardScore(sim,'mt'))+'</td>'+
  '<td>'+triDashFormat(triDashboardScore(sim,'redaction'),0)+'</td></tr>'
 ).join('');
 return '<div class="tri-dashboard-comparison"><h4>Notas dos simulados selecionados</h4><div class="table-wrap"><table><thead><tr><th>Simulado</th><th>TRI geral</th><th>LC</th><th>CH</th><th>CN</th><th>MT</th><th>Redação</th></tr></thead><tbody>'+body+'</tbody></table></div></div>';
}
function triDashboardSeries(rows,key,label,digits=1){
 const ordered=triDashboardSort(rows,true).filter(sim=>triDashboardScore(sim,key)!==null);
 if(!ordered.length)return '<article class="tri-dashboard-series"><h4>'+esc(label)+'</h4><div class="notice">Sem nota TRI importada para esta série.</div></article>';
 const bars=ordered.map(sim=>{
  const value=triDashboardScore(sim,key);
  const height=Math.max(5,Math.min(100,(value/1000)*100));
  return '<div class="tri-dashboard-series-item" title="'+esc((sim.activity||'Simulado')+' · '+(sim.date||''))+'">'+
   '<span class="tri-dashboard-series-value">'+triDashFormat(value,digits)+'</span>'+
   '<div class="tri-dashboard-series-track"><span style="height:'+height+'%"></span></div>'+
   '<small>'+esc(sim.activity||'Simulado')+'</small><em>'+esc(sim.date||'')+'</em></div>';
 }).join('');
 return '<article class="tri-dashboard-series"><h4>'+esc(label)+'</h4><div class="tri-dashboard-series-chart">'+bars+'</div></article>';
}
function triDashboardEvolution(rows){
 const metrics=[
  ['general','TRI geral',1],['lc','Linguagens',1],['ch','Humanas',1],
  ['cn','Natureza',1],['mt','Matemática',1],['redaction','Redação',0]
 ];
 return '<section class="tri-dashboard-evolution"><h4>Evolução TRI por área</h4><p class="micro">A ordem é determinada pela data de aplicação. Cada coluna usa o nome real do simulado.</p><div class="tri-dashboard-evolution-grid">'+metrics.map(item=>triDashboardSeries(rows,item[0],item[1],item[2])).join('')+'</div></section>';
}
function triDashboardRedactionValue(sim,key){
 const red=sim?.redaction||{};
 if(key==='score'){
  const value=triDashNumber(red.score);
  return value===null?triDashboardScore(sim,'redaction'):value;
 }
 return key==='theme'?String(red.theme||''):triDashNumber(red[key]);
}
function triDashboardRedactionHistory(simulations){
 const rows=triDashboardSort(simulations,false).filter(sim=>{
  const red=sim?.redaction||{};
  return triDashboardRedactionValue(sim,'score')!==null||String(red.theme||'').trim()||['c1','c2','c3','c4','c5'].some(k=>triDashboardRedactionValue(sim,k)!==null);
 });
 if(!rows.length)return '<section class="tri-redaction-history"><h4>Histórico de redações</h4><div class="notice">Ainda não há redações importadas para este aluno.</div></section>';
 const body=rows.map(sim=>
  '<tr><td><strong>'+esc(sim.activity||'Simulado')+'</strong><br><small>'+esc(sim.date||'')+'</small></td>'+
  '<td>'+esc(triDashboardRedactionValue(sim,'theme')||'—')+'</td>'+
  '<td><strong>'+triDashFormat(triDashboardRedactionValue(sim,'score'),0)+'</strong></td>'+
  ['c1','c2','c3','c4','c5'].map(k=>'<td>'+triDashFormat(triDashboardRedactionValue(sim,k),0)+'</td>').join('')+
  '</tr>'
 ).join('');
 return '<section class="tri-redaction-history"><h4>Histórico de redações</h4><p class="micro">Redações em ordem da aplicação mais recente para a mais antiga.</p><div class="table-wrap"><table><thead><tr><th>Simulado</th><th>Tema</th><th>Nota</th><th>C1</th><th>C2</th><th>C3</th><th>C4</th><th>C5</th></tr></thead><tbody>'+body+'</tbody></table></div></section>';
}

triStudentPanel=function(d){
 const simulations=(d?.simulations||[]).filter(triDashboardHasTri);
 if(!simulations.length)return '<section class="card student-tri-panel"><p class="eyebrow">Escala TRI</p><h3>Notas TRI</h3><div class="notice">Ainda não há notas TRI importadas para este aluno.</div></section>';
 const selected=triDashboardSelected(simulations);
 const latest=triDashboardSort(selected,false)[0]||null;
 const filter=triDashboardFilterHtml(simulations);
 const selectedBlock=latest?
  '<div class="tri-dashboard-current"><div><p class="eyebrow">Simulado em destaque</p><h3>'+esc(latest.activity||'Simulado')+'</h3><p>'+esc(latest.date||'')+(latest.color?' · prova '+esc(latest.color):'')+'</p></div>'+triDashboardMetricCards(latest)+'</div>'+
  triDashboardComparison(selected)+triDashboardEvolution(selected):
  '<div class="notice warning">Selecione ao menos um simulado para visualizar as notas.</div>';
 return '<section class="card student-tri-panel tri-dashboard-panel"><div class="tri-dashboard-title"><div><p class="eyebrow">Escala TRI</p><h2>Notas e evolução TRI</h2></div></div>'+filter+selectedBlock+triDashboardRedactionHistory(simulations)+'<p class="micro">TRI e acertos/TCT são indicadores diferentes. Use a seleção acima para evitar comparar simulados com parametrizações incompatíveis.</p></section>';
};

document.addEventListener('change',event=>{
 const target=event.target;
 if(!target)return;
 if(target.matches('[data-tri-dashboard-all]')){
  triDashboardSelectedKeys=target.checked?new Set(triDashboardAvailableKeys):new Set();
  if(typeof render==='function')render();
  return;
 }
 if(target.matches('[data-tri-dashboard-key]')){
  if(!(triDashboardSelectedKeys instanceof Set))triDashboardSelectedKeys=new Set(triDashboardAvailableKeys);
  const key=decodeURIComponent(target.dataset.triDashboardKey||'');
  if(target.checked)triDashboardSelectedKeys.add(key);else triDashboardSelectedKeys.delete(key);
  if(typeof render==='function')render();
 }
},true);

// === TRI AVERAGE V3.4 ===
function triDashboardAverage(rows,key){
 const values=(rows||[]).map(sim=>triDashboardScore(sim,key)).filter(value=>value!==null);
 if(!values.length)return null;
 return values.reduce((sum,value)=>sum+value,0)/values.length;
}
function triDashboardAverageCards(rows){
 const metrics=[
  ['general','TRI geral',1],['lc','Linguagens',1],['ch','Humanas',1],
  ['cn','Natureza',1],['mt','Matemática',1],['redaction','Redação',1]
 ];
 return '<div class="tri-dashboard-score-grid">'+metrics.map(item=>{
  const value=triDashboardAverage(rows,item[0]);
  return '<div><strong>'+triDashFormat(value,item[2])+'</strong><span>'+item[1]+'</span></div>';
 }).join('')+'</div>';
}
triStudentPanel=function(d){
 const simulations=(d?.simulations||[]).filter(triDashboardHasTri);
 if(!simulations.length)return '<section class="card student-tri-panel"><p class="eyebrow">Escala TRI</p><h3>Notas TRI</h3><div class="notice">Ainda não há notas TRI importadas para este aluno.</div></section>';
 const selected=triDashboardSelected(simulations);
 const latest=triDashboardSort(simulations,false)[0]||null;
 const filter=triDashboardFilterHtml(simulations);
 let selectedBlock='<div class="notice warning">Selecione ao menos um simulado para calcular as médias e a evolução.</div>';
 if(selected.length){
  selectedBlock=
   '<div class="tri-dashboard-current"><div><p class="eyebrow">Média dos simulados selecionados</p><h3>'+selected.length+' simulado(s) na média</h3><p class="micro">Cada área usa apenas as notas disponíveis entre os simulados marcados.</p></div>'+
   triDashboardAverageCards(selected)+'</div>'+
   triDashboardComparison(selected)+triDashboardEvolution(selected);
 }
 const latestBlock=latest?
  '<section class="tri-dashboard-latest"><div><p class="eyebrow">Último simulado realizado</p><h3>'+esc(latest.activity||'Simulado')+'</h3><p>'+esc(latest.date||'')+(latest.color?' · prova '+esc(latest.color):'')+'</p></div>'+triDashboardMetricCards(latest)+'</section>':'';
 return '<section class="card student-tri-panel tri-dashboard-panel"><div class="tri-dashboard-title"><div><p class="eyebrow">Escala TRI</p><h2>Notas e evolução TRI</h2></div></div>'+
  latestBlock+filter+selectedBlock+triDashboardRedactionHistory(simulations)+
  '<p class="micro">TRI e acertos/TCT são indicadores diferentes. As médias e gráficos consideram somente os simulados selecionados acima.</p></section>';
};
