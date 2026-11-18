"use strict";
// === VISÃO DO ALUNO E REVISÕES UNIFICADAS V3.8.2 ===
// 1) Quando Master ou coordenação passam a editar uma conta de aluno (por qualquer
//    caminho: busca do topo, lista de contas, botão de abrir), a interface mostra
//    somente o que o aluno usa. A troca é detectada no carregamento da conta.
// 2) "Minhas revisões" e "Tabela de revisões" ficam em um único item de menu,
//    com as duas visões preservadas como sub-abas.
// Apenas apresentação: toda permissão continua sendo verificada no servidor.
let svOwner=null;

function svActive(){return !!(typeof ME!=='undefined'&&ME&&ME._studentView);}
function svRealUser(){return svActive()?svOwner:(typeof ME!=='undefined'?ME:null);}
function svAccount(id){try{return Array.isArray(accounts)?accounts.find(a=>a&&String(a.id)===String(id))||null:null;}catch(_){return null;}}

function svSync(){
 const owner=svRealUser();
 if(!owner||!['master','coordenador'].includes(owner.role)){return;}
 const account=target&&String(target)!==String(owner.id)?svAccount(target):null;
 if(account&&['aluno','user','especial'].includes(account.role)){
  svOwner=owner;
  ME={...owner,id:account.id,name:account.name,username:account.username,role:account.role==='especial'?'especial':'aluno',must_change:0,_studentView:true};
  if(['password','accounts','exams','result-model','result-import','result-export','report-admin'].includes(view))view='home';
 }else if(svActive()){
  ME=svOwner;svOwner=null;
 }
}

async function svLeave(){
 if(!svActive())return false;
 const owner=svOwner;ME=owner;svOwner=null;
 target=owner.id;
 try{await refreshAccounts();}catch(_){}
 view='home';
 await load();
 window.scrollTo(0,0);
 return true;
}

const SV_REVIEW_VIEWS=[['review-table','Tabela de revisões'],['reviews','Programação e histórico']];
function svIsReviewView(){return view==='review-table'||view==='reviews';}

function svSubtabs(){
 const main=document.getElementById('main');if(!main)return;
 const old=main.querySelector(':scope > .sv-subtabs');
 if(!svIsReviewView()){if(old)old.remove();return;}
 if(old&&old.dataset.key===view&&main.firstElementChild===old)return;
 if(old)old.remove();
 main.insertAdjacentHTML('afterbegin',`<div class="sv-subtabs" data-key="${view}" role="tablist" aria-label="Revisões">${SV_REVIEW_VIEWS.map(([id,label])=>`<button type="button" role="tab" data-view="${id}" aria-selected="${view===id}" class="${view===id?'active':''}">${label}</button>`).join('')}</div>`);
}

function svHideAccountSelect(){
 const wrap=document.getElementById('account-wrap');
 if(wrap&&document.getElementById('account-search-wrap'))wrap.style.setProperty('display','none','important');
}

function svNavFix(){
const nav=document.getElementById('nav');
 if(nav){
  nav.querySelectorAll('[data-view="reviews"]:not([data-sv-merged])').forEach(b=>b.remove());
  if(svActive())nav.querySelectorAll('[data-view="password"]').forEach(b=>b.remove());
  if(svActive()||!(typeof manages==='function'&&manages()))nav.querySelectorAll('[data-view="data"]').forEach(b=>b.remove());
  const rev=nav.querySelector('[data-sv-merged]')||nav.querySelector('[data-view="review-table"]');
  if(rev){
   rev.dataset.svMerged='1';
   const num=rev.querySelector('.nav-number');
   rev.textContent='Revisões';if(num)rev.prepend(num);
   if(svIsReviewView()){rev.classList.add('active');rev.dataset.view=view;}else{rev.classList.remove('active');rev.dataset.view='review-table';}
  }
  nav.querySelectorAll('button .nav-number').forEach((n,i)=>{n.textContent=String(i+1).padStart(2,'0');});
 }
}

function svChrome(){
 svHideAccountSelect();
 const note=document.getElementById('master-note');
 const label=document.getElementById('user-label');
 if(svActive()){
  if(label)label.textContent=ME.name+' · Aluno (visualização de '+svOwner.name+')';
  if(note){
   note.hidden=false;
   note.innerHTML=`<strong>Você está vendo o Meu Cronograma como ${esc(ME.name)} vê.</strong> As alterações feitas aqui são salvas na conta do aluno. <button type="button" class="secondary" data-act="student-view-return">Voltar ao meu usuário</button>`;
  }
 }
 svNavFix();
 svSubtabs();
}

(function svInstall(){
 if(typeof render!=='function'||typeof load!=='function'||typeof acts==='undefined')return;
 const style=document.createElement('style');
 style.textContent='#account-wrap{display:none!important}'
  +'.sv-subtabs{display:flex;gap:4px;flex-wrap:wrap;border-bottom:1px solid var(--line,#ecd2d7);margin:0 0 16px}'
  +'.sv-subtabs button{border:0;background:transparent;color:var(--muted,#7b5c62);padding:8px 14px;border-bottom:3px solid transparent;font:inherit;font-weight:600;cursor:pointer;border-radius:0}'
  +'.sv-subtabs button.active{color:var(--ink,#3b2026);border-bottom-color:var(--primary,#b65362)}'
  +'.sv-subtabs button:focus-visible{outline:3px solid var(--primary,#b65362);outline-offset:2px}';
 document.head.appendChild(style);
 if(typeof renderNav==='function'){const baseNav=renderNav;renderNav=function(){const out=baseNav.apply(this,arguments);try{svNavFix();}catch(_){}return out;};}
 const baseLoad=load;
 load=async function(){svSync();return baseLoad.apply(this,arguments);};
 const baseRender=render;
 render=function(){
  if(svActive()&&view==='password')view='home';
  if(view==='data'&&(svActive()||!(typeof manages==='function'&&manages())))view='home';
  const out=baseRender.apply(this,arguments);
  try{svChrome();}catch(_){}
  return out;
 };
 const baseReturn=acts['return-owner'];
 acts['return-owner']=async function(){if(await svLeave())return;if(typeof baseReturn==='function')return baseReturn.apply(this,arguments);};
 acts['student-view-return']=async()=>{await svLeave();};
 const start=()=>{svHideAccountSelect();const wrap=document.getElementById('account-wrap');if(wrap)new MutationObserver(()=>{if(wrap.style.getPropertyPriority('display')!=='important')svHideAccountSelect();}).observe(wrap,{attributes:true,attributeFilter:['style','hidden']});const main=document.getElementById('main');if(main)new MutationObserver(()=>{try{svSubtabs();}catch(_){}}).observe(main,{childList:true});};
 if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',start,{once:true});else start();
})();
