"use strict";
// === SCHEDULE ADMIN REFINEMENT V1 ===
function studyPresetSelectedAccountName(){
 return String(P?.name||S?.profile?.name||'Conta selecionada');
}
function studyPresetAdminAssociation(){
 if(typeof manages!=='function'||!manages())return '';
 const actorId=typeof ME!=='undefined'?String(ME.id||''):'';
 const selectedId=String(typeof target!=='undefined'?target:'');
 const selectedName=studyPresetSelectedAccountName();
 if(actorId&&selectedId===actorId){
  return `<section class="card study-preset-association"><div class="page-head"><div><p class="eyebrow">PERFIS DE ORGANIZAÇÃO</p><h2>Associar perfil-base a um aluno</h2><p>Selecione primeiro uma conta de aluno no campo <strong>Conta</strong>, no topo da página. Depois volte a este painel para escolher e aplicar o perfil.</p></div></div></section>`;
 }
 return `<section class="card study-preset-association-intro"><div class="page-head"><div><p class="eyebrow">ALUNO SELECIONADO</p><h2>${esc(selectedName)}</h2><p>O perfil escolhido abaixo será associado somente a esta conta. Para trocar o aluno, use o campo <strong>Conta</strong> no topo.</p></div>${button('Abrir rotina do aluno','study-preset-open-routine','secondary')}</div></section>`+studyPresetPanel();
}
if(typeof accountsView==='function'){
 const studyPresetAdminBaseAccountsView=accountsView;
 accountsView=function(){return studyPresetAdminAssociation()+studyPresetAdminBaseAccountsView();};
}
if(typeof coordinatorView==='function'){
 const studyPresetAdminBaseCoordinatorView=coordinatorView;
 coordinatorView=function(){return studyPresetAdminAssociation()+studyPresetAdminBaseCoordinatorView();};
}
acts['study-preset-open-routine']=()=>{view='routine';render();window.scrollTo(0,0);};

function removeRankingFromTriSummary(root=document){
 const nodes=root.querySelectorAll?.('small,span,p')||[];
 nodes.forEach(node=>{
  if(node.childElementCount)return;
  const text=String(node.textContent||'');
  if(!/TRI\s*geral/i.test(text)||!/ranking/i.test(text))return;
  node.textContent=text.replace(/\s*[·|—-]\s*ranking\s*[-\d.,ºª]+/ig,'').replace(/\s{2,}/g,' ').trim();
 });
}
const rankingObserver=new MutationObserver(records=>{for(const record of records)for(const node of record.addedNodes)if(node.nodeType===1)removeRankingFromTriSummary(node);});
rankingObserver.observe(document.documentElement,{childList:true,subtree:true});
queueMicrotask(()=>removeRankingFromTriSummary());
