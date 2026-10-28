'use strict';
// Model-first workflow. Field selection never edits a student's stored results.
let modelFields=null,modelRequest=null,modelSelection=new Set(['NOME','TIPO de prova','data de aplicação']);
let modelExtras=[],modelFormat='xlsx';
const modelRequired=new Set(['NOME','TIPO de prova','data de aplicação']);
const modelGroups=['Identificação','Notas e totais','Disciplinas','Habilidades','Questões'];
const modelNorm=s=>String(s).normalize('NFD').replace(/[\u0300-\u036f]/g,'').toLocaleLowerCase().replace(/\s+/g,' ').trim();
function allModelFields(){return [...(modelFields||[]),...modelExtras];}
function selectedModelFields(){return allModelFields().filter(x=>x.required||modelSelection.has(x.name)).map(x=>x.name);}
function modelGo(where){if(!safeLeave())return;view=where;render();window.scrollTo(0,0);}
async function loadModelFields(){
 if(modelFields)return;
 if(!modelRequest)modelRequest=api('/api/performance/fields').then(d=>{
  modelFields=d.fields;const names=new Set(modelFields.map(x=>modelNorm(x.name)));
  modelExtras=modelExtras.filter(x=>!names.has(modelNorm(x.name)));
 }).finally(()=>{modelRequest=null;});
 await modelRequest;
}
function modelRow(x,i){
 const checked=x.required||modelSelection.has(x.name),id='model-column-'+i;
 return `<tr class="${checked?'model-selected':''}" data-model-row><td class="model-tick"><input id="${id}" type="checkbox" data-model-field="${esc(x.name)}" data-model-group="${esc(x.group)}" ${checked?'checked':''} ${x.required?'disabled':''} aria-label="Incluir ${esc(x.name)} no modelo"></td><td><label for="${id}">${esc(x.name)}</label>${x.required?'<span class="tag">Obrigatório</span>':''}</td></tr>`;
}
function resultModelView(){
 if(!manages())return head('Modelo de resultados','Acesso reservado ao Master e à coordenação.');
 if(!modelFields){queueMicrotask(async()=>{try{await loadModelFields();if(view==='result-model')render();}catch(e){const b=$('#model-loading');if(b)b.textContent=e.message;}});return head('Modelo de resultados','Marque as informações que devem virar colunas na sua planilha.')+'<section class="card" id="model-loading">Carregando a lista de informações…</section>';}
 const fields=allModelFields();
 const groups=modelGroups.map(g=>{
  const rows=fields.map((x,i)=>({x,i})).filter(o=>o.x.group===g);
  return `<section class="card model-group" aria-label="${esc(g)}"><div class="model-group-title"><h2>${esc(g)}</h2><div class="actions">${button('Marcar grupo','model-group','secondary',`data-group="${esc(g)}" data-value="1"`)}${button('Desmarcar grupo','model-group','secondary',`data-group="${esc(g)}" data-value="0"`)}</div></div>${g==='Habilidades'?'<p class="micro">Acertos Hab 01 a 30. A área (LC, CH, CN ou MT) será informada ao importar os resultados.</p>':''}${g==='Questões'?`<div class="model-range">${input('Da questão','model-first',1,'number','min="1" max="180"')}${input('Até a questão','model-last',90,'number','min="1" max="180"')}${button('Marcar esse intervalo','model-range')}</div><p class="micro">1 = acerto, 0 = erro, vazio = não informado. Pode selecionar questões de 01 a 180.</p>`:''}<table class="model-field-table"><thead><tr><th>Incluir</th><th>Informação que será uma coluna no arquivo</th></tr></thead><tbody>${rows.map(o=>modelRow(o.x,o.i)).join('')}</tbody></table></section>`;
 }).join('');
 return head('Modelo de resultados','Marque as informações abaixo. O Excel será gerado somente com as colunas marcadas.')+
 `<div class="notice"><strong>Marcar campos → baixar modelo → preencher no Excel → importar resultados.</strong><br>Você não precisa enviar um arquivo para começar nem preencher valores nesta tela.</div>`+
 `<div class="actions model-main-actions">${button('Marcar todos os campos','model-all','secondary','data-value="1"')}${button('Desmarcar os opcionais','model-all','secondary','data-value="0"')}${button('Já preenchi a planilha: importar resultados','model-to-results')}</div>`+
 `<div class="model-layout"><div>${groups}<section class="card"><h2>Adicionar outra disciplina</h2><p>Ela será incluída na lista e marcada para entrar no modelo.</p><div class="model-custom">${input('Nome da disciplina','model-discipline','','text','maxlength="140" placeholder="Ex.: Robótica"')}${button('Adicionar disciplina','model-add','secondary')}</div></section></div>`+
 `<section class="card model-summary" aria-label="Prévia do arquivo modelo"><h2>Seu arquivo modelo</h2><p id="model-count" role="status" aria-live="polite"></p><p>As colunas sairão nesta ordem:</p><ol id="model-columns"></ol>${select('Formato do arquivo','model-format',modelFormat,[['xlsx','Excel (.xlsx)'],['csv','CSV UTF-8 (.csv)']])}<div class="actions">${button('Gerar modelo com os campos marcados','model-download','primary')}</div><p class="micro">Nome, tipo de prova e data identificam o registro e ficam sempre incluídos. Nenhum resultado será importado ao baixar o modelo.</p><p id="model-downloaded" role="status"></p></section></div>`;
}
function updateModelSummary(){
 const selected=selectedModelFields(),count=$('#model-count'),cols=$('#model-columns');
 if(count)count.textContent=selected.length+' colunas selecionadas';
 if(cols)cols.innerHTML=selected.map(n=>'<li>'+esc(n)+'</li>').join('');
 $$('[data-model-field]').forEach(el=>{el.checked=modelRequired.has(el.dataset.modelField)||modelSelection.has(el.dataset.modelField);el.closest('tr')?.classList.toggle('model-selected',el.checked);});
}
const renderBeforeModel=render;
render=function(){renderBeforeModel();if(view==='result-model')updateModelSummary();};
acts['perf-template']=()=>modelGo('result-model');
acts['model-to-results']=()=>modelGo('performance');
acts['model-all']=el=>{allModelFields().forEach(x=>{if(x.required)return;el.dataset.value==='1'?modelSelection.add(x.name):modelSelection.delete(x.name);});updateModelSummary();};
acts['model-group']=el=>{allModelFields().filter(x=>x.group===el.dataset.group&&!x.required).forEach(x=>{el.dataset.value==='1'?modelSelection.add(x.name):modelSelection.delete(x.name);});updateModelSummary();};
acts['model-range']=()=>{
 const a=Number(document.querySelector('[name=model-first]').value),b=Number(document.querySelector('[name=model-last]').value);
 if(!Number.isInteger(a)||!Number.isInteger(b)||a<1||b>180||a>b)throw new Error('Informe um intervalo entre 1 e 180.');
 allModelFields().filter(x=>x.group==='Questões').forEach(x=>{const n=Number(x.name.split(' ').at(-1));if(n>=a&&n<=b)modelSelection.add(x.name);else modelSelection.delete(x.name);});updateModelSummary();toast('Intervalo de questões marcado.');
};
acts['model-add']=()=>{
 const el=document.querySelector('[name=model-discipline]');let name=el.value.trim().replace(/^Acertos\s*[-–—]\s*/i,'').trim();
 if(!name||name.length>140)throw new Error('Informe o nome da disciplina (até 140 caracteres).');
 name='Acertos - '+name;const found=allModelFields().find(x=>modelNorm(x.name)===modelNorm(name));
 if(found){modelSelection.add(found.name);updateModelSummary();el.value='';toast('Disciplina existente marcada.');return;}
 if(allModelFields().length>=300)throw new Error('Limite de 300 campos. Use outro lote para mais disciplinas.');
 modelExtras.push({name,group:'Disciplinas',required:false});modelSelection.add(name);render();toast('Disciplina acrescentada e marcada.');
};
acts['model-download']=async()=>{
 const format=document.querySelector('[name=model-format]').value,fields=selectedModelFields();
 if(fields.length>300)throw new Error('Selecione no máximo 300 colunas por arquivo.');
 modelFormat=format;await downloadPost('/api/performance/template-selected',{fields,format},'Modelo_resultados_selecionados.'+format);
 const box=$('#model-downloaded');if(box)box.textContent='Modelo gerado. Preencha o arquivo baixado e depois use Desempenho → Importar planilha preenchida.';
 toast('Modelo gerado somente com as colunas marcadas.');
};
document.addEventListener('change',e=>{const el=e.target;if(el.matches('[data-model-field]')){el.checked?modelSelection.add(el.dataset.modelField):modelSelection.delete(el.dataset.modelField);updateModelSummary();}if(el.name==='model-format')modelFormat=el.value;});
// Put the model-first route before the upload, not behind the map-of-items screen.
const performanceBeforeModel=performanceView;
performanceView=function(){
 let html=performanceBeforeModel();if(!manages())return html;
 const intro=`<section class="card model-entry"><h2>1. Escolha as colunas e baixe o modelo</h2><p>Marque Nome, turma, notas, acertos, disciplinas, habilidades ou questões. O arquivo será criado somente com os campos escolhidos.</p>${button('Marcar campos e gerar modelo de resultados','perf-template','primary')}</section>`;
 html=html.replace('<section class="card"><h2>Importar resultados em lote</h2>',intro+'<section class="card"><h2>2. Importar planilha preenchida</h2>');
 html=html.replace('Mantenha as colunas existentes. Acrescente <strong>Acertos - Nome da disciplina</strong> e, opcionalmente, <strong>Questões - Nome da disciplina</strong>.','Preencha o modelo no Excel e envie-o aqui. Os cabeçalhos do modelo serão reconhecidos. Confira os alunos antes de confirmar a gravação.');
 html=html.replace('Escolher campos e gerar modelo','Voltar à seleção de campos').replace('Selecionar campos / conferir','Ler planilha preenchida');
 return html;
};
// Standard generated templates need no manual correspondence. Keep it optional
// for existing spreadsheets with different headers, without removing that support.
const selectionBeforeModel=perfSelection;
perfSelection=function(d){
 const mapping=mappingRows('perf',d,perfDraft);
 const known=new Set((d.fields||[]).map(x=>modelNorm(x.name)));
 const unknown=d.columns.some(x=>!x.suggested||!known.has(modelNorm(x.suggested))&&!/^Questões\s*[-–—]/i.test(x.suggested));
 const columns=d.columns.map(x=>perfDraft.columnMapping?.[x.index]??x.suggested).filter(Boolean);
 const optional=`<div class="notice"><strong>Colunas reconhecidas:</strong> ${columns.map(esc).join(' · ')}</div><details class="model-advanced" ${unknown?'open':''}><summary>${unknown?'Conferir cabeçalhos não padronizados':'Opcional: corrigir ou ignorar uma coluna de outro modelo'}</summary>${mapping}</details>`;
 return selectionBeforeModel(d).replace(mapping,optional).replace('1. Escolha as informações deste lote','3. Confira a planilha preenchida').replace('Uma coluna pode ser ligada a outro campo ou deixada de fora.','Se usou o modelo gerado, não é necessário escolher novamente os campos.');
};
const examsBeforeModel=examsView;
examsView=function(){return examsBeforeModel().replace('<section class="card"><div class="actions">','<section class="card model-entry"><h2>Esta página é somente para classificar questões</h2><p>O arquivo contém questão, disciplina, tópico, assunto e habilidade. <strong>Para escolher Nome, turma, notas e acertos dos alunos, use Modelo de resultados.</strong></p>'+button('Selecionar campos dos resultados dos alunos','perf-template','primary')+'</section><section class="card"><div class="actions">');};
const examSelectionBeforeModel=examSelection;
examSelection=function(d){
 const names=d.columns.map(x=>modelNorm(x.header).replace(/_/g,' '));
 const hasStudent=names.some(n=>['nome','nome do aluno','aluno'].includes(n));
 const hasQuestion=d.columns.some(x=>modelNorm(x.suggested)==='questao');
 if(hasStudent&&!hasQuestion)return '<div class="notice warning"><strong>Este arquivo parece conter resultados de alunos, não um mapa de questões.</strong><p>Não relacione Nome com Questão. Use Modelo de resultados para gerar a planilha, ou Desempenho para importar o arquivo preenchido.</p>'+button('Abrir seleção de campos do modelo','perf-template','primary')+' '+button('Ir para importação de resultados','model-to-results')+'</div>';
 return examSelectionBeforeModel(d);
};
