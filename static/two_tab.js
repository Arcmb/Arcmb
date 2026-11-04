'use strict';
// v2.8 — modelo definitivo com somente DADOS DOS ALUNOS e DADOS DO SIMULADO.
let v28QuestionCount=180;
let v28Colors='AZUL, AMARELO, BRANCO, VERDE';
let v28ExamTitle='';
let v28ExamDate='';

function v28ColorList(){
 return String(document.querySelector('[name=v28-colors]')?.value||v28Colors)
  .split(/[,;|\n]+/).map(x=>x.trim()).filter(Boolean);
}

resultModelView=function(){
 if(!manages())return head('Modelo de dados','Acesso reservado ao Master e à coordenação.');
 const colors=v28ColorList(),mapPerColor=v28QuestionCount+(Math.min(v28QuestionCount,5));
 return head('Modelo de dados — duas abas','Um arquivo simples para respostas dos alunos e classificação completa do simulado.')+
 `<div class="notice"><strong>Estrutura definitiva:</strong> somente <strong>DADOS DOS ALUNOS</strong> e <strong>DADOS DO SIMULADO</strong>. Não há separação por abas de áreas, bonificação ou seleção de dezenas de campos.</div>`+
 `<section class="card"><h2>Gerar MODELO DADOS.xlsx</h2><div class="form-grid">${input('Nome do simulado (opcional para pré-preencher)','v28-title',v28ExamTitle,'text','maxlength="200"')}${input('Data de aplicação (opcional para pré-preencher)','v28-date',v28ExamDate,'date')}${input('Quantidade de questões respondidas por aluno','v28-questions',v28QuestionCount,'number','min="1" max="180" step="1" required')}${input('Cores da prova, separadas por vírgula','v28-colors',v28Colors,'text','maxlength="200" required')}</div><div class="actions">${button('Gerar arquivo com 2 abas','model-download','primary')}${button('Já tenho o arquivo: importar','model-to-results')}</div><p id="model-downloaded" role="status"></p></section>`+
 `<section class="card"><h2>Como Linguagens será tratada</h2><p><strong>DADOS DOS ALUNOS:</strong> cada participante possui somente 45 respostas de Linguagens — questões 01 a 45.</p><p><strong>DADOS DO SIMULADO:</strong> por cor, as questões 01 a 05 aparecem duas vezes: uma linha de Inglês e outra de Espanhol. As questões 06 a 45 aparecem uma vez. Portanto, Linguagens possui <strong>50 registros de mapa por cor</strong>, sem duplicar a resposta do aluno.</p><p>O sistema escolhe o gabarito, a habilidade, a disciplina, o tópico e o assunto de Inglês ou Espanhol conforme a língua estrangeira informada para o participante.</p></section>`+
 `<section class="card"><h2>Prévia da estrutura</h2><p><strong>DADOS DOS ALUNOS:</strong> identificação + ${v28QuestionCount} colunas de respostas A–E.</p><p><strong>DADOS DO SIMULADO:</strong> ${mapPerColor} registros por cor; com ${colors.length||0} cor(es), serão ${(colors.length||0)*mapPerColor} linhas pré-criadas no mapa.</p><p class="micro">Resposta correta = 1; diferente ou vazia = 0; anulada não gera acerto nem erro e fica fora do denominador.</p></section>`;
};

acts['model-download']=async()=>{
 const questions=Number(document.querySelector('[name=v28-questions]')?.value||180);
 if(!Number.isInteger(questions)||questions<1||questions>180)throw new Error('Informe de 1 a 180 questões.');
 const colors=v28ColorList();if(!colors.length)throw new Error('Informe ao menos uma cor da prova.');
 v28QuestionCount=questions;v28Colors=colors.join(', ');
 v28ExamTitle=document.querySelector('[name=v28-title]')?.value?.trim()||'';
 v28ExamDate=document.querySelector('[name=v28-date]')?.value||'';
 await downloadPost('/api/model-data/template',{questions,colors,title:v28ExamTitle,date:v28ExamDate},'MODELO_DADOS_2_ABAS.xlsx');
 const box=$('#model-downloaded');if(box)box.textContent='Arquivo gerado com somente DADOS DOS ALUNOS e DADOS DO SIMULADO.';
 toast('Modelo de duas abas gerado.');
};
