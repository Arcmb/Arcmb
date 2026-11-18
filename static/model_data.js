'use strict';
// v2.7 — fluxo simples baseado em DADOS DOS ALUNOS + DADOS DO SIMULADO.
let modelDataQuestions=180,modelDataLogin=true,modelDataDate=true;

function resultModelView(){
 if(!manages())return head('Modelo de dados','Acesso reservado ao Master e à coordenação.');
 return head('Modelo de dados do simulado','Use o formato simples: respostas A–E dos alunos e um mapa com gabarito e classificação das questões.')+
 `<div class="notice"><strong>Você não precisa converter respostas para 1 e 0.</strong><br>O sistema compara A–E com o gabarito: resposta correta = 1; resposta diferente ou em branco = 0. Questão anulada não gera acerto nem erro calculado.</div>`+
 `<section class="card"><h2>Gerar modelo simples</h2><div class="form-grid">${input('Quantidade de questões','model-data-questions',modelDataQuestions,'number','min="1" max="180" step="1"')}${check('Incluir coluna LOGIN para vínculo exato','model-data-login',modelDataLogin)}${check('Incluir data de aplicação no arquivo','model-data-date',modelDataDate)}</div><div class="actions">${button('Gerar MODELO DADOS.xlsx','model-download','primary')}${button('Já tenho o arquivo: importar','model-to-results')}</div><p class="micro">O Excel terá as abas DADOS DOS ALUNOS e DADOS DO SIMULADO. Bonificação não faz parte deste modelo. A nota com bônus, quando necessária em outro fluxo, já deve vir pronta.</p><p id="model-downloaded" role="status"></p></section>`+
 `<section class="card"><h2>Como preencher</h2><p><strong>DADOS DOS ALUNOS:</strong> uma linha por aluno; informe nome, turma, simulado, data, cor, língua estrangeira e as alternativas A–E nas colunas das questões.</p><p><strong>DADOS DO SIMULADO:</strong> uma linha por questão e cor; informe área, disciplina, tópico, assunto, habilidade, língua estrangeira quando aplicável e gabarito.</p><p>Para as questões com versões de Inglês e Espanhol, use duas linhas com o mesmo número e identifique a língua. O sistema cruza a língua escolhida pelo participante.</p></section>`;
}

acts['model-download']=async()=>{
 const q=Number(document.querySelector('[name=model-data-questions]')?.value||modelDataQuestions);
 if(!Number.isInteger(q)||q<1||q>180)throw new Error('Informe de 1 a 180 questões.');
 modelDataQuestions=q;modelDataLogin=document.querySelector('[name=model-data-login]')?.checked??true;modelDataDate=document.querySelector('[name=model-data-date]')?.checked??true;
 await downloadPost('/api/model-data/template',{questions:q,login:modelDataLogin,dateField:modelDataDate},'MODELO_DADOS.xlsx');
 const box=$('#model-downloaded');if(box)box.textContent='Modelo gerado. Preencha as duas abas e importe em Desempenho.';
 toast('MODELO DADOS.xlsx gerado.');
};

function workbookEntry(){return `<section class="card model-entry"><h2>Importar MODELO DADOS.xlsx</h2><p>O arquivo deve conter <strong>DADOS DOS ALUNOS</strong> e <strong>DADOS DO SIMULADO</strong>. As respostas podem permanecer como A, B, C, D ou E. Somente uma alternativa isolada A, B, C, D ou E é válida. Qualquer outro conteúdo (ex.: A/A, A|A, A | A, x, x/x, números, símbolos, texto ou vazio) será considerado erro (0).</p><p class="micro"><strong>Vínculo dos alunos:</strong> o sistema procura primeiro o nome completo. O login serve apenas para desempatar homônimos.</p><div class="actions">${button('Gerar modelo simples','perf-template','secondary')}</div><label>Arquivo Excel preenchido (até 3 MB)<input id="workbook-file" type="file" accept=".xlsx"></label><p id="workbook-filename">${esc(workbookDraft?.filename||'Nenhum arquivo selecionado.')}</p>${button('Ler e conferir arquivo','workbook-inspect','primary')}<div id="workbook-inspection">${workbookDraft?.inspection?workbookInspection(workbookDraft.inspection):''}</div><div id="workbook-preview" class="workbook-preview">${workbookDraft?.preview?workbookPreview(workbookDraft.preview):''}</div></section>`;}

