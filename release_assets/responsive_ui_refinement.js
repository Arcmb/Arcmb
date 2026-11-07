"use strict";
// === RESPONSIVE UI SEARCH AND QI LOGO V2 ===
(function(){
 const norm=value=>String(value||'').normalize('NFD').replace(/[\u0300-\u036f]/g,'').toLocaleLowerCase('pt-BR').trim();
 function installAccountSearch(){
  const wrap=document.querySelector('#account-wrap'),select=document.querySelector('#account-select');
  if(!wrap||!select)return false;
  let box=document.querySelector('#account-search-wrap');
  if(!box){
   box=document.createElement('label');
   box.id='account-search-wrap';
   box.className='account-search-wrap';
   box.innerHTML='<span>Pesquisar aluno</span><div class="account-search-control"><input id="account-search" type="search" autocomplete="off" placeholder="Digite parte do nome" list="account-search-list" aria-label="Pesquisar aluno pelo nome"><button type="button" class="account-search-clear" title="Limpar pesquisa" aria-label="Limpar pesquisa">×</button></div><datalist id="account-search-list"></datalist><small id="account-search-count" aria-live="polite"></small>';
   wrap.parentNode.insertBefore(box,wrap);
  }
  const input=box.querySelector('#account-search'),list=box.querySelector('#account-search-list'),counter=box.querySelector('#account-search-count'),clear=box.querySelector('.account-search-clear');
  let entries=[];
  const matches=query=>{const q=norm(query);return entries.filter(item=>!q||norm(item.name).includes(q));};
  function refresh(){
   const found=matches(input.value);
   list.innerHTML=found.slice(0,80).map(item=>`<option value="${item.name.replace(/&/g,'&amp;').replace(/"/g,'&quot;').replace(/</g,'&lt;').replace(/>/g,'&gt;')}"></option>`).join('');
   counter.textContent=input.value?`${found.length} aluno(s) encontrado(s)`:`${entries.length} aluno(s) disponível(is)`;
  }
  function read(){
   entries=Array.from(select.options).map(option=>({value:String(option.value||''),name:String(option.textContent||'').trim()})).filter(item=>item.value&&item.name);
   refresh();
  }
  function choose(){
   const q=norm(input.value);if(!q)return;
   const found=matches(input.value),chosen=found.find(item=>norm(item.name)===q)||(found.length===1?found[0]:null);
   if(!chosen)return;
   if(select.value!==chosen.value){select.value=chosen.value;select.dispatchEvent(new Event('change',{bubbles:true}));}
   input.value=chosen.name;refresh();
  }
  if(!box.dataset.bound){
   box.dataset.bound='1';
   input.addEventListener('input',refresh);
   input.addEventListener('change',choose);
   input.addEventListener('keydown',event=>{if(event.key==='Enter'){event.preventDefault();const found=matches(input.value);if(found.length&&!found.some(item=>norm(item.name)===norm(input.value)))input.value=found[0].name;choose();}});
   clear.addEventListener('click',()=>{input.value='';refresh();input.focus();});
   select.addEventListener('change',()=>{const selected=select.selectedOptions?.[0];if(selected){input.value=String(selected.textContent||'').trim();refresh();}});
   new MutationObserver(read).observe(select,{childList:true,subtree:true,characterData:true});
   new MutationObserver(()=>{box.hidden=wrap.hidden;}).observe(wrap,{attributes:true,attributeFilter:['hidden']});
  }
  box.hidden=wrap.hidden;
  read();
  return true;
 }
 function boot(){
  if(installAccountSearch())return;
  let attempts=0;
  const timer=setInterval(()=>{
   attempts+=1;
   if(installAccountSearch()||attempts>=50)clearInterval(timer);
  },120);
 }
 if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',boot,{once:true});
 else boot();
 window.addEventListener('load',installAccountSearch,{once:true});
})();
