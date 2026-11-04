'use strict';
// v2.8.1 — modelo definitivo com somente DADOS DOS ALUNOS e DADOS DO SIMULADO.
let v281QuestionCount=180;
let v281Colors='AZUL, AMARELO, BRANCO, VERDE';
let v281ExamTitle='';
let v281ExamDate='';
let v281Observer=null;

function v281ColorList(){
 return String(document.querySelector('[name=v281-colors]')?.value||v281Colors)
  .split(/[,;|\n]+/).map(x=>x.trim()).filter(Boolean);
}

function v281ResultModelView(){
 if(!manages())return head('Modelo de dados','Acesso reservado ao Master e à coordenação.');
 const colors=v281ColorList(),mapPerColor=v281QuestionCount+Math.min(v281QuestionCount,5);
 return head('Modelo de dados — duas abas','Um arquivo simples para respostas dos alunos e classificação completa do simulado.')+
 `<div data-v281-model="1"><div class="notice"><strong>Estrutura definitiva:</strong> somente <strong>DADOS DOS ALUNOS</strong> e <strong>DADOS DO SIMULADO</strong>. Não há separação por abas de áreas, bonificação ou seleção de dezenas de campos.</div>`+
 `<section class="card"><h2>Gerar MODELO DADOS.xlsx</h2><div class="form-grid">${input('Nome do simulado (opcional para pré-preencher)','v281-title',v281ExamTitle,'text','maxlength="200"')}${input('Data de aplicação (opcional para pré-preencher)','v281-date',v281ExamDate,'date')}${input('Quantidade de questões respondidas por aluno','v281-questions',v281QuestionCount,'number','min="1" max="180" step="1" required')}${input('Cores da prova, separadas por vírgula','v281-colors',v281Colors,'text','maxlength="200" required')}</div><div class="actions">${button('Gerar arquivo com 2 abas','model-download','primary')}${button('Já tenho o arquivo: importar','model-to-results')}</div><p id="model-downloaded" role="status"></p></section>`+
 `<section class="card"><h2>Como Linguagens será tratada</h2><p><strong>DADOS DOS ALUNOS:</strong> cada participante possui somente 45 respostas de Linguagens — questões 01 a 45.</p><p><strong>DADOS DO SIMULADO:</strong> por cor, as questões 01 a 05 aparecem duas vezes: uma linha de Inglês e outra de Espanhol. As questões 06 a 45 aparecem uma vez. Portanto, Linguagens possui <strong>50 registros de mapa por cor</strong>, sem duplicar a resposta do aluno.</p><p>O sistema escolhe o gabarito, a habilidade, a disciplina, o tópico e o assunto de Inglês ou Espanhol conforme a língua estrangeira informada para o participante.</p></section>`+
 `<section class="card"><h2>Prévia da estrutura</h2><p><strong>DADOS DOS ALUNOS:</strong> identificação + ${v281QuestionCount} colunas de respostas A–E.</p><p><strong>DADOS DO SIMULADO:</strong> ${mapPerColor} registros por cor; com ${colors.length||0} cor(es), serão ${(colors.length||0)*mapPerColor} linhas pré-criadas no mapa.</p><p class="micro">Resposta correta = 1; diferente ou vazia = 0; anulada não gera acerto nem erro e fica fora do denominador.</p></section></div>`;
}

async function v281DownloadModel(){
 const questions=Number(document.querySelector('[name=v281-questions]')?.value||180);
 if(!Number.isInteger(questions)||questions<1||questions>180)throw new Error('Informe de 1 a 180 questões.');
 const colors=v281ColorList();if(!colors.length)throw new Error('Informe ao menos uma cor da prova.');
 v281QuestionCount=questions;v281Colors=colors.join(', ');
 v281ExamTitle=document.querySelector('[name=v281-title]')?.value?.trim()||'';
 v281ExamDate=document.querySelector('[name=v281-date]')?.value||'';
 await downloadPost('/api/model-data/template',{questions,colors,title:v281ExamTitle,date:v281ExamDate},'MODELO_DADOS_2_ABAS.xlsx');
 const box=$('#model-downloaded');if(box)box.textContent='Arquivo gerado com somente DADOS DOS ALUNOS e DADOS DO SIMULADO.';
 toast('Modelo de duas abas gerado.');
}

function v281ReplaceLegacyScreen(){
 const legacyPattern=new RegExp('Gerar Excel separado por '+'áreas','i');
 const legacyButton=[...document.querySelectorAll('button')].find(button=>legacyPattern.test(button.textContent||''));
 if(!legacyButton)return;
 const target=document.querySelector('main')||document.querySelector('#content')||document.querySelector('#app-content')||legacyButton.closest('.page')||legacyButton.parentElement;
 if(target&&!target.querySelector('[data-v281-model]'))target.innerHTML=v281ResultModelView();
}

function v281Install(){
 try{resultModelView=v281ResultModelView;}catch(_){globalThis.resultModelView=v281ResultModelView;}
 if(typeof acts==='object'&&acts)acts['model-download']=v281DownloadModel;
 if(typeof render==='function'){
  try{render();}catch(_){/* A tela pode ainda estar inicializando. */}
 }
 setTimeout(v281ReplaceLegacyScreen,0);
}

// Instala imediatamente e novamente depois de todos os scripts deferidos. Isso
// impede que o gerador antigo por áreas reassuma a tela após este arquivo.
v281Install();
document.addEventListener('DOMContentLoaded',v281Install,{once:true});
window.addEventListener('load',v281Install,{once:true});
document.addEventListener('DOMContentLoaded',()=>{
 if(typeof MutationObserver!=='undefined'){
  v281Observer=new MutationObserver(v281ReplaceLegacyScreen);
  v281Observer.observe(document.body,{childList:true,subtree:true});
  v281ReplaceLegacyScreen();
 }
},{once:true});
