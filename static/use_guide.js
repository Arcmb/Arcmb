"use strict";
// === MEU CRONOGRAMA: GUIA RÁPIDO V2 (v3.14.2) ===
// Uma dica curta por aba, com texto próprio para o aluno e para a gestão.
// Abre sozinha só para o aluno no próprio usuário, uma vez por aba. Para todos, fica no botão "? Ajuda" e na aba "Guia de Uso".
(function(){
 const VERSION='1';let guideActive=false,lastAutoKey='';
 const escText=value=>String(value||'').replace(/[&<>"']/g,ch=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[ch]));
 const norm=value=>String(value||'').normalize('NFD').replace(/[̀-ͯ]/g,'').toLocaleLowerCase('pt-BR').trim();
 const slug=value=>norm(value).replace(/[^a-z0-9]+/g,'-').replace(/^-|-$/g,'')||'aba';
 const STUDENT={
  home:['O resumo da sua semana: o que estudar hoje, as revisões que vencem e como foi o último simulado.','O cartão "Meu foco de estudos" mostra como o motor está organizando seus estudos. Você pode trocar o foco.','Para ver a semana completa, abra o Quadro semanal.'],
  mapping:['São 20 perguntas rápidas sobre como você estuda.','As respostas ajustam o tamanho dos blocos, as pausas e a carga de cada dia.','Leva uns 5 minutos. Refaça quando sua rotina mudar.'],
  diagnosis:['Conte com suas palavras o seu objetivo, os prazos e o que costuma atrapalhar.','A coordenação lê estas respostas para orientar você melhor.','Elas não mudam o cronograma automaticamente.'],
  routine:['Marque os horários livres e os compromissos fixos: escola, trabalho, cursos.','O cronograma só coloca estudo onde você disse que está livre.','Mudou a rotina? Atualize aqui e gere a semana de novo.'],
  subjects:['Suas disciplinas, cada uma com dificuldade e importância de 1 a 5.','Quanto mais difícil e importante, mais espaço ela ganha na semana.','As disciplinas dos simulados aparecem aqui sozinhas.'],
  contents:['Registre cada assunto que estudou e quando.','É daqui que nascem as revisões, nos dias certos para não esquecer.','Os erros dos simulados também entram como conteúdos para revisar.'],
  calendar:['Sua semana montada em blocos de estudo e de revisão.','Depois de estudar, marque cada bloco como feito, parcial ou não feito.','Mudou horários ou disciplinas? Use "Gerar semana".'],
  reviews:['Tudo o que precisa voltar, organizado em atrasadas, de hoje e próximas.','Na tabela você vê o histórico de cada conteúdo e as próximas datas.','Não deu tempo hoje? Remarque, sem acumular uma lista impossível.'],
  checks:['Confirme o que você realmente conseguiu fazer na semana.','Isso calibra a próxima semana para caber na sua vida real.'],
  performance:['Seus simulados: nota TRI por área, acertos e evolução.','Veja as disciplinas e os assuntos em que mais errou.','Esses erros já entram nas suas revisões.'],
  reports:['Relatórios que a coordenação preparou para você.'],
  password:['Troque sua senha aqui. Use pelo menos 12 caracteres e não repita senhas de outros sites.']
 };
 STUDENT['review-table']=STUDENT.reviews;
 const MANAGER={
  home:['Painel da coordenação: participação, acertos, TRI, redação e turmas.','Use os filtros de ano, turma e simulado para recortar os números.','Para abrir um aluno, use "Pesquisar aluno" no topo da tela.'],
  'result-model':['Gere a planilha modelo para lançar os resultados de um simulado.','Escolha as cores da prova e o número de questões antes de baixar.'],
  'result-import':['Importe a planilha do simulado com as respostas dos alunos e o gabarito.','Confira a prévia antes de confirmar: nada é salvo antes disso.','Os erros de cada aluno viram revisões automaticamente.'],
  performance:['Resultados importados, por aluno e por simulado.','Para ver como um aluno vê, abra-o pela busca no topo.'],
  reports:['Relatórios publicados para os alunos.'],
  'report-admin':['Cadastre e publique relatórios para os alunos.'],
  'result-export':['Baixe os resultados em planilha para análises fora do sistema.'],
  exams:['O mapa de cada simulado: disciplina, assunto e habilidade de cada questão.','No fim da página, o quadro "Disciplinas oficiais" padroniza os nomes das disciplinas nas importações.'],
  'enem-items':['Banco de itens do ENEM com os parâmetros a, b e c da TRI.','Mostra a dificuldade cobrada, a complexidade de resolução e os conteúdos que mais caem.','Baixe a planilha modelo, preencha e importe.'],
  data:['Cópias de segurança e restauração dos dados.'],
  password:['Troque sua senha aqui. Use pelo menos 12 caracteres.'],
  'school-reports':['Relatórios para a coordenação e para entregar aos professores.','Alunos que pedem atenção, análise por questão, assuntos, disciplinas, redação e perfis por turma.','No topo, escolha o ano letivo e compare com outro ano. Tudo pode ser baixado em CSV.'],
  motor:['As regras do motor de estudos: faixas de nota e parâmetros de cada perfil de foco.','As mudanças valem para todos os alunos na próxima vez que a semana for gerada.'],
  accounts:['Cadastro de alunos e da coordenação, turmas e senhas provisórias.','Para abrir um aluno, use "Pesquisar aluno" no topo da tela.']
 };
 const GENERIC=['Use os campos e botões desta tela para registrar ou consultar as informações.','Se precisar rever esta dica, toque em "? Ajuda".'];
 function me(){try{return typeof ME!=='undefined'?ME:null;}catch(_){return null;}}
 function managerOwn(){const u=me();return !!(u&&!u._studentView&&['master','coordenador'].includes(u.role));}
 function learnerId(){try{return String(typeof target!=='undefined'&&target?target:'self');}catch(_){return 'self';}}
 function autoOffKey(){const u=me();return 'meucronograma:tutorial:auto-off:'+(u?u.id:'');}
 function autoTutorialAllowed(){
  try{
   if(typeof window.qiOnboardingPending==='function'&&window.qiOnboardingPending())return false;
   const u=me();if(!u||u._studentView||!['aluno','user','especial'].includes(u.role))return false;
   return localStorage.getItem(autoOffKey())!=='1';
  }catch(_){return false;}
 }
 function storageKey(key){return `meucronograma:tutorial:${VERSION}:${learnerId()}:${key}`;}
 function wasSeen(key){try{return localStorage.getItem(storageKey(key))==='1';}catch(_){return false;}}
 function markSeen(key){try{localStorage.setItem(storageKey(key),'1');}catch(_){}}
 function navRoot(){return document.getElementById('nav')||document.querySelector('aside nav')||document.querySelector('nav');}
 function cleanLabel(button){
  if(!button)return 'Esta aba';
  const clone=button.cloneNode(true);clone.querySelectorAll('.nav-number,[aria-hidden="true"]').forEach(x=>x.remove());
  return String(clone.textContent||'Esta aba').replace(/\s+/g,' ').trim();
 }
 function navButtons(){const root=navRoot();if(!root)return[];return Array.from(root.querySelectorAll('button')).filter(b=>!b.classList.contains('guide-use-nav-button')&&String(b.textContent||'').trim());}
 function activeNav(){return navButtons().find(b=>b.classList.contains('active')||b.getAttribute('aria-current')==='page')||null;}
 function tabInfo(button){const label=cleanLabel(button);return{label,key:String(button?.dataset?.view||slug(label))};}
 function stepsFor(info){
  const book=managerOwn()?MANAGER:STUDENT;
  return book[info.key]||STUDENT[info.key]||MANAGER[info.key]||GENERIC;
 }
 function ensureOverlay(){
  let overlay=document.getElementById('qg-overlay');if(overlay)return overlay;
  overlay=document.createElement('div');overlay.id='qg-overlay';overlay.className='qg-overlay';
  overlay.innerHTML='<section class="qg-dialog" role="dialog" aria-modal="true" aria-labelledby="qg-title"><header class="qg-head"><span class="qg-kicker">Guia rápido</span><h2 id="qg-title"></h2><button type="button" class="qg-close" aria-label="Fechar">×</button></header><ol id="qg-steps" class="qg-steps"></ol><footer class="qg-foot"><label class="qg-never"><input type="checkbox" id="qg-never"> Não abrir dicas sozinhas</label><button type="button" class="qg-ok" id="qg-ok">Entendi</button></footer></section>';
  document.body.appendChild(overlay);return overlay;
 }
 function openTutorial(info,force=false){
  if(!info)return;if(!force&&wasSeen(info.key))return;
  const overlay=ensureOverlay(),steps=stepsFor(info);
  overlay.querySelector('#qg-title').textContent=info.label;
  overlay.querySelector('#qg-steps').innerHTML=steps.map(s=>`<li>${escText(s)}</li>`).join('');
  const never=overlay.querySelector('#qg-never');never.checked=false;
  const u=me();overlay.querySelector('.qg-never').hidden=!(u&&!u._studentView&&['aluno','user','especial'].includes(u.role));
  const finish=()=>{markSeen(info.key);if(never.checked){try{localStorage.setItem(autoOffKey(),'1');}catch(_){}}overlay.classList.remove('open');document.removeEventListener('keydown',onKey);};
  const onKey=e=>{if(e.key==='Escape')finish();};
  overlay.querySelector('#qg-ok').onclick=finish;overlay.querySelector('.qg-close').onclick=finish;
  overlay.onclick=e=>{if(e.target===overlay)finish();};
  document.addEventListener('keydown',onKey);
  overlay.classList.add('open');setTimeout(()=>overlay.querySelector('#qg-ok').focus({preventScroll:true}),30);
 }
 function renderGuidePage(){
  const main=document.getElementById('main')||document.querySelector('main');if(!main)return;
  const tabs=navButtons().map(tabInfo);
  main.innerHTML=`<div class="page-head use-guide-page-head"><div><p class="eyebrow">AJUDA</p><h1>Guia de Uso</h1><p>Uma explicação curta de cada aba. Toque em "Ver dica" para abrir.</p></div></div><section class="card"><div class="qg-grid">${tabs.map(x=>`<article class="qg-card"><div><h3>${escText(x.label)}</h3><p>${escText(stepsFor(x)[0])}</p></div><button type="button" class="secondary" data-guide-open="${escText(x.key)}" data-guide-label="${escText(x.label)}">Ver dica</button></article>`).join('')}</div>${managerOwn()?'':'<p class="micro">As dicas abrem sozinhas na primeira visita a cada aba. Para voltar a vê-las sozinhas, use o botão abaixo.</p><button type="button" class="secondary" data-guide-reset="1">Voltar a abrir dicas sozinhas</button>'}</section>`;
  main.querySelectorAll('[data-guide-open]').forEach(btn=>btn.addEventListener('click',()=>openTutorial({key:btn.dataset.guideOpen,label:btn.dataset.guideLabel},true)));
  const reset=main.querySelector('[data-guide-reset]');if(reset)reset.addEventListener('click',()=>{try{localStorage.removeItem(autoOffKey());Object.keys(localStorage).filter(k=>k.startsWith(`meucronograma:tutorial:${VERSION}:${learnerId()}:`)).forEach(k=>localStorage.removeItem(k));}catch(_){}if(typeof toast==='function')toast('As dicas voltam a abrir na primeira visita a cada aba.');});
 }
 function installGuideTab(){
  const root=navRoot();if(!root)return false;
  let button=root.querySelector('.guide-use-nav-button');
  if(!button){button=document.createElement('button');button.type='button';button.className='guide-use-nav-button';button.innerHTML='<span aria-hidden="true">?</span><span>Guia de Uso</span>';root.appendChild(button);
   button.addEventListener('click',()=>{guideActive=true;navButtons().forEach(b=>b.classList.remove('active'));button.classList.add('active');renderGuidePage();window.scrollTo(0,0);});}
  return true;
 }
 function currentInfo(){const b=activeNav();return b?tabInfo(b):null;}
 function installContextHelp(){
  if(guideActive)return;const main=document.getElementById('main')||document.querySelector('main');if(!main)return;
  if(main.querySelector('.use-guide-context'))return;const info=currentInfo();if(!info)return;
  const btn=document.createElement('button');btn.type='button';btn.className='secondary use-guide-context';btn.textContent='? Ajuda';
  btn.addEventListener('click',()=>openTutorial(currentInfo()||info,true));
  const head=main.querySelector('.page-head');
  if(head){const actions=head.querySelector('.actions');if(actions)actions.appendChild(btn);else head.appendChild(btn);}else main.prepend(btn);
 }
 function maybeAutoTutorial(){if(guideActive||!autoTutorialAllowed())return;const info=currentInfo();if(!info||wasSeen(info.key)||lastAutoKey===info.key)return;lastAutoKey=info.key;setTimeout(()=>{if(autoTutorialAllowed())openTutorial(info,false);},350);}
 document.addEventListener('click',event=>{const native=event.target.closest('#nav button,aside nav button');if(native&&!native.classList.contains('guide-use-nav-button')){guideActive=false;document.querySelector('.guide-use-nav-button')?.classList.remove('active');setTimeout(()=>{installContextHelp();maybeAutoTutorial();},80);}},true);
 function refresh(){installGuideTab();if(guideActive)renderGuidePage();else{installContextHelp();maybeAutoTutorial();}}
 if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',()=>setTimeout(refresh,120),{once:true});else setTimeout(refresh,120);
 window.addEventListener('load',refresh,{once:true});
 new MutationObserver(()=>{clearTimeout(window.__useGuideRefresh);window.__useGuideRefresh=setTimeout(()=>{installGuideTab();if(!guideActive)installContextHelp();},60);}).observe(document.documentElement,{childList:true,subtree:true});
 window.qiOpenGuide=()=>openTutorial(currentInfo(),true);
})();
