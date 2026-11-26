"use strict";
// === MEU CRONOGRAMA: CICLOS DE ANO LETIVO V2 ===
(function(){
 let statusCache=new Map(),comparisonCache=new Map(),loadingStatus=new Set(),loadingComparison=new Set();
 const canManage=()=>typeof manages==='function'&&manages();
 const id=()=>String(typeof target!=='undefined'&&target?target:'');
 const own=()=>String(typeof ME!=='undefined'&&ME?.id?ME.id:'');
 const contextId=()=>id()||own();
 const pct=v=>v===null||v===undefined?'—':Number(v).toLocaleString('pt-BR',{minimumFractionDigits:1,maximumFractionDigits:1})+'%';
 const studentSelected=()=>canManage()&&!!contextId();

 async function loadStatus(force=false){
  const key=contextId();if(!studentSelected())return;
  if((!force&&statusCache.has(key))||loadingStatus.has(key))return;
  loadingStatus.add(key);
  try{statusCache.set(key,await api('/api/academic-year?user='+encodeURIComponent(key)));}
  catch(e){statusCache.set(key,{error:e.message||'Não foi possível carregar o ano letivo.'});}
  finally{loadingStatus.delete(key);if(view==='accounts'||view==='coordinator')render();}
 }
 async function loadComparison(force=false){
  const key=contextId();if(!studentSelected())return;
  if((!force&&comparisonCache.has(key))||loadingComparison.has(key))return;
  loadingComparison.add(key);
  try{comparisonCache.set(key,await api('/api/academic-year/comparison?user='+encodeURIComponent(key)));}
  catch(e){comparisonCache.set(key,{error:e.message||'Não foi possível comparar os anos.'});}
  finally{loadingComparison.delete(key);if(view==='performance')render();}
 }
 function yearPanel(){
  if(!canManage())return '';
  if(!studentSelected())return '';
  const key=contextId();
  if(!statusCache.has(key)&&!loadingStatus.has(key))queueMicrotask(()=>loadStatus());
  const d=statusCache.get(key);
  if(!d)return '<section class="card academic-year-card"><h2>Ano letivo</h2><p>Carregando situação do perfil…</p></section>';
  if(d.error)return '<section class="card academic-year-card"><h2>Ano letivo</h2><div class="notice warning">'+esc(d.error)+'</div>'+button('Tentar novamente','academic-year-refresh','secondary')+'</section>';
  const archived=(d.archived||[]).map(x=>'<span class="academic-year-pill">'+x.academic_year+' disponível</span>').join('');
  const years=[...(d.availableYears||[])].sort((a,b)=>a-b);
  const newest=years.length?Math.max(...years.map(Number)):Number(d.activeYear);
  const options=years.map(y=>'<option value="'+y+'" '+(Number(y)===Number(d.activeYear)?'selected':'')+'>'+y+(Number(y)===Number(d.activeYear)?' — ativo':' — acessar')+'</option>').join('')+(Number(d.activeYear)===newest?'<option value="'+d.nextYear+'">'+d.nextYear+' — iniciar novo ciclo</option>':'');
  return '<section class="card academic-year-card"><div class="page-head"><div><p class="eyebrow">ANO LETIVO</p><h2>Ano letivo de '+esc(d.student.name)+'</h2><p>Escolha qual ciclo ficará ativo para esta conta.</p></div>'+button('Atualizar','academic-year-refresh','secondary')+'</div>'+
   '<div class="academic-year-control"><label>Ano letivo ativo<select id="academic-year-select">'+options+'</select></label>'+button('Ativar ano selecionado','academic-year-activate','primary')+'</div>'+
   '<div class="stats"><div class="stat"><strong>'+d.activeYear+'</strong><span>ano ativo agora</span></div><div class="stat"><strong>'+(d.archived||[]).length+'</strong><span>ano(s) arquivado(s)</span></div></div>'+
   '<div class="notice"><strong>Navegação entre anos:</strong><p>Você pode alternar entre os anos já existentes sem apagar dados. Ao trocar de ano, o estado atual é salvo e o ciclo escolhido é carregado. Somente a opção “iniciar novo ciclo” cria um ano novo.</p></div>'+
   '<div class="academic-year-archive">'+(archived||'<span class="micro">Ainda não há outro ano disponível.</span>')+'</div></section>';
 }
 function comparePanel(){
  if(!studentSelected())return '';
  const key=contextId();
  if(!comparisonCache.has(key)&&!loadingComparison.has(key))queueMicrotask(()=>loadComparison());
  const d=comparisonCache.get(key);if(!d)return '<section class="card academic-year-compare"><h2>Evolução anual</h2><p>Carregando comparação…</p></section>';
  if(d.error)return '<section class="card academic-year-compare"><h2>Evolução anual</h2><div class="notice warning">'+esc(d.error)+'</div></section>';
  const p=d.previous||{},c=d.current||{},delta=d.delta;
  const deltaText=delta===null?'—':(delta>0?'+':'')+Number(delta).toLocaleString('pt-BR',{minimumFractionDigits:1,maximumFractionDigits:1})+' p.p.';
  const rows=(d.areas||[]).map(x=>'<tr><td>'+esc(x.name)+'</td><td>'+pct(x.previous)+'</td><td>'+pct(x.current)+'</td><td>'+(x.delta===null?'—':(x.delta>0?'+':'')+Number(x.delta).toLocaleString('pt-BR',{minimumFractionDigits:1,maximumFractionDigits:1})+' p.p.')+'</td></tr>').join('');
  return '<section class="card academic-year-compare"><div class="page-head"><div><p class="eyebrow">COMPARAÇÃO</p><h2>Evolução '+p.year+' → '+c.year+'</h2><p>'+esc(d.notice||'')+'</p></div>'+button('Atualizar comparação','academic-year-compare-refresh','secondary')+'</div><div class="academic-year-compare-grid"><div><span>Atividade inicial · média de '+p.year+'</span><strong>'+pct(p.accuracy)+'</strong><small>'+(p.simulations||0)+' simulado(s) · média '+(p.averageCorrect??'—')+' acertos</small></div><div class="academic-year-delta"><span>Evolução</span><strong>'+deltaText+'</strong><small>diferença no aproveitamento acumulado</small></div><div><span>'+c.year+'</span><strong>'+pct(c.accuracy)+'</strong><small>'+(c.simulations||0)+' simulado(s) · média '+(c.averageCorrect??'—')+' acertos</small></div></div>'+(rows?'<h3>Comparação por área</h3><div class="table-wrap"><table><thead><tr><th>Área</th><th>'+p.year+'</th><th>'+c.year+'</th><th>Variação</th></tr></thead><tbody>'+rows+'</tbody></table></div>':'<div class="notice">Ainda não há resultados suficientes nos dois anos para comparar por área.</div>')+'</section>';
 }
 if(typeof accountsView==='function'){const base=accountsView;accountsView=function(){return yearPanel()+base();};}
 if(typeof coordinatorView==='function'){const base=coordinatorView;coordinatorView=function(){return yearPanel()+base();};}
 if(typeof performanceView==='function'){const base=performanceView;performanceView=function(){return base()+comparePanel();};}
 acts['academic-year-refresh']=async()=>{statusCache.delete(contextId());await loadStatus(true);};
 acts['academic-year-compare-refresh']=async()=>{comparisonCache.delete(contextId());await loadComparison(true);};
 acts['academic-year-activate']=async()=>{
  const d=statusCache.get(contextId());if(!d)throw new Error('Atualize a situação do ano letivo.');
  const selected=Number(document.getElementById('academic-year-select')?.value||d.activeYear);
  if(selected===Number(d.activeYear)){toast(String(d.activeYear)+' já é o ano letivo ativo.');return;}
  const years=(d.availableYears||[]).map(Number);const newest=years.length?Math.max(...years):Number(d.activeYear);
  if(selected===Number(d.nextYear)&&Number(d.activeYear)===newest){
   const msg='Iniciar '+selected+' para '+d.student.name+'?\n\nO estado de '+d.activeYear+' será salvo e '+selected+' começará como um novo ciclo.';
   if(!confirm(msg))return;
   await api('/api/academic-year/open',{user:contextId(),year:selected});
  }else{
   const available=years;
   if(!available.includes(selected))throw new Error('Ano letivo indisponível para este aluno.');
   const msg='Acessar o ano '+selected+' de '+d.student.name+'?\n\nO estado atual de '+d.activeYear+' será salvo antes da troca.';
   if(!confirm(msg))return;
   await api('/api/academic-year/switch',{user:contextId(),year:selected});
  }
  statusCache.delete(contextId());comparisonCache.delete(contextId());toast('Ano '+selected+' ativado.');location.reload();
 };
})();
