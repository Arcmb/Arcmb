"use strict";
// === RESPONSIVE UI SEARCH AND QI LOGO V3 ===
(function(){
 const norm=value=>String(value||'').normalize('NFD').replace(/[\u0300-\u036f]/g,'').toLocaleLowerCase('pt-BR').trim();
 function installAccountSearch(){
  const wrap=document.querySelector('#account-wrap'),select=document.querySelector('#account-select');
  if(!wrap||!select)return false;
  let box=document.querySelector('#account-search-wrap');
  if(!box){
   box=document.createElement('label');box.id='account-search-wrap';box.className='account-search-wrap';
   box.innerHTML='<span>Pesquisar aluno</span><div class="account-search-control"><input id="account-search" type="search" autocomplete="off" placeholder="Digite o nome do aluno" aria-label="Pesquisar aluno pelo nome"><button type="button" class="account-search-clear" title="Limpar pesquisa" aria-label="Limpar pesquisa">×</button><div id="account-search-results" class="account-search-results" role="listbox"></div></div><small id="account-search-count" aria-live="polite"></small>';
   wrap.parentNode.insertBefore(box,wrap);
  }
  wrap.style.display='none';
  const input=box.querySelector('#account-search'),results=box.querySelector('#account-search-results'),counter=box.querySelector('#account-search-count'),clear=box.querySelector('.account-search-clear');
  let entries=[];
  const matches=query=>{const q=norm(query);return entries.filter(item=>!q||norm(item.name).includes(q));};
  function closeResults(){results.classList.remove('open');results.innerHTML='';}
  function chooseItem(item){if(!item)return;if(select.value!==item.value){select.value=item.value;select.dispatchEvent(new Event('change',{bubbles:true}));}input.value=item.name;counter.textContent='Aluno selecionado';closeResults();}
  function refresh(){
   const q=input.value.trim(),found=matches(q);counter.textContent=q?`${found.length} aluno(s) encontrado(s)`:`${entries.length} aluno(s) disponível(is)`;
   results.innerHTML='';if(!q){closeResults();return;}
   found.slice(0,20).forEach(item=>{const b=document.createElement('button');b.type='button';b.className='account-search-result';b.textContent=item.name;b.setAttribute('role','option');b.addEventListener('mousedown',event=>{event.preventDefault();chooseItem(item);});results.appendChild(b);});
   results.classList.toggle('open',found.length>0);
  }
  function read(){entries=Array.from(select.options).map(option=>({value:String(option.value||''),name:String(option.textContent||'').trim()})).filter(item=>item.value&&item.name);const selected=select.selectedOptions?.[0];if(selected&&!input.matches(':focus'))input.value=String(selected.textContent||'').trim();refresh();}
  if(!box.dataset.bound){
   box.dataset.bound='1';input.addEventListener('input',refresh);input.addEventListener('focus',refresh);input.addEventListener('keydown',event=>{if(event.key==='Enter'){const found=matches(input.value);if(found.length){event.preventDefault();chooseItem(found[0]);}}else if(event.key==='Escape')closeResults();});
   clear.addEventListener('click',()=>{input.value='';counter.textContent=`${entries.length} aluno(s) disponível(is)`;closeResults();input.focus();});
   select.addEventListener('change',()=>{const selected=select.selectedOptions?.[0];if(selected){input.value=String(selected.textContent||'').trim();counter.textContent='Aluno selecionado';closeResults();}});
   document.addEventListener('mousedown',event=>{if(!box.contains(event.target))closeResults();});
   new MutationObserver(read).observe(select,{childList:true,subtree:true,characterData:true});new MutationObserver(()=>{box.hidden=wrap.hidden;}).observe(wrap,{attributes:true,attributeFilter:['hidden']});
  }
  box.hidden=wrap.hidden;read();return true;
 }
 function boot(){if(installAccountSearch())return;let attempts=0;const timer=setInterval(()=>{attempts+=1;if(installAccountSearch()||attempts>=50)clearInterval(timer);},120);}
 if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',boot,{once:true});else boot();window.addEventListener('load',installAccountSearch,{once:true});
})();