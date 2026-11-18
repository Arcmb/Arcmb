"use strict";
// === RENOVAÇÃO DE SENHA PROVISÓRIA V3.7.17 ===
// Master e coordenação renovam a senha provisória (válida por 7 dias) de alunos
// que ainda não concluíram o primeiro acesso. A autorização é feita no servidor.
let provisionalRenewalResult=null;

function provisionalRenewalPanel(){
 if(typeof manages!=='function'||!manages())return '';
 const result=provisionalRenewalResult?`<div class="notice success" role="status"><strong>Senha provisória renovada.</strong><p>${esc(provisionalRenewalResult.name)} — login <strong>${esc(provisionalRenewalResult.username)}</strong>. Válida até ${esc(provisionalRenewalResult.expiresAt)}.</p></div>`:'';
 return `<section class="card provisional-renewal-panel" data-provisional-renewal-panel id="provisional-renewal-panel"><h2>Renovar senha provisória</h2><p>Senhas provisórias de novos cadastros valem <strong>7 dias</strong>. Se o prazo vencer antes do primeiro acesso, informe o login do aluno e uma nova senha provisória.</p><form id="provisional-renewal-form" class="form-grid"><label>Login do aluno<input name="username" required minlength="3" maxlength="40" autocapitalize="none" autocomplete="off"></label><label>Nova senha provisória<input name="password" type="password" required minlength="8" maxlength="128" autocomplete="new-password"></label><div class="actions"><button class="primary" type="submit">Renovar por 7 dias</button></div></form>${result}<p class="micro">Disponível somente para alunos que ainda não trocaram a senha provisória. Depois do primeiro acesso, a redefinição é feita pelo Master.</p></section>`;
}

function provisionalRenewalInsert(html){
 if(!html||html.includes('data-provisional-renewal-panel'))return html;
 const panel=provisionalRenewalPanel();
 if(!panel)return html;
 const marker='<section class="card bulk-accounts-panel"';
 if(html.includes(marker))return html.replace(marker,panel+marker);
 return html+panel;
}

if(typeof accountsView==='function'){
 const provisionalOriginalAccountsView=accountsView;
 accountsView=function(){return provisionalRenewalInsert(provisionalOriginalAccountsView());};
}
if(typeof coordinatorView==='function'){
 const provisionalOriginalCoordinatorView=coordinatorView;
 coordinatorView=function(){return provisionalRenewalInsert(provisionalOriginalCoordinatorView());};
}

document.addEventListener('submit',async event=>{
 if(event.target.id!=='provisional-renewal-form')return;
 event.preventDefault();
 const form=event.target,buttonEl=form.querySelector('button[type="submit"]');
 const username=String(form.elements.username.value||'').trim().toLowerCase();
 const password=String(form.elements.password.value||'');
 if(buttonEl){buttonEl.disabled=true;buttonEl.textContent='Renovando…';}
 try{
  provisionalRenewalResult=await api('/api/provisional/renew',{username,password});
  toast('Senha provisória renovada por 7 dias.');
  render();
 }catch(err){
  toast(err.message||'Não foi possível renovar a senha.',true);
  if(buttonEl){buttonEl.disabled=false;buttonEl.textContent='Renovar por 7 dias';}
 }
});
