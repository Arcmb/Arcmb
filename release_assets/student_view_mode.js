"use strict";
// === VISÃO DO ALUNO V3.7.19 ===
// Quando Master ou coordenação abrem a conta de um aluno, a interface passa a ser
// exatamente a do aluno (menu, abas e telas). Um aviso no topo de cada aba permite
// voltar ao usuário original. As permissões continuam sendo verificadas no servidor:
// isto altera apenas a apresentação.
let studentViewOwner=null;

function studentViewActive(){return !!(typeof ME!=='undefined'&&ME&&ME._studentView);}

function studentViewAccount(id){
 try{return (typeof accounts!=='undefined'&&Array.isArray(accounts))?accounts.find(a=>a&&a.id===id)||null:null;}catch(_){return null;}
}

function studentViewEnter(id){
 const owner=studentViewActive()?studentViewOwner:ME;
 if(!owner||!['master','coordenador'].includes(owner.role)||!id||id===owner.id)return false;
 const account=studentViewAccount(id);
 if(!account||!['aluno','user','especial'].includes(account.role))return false;
 studentViewOwner=owner;
 ME={...owner,id:account.id,name:account.name,username:account.username,role:account.role==='especial'?'especial':'aluno',must_change:0,_studentView:true};
 return true;
}

function studentViewLeave(){
 if(!studentViewActive()||!studentViewOwner)return;
 ME=studentViewOwner;studentViewOwner=null;
}

function studentViewChrome(){
 const note=document.getElementById('master-note');
 const wrap=document.getElementById('account-wrap');
 const label=document.getElementById('user-label');
 if(!studentViewActive()){
  if(note)note.classList.remove('student-view-banner');
  if(wrap&&studentViewOwner===null&&typeof manages==='function'&&manages())wrap.hidden=false;
  return;
 }
 if(wrap)wrap.hidden=true;
 if(label)label.textContent=ME.name+' · Aluno (visualização de '+studentViewOwner.name+')';
 if(note){
  note.hidden=false;note.classList.add('student-view-banner');
  note.innerHTML=`<strong>Você está vendo o Meu Cronograma como ${esc(ME.name)} vê.</strong> As alterações feitas aqui são salvas na conta do aluno. <span class="actions" style="display:inline-flex;margin-left:.75rem"><button type="button" class="secondary" data-act="student-view-return">Voltar ao meu usuário</button></span>`;
 }
 document.querySelectorAll('#nav [data-view="password"]').forEach(x=>x.remove());
}

(function installStudentView(){
 if(typeof render!=='function'||typeof acts==='undefined')return;
 const baseRender=render;
 render=function(){
  if(studentViewActive()&&view==='password')view='home';
  const out=baseRender.apply(this,arguments);
  studentViewChrome();
  return out;
 };
 const baseOpen=acts['open-account'];
 acts['open-account']=async function(e){
  const id=e?.dataset?.id;
  if(studentViewActive()&&id!==ME.id)studentViewLeave();
  if(typeof baseOpen==='function')await baseOpen.apply(this,arguments);
  if(id&&studentViewEnter(id)){view='home';render();window.scrollTo(0,0);}
 };
 const leave=async()=>{
  if(!studentViewActive())return;
  const owner=studentViewOwner;
  studentViewLeave();
  if(typeof baseOpen==='function')await baseOpen({dataset:{id:owner.id}});
  else{target=owner.id;await load();}
  view='accounts';render();window.scrollTo(0,0);
 };
 acts['student-view-return']=leave;
 acts['return-owner']=leave;
})();
