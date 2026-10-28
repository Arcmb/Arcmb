'use strict';
let perfDraft=null,perfSequence=0,perfRecords=[];
function coordinatorView(){return head('Meus alunos','Abra a rotina para ajustar horários, disciplinas e metas. Contas especiais e de outros gestores não são exibidas.')+`<section class="card">${items(accounts.map(a=>`<div class="item"><div><strong>${esc(a.name)}</strong><p>${esc(a.username)} · ${esc(roleLabel(a.role))}</p></div>${button('Abrir e ajustar rotina','open-account','primary',`data-id="${esc(a.id)}"`)}</div>`))}</section>`;}
function performanceView(){
 const request=++perfSequence,who=target;
 queueMicrotask(async()=>{try{const result=await api('/api/performance?user='+encodeURIComponent(who));if(request!==perfSequence||view!=='performance'||target!==who)return;perfRecords=result.records;$('#performance-results').innerHTML=result.records.length?`<p class="micro">${result.records.length} de ${result.total} atividades. Exibição limitada às 500 mais recentes.</p>`+result.records.map(performanceRecord).join(''):empty('Nenhum resultado importado para esta conta.');}catch(e){if(request===perfSequence&&$('#performance-results'))$('#performance-results').textContent=e.message;}});
 return head('Desempenho','Resultados por atividade e disciplina, sem lista fixa de matérias.')+`<div class="notice">Vazio significa não informado; zero significa nenhum acerto. Percentuais só aparecem quando o total de questões foi informado. Importar não altera automaticamente o cronograma nem a dificuldade.</div>${manages()?`<section class="card"><h2>Importar resultados em lote</h2><p>Mantenha as colunas existentes. Acrescente <strong>Acertos - Nome da disciplina</strong> e, opcionalmente, <strong>Questões - Nome da disciplina</strong>.</p><label>Arquivo XLSX ou CSV (até 3 MB, 5.000 registros e 300 colunas)<input type="file" id="performance-file" accept=".xlsx,.csv"></label><p class="micro">A primeira linha deve conter os cabeçalhos. NOME, TIPO/Atividade e data são obrigatórios. LOGIN é opcional para distinguir homônimos.</p><div class="actions">${button('Baixar modelo CSV','perf-template')}${button('Conferir arquivo','perf-preview','primary')}</div><p id="perf-file-name">${perfDraft?esc(perfDraft.filename):'Nenhum arquivo selecionado.'}</p><div id="perf-preview">${perfDraft?.preview?performancePreview(perfDraft.preview):''}</div></section>`:''}<section class="card"><h2>Histórico de ${esc(P.name)}</h2><div id="performance-results">Carregando resultados…</div></section>`;
}
function performanceRecord(r){
 const metrics=Object.values(r.metrics);
 return `<details class="card"><summary><strong>${esc(r.activity)}</strong> · ${br(r.applied_on)} · ${metrics.length} disciplinas</summary><div class="table-wrap"><table><thead><tr><th>Disciplina</th><th>Acertos</th><th>Questões</th><th>Aproveitamento</th></tr></thead><tbody>${metrics.map(m=>`<tr><td>${esc(m.name)}</td><td>${m.correct===null?'Não informado':esc(m.correct)}</td><td>${m.total===null?'Não informado':esc(m.total)}</td><td>${m.correct!==null&&m.total>0?(100*m.correct/m.total).toLocaleString('pt-BR',{maximumFractionDigits:1})+'%':'—'}</td></tr>`).join('')}</tbody></table></div>${Object.keys(r.metadata).length?`<details><summary>Dados gerais da avaliação</summary><div class="table-wrap"><table><tbody>${Object.entries(r.metadata).map(([k,v])=>`<tr><th>${esc(k)}</th><td>${esc(v)}</td></tr>`).join('')}</tbody></table></div></details>`:''}<p class="micro">Versão ${r.version}. Estes resultados são independentes das notas TRI e dos registros de revisão.</p></details>`;
}
function performancePreview(d){
 const s=d.summary;
 return `<hr><h3>Conferência antes da gravação</h3><p>${s.rows} registros · ${s.linked} vinculados · ${s.new} novos · ${s.updated} atualizações · ${s.unchanged} sem mudança.</p><p>${s.skipped} registros sem vínculo serão ignorados somente com sua confirmação. Contas não são criadas automaticamente.</p>${d.sheets.length>1?select('Aba do arquivo','perf-sheet',d.sheet,d.sheets.map(n=>[n,n])):''}<p><strong>Disciplinas reconhecidas:</strong> ${d.subjects.length?d.subjects.map(x=>esc(x.name)).join(', '):'Nenhuma coluna Acertos - ...; somente os dados gerais serão importados.'}</p><p class="micro">Acentos, maiúsculas e espaços são normalizados. Nomes diferentes, como Português e Gramática, continuam separados.</p><details open><summary>Vincular alunos às contas (${d.students.length})</summary><div class="table-wrap"><table><thead><tr><th>Aluno do arquivo</th><th>Turma</th><th>Conta no sistema</th></tr></thead><tbody>${d.students.map(s=>`<tr><td>${esc(s.name)}</td><td>${esc(s.group)}</td><td><select data-perf-student="${s.key}" aria-label="Conta de ${esc(s.name)}"><option value="">Não importar este aluno</option>${d.accounts.map(a=>`<option value="${esc(a.id)}" ${s.selected===a.id?'selected':''}>${esc(a.name)} (${esc(a.username)})</option>`).join('')}</select></td></tr>`).join('')}</tbody></table></div></details><div class="notice warning">${s.conflicts} valores já existentes diferem do arquivo. Por padrão, os existentes são mantidos; apenas campos ainda vazios são completados.</div>${check('Substituir valores existentes pelos valores preenchidos neste arquivo','perf-replace',!!perfDraft.replace)}${check('Ignorar os registros sem vínculo e importar apenas os vinculados','perf-skip',false)}<p class="micro">Células vazias nunca apagam dados. Colunas de uma disciplina nova serão incluídas mesmo vazias, sem presumir resultado zero.</p><div class="actions">${button('Atualizar conferência','perf-preview')}${button('Confirmar importação','perf-confirm','primary',!s.linked?'disabled':'')}</div><p id="perf-token-state" class="micro">Conferência válida. Revise os vínculos antes de confirmar.</p>`;
}
function performancePayload(){
 if(!perfDraft)throw new Error('Selecione um arquivo primeiro.');
 const mapping=Object.fromEntries($$('[data-perf-student]').map(s=>[s.dataset.perfStudent,s.value]));
 return {filename:perfDraft.filename,file:perfDraft.file,sheet:document.querySelector('[name="perf-sheet"]')?.value||perfDraft.sheet||'',mapping:Object.keys(mapping).length?mapping:(perfDraft.mapping||{}),replace:document.querySelector('[name="perf-replace"]')?.checked||false};
}
acts['perf-template']=async()=>{const r=await fetch('/api/performance/template',{credentials:'same-origin',cache:'no-store'});if(!r.ok){const d=await r.json();throw new Error(d.error||'Não foi possível gerar o modelo.');}download('Modelo_disciplinas_dinamicas.csv',await r.text(),'text/csv;charset=utf-8');};
acts['perf-preview']=async()=>{
 const payload=performancePayload();status('Conferindo arquivo · nenhum resultado gravado');
 const d=await api('/api/performance/preview',payload);perfDraft={...payload,preview:d,token:d.token,sheet:d.sheet,mapping:d.mapping};
 $('#perf-preview').innerHTML=performancePreview(d);status('Conferência pronta · aguarda confirmação');
};
acts['perf-confirm']=async()=>{
 if(!perfDraft?.token)throw new Error('Atualize a conferência após alterar os vínculos ou as opções.');
 const payload=performancePayload();payload.token=perfDraft.token;payload.skipUnmapped=document.querySelector('[name="perf-skip"]')?.checked||false;
 if(!confirm('Gravar os resultados nas contas vinculadas? A rotina não será alterada automaticamente.'))return;
 status('Gravando resultados…');const d=await api('/api/performance/confirm',payload);perfDraft=null;render();status('Resultados salvos no servidor.');toast(`${d.summary.new} atividades novas; ${d.summary.updated} atualizadas; ${d.summary.skipped} registros ignorados.`);
};
document.addEventListener('change',async e=>{
 if(e.target.id==='performance-file'){
  try{const f=e.target.files[0];if(!f)return;if(f.size>3000000)throw new Error('Limite de 3 MB. Divida a planilha em lotes menores.');
   const b64=await new Promise((resolve,reject)=>{const r=new FileReader();r.onload=()=>resolve(String(r.result).split(',')[1]);r.onerror=()=>reject(new Error('Falha na leitura do arquivo.'));r.readAsDataURL(f);});
   perfDraft={filename:f.name,file:b64};$('#perf-file-name').textContent=f.name;$('#perf-preview').innerHTML='Arquivo carregado no navegador. Clique em Conferir arquivo.';
  }catch(ex){perfDraft=null;toast(ex.message,true);}
 }
 if(e.target.matches('[data-perf-student],[name="perf-sheet"],[name="perf-replace"]')){
  if(perfDraft)perfDraft.token=null;
  const note=$('#perf-token-state');if(note)note.textContent='Opções alteradas. Clique em Atualizar conferência antes de confirmar.';
 }
});