function workbookInspection(d){
 const warnings=(d.warnings||[]).map(x=>'<li>'+esc(x)+'</li>').join('');
 return `<hr><h3>Arquivo reconhecido</h3><p><strong>${d.rows}</strong> participantes · <strong>${d.mapRows}</strong> linhas no mapa · questões ${String(d.firstQuestion).padStart(2,'0')}–${String(d.lastQuestion).padStart(2,'0')}.</p><p><strong>Simulado:</strong> ${esc(d.title)} · <strong>Cores:</strong> ${d.colors.map(esc).join(', ')}</p><div class="form-grid">${input('Data de aplicação','workbook-date',workbookDraft?.date||d.date||'','date','required')}${resultImportOption(check('Substituir respostas/resultados existentes','workbook-replace',!!workbookDraft?.replace),'result-import-help-results','Explicar substituição de respostas e resultados')}${resultImportOption(check('Substituir classificações existentes do mapa','workbook-replace-map',!!workbookDraft?.replaceMap),'result-import-help-map','Explicar substituição das classificações do mapa')}</div>${warnings?'<div class="notice warning"><strong>Conferências necessárias:</strong><ul>'+warnings+'</ul></div>':''}<p class="micro">A coluna % ACERTOS do arquivo não é importada como verdade. O sistema recalcula os percentuais com as respostas vinculadas.</p>${button('Vincular alunos e gerar prévia','workbook-preview','primary')}`;
}

function workbookPayload(){
 if(!workbookDraft?.file)throw new Error('Selecione o Excel preenchido.');
 const bindings=Object.fromEntries($$('[data-workbook-student]').map(e=>[e.dataset.workbookStudent,e.value]));
 return {file:workbookDraft.file,filename:workbookDraft.filename,date:document.querySelector('[name=workbook-date]')?.value||workbookDraft.date||'',replace:document.querySelector('[name=workbook-replace]')?.checked??workbookDraft.replace??false,replaceMap:document.querySelector('[name=workbook-replace-map]')?.checked??workbookDraft.replaceMap??false,mapping:Object.keys(bindings).length?bindings:workbookDraft.mapping||{}};
}

function workbookPreview(d){
 const s=d.summary,warnings=(s.warnings||[]).map(x=>'<li>'+esc(x)+'</li>').join('');
 return `<hr><h3>Conferência antes de salvar</h3><p><strong>${esc(s.title)}</strong> · ${br(s.date)} · cores: ${(s.colors||[]).map(esc).join(', ')}</p><p>${s.linked} alunos vinculados; ${s.new} resultados novos; ${s.updated} atualizados; ${s.unchanged} sem mudança; ${s.conflicts} divergências preservadas, salvo substituição marcada.</p><p>Mapas: ${s.map.total} questões/versões · ${s.map.new} novas · ${s.map.updated} atualizadas · ${s.map.conflicts} divergências.</p>${warnings?'<div class="notice warning"><ul>'+warnings+'</ul></div>':''}<div class="table-wrap"><table><thead><tr><th>Aluno do arquivo</th><th>Turma</th><th>Cor</th><th>Conta no site</th></tr></thead><tbody>${d.students.map(x=>`<tr><td>${esc(x.name)}</td><td>${esc(x.group)}</td><td>${esc(x.color)}</td><td><select data-workbook-student="${esc(x.key)}"><option value="">Não importar este aluno</option>${d.accounts.map(a=>`<option value="${esc(a.id)}" ${d.mapping[x.key]===a.id?'selected':''}>${esc(a.name)} (${esc(a.username)})</option>`).join('')}</select></td></tr>`).join('')}</tbody></table></div>${s.unresolved?check('Ignorar alunos sem vínculo e importar somente os vinculados','workbook-skip',false):''}${(d.sample||[]).map(x=>'<details><summary>Prévia detalhada de '+esc(x.name)+'</summary>'+workbookAnalysis(x.analysis)+'</details>').join('')}<div class="actions">${button('Atualizar prévia','workbook-preview')}${button('Confirmar importação','workbook-confirm','primary')}</div><p id="workbook-token-state" role="status">Nenhum dado foi gravado até a confirmação.</p>`;
}

