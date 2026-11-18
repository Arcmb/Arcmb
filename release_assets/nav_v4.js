"use strict";
// === NAVEGAÇÃO AGRUPADA V3.8.0 ===
// Reorganiza o menu em grupos com sub-abas, sem remover nenhuma tela: cada sub-aba
// abre exatamente a mesma tela de antes (mesmos formulários, ações e permissões).
const NAV4_STUDENT=[
 ['Início',[['home','Visão geral']]],
 ['Minha semana',[['calendar','Quadro semanal']]],
 ['Revisões',[['review-table','Tabela de revisões'],['reviews','Minhas revisões'],['contents','Conteúdos estudados'],['checks','Registrar o que fiz']]],
 ['Meus resultados',[['performance','Desempenho e simulados'],['reports','Meus relatórios']]],
 ['Configurar meu plano',[['routine','1 · Rotina e horários'],['subjects','2 · Disciplinas e metas']]],
 ['Diagnóstico',[['mapping','Mapeamento objetivo'],['diagnosis','Observações pessoais']]],
 ['Minha conta',[['data','Dados e backup'],['password','Minha senha']]]
];
const NAV4_MANAGER=[
 ['Painel da escola',[['home','Painel gerencial']]],
 ['Alunos e contas',[['accounts','Alunos e contas']]],
 ['Simulados',[['result-model','1 · Gerar modelo'],['result-import','2 · Importar resultados'],['exams','3 · Mapa de questões'],['performance','4 · Resultados e análise'],['result-export','5 · Exportar']]],
 ['Relatórios',[['report-admin','Cadastro de relatórios'],['reports','Relatórios por aluno']]],
 ['Minha conta',[['data','Dados e backup'],['password','Minha senha']]]
];

function nav4Groups(){
 const managing=typeof manages==='function'&&manages();
 const groups=managing?NAV4_MANAGER:NAV4_STUDENT;
 const viewing=typeof ME!=='undefined'&&ME&&ME._studentView;
 return groups.map(([label,subs])=>[label,subs.filter(([id])=>!(viewing&&id==='password'))]).filter(([,subs])=>subs.length);
}
function nav4Current(){
 const groups=nav4Groups();
 return groups.find(([,subs])=>subs.some(([id])=>id===view))||null;
}
function nav4Label(label){
 if(label==='Alunos e contas'&&typeof ME!=='undefined'&&ME?.role==='master')return 'Painel Master · contas';
 return label;
}

renderNav=function(){
 const nav=document.getElementById('nav');if(!nav)return;
 const current=nav4Current();
 nav.innerHTML=nav4Groups().map(([label,subs],i)=>{const on=current&&current[0]===label;return `<button data-view="${on?view:subs[0][0]}" class="${on?'active':''}" ${on?'aria-current="page"':''}><span class="nav-number">${String(i+1).padStart(2,'0')}</span>${esc(nav4Label(label))}</button>`;}).join('');
};

function nav4SubtabsHtml(){
 const current=nav4Current();
 if(!current||current[1].length<2)return '';
 return `<div class="nav4-subtabs" data-key="${esc(current[0]+'|'+view)}" role="tablist" aria-label="${esc(current[0])}">${current[1].map(([id,label])=>`<button type="button" role="tab" data-view="${id}" aria-selected="${view===id}" class="${view===id?'active':''}">${esc(label)}</button>`).join('')}</div>`;
}
function nav4EnsureSubtabs(){
 const main=document.getElementById('main');if(!main)return;
 const html=nav4SubtabsHtml();
 const old=main.querySelector(':scope > .nav4-subtabs');
 if(!html){if(old)old.remove();return;}
 const current=nav4Current(),key=current[0]+'|'+view;
 if(old&&old.dataset.key===key&&main.firstElementChild===old)return;
 if(old)old.remove();
 main.insertAdjacentHTML('afterbegin',html);
}

(function nav4Install(){
 const style=document.createElement('style');
 style.textContent='.nav4-subtabs{display:flex;gap:4px;flex-wrap:wrap;border-bottom:1px solid var(--line,#ecd2d7);margin:0 0 16px}'
  +'.nav4-subtabs button{border:0;background:transparent;color:var(--muted,#7b5c62);padding:8px 14px;border-bottom:3px solid transparent;font:inherit;font-weight:600;cursor:pointer;border-radius:0}'
  +'.nav4-subtabs button.active{color:var(--ink,#3b2026);border-bottom-color:var(--primary,#b65362)}'
  +'.nav4-subtabs button:focus-visible{outline:3px solid var(--primary,#b65362);outline-offset:2px}';
 document.head.appendChild(style);
 if(typeof render==='function'){
  const base=render;
  render=function(){const out=base.apply(this,arguments);try{renderNav();nav4EnsureSubtabs();}catch(_){}return out;};
 }
 const start=()=>{const main=document.getElementById('main');if(main)new MutationObserver(()=>nav4EnsureSubtabs()).observe(main,{childList:true});nav4EnsureSubtabs();};
 if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',start,{once:true});else start();
})();