acts['workbook-inspect']=async()=>{
 if(!workbookDraft?.file)throw new Error('Selecione o Excel preenchido.');
 const d=await api('/api/model-data/inspect',{file:workbookDraft.file,filename:workbookDraft.filename,date:workbookDraft.date||''});
 workbookDraft={...workbookDraft,inspection:d,date:d.date||workbookDraft.date||'',token:null,preview:null,mapping:{}};
 $('#workbook-inspection').innerHTML=workbookInspection(d);$('#workbook-preview').innerHTML='';
};
acts['workbook-preview']=async()=>{
 const p=workbookPayload(),d=await api('/api/model-data/preview',p);
 workbookDraft={...p,inspection:workbookDraft.inspection,preview:d,token:d.token,mapping:d.mapping};
 $('#workbook-preview').innerHTML=workbookPreview(d);
};
acts['workbook-confirm']=async()=>{
 if(!workbookDraft?.token)throw new Error('Atualize a prévia após alterar opções ou vínculos.');
 const p=workbookPayload();p.token=workbookDraft.token;p.skipUnmapped=document.querySelector('[name=workbook-skip]')?.checked||false;
 if(!confirm('Converter as alternativas pelo gabarito e salvar os resultados nas contas vinculadas?'))return;
 const d=await api('/api/model-data/confirm',p);workbookDraft=null;render();toast('Importação concluída: '+d.summary.new+' resultados novos; '+d.summary.updated+' atualizados.');
};

const modelDataPreviousPerformanceRecord=performanceRecord;
performanceRecord=function(r){
 let html=modelDataPreviousPerformanceRecord(r);
 if(r.analysis?.overall){
  const buttonHtml=button('Baixar detalhamento em Excel','model-data-detail','secondary',`data-record="${esc(r.id)}"`);
  html=html.replace('</details>',`<div class="actions">${buttonHtml}</div></details>`);
 }
 return html;
};
acts['model-data-detail']=async el=>{
 const response=await fetch('/api/model-data/detail?user='+encodeURIComponent(target)+'&record='+encodeURIComponent(el.dataset.record),{credentials:'same-origin',cache:'no-store'});
 if(!response.ok){let message='Não foi possível gerar o detalhamento.';try{const d=await response.json();message=d.error||message;}catch{}throw new Error(message);}
 const blob=await response.blob(),url=URL.createObjectURL(blob),a=document.createElement('a');a.href=url;a.download='Detalhamento_resultado.xlsx';document.body.appendChild(a);a.click();a.remove();setTimeout(()=>URL.revokeObjectURL(url),1000);
};


// === MEU CRONOGRAMA: AJUDA E REGRAS DE IMPORTAÇÃO ===
function resultImportOption(fieldHtml, action, label){
 return `<div style="display:flex;align-items:center;gap:.55rem;min-width:0">${fieldHtml}<button type="button" class="secondary" data-act="${action}" aria-label="${esc(label)}" title="${esc(label)}" style="width:2rem;height:2rem;min-width:2rem;padding:0;border-radius:999px;font-weight:800">?</button></div>`;
}

acts['result-import-help-results']=()=>modal(
 'Substituir respostas/resultados existentes',
 '<p>Use somente ao reenviar o <strong>mesmo simulado na mesma data</strong> com respostas corrigidas.</p><p>Marcada, a nova importação regrava os resultados já existentes dos alunos vinculados. Desmarcada, resultados anteriores são preservados e divergências não são sobrescritas.</p>',
 null
);
acts['result-import-help-map']=()=>modal(
 'Substituir classificações existentes do mapa',
 '<p>Use quando corrigir o mapa das questões: área, disciplina, tópico, assunto, habilidade, língua estrangeira ou gabarito.</p><p>Ao corrigir o <strong>gabarito</strong>, marque também a substituição de respostas/resultados para recalcular os acertos dos alunos.</p>',
 null
);
