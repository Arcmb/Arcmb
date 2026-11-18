"use strict";
// Resumo individual integrado à página Desempenho.
let studentSummaryCache=new Map();
let studentSummaryLoading=new Set();

function studentSummaryTarget(){return (typeof target!=='undefined'&&target)||(typeof P!=='undefined'&&P?.id)||(typeof ME!=='undefined'&&ME?.id)||'';}
function studentSummaryPercent(value){return value===null||value===undefined?'—':Number(value).toLocaleString('pt-BR',{minimumFractionDigits:1,maximumFractionDigits:1})+'%';}
function studentSummaryMinutes(value){const n=Number(value||0);if(n<60)return n+' min';const h=Math.floor(n/60),m=n%60;return h+'h'+(m?' '+m+'min':'');}
function studentSummaryRows(rows,limit=12){return (rows||[]).slice(0,limit).map(x=>`<tr><td>${esc(x.name)}</td><td>${x.correct||0}</td><td>${x.errors||0}</td><td>${studentSummaryPercent(x.accuracy)}</td><td>${x.marked||0}/${x.total||0}</td></tr>`).join('');}

async function loadStudentSummary(force=false){
 const id=studentSummaryTarget();if(!id)return;
 if(studentSummaryLoading.has(id))return;
 if(studentSummaryCache.has(id)&&!force)return;
 studentSummaryLoading.add(id);
 try{studentSummaryCache.set(id,await api('/api/model-data/student-summary?user='+encodeURIComponent(id)));}
 catch(err){studentSummaryCache.set(id,{error:err.message||'Não foi possível carregar o resumo.'});}
 finally{studentSummaryLoading.delete(id);if(view==='performance'||view==='home')render();}
}

function studentSummaryPanel(){
 const id=studentSummaryTarget();
 if(!studentSummaryCache.has(id)&&!studentSummaryLoading.has(id))queueMicrotask(()=>loadStudentSummary());
 if(studentSummaryLoading.has(id)||!studentSummaryCache.has(id))return `<section class="card"><h2>Resumo individual</h2><p>Carregando trajetória acadêmica…</p></section>`;
 const d=studentSummaryCache.get(id);if(d?.error)return `<section class="card"><h2>Resumo individual</h2><div class="notice warning">${esc(d.error)}</div>${button('Tentar novamente','student-summary-refresh','secondary')}</section>`;
 const s=d.study||{},p=d.performance||{};
 const subjects=(s.bySubject||[]).map(x=>`<tr><td>${esc(x.name)}</td><td>${x.studied||0}/${x.contents||0}</td><td>${studentSummaryMinutes(x.actualMinutes||0)}</td><td>${studentSummaryMinutes(x.plannedMinutes||0)}</td></tr>`).join('');
 const sims=(d.simulations||[]).map(x=>`<tr><td>${esc(x.activity)}</td><td>${esc(x.date)}</td><td>${esc(x.color||'—')}</td><td>${x.correct||0}/${x.valid||0}</td><td>${studentSummaryPercent(x.accuracy)}</td></tr>`).join('');
 const recent=(s.recentContents||[]).map(x=>`<li><strong>${esc(x.title)}</strong>${x.subject?' · '+esc(x.subject):''}${x.topic?' · '+esc(x.topic):''}<br><small>${x.status==='studied'?'Estudado':'Planejado'}${x.studiedOn?' em '+esc(x.studiedOn):''}</small></li>`).join('');
 return `<section class="card student-summary-card"><div class="item"><div><h2>Resumo individual de ${esc(d.student?.name||'aluno')}</h2><p>Conteúdos, tempo registrado e simulados consolidados no mesmo perfil.</p></div><div class="item-actions">${button('Atualizar resumo','student-summary-refresh','secondary')}</div></div><div class="stats"><div class="stat"><strong>${s.studied||0}/${s.contents||0}</strong><span>conteúdos estudados</span></div><div class="stat"><strong>${p.simulations||0}</strong><span>simulados</span></div><div class="stat"><strong>${p.correct||0}</strong><span>acertos acumulados</span></div><div class="stat"><strong>${studentSummaryPercent(p.accuracy)}</strong><span>aproveitamento</span></div><div class="stat"><strong>${studentSummaryMinutes(s.actualMinutes||0)}</strong><span>tempo registrado</span></div></div>${subjects?`<h3>Estudo por disciplina</h3><div class="table-wrap"><table><thead><tr><th>Disciplina</th><th>Conteúdos estudados</th><th>Tempo realizado</th><th>Tempo planejado</th></tr></thead><tbody>${subjects}</tbody></table></div>`:'<div class="notice">Ainda não há conteúdos de estudo cadastrados.</div>'}${sims?`<h3>Simulados realizados</h3><div class="table-wrap"><table><thead><tr><th>Simulado</th><th>Data</th><th>Cor</th><th>Acertos</th><th>Aproveitamento</th></tr></thead><tbody>${sims}</tbody></table></div>`:'<div class="notice">Ainda não há simulados associados a este perfil.</div>'}${(d.aggregates?.area||[]).length?`<h3>Desempenho acumulado por área</h3><div class="table-wrap"><table><thead><tr><th>Área</th><th>Acertos</th><th>Erros</th><th>Aproveitamento</th><th>Cobertura</th></tr></thead><tbody>${studentSummaryRows(d.aggregates.area)}</tbody></table></div>`:''}${(d.aggregates?.discipline||[]).length?`<h3>Desempenho acumulado por disciplina</h3><div class="table-wrap"><table><thead><tr><th>Disciplina</th><th>Acertos</th><th>Erros</th><th>Aproveitamento</th><th>Cobertura</th></tr></thead><tbody>${studentSummaryRows(d.aggregates.discipline,30)}</tbody></table></div>`:''}${recent?`<details><summary>Conteúdos mais recentes</summary><ul>${recent}</ul></details>`:''}<details><summary>Detalhamento por tópico, assunto e habilidade</summary>${['topic','subject','skill'].map(k=>{const title={topic:'Tópicos',subject:'Assuntos',skill:'Habilidades'}[k],rows=studentSummaryRows(d.aggregates?.[k]||[],40);return rows?`<h4>${title}</h4><div class="table-wrap"><table><thead><tr><th>Classificação</th><th>Acertos</th><th>Erros</th><th>Aproveitamento</th><th>Cobertura</th></tr></thead><tbody>${rows}</tbody></table></div>`:'';}).join('')}</details></section>`;
}

acts['student-summary-refresh']=async()=>{await loadStudentSummary(true);};

if(typeof performanceView==='function'){
 const studentSummaryOriginalPerformanceView=performanceView;
 performanceView=function(){
  const base=studentSummaryOriginalPerformanceView();
  const panel=studentSummaryPanel();
  const marker='<section class="card"';
  const pos=base.indexOf(marker);
  return pos>=0?base.slice(0,pos)+panel+base.slice(pos):base+panel;
 };
}

// === MEU CRONOGRAMA: TRAJETÓRIA ACADÊMICA NA VISÃO GERAL ===
const studentHomeAreaLabels={LC:'Linguagens',CH:'Humanas',CN:'Natureza',MT:'Matemática',RED:'Redação'};
function studentHomeNumber(value){const n=Number(value);return Number.isFinite(n)?n:0;}
function studentHomePct(value){return value===null||value===undefined?'—':studentHomeNumber(value).toLocaleString('pt-BR',{minimumFractionDigits:1,maximumFractionDigits:1})+'%';}
function studentHomeAreaName(name){const raw=String(name||'Não informado').trim();return studentHomeAreaLabels[raw.toUpperCase()]||raw;}
function studentHomeAccuracy(item){return item&&item.accuracy!==null&&item.accuracy!==undefined?studentHomeNumber(item.accuracy):null;}
function studentHomeBar(item,label){
 const accuracy=studentHomeAccuracy(item),width=accuracy===null?0:Math.max(0,Math.min(100,accuracy));
 return `<div class="student-home-bar-row"><div class="student-home-bar-label"><strong>${esc(label||item?.name||'Não informado')}</strong><span>${item?.correct||0}/${item?.total||0} · ${studentHomePct(accuracy)}</span></div><div class="student-home-bar"><span style="width:${width}%"></span></div></div>`;
}
function studentHomeEvolution(simulations){
 const rows=[...(simulations||[])].reverse().slice(-10);
 if(!rows.length)return '<div class="notice">O primeiro simulado ainda não foi associado a este perfil.</div>';
 const bars=rows.map((x,index)=>{const accuracy=studentHomeAccuracy(x),height=Math.max(8,Math.min(100,accuracy===null?0:accuracy));return `<div class="student-home-evolution-item" title="${esc(x.activity||'Simulado')} · ${esc(x.date||'')} · ${studentHomePct(accuracy)}"><span class="student-home-evolution-value">${studentHomePct(accuracy)}</span><div class="student-home-evolution-track"><span style="height:${height}%"></span></div><small>${index+1}º</small></div>`;}).join('');
 return `<div class="student-home-evolution">${bars}</div><p class="micro">${rows.length===1?'Este resultado é o ponto de partida. A evolução aparecerá quando novos simulados forem importados.':'Cada coluna representa um simulado, em ordem cronológica.'}</p>`;
}
function studentHomeRankRows(rows,mode='need',limit=5){
 const usable=(rows||[]).filter(x=>studentHomeNumber(x.marked)>0&&studentHomeAccuracy(x)!==null);
 usable.sort((a,b)=>mode==='strength'?(studentHomeAccuracy(b)-studentHomeAccuracy(a)||studentHomeNumber(b.marked)-studentHomeNumber(a.marked)):(studentHomeAccuracy(a)-studentHomeAccuracy(b)||studentHomeNumber(b.marked)-studentHomeNumber(a.marked)));
 return usable.slice(0,limit);
}
function studentHomeDashboard(){
 const id=studentSummaryTarget();
 if(!studentSummaryCache.has(id)&&!studentSummaryLoading.has(id))queueMicrotask(()=>loadStudentSummary());
 if(studentSummaryLoading.has(id)||!studentSummaryCache.has(id))return `<section class="card student-home-dashboard"><h2>Meu desempenho e trajetória</h2><p>Carregando simulados, revisões e atividades…</p></section>`;
 const d=studentSummaryCache.get(id);
 if(d?.error)return `<section class="card student-home-dashboard"><h2>Meu desempenho e trajetória</h2><div class="notice warning">${esc(d.error)}</div>${button('Tentar novamente','student-summary-refresh','secondary')}</section>`;
 const p=d.performance||{},s=d.study||{},e=d.engagement||{},activities=e.activities||{},reviews=e.reviews||{};
 const latest=(d.simulations||[])[0]||null;
 const latestAreas=latest?.areas||[];
 const priorities=studentHomeRankRows(d.aggregates?.discipline||[],'need',5);
 const strengths=studentHomeRankRows(d.aggregates?.discipline||[],'strength',4);
 const latestAccuracy=latest?studentHomeAccuracy(latest):null;
 const ring=latest?`<div class="student-home-ring" style="--student-progress:${Math.max(0,Math.min(100,latestAccuracy||0))}%"><div><strong>${studentHomePct(latestAccuracy)}</strong><span>aproveitamento</span></div></div>`:`<div class="student-home-ring is-empty"><div><strong>—</strong><span>sem simulado</span></div></div>`;
 const latestText=latest?`<p class="eyebrow">Resultado mais recente</p><h3>${esc(latest.activity||'Simulado')}</h3><p>${esc(latest.date||'Data não informada')} · prova ${esc(latest.color||'sem cor')} ${latest.language?'· '+esc(latest.language):''}</p><p class="student-home-score"><strong>${latest.correct||0}</strong><span>acertos em ${latest.valid||0} questões válidas</span></p>`:`<p class="eyebrow">Desempenho acadêmico</p><h3>Nenhum simulado vinculado</h3><p>Quando um resultado for importado para esta conta, ele aparecerá aqui automaticamente.</p>`;
 const areaHtml=latestAreas.length?latestAreas.map(x=>studentHomeBar(x,studentHomeAreaName(x.name))).join(''):'<div class="notice">O simulado atual ainda não possui divisão por área disponível.</div>';
 const priorityHtml=priorities.length?priorities.map(x=>studentHomeBar(x,x.name)).join(''):'<div class="notice">Ainda não há base suficiente para indicar prioridades por disciplina.</div>';
 const strengthHtml=strengths.length?strengths.map(x=>`<span class="student-home-chip"><strong>${esc(x.name)}</strong> ${studentHomePct(x.accuracy)}</span>`).join(''):'<span class="micro">Os destaques aparecerão após a primeira análise por disciplina.</span>';
 const completion=activities.completionRate;
 return `<section class="card student-home-dashboard"><div class="student-home-dashboard-head"><div><p class="eyebrow">Trajetória acadêmica</p><h2>Meu desempenho e progresso</h2><p>Simulados, conteúdos, revisões e atividades registrados neste perfil.</p></div><div class="actions">${button('Atualizar','student-summary-refresh','secondary')}${button('Ver desempenho completo','student-home-performance','primary')}</div></div><div class="student-home-summary-grid"><div class="student-home-latest">${ring}<div>${latestText}</div></div><div class="student-home-kpis"><div><strong>${p.simulations||0}</strong><span>simulado(s)</span></div><div><strong>${p.correct||0}</strong><span>acertos acumulados</span></div><div><strong>${s.studied||0}/${s.contents||0}</strong><span>conteúdos estudados</span></div><div><strong>${studentSummaryMinutes(s.actualMinutes||0)}</strong><span>tempo registrado</span></div></div></div><div class="student-home-columns"><div class="student-home-block"><h3>Desempenho por área</h3>${areaHtml}</div><div class="student-home-block"><h3>Evolução nos simulados</h3>${studentHomeEvolution(d.simulations||[])}</div></div><div class="student-home-columns"><div class="student-home-block"><h3>Trilha de aprendizagem</h3><p class="micro">Disciplinas com menor aproveitamento acumulado aparecem primeiro e orientam a próxima prévia do cronograma.</p>${priorityHtml}<h4>Destaques</h4><div class="student-home-chips">${strengthHtml}</div></div><div class="student-home-block"><h3>Execução da rotina</h3><div class="student-home-mini-stats"><div><strong>${activities.done||0}</strong><span>atividades concluídas</span></div><div><strong>${activities.partial||0}</strong><span>parciais</span></div><div><strong>${activities.missed||0}</strong><span>não realizadas</span></div><div><strong>${studentHomePct(completion)}</strong><span>índice de execução</span></div></div><h4>Revisões</h4><div class="student-home-mini-stats"><div><strong>${(reviews.done||0)+(reviews.partial||0)}</strong><span>realizadas</span></div><div><strong>${reviews.planned||0}</strong><span>programadas</span></div><div><strong>${reviews.overdue||0}</strong><span>vencidas</span></div><div><strong>${reviews.dueSoon||0}</strong><span>nos próximos 7 dias</span></div></div><div class="actions">${button('Abrir revisões','student-home-reviews','secondary')}${button('Abrir quadro semanal','student-home-calendar','secondary')}</div></div></div><p class="micro student-home-footnote">Os resultados acadêmicos orientam prioridades relativas; horários só mudam depois de gerar, conferir e confirmar uma nova proposta.</p></section>`;
}

const studentHomeOriginalHomeView=homeView;
homeView=function(){
 const base=studentHomeOriginalHomeView();
 const panel=studentHomeDashboard();
 const marker='<div class="columns">';
 const pos=base.indexOf(marker);
 return pos>=0?base.slice(0,pos)+panel+base.slice(pos):base+panel;
};

acts['student-home-performance']=()=>{view='performance';render();window.scrollTo(0,0);};
acts['student-home-reviews']=()=>{view='reviews';render();window.scrollTo(0,0);};
acts['student-home-calendar']=()=>{view='calendar';render();window.scrollTo(0,0);};

// === TRI HOME DASHBOARD V3.3 ===
function triHomeScore(sim,key){
 const scores=sim?.triScores||{};
 const raw=key==='redaction'?(scores.redaction??sim?.redaction?.score):scores[key];
 const n=Number(raw);
 return raw===null||raw===undefined||raw===''||!Number.isFinite(n)?null:n;
}
function triHomeSorted(simulations,ascending=true){
 const rows=[...(simulations||[])];
 rows.sort((a,b)=>{
  const date=String(a?.date||'').localeCompare(String(b?.date||''));
  if(date)return ascending?date:-date;
  const name=String(a?.activity||'').localeCompare(String(b?.activity||''),'pt-BR');
  return ascending?name:-name;
 });
 return rows;
}
function triHomeFmt(value,digits=1){
 const n=Number(value);
 return value===null||value===undefined||value===''||!Number.isFinite(n)?'—':n.toLocaleString('pt-BR',{minimumFractionDigits:digits,maximumFractionDigits:digits});
}
studentHomeEvolution=function(simulations){
 const rows=triHomeSorted(simulations,true).filter(sim=>triHomeScore(sim,'general')!==null);
 if(!rows.length)return '<div class="notice">As notas TRI aparecerão aqui depois da importação.</div>';
 const bars=rows.map(sim=>{
  const value=triHomeScore(sim,'general'),height=Math.max(5,Math.min(100,(value/1000)*100));
  return '<div class="student-home-evolution-item tri-home-evolution-item" title="'+esc((sim.activity||'Simulado')+' · '+(sim.date||''))+'">'+
   '<span class="student-home-evolution-value">'+triHomeFmt(value,0)+'</span>'+
   '<div class="student-home-evolution-track tri-track"><span style="height:'+height+'%"></span></div>'+
   '<small>'+esc(sim.activity||'Simulado')+'</small><em>'+esc(sim.date||'')+'</em></div>';
 }).join('');
 return '<div class="student-home-evolution tri-home-evolution">'+bars+'</div><p class="micro">TRI geral em ordem cronológica pela data de aplicação.</p>';
};

const triHomeOriginalDashboardV33=studentHomeDashboard;
studentHomeDashboard=function(){
 let base=triHomeOriginalDashboardV33();
 base=base.replace('<h3>Desempenho por área</h3>','<h3>Acertos/TCT por área</h3>');
 base=base.replace('<h3>Evolução nos simulados</h3>','<h3>Evolução da TRI geral</h3>');
 const id=studentSummaryTarget();
 const d=studentSummaryCache.get(id);
 if(!d||d.error)return base;
 const latest=triHomeSorted((d.simulations||[]).filter(sim=>['lc','ch','cn','mt','redaction'].some(k=>triHomeScore(sim,k)!==null)),false)[0];
 if(!latest)return base;
 const metrics=[
  ['general','TRI geral',1],['lc','Linguagens',1],['ch','Humanas',1],
  ['cn','Natureza',1],['mt','Matemática',1],['redaction','Redação',0]
 ];
 const cards=metrics.map(item=>'<div><strong>'+triHomeFmt(triHomeScore(latest,item[0]),item[2])+'</strong><span>'+item[1]+'</span></div>').join('');
 const block='<div class="student-home-columns tri-home-tri-columns"><div class="student-home-block tri-home-tri-block"><div class="tri-home-tri-head"><div><h3>TRI por área</h3><p class="micro">'+esc(latest.activity||'Simulado')+' · '+esc(latest.date||'')+'</p></div></div><div class="student-home-mini-stats tri-home-tri-grid">'+cards+'</div></div></div>';
 const marker='<div class="student-home-columns"><div class="student-home-block"><h3>Trilha de aprendizagem</h3>';
 return base.includes(marker)?base.replace(marker,block+marker):base+block;
};

// === PERFORMANCE OVERVIEW V3.4 ===
function prLatestSimulation(d){
 const rows=[...(d?.simulations||[])];
 rows.sort((a,b)=>String(b?.date||'').localeCompare(String(a?.date||''))||String(a?.activity||'').localeCompare(String(b?.activity||''),'pt-BR'));
 return rows[0]||null;
}
function prFmt(value,digits=1){
 const n=Number(value);
 return value===null||value===undefined||value===''||!Number.isFinite(n)?'—':n.toLocaleString('pt-BR',{minimumFractionDigits:digits,maximumFractionDigits:digits});
}
function prLatestDisciplinesHtml(sim){
 const rows=[...(sim?.disciplines||[])].filter(x=>Number(x?.marked||0)>0);
 rows.sort((a,b)=>{
  const aa=a?.accuracy===null||a?.accuracy===undefined?999:Number(a.accuracy);
  const bb=b?.accuracy===null||b?.accuracy===undefined?999:Number(b.accuracy);
  return aa-bb||String(a?.name||'').localeCompare(String(b?.name||''),'pt-BR');
 });
 if(!rows.length)return '<div class="notice">O simulado mais recente ainda não possui divisão por disciplina disponível.</div>';
 return '<p class="micro">Todas as disciplinas de '+esc(sim.activity||'Simulado')+' · '+esc(sim.date||'')+'.</p>'+
  rows.map(x=>studentHomeBar(x,x.name)).join('');
}
const prDashboardBeforeV34=studentHomeDashboard;
studentHomeDashboard=function(){
 let html=prDashboardBeforeV34();
 const id=studentSummaryTarget();
 const d=studentSummaryCache.get(id);
 if(!d||d.error)return html;
 const p=d.performance||{};
 const latest=prLatestSimulation(d);
 if(!latest)return html;

 html=html.replace(
  /<strong>[^<]*<\/strong><span>acertos acumulados<\/span>/,
  '<strong>'+Number(p.correct||0)+'/'+Number(p.valid||0)+'</strong><span>acertos acumulados</span>'
 );

 const triGeneral=triHomeScore(latest,'general');
 if(triGeneral!==null&&!html.includes('<span>TRI geral mais recente</span>')){
  html=html.replace(
   /(<strong>[^<]*<\/strong><span>acertos acumulados<\/span><\/div>)/,
   '$1<div><strong>'+prFmt(triGeneral,1)+'</strong><span>TRI geral mais recente</span></div>'
  );
 }

 const redaction=triHomeScore(latest,'redaction');
 if(redaction!==null){
  const redAccuracy=Math.max(0,Math.min(100,redaction/10));
  const redRow=studentHomeBar({correct:Math.round(redaction),total:1000,accuracy:redAccuracy},'Redação');
  html=html.replace(
   /(<div class="student-home-block"><h3>Acertos\/TCT por área<\/h3>)([\s\S]*?)(<\/div><div class="student-home-block"><h3>Evolução da TRI geral<\/h3>)/,
   (all,start,body,end)=>start+body+redRow+end
  );
 }

 const disciplines=prLatestDisciplinesHtml(latest);
 html=html.replace(
  /<div class="student-home-block"><h3>Trilha de aprendizagem<\/h3>[\s\S]*?<\/div><div class="student-home-block"><h3>Execução da rotina<\/h3>/,
  '<div class="student-home-block"><h3>Trilha de aprendizagem</h3>'+disciplines+'</div><div class="student-home-block"><h3>Execução da rotina</h3>'
 );
 return html;
};

// Dados cadastrais do caderno, editáveis independentemente do arquivo de questões.
async function loadExamMapList(seq){
 try{
  const data=await api('/api/model-data/exam-edit-list');
  if(view!=='exams'||seq!==examSeq)return;
  examCatalogue=data.exams;
  const box=$('#exam-list');
  if(!box)return;
  box.innerHTML=items(examCatalogue.map(exam=>{
   const attrs='data-id="'+esc(exam.id)+'"';
   const edit=button(exam.canEdit?'Editar dados':'Editar data','exam-metadata-edit','secondary',attrs);
   const complement=exam.canEdit?button('Complementar mapa','exam-edit','secondary',attrs):'';
   return '<div class="item"><div><strong>'+esc(exam.title)+'</strong><p>'+
     br(exam.applied_on)+' · '+esc(exam.color)+' · '+esc(exam.area||'Sem área padrão')+
     ' · '+Number(exam.linkedResults)+' resultado(s) vinculado(s) · versão '+Number(exam.version)+
     '</p></div><div class="actions">'+edit+complement+'</div></div>';
  }));
 }catch(error){
  const box=$('#exam-list');
  if(box&&view==='exams'&&seq===examSeq)box.textContent=error.message;
 }
}

acts['exam-metadata-edit']=el=>{
 const exam=examCatalogue.find(row=>row.id===el.dataset.id);
 if(!exam)throw new Error('Atualize a lista para localizar este caderno.');
 const full=exam.canEdit;
 const fields=input('Nome do simulado','title',exam.title,'text','required maxlength="200"')+
  input('Data de aplicação','date',exam.applied_on,'date','required min="1900-01-01" max="2100-12-31"')+
  input('Cor da prova','color',exam.color,'text','required maxlength="80"')+
  select('Área padrão das questões','area',exam.area||'',[['','Sem área padrão'],...areaOptions.slice(1)]);
 const help='A alteração vale para este caderno e seus resultados vinculados. A área padrão será usada ao complementar o mapa com questões sem área informada.';
 modalForm(full?'Editar dados do simulado':'Editar data do caderno',
  '<p>'+esc(exam.title)+' · '+esc(exam.color)+' · '+br(exam.applied_on)+'</p><div class="form-grid">'+fields+'</div><p class="micro">'+help+'</p>',
  async(form,values)=>{
   const data={examId:exam.id,version:exam.version,title:exam.title,color:exam.color,area:exam.area||'',...values};
   let result;
   try{result=await api('/api/model-data/exam-metadata-update',data);}
   catch(error){await loadExamMapList(++examSeq);throw error;}
   if(examDraft?.examId===exam.id){
    Object.assign(examDraft,{title:result.title,date:result.newDate,color:result.color,area:result.area,token:null});
    const editor=$('#exam-editor');
    if(editor)editor.innerHTML=examEditor();
   }
   if(typeof resultExportSimulations!=='undefined')resultExportSimulations=null;
   if(typeof studentSummaryCache!=='undefined')studentSummaryCache.clear();
   if(typeof managementDashboardCache!=='undefined')managementDashboardCache=null;
   if(typeof managementClassAnalyticsCache!=='undefined'){
    managementClassAnalyticsCache=null;
    managementClassDetailCache.clear();
    managementStudentDetailCache.clear();
   }
   if(typeof triCoverage!=='undefined')triCoverage=null;
   await loadExamMapList(++examSeq);
   toast(result.unchanged?'Os dados já estavam atualizados.':'Caderno salvo. Resultados vinculados atualizados: '+result.updatedResults+'.');
  },'Salvar alterações');
 if(!full){
  const fields=$('#modal-form').elements;
  for(const key of ['title','color','area'])fields.namedItem(key).disabled=true;
 }
};

// === MANAGEMENT DASHBOARD V3.5 ===
let managementDashboardCache=null;
let managementDashboardLoading=false;
let managementDashboardFilters={year:'',turma:'',activityKey:'',date:''};

function managementDashboardAllowed(){return typeof ME!=='undefined'&&ME&&['master','coordenador'].includes(ME.role);}
function managementFmt(value,digits=1,suffix=''){const n=Number(value);return value===null||value===undefined||value===''||!Number.isFinite(n)?'—':n.toLocaleString('pt-BR',{minimumFractionDigits:digits,maximumFractionDigits:digits})+suffix;}
function managementInt(value){const n=Number(value);return Number.isFinite(n)?Math.round(n).toLocaleString('pt-BR'):'0';}
async function loadManagementDashboard(force=false){
 if(!managementDashboardAllowed()||managementDashboardLoading||(!force&&managementDashboardCache))return;
 managementDashboardLoading=true;
 try{
  const q=new URLSearchParams();
  Object.entries(managementDashboardFilters).forEach(([key,value])=>{if(value)q.set(key,value);});
  managementDashboardCache=await api('/api/model-data/management-dashboard'+(q.toString()?'?'+q.toString():''));
 }catch(error){managementDashboardCache={error:error?.message||'Não foi possível carregar o painel gerencial.'};}
 finally{managementDashboardLoading=false;if(view==='home'&&typeof render==='function')render();}
}
function managementSelect(label,id,value,options){
 return '<label>'+label+'<select id="'+id+'"><option value="">Todos</option>'+options.map(opt=>{const raw=typeof opt==='string'?opt:opt.value,text=typeof opt==='string'?opt:opt.label;return '<option value="'+esc(raw)+'"'+(String(raw)===String(value||'')?' selected':'')+'>'+esc(text)+'</option>';}).join('')+'</select></label>';
}
function managementFiltersHtml(d){
 const f=d?.filters||{},s=f.selected||{};
 const sims=(f.simulations||[]).map(x=>({value:(x.activityKey||'')+'@@'+(x.date||''),label:(x.activity||'Simulado')+' · '+(x.date||'')}));
 const selected=(s.activityKey||s.date)?(s.activityKey||'')+'@@'+(s.date||''):'';
 return '<section class="management-filter-card"><div class="management-filter-grid">'+managementSelect('Ano','management-year',s.year||'',f.years||[])+managementSelect('Turma','management-turma',s.turma||'',f.turmas||[])+managementSelect('Simulado','management-simulation',selected,sims)+'</div><div class="actions"><button type="button" class="secondary" data-act="management-dashboard-refresh">Atualizar painel</button></div></section>';
}
function managementKpisHtml(k){
 const cards=[[managementInt(k.activeStudents),'alunos ativos'],[managementInt(k.participants),'alunos com participação'],[managementInt(k.catalogSimulations),'simulados cadastrados'],[managementInt(k.maps),'mapas cadastrados'],[managementInt(k.simulationsWithResults),'simulados com resultados'],[managementInt(k.participations),'participações registradas'],[managementFmt(k.accuracy,1,'%'),'aproveitamento TCT'],[managementFmt(k.triGeneral,1),'TRI geral média'],[managementFmt(k.redaction,1),'Redação média']];
 return '<div class="management-kpi-grid">'+cards.map(([v,l])=>'<div><strong>'+v+'</strong><span>'+l+'</span></div>').join('')+'</div>';
}
function managementAreaHtml(rows){
 if(!(rows||[]).length)return '<div class="notice">Sem dados de área para os filtros selecionados.</div>';
 return '<div class="management-area-grid">'+rows.map(x=>{const width=Math.max(0,Math.min(100,Number(x.accuracy||0)));return '<article><div class="management-area-title"><strong>'+esc(x.name)+'</strong><span>'+managementFmt(x.accuracy,1,'%')+'</span></div><div class="management-bar"><span style="width:'+width+'%"></span></div><div class="management-area-meta"><span>'+managementInt(x.correct)+'/'+managementInt(x.valid)+' acertos</span><span>TRI média '+managementFmt(x.tri,1)+'</span></div></article>';}).join('')+'</div>';
}
function managementSimulationChart(rows){
 const ordered=[...(rows||[])].sort((a,b)=>String(a.date||'').localeCompare(String(b.date||'')));
 if(!ordered.length)return '<div class="notice">Nenhum simulado com resultados nos filtros selecionados.</div>';
 return '<div class="management-sim-chart">'+ordered.map(x=>{const acc=Math.max(4,Math.min(100,Number(x.accuracy||0))),tri=Math.max(4,Math.min(100,Number(x.triGeneral||0)/10));return '<div class="management-sim-col" title="'+esc((x.activity||'Simulado')+' · '+(x.date||''))+'"><div class="management-dual-bars"><span class="tct" style="height:'+acc+'%"></span><span class="tri" style="height:'+tri+'%"></span></div><strong>'+esc(x.activity||'Simulado')+'</strong><small>'+esc(x.date||'')+'</small><em>'+managementInt(x.participants)+' participantes</em></div>';}).join('')+'</div><div class="management-legend"><span><i class="tct"></i>TCT %</span><span><i class="tri"></i>TRI geral ÷ 10</span></div>';
}
function managementSimulationTable(rows){
 const body=(rows||[]).map(x=>'<tr><td><strong>'+esc(x.activity||'Simulado')+'</strong><br><small>'+esc(x.date||'')+'</small></td><td>'+managementInt(x.participants)+'</td><td>'+managementInt(x.correct)+'/'+managementInt(x.valid)+'</td><td>'+managementFmt(x.accuracy,1,'%')+'</td><td>'+managementFmt(x.triGeneral,1)+'</td><td>'+managementFmt(x.lc,1)+'</td><td>'+managementFmt(x.ch,1)+'</td><td>'+managementFmt(x.cn,1)+'</td><td>'+managementFmt(x.mt,1)+'</td><td>'+managementFmt(x.redaction,1)+'</td></tr>').join('');
 return body?'<div class="table-wrap"><table><thead><tr><th>Simulado</th><th>Participantes</th><th>Acertos</th><th>TCT</th><th>TRI geral</th><th>LC</th><th>CH</th><th>CN</th><th>MT</th><th>Redação</th></tr></thead><tbody>'+body+'</tbody></table></div>':'<div class="notice">Sem resultados para listar.</div>';
}
function managementClassTable(rows){
 const body=(rows||[]).map(x=>'<tr><td><strong>'+esc(x.turma||'Sem turma')+'</strong></td><td>'+managementInt(x.participants)+'</td><td>'+managementInt(x.correct)+'/'+managementInt(x.valid)+'</td><td>'+managementFmt(x.accuracy,1,'%')+'</td><td>'+managementFmt(x.triGeneral,1)+'</td><td>'+managementFmt(x.redaction,1)+'</td></tr>').join('');
 return body?'<div class="table-wrap"><table><thead><tr><th>Turma</th><th>Participantes</th><th>Acertos</th><th>TCT</th><th>TRI geral</th><th>Redação</th></tr></thead><tbody>'+body+'</tbody></table></div>':'<div class="notice">Sem turmas para os filtros selecionados.</div>';
}
function managementDashboardView(){
 if(!managementDashboardCache&&!managementDashboardLoading)queueMicrotask(()=>loadManagementDashboard());
 if(managementDashboardLoading||!managementDashboardCache)return '<section class="card management-dashboard"><h2>Painel de bordo da coordenação</h2><p>Carregando indicadores gerais…</p></section>';
 const d=managementDashboardCache;
 if(d?.error)return '<section class="card management-dashboard"><h2>Painel de bordo da coordenação</h2><div class="notice warning">'+esc(d.error)+'</div><button type="button" class="secondary" data-act="management-dashboard-refresh">Tentar novamente</button></section>';
 return '<section class="management-dashboard"><div class="card management-hero"><div><p class="eyebrow">VISÃO GERENCIAL</p><h1>Painel de bordo da coordenação</h1><p>Simulados, participação, TCT, TRI, redação e turmas em uma única visão operacional.</p></div><div class="actions"><button type="button" class="secondary" data-act="management-go-import">Importar resultados</button><button type="button" class="secondary" data-act="management-go-exams">Mapas de questões</button><button type="button" class="primary" data-act="management-dashboard-refresh">Atualizar</button></div></div>'+managementFiltersHtml(d)+'<section class="card"><h2>Resumo geral</h2>'+managementKpisHtml(d.kpis||{})+'</section><section class="card"><h2>Médias por área</h2><p class="micro">TCT e TRI calculados com os participantes dos filtros selecionados.</p>'+managementAreaHtml(d.areas||[])+'</section><section class="card"><h2>Evolução dos simulados</h2>'+managementSimulationChart(d.simulations||[])+'</section><section class="card"><h2>Resumo por simulado</h2>'+managementSimulationTable(d.simulations||[])+'</section><section class="card"><h2>Resumo por turma</h2>'+managementClassTable(d.classes||[])+'</section></section>';
}
const managementOriginalHomeView=homeView;
homeView=function(){if(managementDashboardAllowed())return managementDashboardView();return managementOriginalHomeView();};
acts['management-dashboard-refresh']=async()=>{managementDashboardCache=null;await loadManagementDashboard(true);};
acts['management-go-import']=()=>{view='result-import';render();window.scrollTo(0,0);};
acts['management-go-exams']=()=>{view='exams';render();window.scrollTo(0,0);};
document.addEventListener('change',event=>{const el=event.target;if(!managementDashboardAllowed()||!el)return;if(el.id==='management-year'){managementDashboardFilters.year=el.value||'';managementDashboardCache=null;loadManagementDashboard(true);}if(el.id==='management-turma'){managementDashboardFilters.turma=el.value||'';managementDashboardCache=null;loadManagementDashboard(true);}if(el.id==='management-simulation'){const parts=(el.value||'').split('@@');managementDashboardFilters.activityKey=parts[0]||'';managementDashboardFilters.date=parts[1]||'';managementDashboardCache=null;loadManagementDashboard(true);}},true);

// === MANAGEMENT REFINEMENT V3.6 ===
let classRegistryCache=null;
let classRegistryLoading=false;

managementSimulationChart=function(rows){
 const ordered=[...(rows||[])].sort((a,b)=>String(a.date||'').localeCompare(String(b.date||'')));
 if(!ordered.length)return '<div class="notice">Nenhum simulado com resultados nos filtros selecionados.</div>';
 const cols=ordered.map(x=>{
  const tri=Number(x.triGeneral),hasTri=Number.isFinite(tri),height=hasTri?Math.max(3,Math.min(100,tri/10)):0;
  return '<div class="management-score-col"><span class="management-score-value">'+(hasTri?managementFmt(tri,1):'—')+'</span><div class="management-score-track"><span style="height:'+height+'%"></span></div><strong>'+esc(x.activity||'Simulado')+'</strong><small>'+esc(x.date||'')+'</small><em>'+managementInt(x.participants)+' participantes · % acertos '+managementFmt(x.accuracy,1,'%')+'</em></div>';
 }).join('');
 return '<div class="management-score-chart"><div class="management-scale"><span>1000</span><span>750</span><span>500</span><span>250</span><span>0</span></div><div class="management-score-columns">'+cols+'</div></div><p class="micro">Nota TRI geral média em escala de 0 a 1000. O percentual de acertos aparece como informação complementar.</p>';
};

managementAreaHtml=function(rows){
 if(!(rows||[]).length)return '<div class="notice">Sem dados de área para os filtros selecionados.</div>';
 return '<div class="management-area-grid">'+rows.map(x=>{
  const tri=Number(x.tri),hasTri=Number.isFinite(tri),width=hasTri?Math.max(0,Math.min(100,tri/10)):0;
  const tct=x.accuracy===null||x.accuracy===undefined?'':('<span>% acertos '+managementFmt(x.accuracy,1,'%')+'</span>');
  return '<article><div class="management-area-title"><strong>'+esc(x.name)+'</strong><span>Nota média '+(hasTri?managementFmt(tri,1):'—')+' / 1000</span></div><div class="management-bar tri-scale"><span style="width:'+width+'%"></span></div><div class="management-area-meta">'+tct+'<span>Escala TRI 0–1000</span></div></article>';
 }).join('')+'</div>';
};

managementSimulationTable=function(rows){
 const body=(rows||[]).map(x=>'<tr><td><strong>'+esc(x.activity||'Simulado')+'</strong><br><small>'+esc(x.date||'')+'</small></td><td>'+managementInt(x.participants)+'</td><td>'+managementFmt(x.accuracy,1,'%')+'</td><td>'+managementFmt(x.triGeneral,1)+'</td><td>'+managementFmt(x.lc,1)+'</td><td>'+managementFmt(x.ch,1)+'</td><td>'+managementFmt(x.cn,1)+'</td><td>'+managementFmt(x.mt,1)+'</td><td>'+managementFmt(x.redaction,1)+'</td></tr>').join('');
 return body?'<div class="table-wrap"><table><thead><tr><th>Simulado</th><th>Participantes</th><th>% acertos</th><th>TRI geral</th><th>LC</th><th>CH</th><th>CN</th><th>MT</th><th>Redação</th></tr></thead><tbody>'+body+'</tbody></table></div>':'<div class="notice">Sem resultados para listar.</div>';
};

managementClassTable=function(rows){
 const body=(rows||[]).map(x=>'<tr><td><strong>'+esc(x.turma||'Sem turma')+'</strong></td><td>'+managementInt(x.participants)+'</td><td>'+managementFmt(x.accuracy,1,'%')+'</td><td>'+managementFmt(x.triGeneral,1)+'</td><td>'+managementFmt(x.redaction,1)+'</td></tr>').join('');
 return body?'<div class="table-wrap"><table><thead><tr><th>Turma</th><th>Participantes</th><th>% acertos</th><th>TRI geral</th><th>Redação</th></tr></thead><tbody>'+body+'</tbody></table></div>':'<div class="notice">Sem turmas para os filtros selecionados.</div>';
};

async function loadClassRegistry(force=false){
 if(!managementDashboardAllowed()||classRegistryLoading||(!force&&classRegistryCache))return;
 classRegistryLoading=true;
 try{classRegistryCache=await api('/api/model-data/classes');}
 catch(error){classRegistryCache={error:error?.message||'Não foi possível carregar o cadastro de turmas.'};}
 finally{classRegistryLoading=false;if(view==='home'&&typeof render==='function')render();}
}
function classRegistryPanel(){
 if(!classRegistryCache&&!classRegistryLoading)queueMicrotask(()=>loadClassRegistry());
 if(classRegistryLoading||!classRegistryCache)return '<section class="card"><h2>Cadastro de turmas</h2><p>Carregando…</p></section>';
 if(classRegistryCache.error)return '<section class="card"><h2>Cadastro de turmas</h2><div class="notice warning">'+esc(classRegistryCache.error)+'</div></section>';
 const rows=(classRegistryCache.classes||[]).map(x=>'<tr><td><input data-class-name="'+esc(x.id)+'" value="'+esc(x.name)+'"></td><td><input data-class-aliases="'+esc(x.id)+'" value="'+esc((x.aliases||[]).join('; '))+'" placeholder="Aliases separados por ;"></td><td><label class="check"><input type="checkbox" data-class-active="'+esc(x.id)+'"'+(x.active?' checked':'')+'> Ativa</label></td><td><button type="button" class="secondary" data-act="class-registry-save" data-class-id="'+esc(x.id)+'">Salvar</button></td></tr>').join('');
 const missing=classRegistryCache.unregistered||[];
 const missingHtml=missing.length?'<div class="notice warning"><strong>Nomes encontrados fora do cadastro:</strong><ul>'+missing.map(x=>'<li>'+esc(x.name)+' · '+managementInt(x.records)+' registro(s)</li>').join('')+'</ul></div>':'<div class="notice success">Todos os nomes já existentes estão cobertos por turma oficial ou alias.</div>';
 return '<section class="card class-registry-card"><h2>Cadastro de turmas</h2><p>O nome oficial e seus aliases são usados para validar novas importações. Um nome não cadastrado bloqueia a confirmação e é listado para correção.</p><div class="class-new-grid"><label>Nova turma<input id="class-new-name" placeholder="Ex.: Qi Med 01"></label><label>Aliases autorizados<input id="class-new-aliases" placeholder="Ex.: 01 Qi Med 01; MED 01"></label><button type="button" class="primary" data-act="class-registry-new">Cadastrar turma</button></div>'+missingHtml+'<div class="table-wrap"><table><thead><tr><th>Nome oficial</th><th>Aliases</th><th>Status</th><th></th></tr></thead><tbody>'+rows+'</tbody></table></div></section>';
}
const managementDashboardViewV36Base=managementDashboardView;
managementDashboardView=function(){return managementDashboardViewV36Base()+classRegistryPanel();};

acts['class-registry-new']=async()=>{
 const name=document.querySelector('#class-new-name')?.value||'',aliases=document.querySelector('#class-new-aliases')?.value||'';
 if(!name.trim())throw new Error('Informe o nome oficial da turma.');
 await api('/api/model-data/classes',{name,aliases,active:true});
 classRegistryCache=null;managementDashboardCache=null;await loadClassRegistry(true);toast('Turma cadastrada.');
};
acts['class-registry-save']=async el=>{
 const id=el?.dataset?.classId||'';
 const name=document.querySelector('[data-class-name="'+CSS.escape(id)+'"]')?.value||'';
 const aliases=document.querySelector('[data-class-aliases="'+CSS.escape(id)+'"]')?.value||'';
 const active=!!document.querySelector('[data-class-active="'+CSS.escape(id)+'"]')?.checked;
 await api('/api/model-data/classes',{id,name,aliases,active});
 classRegistryCache=null;managementDashboardCache=null;await loadClassRegistry(true);toast('Turma atualizada.');
};

function classImportErrorBox(message){
 return '<div class="notice danger"><strong>Turma não cadastrada.</strong><p>'+esc(message)+'</p><p>Abra Visão geral → Cadastro de turmas para cadastrar o nome oficial ou um alias antes de importar.</p></div>';
}
window.addEventListener('load',()=>{
 if(typeof acts!=='undefined'&&acts['result-import-preview']){
  const original=acts['result-import-preview'];
  acts['result-import-preview']=async()=>{try{return await original();}catch(error){const box=document.querySelector('#result-import-preview');if(box)box.innerHTML=classImportErrorBox(error?.message||'Nome de turma inválido.');throw error;}};
 }
 if(typeof acts!=='undefined'&&acts['tri-import-preview']){
  const original=acts['tri-import-preview'];
  acts['tri-import-preview']=async()=>{try{return await original();}catch(error){const box=document.querySelector('#tri-import-preview');if(box)box.innerHTML=classImportErrorBox(error?.message||'Nome de turma inválido.');throw error;}};
 }
});

// === MANAGEMENT REFINEMENT V3.7 ===
let managementClassSort={key:'turma',dir:'asc'};
let managementSimulationSort={key:'date',dir:'desc'};

function managementSortRows(rows,state){
 const copy=[...(rows||[])],dir=state.dir==='asc'?1:-1,key=state.key;
 copy.sort((a,b)=>{
  let av=a?.[key],bv=b?.[key];
  if(['participants','accuracy','triGeneral','redaction'].includes(key)){
   av=Number(av);bv=Number(bv);
   if(!Number.isFinite(av))av=-Infinity;
   if(!Number.isFinite(bv))bv=-Infinity;
   return (av-bv)*dir;
  }
  return String(av??'').localeCompare(String(bv??''),'pt-BR',{numeric:true,sensitivity:'base'})*dir;
 });
 return copy;
}
function managementSortButton(label,scope,key,state){
 const active=state.key===key,arrow=active?(state.dir==='asc'?' ↑':' ↓'):'';
 return '<button type="button" class="management-sort" data-act="management-sort" data-sort-scope="'+scope+'" data-sort-key="'+key+'">'+label+arrow+'</button>';
}
managementClassTable=function(rows){
 const sorted=managementSortRows(rows,managementClassSort);
 const body=sorted.map(x=>'<tr><td><strong>'+esc(x.turma||'Sem turma')+'</strong></td><td>'+managementInt(x.participants)+'</td><td>'+managementFmt(x.accuracy,1,'%')+'</td><td>'+managementFmt(x.triGeneral,1)+'</td><td>'+managementFmt(x.redaction,1)+'</td></tr>').join('');
 return body?'<div class="table-wrap"><table><thead><tr><th>'+managementSortButton('Turma','class','turma',managementClassSort)+'</th><th>'+managementSortButton('Participantes','class','participants',managementClassSort)+'</th><th>'+managementSortButton('% acertos','class','accuracy',managementClassSort)+'</th><th>'+managementSortButton('TRI geral','class','triGeneral',managementClassSort)+'</th><th>'+managementSortButton('Redação','class','redaction',managementClassSort)+'</th></tr></thead><tbody>'+body+'</tbody></table></div>':'<div class="notice">Sem turmas para os filtros selecionados.</div>';
};
managementSimulationTable=function(rows){
 const sorted=managementSortRows(rows,managementSimulationSort);
 const body=sorted.map(x=>'<tr><td><strong>'+esc(x.activity||'Simulado')+'</strong><br><small>'+esc(x.date||'')+'</small></td><td>'+managementInt(x.participants)+'</td><td>'+managementFmt(x.accuracy,1,'%')+'</td><td>'+managementFmt(x.triGeneral,1)+'</td><td>'+managementFmt(x.lc,1)+'</td><td>'+managementFmt(x.ch,1)+'</td><td>'+managementFmt(x.cn,1)+'</td><td>'+managementFmt(x.mt,1)+'</td><td>'+managementFmt(x.redaction,1)+'</td></tr>').join('');
 return body?'<div class="table-wrap"><table><thead><tr><th>'+managementSortButton('Simulado','simulation','activity',managementSimulationSort)+'</th><th>'+managementSortButton('Participantes','simulation','participants',managementSimulationSort)+'</th><th>'+managementSortButton('% acertos','simulation','accuracy',managementSimulationSort)+'</th><th>'+managementSortButton('TRI geral','simulation','triGeneral',managementSimulationSort)+'</th><th>LC</th><th>CH</th><th>CN</th><th>MT</th><th>Redação</th></tr></thead><tbody>'+body+'</tbody></table></div>':'<div class="notice">Sem resultados para listar.</div>';
};
acts['management-sort']=el=>{
 const scope=el?.dataset?.sortScope,key=el?.dataset?.sortKey;
 const state=scope==='simulation'?managementSimulationSort:managementClassSort;
 if(state.key===key)state.dir=state.dir==='asc'?'desc':'asc';else{state.key=key;state.dir=key==='turma'||key==='activity'?'asc':'desc';}
 render();
};

managementSimulationChart=function(rows){
 const ordered=[...(rows||[])].sort((a,b)=>String(a.date||'').localeCompare(String(b.date||'')));
 if(!ordered.length)return '<div class="notice">Nenhum simulado com resultados nos filtros selecionados.</div>';
 const cols=ordered.map(x=>{
  const tri=Number(x.triGeneral),hasTri=Number.isFinite(tri),height=hasTri?Math.max(0,Math.min(100,tri/10)):0;
  return '<div class="management-score-col"><div class="management-score-plot"><span class="management-score-value">'+(hasTri?managementFmt(tri,1):'—')+'</span><div class="management-score-track"><span class="management-score-fill" style="height:'+height+'%"></span></div></div><strong>'+esc(x.activity||'Simulado')+'</strong><small>'+esc(x.date||'')+'</small><em>'+managementInt(x.participants)+' participantes · % acertos '+managementFmt(x.accuracy,1,'%')+'</em></div>';
 }).join('');
 return '<div class="management-score-chart"><div class="management-scale"><span>1000</span><span>750</span><span>500</span><span>250</span><span>0</span></div><div class="management-score-columns">'+cols+'</div></div><p class="micro">A altura da coluna corresponde exatamente à nota TRI geral média na escala de 0 a 1000.</p>';
};

managementAreaHtml=function(rows){
 if(!(rows||[]).length)return '<div class="notice">Sem dados de área para os filtros selecionados.</div>';
 return '<div class="management-area-grid">'+rows.map(x=>{
  const tri=Number(x.tri),max=Number(x.maxTri),hasTri=Number.isFinite(tri),hasMax=Number.isFinite(max)&&max>0;
  const width=hasTri&&hasMax?Math.max(0,Math.min(100,100*tri/max)):0;
  const tct=x.accuracy===null||x.accuracy===undefined?'':('<span>% acertos '+managementFmt(x.accuracy,1,'%')+'</span>');
  return '<article><div class="management-area-title"><strong>'+esc(x.name)+'</strong><span>Média '+(hasTri?managementFmt(tri,1):'—')+(hasMax?' · Máxima '+managementFmt(max,1):'')+'</span></div><div class="management-bar tri-scale"><span style="width:'+width+'%"></span></div><div class="management-area-meta">'+tct+'<span>'+(hasMax?'Preenchimento relativo à maior nota observada':'Sem nota máxima disponível')+'</span></div></article>';
 }).join('')+'</div>';
};

function classRegistryPendingHtml(){
 const missing=classRegistryCache?.unregistered||[],classes=(classRegistryCache?.classes||[]).filter(x=>x.active);
 if(!missing.length)return '<div class="notice success">Nenhuma pendência de turma encontrada.</div>';
 return '<div class="class-pending-list">'+missing.map((x,index)=>'<div class="class-pending-row"><div><strong>'+esc(x.name)+'</strong><small>'+managementInt(x.records)+' registro(s) afetado(s)</small></div><label>Correção<select data-class-pending-target="'+index+'"><option value="">Selecione a turma oficial</option>'+classes.map(c=>'<option value="'+esc(c.name)+'">'+esc(c.name)+'</option>').join('')+'</select></label><button type="button" class="primary" data-act="class-pending-correct" data-source="'+encodeURIComponent(x.name)+'" data-index="'+index+'">Confirmar correção</button></div>').join('')+'</div>';
}
classRegistryPanel=function(){
 if(!classRegistryCache&&!classRegistryLoading)queueMicrotask(()=>loadClassRegistry());
 if(classRegistryLoading||!classRegistryCache)return '<section class="card"><h2>Cadastro de turmas</h2><p>Carregando…</p></section>';
 if(classRegistryCache.error)return '<section class="card"><h2>Cadastro de turmas</h2><div class="notice warning">'+esc(classRegistryCache.error)+'</div></section>';
 const rows=(classRegistryCache.classes||[]).map(x=>'<tr><td><strong>'+esc(x.name)+'</strong></td><td><div class="class-correction-cell"><input data-class-name="'+esc(x.id)+'" value="'+esc(x.name)+'" aria-label="Correção do nome oficial"><small>Aliases: '+esc((x.aliases||[]).join('; ')||'nenhum')+'</small><input data-class-aliases="'+esc(x.id)+'" value="'+esc((x.aliases||[]).join('; '))+'" placeholder="Aliases separados por ;"></div></td><td><label class="check"><input type="checkbox" data-class-active="'+esc(x.id)+'"'+(x.active?' checked':'')+'> Ativa</label></td><td><button type="button" class="secondary" data-act="class-registry-save" data-class-id="'+esc(x.id)+'">Salvar</button></td></tr>').join('');
 return '<section class="card class-registry-card"><h2>Cadastro de turmas</h2><p>Use o nome oficial e, quando necessário, aliases autorizados. Pendências pontuais podem ser corrigidas diretamente abaixo.</p><div class="class-new-grid"><label>Nova turma<input id="class-new-name" placeholder="Ex.: Qi Med 01"></label><label>Aliases autorizados<input id="class-new-aliases" placeholder="Ex.: 01 Qi Med 01; MED 01"></label><button type="button" class="primary" data-act="class-registry-new">Cadastrar turma</button></div><h3>Pendências encontradas</h3>'+classRegistryPendingHtml()+'<div class="table-wrap"><table><thead><tr><th>Cadastrada</th><th>Correção</th><th>Ativa</th><th>Salvar</th></tr></thead><tbody>'+rows+'</tbody></table></div></section>';
};
acts['class-pending-correct']=async el=>{
 const index=Number(el?.dataset?.index),source=decodeURIComponent(el?.dataset?.source||''),select=document.querySelector('[data-class-pending-target="'+index+'"]'),target=select?.value||'';
 if(!target)throw new Error('Selecione a turma oficial para corrigir a pendência.');
 if(!confirm('Corrigir "'+source+'" para "'+target+'" em todos os registros afetados?'))return;
 const d=await api('/api/model-data/class-correction',{source,target});
 classRegistryCache={classes:d.classes||[],unregistered:d.unregistered||[]};managementDashboardCache=null;
 toast('Correção concluída: '+Number(d.updated||0)+' registro(s) atualizados.');
 render();
};

// === STUDENT REPORTS MODULE V1 ===
let studentReportsCache=new Map();
let reportAdminCache=null;
let reportAdminLoading=false;
let reportBatchDraft=null;
let reportBatchPreviewData=null;

function reportTargetId(){
 if(typeof ME==='undefined'||!ME)return '';
 if(['master','coordenador'].includes(ME.role)){
  const id=typeof studentSummaryTarget==='function'?studentSummaryTarget():'';
  return id&&id!==ME.id?id:'';
 }
 return ME.id||'';
}
async function loadStudentReports(force=false){
 const id=reportTargetId();
 const key=id||'__none__';
 if(!force&&studentReportsCache.has(key))return;
 try{
  const d=await api('/api/model-data/student-reports'+(id?'?userId='+encodeURIComponent(id):''));
  studentReportsCache.set(key,d);
 }catch(error){studentReportsCache.set(key,{error:error?.message||'Não foi possível carregar os relatórios.'});}
 if(view==='reports')render();
}
function reportCoverHtml(report){
 const cover=String(report.cover||'').trim();
 if(cover)return '<img class="student-report-cover" src="'+esc(cover)+'" alt="Capa do relatório">';
 return '<div class="student-report-cover placeholder"><span>PDF</span></div>';
}
function reportsView(){
 const id=reportTargetId(),key=id||'__none__';
 if(!studentReportsCache.has(key))queueMicrotask(()=>loadStudentReports());
 const d=studentReportsCache.get(key);
 if(!d)return head('Meus relatórios','Relatórios individuais disponibilizados pela coordenação.')+'<section class="card"><p>Carregando relatórios…</p></section>';
 if(d.error)return head('Meus relatórios','Relatórios individuais disponibilizados pela coordenação.')+'<section class="card"><div class="notice warning">'+esc(d.error)+'</div></section>';
 if(!d.student&&['master','coordenador'].includes(ME.role))return head('Meus relatórios','Selecione um aluno no campo de pesquisa para visualizar os relatórios dele.')+'<section class="card"><div class="notice">Nenhum aluno selecionado.</div></section>';
 const groups=d.groups||[];
 const body=groups.length?groups.map(group=>'<section class="card student-report-group"><div class="student-report-group-head"><h2>'+esc(group.name)+'</h2><span>'+group.reports.length+' relatório(s)</span></div><div class="student-report-row">'+group.reports.map(report=>'<article class="student-report-card">'+reportCoverHtml(report)+'<div class="student-report-content"><p class="eyebrow">'+esc(group.name)+'</p><h3>'+esc(report.name||report.title||'Relatório')+'</h3><p><strong>'+esc(report.activity||'')+'</strong>'+(report.date?' · '+esc(report.date):'')+'</p>'+(report.description?'<p>'+esc(report.description)+'</p>':'')+'<a class="primary report-open-link" href="'+esc(report.url)+'" target="_blank" rel="noopener noreferrer">Abrir relatório</a></div></article>').join('')+'</div></section>').join(''):'<section class="card"><div class="notice">Ainda não há relatórios publicados para este aluno.</div></section>';
 return head('Meus relatórios',d.student?'Relatórios disponíveis para '+esc(d.student.name)+'.':'Relatórios individuais disponibilizados pela coordenação.')+body;
}

function reportsFileBase64(file){
 return file.arrayBuffer().then(buffer=>{const bytes=new Uint8Array(buffer),step=0x8000;let binary='';for(let i=0;i<bytes.length;i+=step)binary+=String.fromCharCode(...bytes.subarray(i,i+step));return btoa(binary);});
}
function reportsDownload(filename,mime,encoded){
 const binary=atob(encoded),bytes=new Uint8Array(binary.length);for(let i=0;i<binary.length;i++)bytes[i]=binary.charCodeAt(i);
 const url=URL.createObjectURL(new Blob([bytes],{type:mime})),a=document.createElement('a');a.href=url;a.download=filename;document.body.appendChild(a);a.click();a.remove();setTimeout(()=>URL.revokeObjectURL(url),1500);
}
async function loadReportAdmin(force=false){
 if(!managementDashboardAllowed()||reportAdminLoading||(!force&&reportAdminCache))return;
 reportAdminLoading=true;
 try{reportAdminCache=await api('/api/model-data/report-admin-data');}
 catch(error){reportAdminCache={error:error?.message||'Não foi possível carregar o cadastro de relatórios.'};}
 finally{reportAdminLoading=false;if(view==='report-admin')render();}
}
function reportTypesAdminHtml(types){
 const rows=(types||[]).map(t=>'<tr><td><input data-report-type-name="'+esc(t.id)+'" value="'+esc(t.name)+'"></td><td><input type="number" data-report-type-order="'+esc(t.id)+'" value="'+Number(t.sort_order||0)+'"></td><td><label class="check"><input type="checkbox" data-report-type-active="'+esc(t.id)+'"'+(t.active?' checked':'')+'> Ativo</label></td><td><button type="button" class="secondary" data-act="report-type-save" data-type-id="'+esc(t.id)+'">Salvar</button></td></tr>').join('');
 return '<section class="card"><h2>Tipos de relatório</h2><p>Os tipos definem as linhas/seções que o aluno verá em “Meus relatórios”.</p><div class="report-type-new"><label>Novo tipo<input id="report-type-new-name" placeholder="Ex.: Diagnóstico"></label><label>Ordem<input id="report-type-new-order" type="number" value="10"></label><button type="button" class="primary" data-act="report-type-new">Criar tipo</button></div><div class="table-wrap"><table><thead><tr><th>Tipo</th><th>Ordem</th><th>Status</th><th></th></tr></thead><tbody>'+rows+'</tbody></table></div></section>';
}
function reportModelsAdminHtml(models){
 const rows=(models||[]).map(m=>'<tr><td><strong>'+esc(m.type_name)+'</strong></td><td>'+esc(m.activity)+(m.applied_on?'<br><small>'+esc(m.applied_on)+'</small>':'')+'</td><td><input data-report-model-title="'+esc(m.id)+'" value="'+esc(m.title||'')+'"><textarea data-report-model-description="'+esc(m.id)+'" rows="2" placeholder="Descrição geral">'+esc(m.description||'')+'</textarea></td><td><div class="report-cover-edit">'+(m.cover?'<img src="'+esc(m.cover)+'" alt="Capa">':'')+'<input data-report-model-cover="'+esc(m.id)+'" value="'+esc(m.cover||'')+'" placeholder="URL da capa ou imagem enviada"><input type="file" accept="image/*" data-report-cover-file="'+esc(m.id)+'"></div></td><td>'+Number(m.assignments||0)+'</td><td><label class="check"><input type="checkbox" data-report-model-active="'+esc(m.id)+'"'+(m.active?' checked':'')+'> Ativo</label></td><td><button type="button" class="secondary" data-act="report-model-save" data-model-id="'+esc(m.id)+'">Salvar</button></td></tr>').join('');
 return '<section class="card"><h2>Modelos cadastrados</h2><p>Título, descrição e capa são informações gerais replicadas a todos os alunos vinculados ao mesmo modelo.</p><div class="table-wrap"><table><thead><tr><th>Tipo</th><th>Atividade</th><th>Informações gerais</th><th>Capa</th><th>Alunos</th><th>Status</th><th></th></tr></thead><tbody>'+rows+'</tbody></table></div></section>';
}
function reportBatchHtml(){
 let preview='';
 if(reportBatchPreviewData){
  const p=reportBatchPreviewData,issues=[];
  if((p.unmatched||[]).length)issues.push('Alunos não encontrados: '+p.unmatched.join(', '));
  if((p.ambiguous||[]).length)issues.push('Nomes duplicados: '+p.ambiguous.join(', '));
  if((p.unknownTypes||[]).length)issues.push('Tipos não cadastrados: '+p.unknownTypes.join(', '));
  preview='<div class="'+(issues.length?'notice warning':'notice success')+'"><strong>'+Number(p.matched||0)+' de '+Number(p.rows||0)+' linha(s) prontas.</strong>'+(issues.length?'<ul>'+issues.map(x=>'<li>'+esc(x)+'</li>').join('')+'</ul>':'<p>Todos os alunos e tipos foram reconhecidos.</p>')+'</div><div class="table-wrap"><table><thead><tr><th>Aluno</th><th>Atividade</th><th>Tipo</th><th>Data</th><th>Relatório</th></tr></thead><tbody>'+(p.sample||[]).map(x=>'<tr><td>'+esc(x.name)+'</td><td>'+esc(x.activity)+'</td><td>'+esc(x.type)+'</td><td>'+esc(x.date||'')+'</td><td>'+esc(x.reportName||'')+'</td></tr>').join('')+'</tbody></table></div><div class="actions"><button type="button" class="primary" data-act="report-batch-confirm"'+(issues.length?' disabled':'')+'>Confirmar cadastro em lote</button></div>';
 }
 return '<section class="card"><h2>Cadastro em lote</h2><p>Envie um XLSX com aluno, atividade/simulado, tipo de relatório e link individual.</p><div class="actions"><button type="button" class="secondary" data-act="report-batch-template">Baixar modelo XLSX</button></div><label>Arquivo preenchido<input id="report-batch-file" type="file" accept=".xlsx"></label><p class="micro">'+esc(reportBatchDraft?.filename||'Nenhum arquivo selecionado.')+'</p><div class="actions"><button type="button" class="primary" data-act="report-batch-preview"'+(reportBatchDraft?.file?'':' disabled')+'>Ler e conferir</button></div>'+preview+'</section>';
}
function reportAdminView(){
 if(!managementDashboardAllowed())return head('Cadastro de relatórios','Acesso reservado ao Master e à coordenação.');
 if(!reportAdminCache&&!reportAdminLoading)queueMicrotask(()=>loadReportAdmin());
 if(reportAdminLoading||!reportAdminCache)return head('Cadastro de relatórios','Gerencie tipos, modelos, capas e links individuais.')+'<section class="card"><p>Carregando…</p></section>';
 if(reportAdminCache.error)return head('Cadastro de relatórios','Gerencie tipos, modelos, capas e links individuais.')+'<section class="card"><div class="notice warning">'+esc(reportAdminCache.error)+'</div></section>';
 return head('Cadastro de relatórios','Gerencie tipos, modelos, capas e cadastros individuais em lote.')+reportTypesAdminHtml(reportAdminCache.types||[])+reportBatchHtml()+reportModelsAdminHtml(reportAdminCache.models||[]);
}

acts['report-type-new']=async()=>{
 const name=document.querySelector('#report-type-new-name')?.value||'',sortOrder=Number(document.querySelector('#report-type-new-order')?.value||0);
 if(!name.trim())throw new Error('Informe o nome do tipo.');
 reportAdminCache=await api('/api/model-data/report-type-save',{name,sortOrder,active:true});render();toast('Tipo criado.');
};
acts['report-type-save']=async el=>{
 const id=el?.dataset?.typeId||'',name=document.querySelector('[data-report-type-name="'+CSS.escape(id)+'"]')?.value||'',sortOrder=Number(document.querySelector('[data-report-type-order="'+CSS.escape(id)+'"]')?.value||0),active=!!document.querySelector('[data-report-type-active="'+CSS.escape(id)+'"]')?.checked;
 reportAdminCache=await api('/api/model-data/report-type-save',{id,name,sortOrder,active});render();toast('Tipo atualizado.');
};
acts['report-model-save']=async el=>{
 const id=el?.dataset?.modelId||'',title=document.querySelector('[data-report-model-title="'+CSS.escape(id)+'"]')?.value||'',description=document.querySelector('[data-report-model-description="'+CSS.escape(id)+'"]')?.value||'',cover=document.querySelector('[data-report-model-cover="'+CSS.escape(id)+'"]')?.value||'',active=!!document.querySelector('[data-report-model-active="'+CSS.escape(id)+'"]')?.checked;
 reportAdminCache=await api('/api/model-data/report-model-save',{id,title,description,cover,active});studentReportsCache.clear();render();toast('Modelo atualizado.');
};
acts['report-batch-template']=async()=>{const d=await api('/api/model-data/report-batch-template',{});reportsDownload(d.filename,d.mime,d.file);};
acts['report-batch-preview']=async()=>{
 if(!reportBatchDraft?.file)throw new Error('Selecione o XLSX.');
 reportBatchPreviewData=await api('/api/model-data/report-batch-preview',{file:reportBatchDraft.file,filename:reportBatchDraft.filename});
 render();
};
acts['report-batch-confirm']=async()=>{
 if(!reportBatchDraft?.file)throw new Error('Selecione o XLSX.');
 if(!confirm('Cadastrar/atualizar os relatórios individuais listados na prévia?'))return;
 const d=await api('/api/model-data/report-batch-confirm',{file:reportBatchDraft.file,filename:reportBatchDraft.filename});
 reportAdminCache=null;reportBatchPreviewData=null;studentReportsCache.clear();await loadReportAdmin(true);
 toast('Cadastro concluído: '+Number(d.summary?.newReports||0)+' novo(s), '+Number(d.summary?.updatedReports||0)+' atualizado(s).');
};
document.addEventListener('change',async event=>{
 const el=event.target;
 if(el?.id==='report-batch-file'){
  const file=el.files?.[0];el.value='';if(!file)return;
  if(!/\.xlsx$/i.test(file.name))throw new Error('Selecione um arquivo .xlsx.');
  if(file.size>5000000)throw new Error('O arquivo excede 5 MB.');
  reportBatchDraft={filename:file.name,file:await reportsFileBase64(file)};reportBatchPreviewData=null;render();return;
 }
 if(el?.matches('[data-report-cover-file]')){
  const file=el.files?.[0];if(!file)return;
  if(!file.type.startsWith('image/'))throw new Error('Selecione uma imagem.');
  if(file.size>600000)throw new Error('A capa deve ter no máximo 600 KB.');
  const data=await new Promise((resolve,reject)=>{const reader=new FileReader();reader.onload=()=>resolve(String(reader.result||''));reader.onerror=()=>reject(new Error('Não foi possível ler a imagem.'));reader.readAsDataURL(file);});
  const id=el.dataset.reportCoverFile,input=document.querySelector('[data-report-model-cover="'+CSS.escape(id)+'"]');if(input)input.value=data;
 }
},true);

// === HOTFIX V3.7.1 ===
managementSimulationChart=function(rows){
 const ordered=[...(rows||[])].sort((a,b)=>String(a.date||'').localeCompare(String(b.date||'')));
 if(!ordered.length)return '<div class="notice">Nenhum simulado com resultados nos filtros selecionados.</div>';
 const cols=ordered.map(x=>{
  const tri=Number(x.triGeneral),hasTri=Number.isFinite(tri),height=hasTri?Math.max(0,Math.min(100,tri/10)):0;
  return '<div class="management-score-col"><div class="management-score-plot"><div class="management-score-track"><span class="management-score-fill" style="height:'+height+'%"></span><span class="management-score-marker" style="bottom:'+height+'%">'+(hasTri?managementFmt(tri,1):'—')+'</span></div></div><strong>'+esc(x.activity||'Simulado')+'</strong><small>'+esc(x.date||'')+'</small><em>'+managementInt(x.participants)+' participantes · % acertos '+managementFmt(x.accuracy,1,'%')+'</em></div>';
 }).join('');
 return '<div class="management-score-chart"><div class="management-scale"><span>1000</span><span>750</span><span>500</span><span>250</span><span>0</span></div><div class="management-score-columns">'+cols+'</div></div><p class="micro">A área pintada corresponde exatamente à nota TRI geral média na escala de 0 a 1000.</p>';
};

reportTypesAdminHtml=function(types){
 const rows=(types||[]).map(t=>'<tr><td><input data-report-type-name="'+esc(t.id)+'" value="'+esc(t.name)+'"></td><td><input type="number" data-report-type-order="'+esc(t.id)+'" value="'+Number(t.sort_order||0)+'"></td><td><label class="check"><input type="checkbox" data-report-type-active="'+esc(t.id)+'"'+(t.active?' checked':'')+'> Ativo</label></td><td><div class="actions"><button type="button" class="secondary" data-act="report-type-save" data-type-id="'+esc(t.id)+'">Salvar</button><button type="button" class="secondary danger" data-act="report-type-delete" data-type-id="'+esc(t.id)+'" data-type-name="'+esc(t.name)+'">Excluir</button></div></td></tr>').join('');
 return '<section class="card"><h2>Tipos de relatório</h2><p>Os tipos definem as linhas/seções que o aluno verá em “Meus relatórios”.</p><div class="report-type-new"><label>Novo tipo<input id="report-type-new-name" placeholder="Ex.: Diagnóstico"></label><label>Ordem<input id="report-type-new-order" type="number" value="10"></label><button type="button" class="primary" data-act="report-type-new">Criar tipo</button></div><div class="table-wrap"><table><thead><tr><th>Tipo</th><th>Ordem</th><th>Status</th><th>Ações</th></tr></thead><tbody>'+rows+'</tbody></table></div></section>';
};
acts['report-type-delete']=async el=>{
 const id=el?.dataset?.typeId||'',name=el?.dataset?.typeName||'este tipo';
 if(!id)throw new Error('Tipo não informado.');
 if(!confirm('Excluir "'+name+'"? Se houver modelos e relatórios individuais vinculados a este tipo, eles também serão excluídos.'))return;
 const d=await api('/api/model-data/report-type-delete',{id});
 reportAdminCache={types:d.types||[],models:d.models||[]};studentReportsCache.clear();render();
 toast('Tipo excluído: '+String(d.deletedType||name)+'.');
};

acts['report-batch-template']=async()=>{
 try{
  const d=await api('/api/model-data/report-batch-template',{});
  reportsDownload(d.filename,d.mime,d.file);
  toast('Modelo XLSX gerado e disponibilizado para download.');
 }catch(error){
  toast('Não foi possível gerar o modelo XLSX: '+(error?.message||'erro inesperado'),true);
  throw error;
 }
};

// === HOTFIX V3.7.2 ===
classRegistryPanel=function(){
 if(!classRegistryCache&&!classRegistryLoading)queueMicrotask(()=>loadClassRegistry());
 if(classRegistryLoading||!classRegistryCache)return '<section class="card"><h2>Cadastro de turmas</h2><p>Carregando…</p></section>';
 if(classRegistryCache.error)return '<section class="card"><h2>Cadastro de turmas</h2><div class="notice warning">'+esc(classRegistryCache.error)+'</div></section>';
 const classes=classRegistryCache.classes||[];
 const rows=classes.map(x=>{
  const divergent=(x.divergents||[]);
  const divergentHtml=divergent.length?divergent.map(d=>'<span class="class-divergent-chip">'+esc(d.name)+' · '+managementInt(d.records)+'</span>').join(''):'<span class="micro">Nenhuma divergência</span>';
  return '<tr><td><strong>'+esc(x.name)+'</strong></td><td><div class="class-divergent-list">'+divergentHtml+'</div></td><td><input data-class-name="'+esc(x.id)+'" value="'+esc(x.name)+'" aria-label="Novo nome oficial"><input type="hidden" data-class-aliases="'+esc(x.id)+'" value="'+esc((x.aliases||[]).join('; '))+'"></td><td><label class="check"><input type="checkbox" data-class-active="'+esc(x.id)+'"'+(x.active?' checked':'')+'> Ativa</label></td><td><button type="button" class="primary" data-act="class-registry-save" data-class-id="'+esc(x.id)+'">Salvar correção</button></td></tr>';
 }).join('');
 const missing=classRegistryCache.unregistered||[];
 const missingHtml=missing.length?'<div class="notice warning"><strong>Turmas ainda não vinculadas a um cadastro:</strong><ul>'+missing.map(x=>'<li>'+esc(x.name)+' · '+managementInt(x.records)+' registro(s)</li>').join('')+'</ul></div>':'<div class="notice success">Nenhuma turma sem cadastro encontrada.</div>';
 return '<section class="card class-registry-card"><h2>Cadastro e correção de turmas</h2><p>Ao alterar o nome oficial e salvar, o sistema atualiza também todos os resultados históricos que usam o nome anterior ou uma variação já reconhecida.</p><div class="class-new-grid"><label>Nova turma<input id="class-new-name" placeholder="Ex.: Qi Med 01"></label><label>Aliases autorizados<input id="class-new-aliases" placeholder="Ex.: 01 Qi Med 01; MED 01"></label><button type="button" class="primary" data-act="class-registry-new">Cadastrar turma</button></div>'+missingHtml+'<div class="table-wrap"><table><thead><tr><th>Turma cadastrada</th><th>Turmas divergentes</th><th>Correção</th><th>Ativa</th><th>Salvar correção</th></tr></thead><tbody>'+rows+'</tbody></table></div></section>';
};

acts['class-registry-save']=async el=>{
 const id=el?.dataset?.classId||'';
 const name=document.querySelector('[data-class-name="'+CSS.escape(id)+'"]')?.value||'';
 const aliases=document.querySelector('[data-class-aliases="'+CSS.escape(id)+'"]')?.value||'';
 const active=!!document.querySelector('[data-class-active="'+CSS.escape(id)+'"]')?.checked;
 const current=(classRegistryCache?.classes||[]).find(x=>x.id===id);
 if(!name.trim())throw new Error('Informe o nome oficial da turma.');
 const changed=current&&current.name!==name.trim();
 const question=changed?'Alterar a turma "'+current.name+'" para "'+name.trim()+'" e atualizar todos os registros vinculados?':'Normalizar as divergências desta turma para "'+name.trim()+'"?';
 if(!confirm(question))return;
 const d=await api('/api/model-data/classes',{id,name,aliases,active});
 classRegistryCache={classes:d.classes||[],unregistered:d.unregistered||[]};
 managementDashboardCache=null;
 const updated=Number(d.saved?.updatedResults||0);
 toast('Turma salva. '+updated+' registro(s) histórico(s) atualizado(s).');
 render();
};

managementSimulationChart=function(rows){
 const ordered=[...(rows||[])].sort((a,b)=>String(a.date||'').localeCompare(String(b.date||'')));
 if(!ordered.length)return '<div class="notice">Nenhum simulado com resultados nos filtros selecionados.</div>';
 const cols=ordered.map(x=>{
  const tri=Number(x.triGeneral),hasTri=Number.isFinite(tri),height=hasTri?Math.max(0,Math.min(100,tri/10)):0;
  return '<div class="management-score-col"><div class="management-score-plot"><div class="management-score-track"><span class="management-score-fill" style="height:'+height+'%"></span><span class="management-score-marker" style="bottom:'+height+'%">'+(hasTri?managementFmt(tri,1):'—')+'</span></div></div><strong>'+esc(x.activity||'Simulado')+'</strong><small>'+esc(x.date||'')+'</small><em>'+managementInt(x.participants)+' participantes · % acertos '+managementFmt(x.accuracy,1,'%')+'</em></div>';
 }).join('');
 return '<div class="management-score-axis"><div class="management-scale"><span>1000</span><span>750</span><span>500</span><span>250</span><span>0</span></div><div class="management-score-columns">'+cols+'</div></div><p class="micro">A base das colunas coincide com o zero da escala. A área pintada corresponde à nota TRI média em 0–1000.</p>';
};

// === HOTFIX V3.7.3 ===
acts['class-registry-save']=async el=>{
 const id=el?.dataset?.classId||'';
 const name=document.querySelector('[data-class-name="'+CSS.escape(id)+'"]')?.value?.trim()||'';
 const aliases=document.querySelector('[data-class-aliases="'+CSS.escape(id)+'"]')?.value||'';
 const active=!!document.querySelector('[data-class-active="'+CSS.escape(id)+'"]')?.checked;
 const classes=classRegistryCache?.classes||[];
 const current=classes.find(x=>x.id===id);
 if(!name)throw new Error('Informe o nome oficial da turma.');

 const sameName=value=>String(value||'').trim().toLocaleLowerCase('pt-BR')===name.toLocaleLowerCase('pt-BR');
 const existing=classes.find(x=>x.id!==id&&sameName(x.name));

 let question='';
 if(existing){
  question='Mesclar a turma "'+(current?.name||'')+'" com a turma já existente "'+existing.name+'"? Todos os resultados vinculados serão atualizados para "'+existing.name+'" e a turma duplicada será removida.';
 }else if(current&&current.name!==name){
  question='Alterar a turma "'+current.name+'" para "'+name+'" e atualizar todos os registros vinculados?';
 }else{
  question='Normalizar as divergências desta turma para "'+name+'"?';
 }
 if(!confirm(question))return;

 const d=await api('/api/model-data/classes',{id,name,aliases,active});
 classRegistryCache={classes:d.classes||[],unregistered:d.unregistered||[]};
 managementDashboardCache=null;
 const saved=d.saved||{};
 const updated=Number(saved.updatedResults||0);
 if(saved.merged){
  toast('Turmas mescladas: "'+saved.mergedFrom+'" → "'+saved.mergedInto+'". '+updated+' registro(s) atualizado(s).');
 }else{
  toast('Turma salva. '+updated+' registro(s) histórico(s) atualizado(s).');
 }
 render();
};

// === REPORT PAPER LAYOUT V3.7.5 ===
function reportPaperCoverHtml(report){
 const cover=String(report?.cover||'').trim();
 if(cover){
  return '<div class="report-paper-cover-wrap"><img class="report-paper-cover" src="'+esc(cover)+'" alt="Capa de '+esc(report.name||report.title||'relatório')+'"></div>';
 }
 return '<div class="report-paper-cover-wrap"><div class="report-paper-cover report-paper-placeholder"><div class="report-paper-placeholder-mark">Qi</div><span>Relatório</span></div></div>';
}
function reportPaperCardHtml(group,report){
 const name=report?.name||report?.title||report?.activity||'Relatório';
 const activity=String(report?.activity||'').trim();
 const showActivity=activity&&activity.toLocaleLowerCase('pt-BR')!==String(name).trim().toLocaleLowerCase('pt-BR');
 return '<article class="student-report-card report-paper-card">'+
  reportPaperCoverHtml(report)+
  '<div class="report-paper-info">'+
   '<span class="report-paper-type">'+esc(group?.name||'Relatório')+'</span>'+
   '<h3 class="report-paper-title">'+esc(name)+'</h3>'+
   (showActivity?'<p class="report-paper-activity">'+esc(activity)+'</p>':'')+
   (report?.date?'<time class="report-paper-date">'+esc(report.date)+'</time>':'')+
   (report?.description?'<p class="report-paper-description">'+esc(report.description)+'</p>':'')+
   '<a class="primary report-open-link report-paper-open" href="'+esc(report.url)+'" target="_blank" rel="noopener noreferrer">Abrir relatório</a>'+
  '</div>'+
 '</article>';
}
reportsView=function(){
 const id=reportTargetId(),key=id||'__none__';
 if(!studentReportsCache.has(key))queueMicrotask(()=>loadStudentReports());
 const d=studentReportsCache.get(key);
 if(!d)return head('Meus relatórios','Relatórios individuais disponibilizados pela coordenação.')+'<section class="card"><p>Carregando relatórios…</p></section>';
 if(d.error)return head('Meus relatórios','Relatórios individuais disponibilizados pela coordenação.')+'<section class="card"><div class="notice warning">'+esc(d.error)+'</div></section>';
 if(!d.student&&['master','coordenador'].includes(ME.role))return head('Meus relatórios','Selecione um aluno no campo de pesquisa para visualizar os relatórios dele.')+'<section class="card"><div class="notice">Nenhum aluno selecionado.</div></section>';
 const groups=d.groups||[];
 const body=groups.length?groups.map(group=>
  '<section class="card student-report-group report-paper-group">'+
   '<div class="student-report-group-head"><div><p class="eyebrow">RELATÓRIOS</p><h2>'+esc(group.name)+'</h2></div><span>'+group.reports.length+' relatório(s)</span></div>'+
   '<div class="student-report-row report-paper-grid">'+group.reports.map(report=>reportPaperCardHtml(group,report)).join('')+'</div>'+
  '</section>'
 ).join(''):'<section class="card"><div class="notice">Ainda não há relatórios publicados para este aluno.</div></section>';
 return head('Meus relatórios',d.student?'Relatórios disponíveis para '+esc(d.student.name)+'.':'Relatórios individuais disponibilizados pela coordenação.')+body;
};

// === REPORT SCOPED DELETE V3.7.6 ===
let reportDeleteContext=null;

function reportModelsAdminHtml(models){
 const rows=(models||[]).map(m=>
  '<tr>'+
   '<td><strong>'+esc(m.type_name)+'</strong></td>'+
   '<td>'+esc(m.activity)+(m.applied_on?'<br><small>'+esc(m.applied_on)+'</small>':'')+'</td>'+
   '<td><input data-report-model-title="'+esc(m.id)+'" value="'+esc(m.title||'')+'"><textarea data-report-model-description="'+esc(m.id)+'" rows="2" placeholder="Descrição geral">'+esc(m.description||'')+'</textarea></td>'+
   '<td><div class="report-cover-edit">'+(m.cover?'<img src="'+esc(m.cover)+'" alt="Capa">':'')+'<input data-report-model-cover="'+esc(m.id)+'" value="'+esc(m.cover||'')+'" placeholder="URL da capa ou imagem enviada"><input type="file" accept="image/*" data-report-cover-file="'+esc(m.id)+'"></div></td>'+
   '<td>'+Number(m.assignments||0)+'</td>'+
   '<td><label class="check"><input type="checkbox" data-report-model-active="'+esc(m.id)+'"'+(m.active?' checked':'')+'> Ativo</label></td>'+
   '<td><div class="actions report-model-actions"><button type="button" class="secondary" data-act="report-model-save" data-model-id="'+esc(m.id)+'">Salvar</button><button type="button" class="secondary danger" data-act="report-model-delete-open" data-model-id="'+esc(m.id)+'" data-model-title="'+esc(m.title||m.activity||'Relatório')+'">Excluir</button></div></td>'+
  '</tr>'
 ).join('');
 return '<section class="card"><h2>Modelos cadastrados</h2><p>Título, descrição e capa são informações gerais replicadas a todos os alunos vinculados ao mesmo modelo.</p><div class="table-wrap"><table><thead><tr><th>Tipo</th><th>Atividade</th><th>Informações gerais</th><th>Capa</th><th>Alunos</th><th>Status</th><th>Ações</th></tr></thead><tbody>'+rows+'</tbody></table></div></section>';
}

function reportDeleteScopeHtml(data){
 const groups=data?.classes||[];
 const model=data?.model||{};
 const groupHtml=groups.map((group,index)=>
  '<section class="report-delete-class" data-report-delete-group="'+index+'">'+
   '<label class="report-delete-class-head"><input type="checkbox" data-report-delete-class="'+index+'" value="'+esc(group.name)+'"><span><strong>'+esc(group.name)+'</strong><small>'+Number(group.count||0)+' aluno(s) com este relatório</small></span></label>'+
   '<div class="report-delete-students" data-report-delete-students="'+index+'">'+
    group.students.map(student=>
     '<label><input type="checkbox" data-report-delete-student="'+index+'" value="'+esc(student.id)+'" disabled><span>'+esc(student.name)+'<small>'+esc(student.username||'')+'</small></span></label>'
    ).join('')+
   '</div>'+
  '</section>'
 ).join('');

 return '<div class="report-delete-scope">'+
  '<div class="notice warning"><strong>Excluir '+esc(model.title||'relatório')+'</strong><p>Se nenhuma turma for selecionada, o relatório será removido de todos os alunos e o modelo será excluído.</p></div>'+
  '<p><strong>'+Number(data?.totalAssignments||0)+'</strong> vínculo(s) atualmente cadastrado(s).</p>'+
  '<p class="micro">Ao selecionar uma turma: se nenhum aluno dela for marcado, o relatório será removido de toda a turma. Se marcar alunos, será removido somente desses alunos.</p>'+
  '<div class="report-delete-class-list">'+groupHtml+'</div>'+
  '<div class="actions"><button type="button" class="secondary" data-act="report-delete-cancel">Cancelar</button><button type="button" class="primary danger" data-act="report-delete-confirm">Excluir relatório</button></div>'+
 '</div>';
}

acts['report-model-delete-open']=async el=>{
 const modelId=el?.dataset?.modelId||'';
 if(!modelId)throw new Error('Modelo de relatório não informado.');
 const data=await api('/api/model-data/report-delete-options',{modelId});
 reportDeleteContext={modelId,data};
 modal('Excluir relatório',reportDeleteScopeHtml(data),null);
};

acts['report-delete-cancel']=()=>{reportDeleteContext=null;closeModal(true);};

acts['report-delete-confirm']=async()=>{
 if(!reportDeleteContext?.modelId)throw new Error('Nenhum relatório selecionado para exclusão.');
 const data=reportDeleteContext.data||{};
 const selectedClasses=[...document.querySelectorAll('[data-report-delete-class]:checked')];
 const selections=selectedClasses.map(input=>{
  const index=input.dataset.reportDeleteClass;
  const userIds=[...document.querySelectorAll('[data-report-delete-student="'+CSS.escape(index)+'"]:checked')].map(x=>x.value);
  return {turma:input.value,userIds};
 });

 let message='';
 if(!selections.length){
  message='Nenhuma turma foi selecionada. Isso excluirá o modelo "'+(data.model?.title||'Relatório')+'" e removerá o relatório de TODOS os '+Number(data.totalAssignments||0)+' aluno(s). Confirmar?';
 }else{
  const parts=selections.map(item=>item.turma+(item.userIds.length?' · '+item.userIds.length+' aluno(s) selecionado(s)':' · turma inteira'));
  message='Confirmar a exclusão neste escopo?\n\n'+parts.join('\n');
 }
 if(!confirm(message))return;

 const result=await api('/api/model-data/report-delete-scope',{
  modelId:reportDeleteContext.modelId,
  selections
 });
 reportDeleteContext=null;
 reportAdminCache={types:result.types||[],models:result.models||[]};
 studentReportsCache.clear();
 closeModal(true);
 render();
 toast(
  'Exclusão concluída: '+Number(result.deletedAssignments||0)+' vínculo(s) removido(s).'+
  (result.modelDeleted?' Modelo excluído.':' '+Number(result.remainingAssignments||0)+' vínculo(s) permanecem.')
 );
};

document.addEventListener('change',event=>{
 const el=event.target;
 if(!el?.matches('[data-report-delete-class]'))return;
 const index=el.dataset.reportDeleteClass;
 const students=document.querySelectorAll('[data-report-delete-student="'+CSS.escape(index)+'"]');
 students.forEach(input=>{
  input.disabled=!el.checked;
  if(!el.checked)input.checked=false;
 });
 const group=document.querySelector('[data-report-delete-group="'+CSS.escape(index)+'"]');
 if(group)group.classList.toggle('selected',el.checked);
},true);

// === REPORT REGISTRY VIEW V3.7.7 ===
let reportRegistryCache=null;
let reportRegistryLoading=false;
let reportRegistryFilters={q:'',type:'',student:'',turma:''};
let reportRegistryDetailCache=new Map();
let reportRegistryExpandedModel='';
let reportRegistryExpandedClass={};
let reportRegistryDebounce=null;

const reportsViewStudentV377=reportsView;

function reportRegistryQuery(){
 const q=new URLSearchParams();
 Object.entries(reportRegistryFilters).forEach(([key,value])=>{if(String(value||'').trim())q.set(key,String(value).trim());});
 return q.toString();
}
async function loadReportRegistry(force=false){
 if(!managementDashboardAllowed()||reportRegistryLoading||(!force&&reportRegistryCache))return;
 reportRegistryLoading=true;
 try{
  const query=reportRegistryQuery();
  reportRegistryCache=await api('/api/model-data/report-registry'+(query?'?'+query:''));
 }catch(error){
  reportRegistryCache={error:error?.message||'Não foi possível carregar os relatórios cadastrados.'};
 }finally{
  reportRegistryLoading=false;
  if(view==='reports')render();
 }
}
async function loadReportRegistryDetail(modelId){
 if(reportRegistryDetailCache.has(modelId))return reportRegistryDetailCache.get(modelId);
 const data=await api('/api/model-data/report-registry-detail?modelId='+encodeURIComponent(modelId));
 reportRegistryDetailCache.set(modelId,data);
 return data;
}
function reportRegistryDatalist(id,values){
 return '<datalist id="'+id+'">'+(values||[]).map(value=>'<option value="'+esc(value)+'"></option>').join('')+'</datalist>';
}
function reportRegistryFilterHtml(data){
 const s=data?.suggestions||{};
 const f=data?.filters||reportRegistryFilters;
 return '<section class="card report-registry-filter">'+
  '<div class="report-registry-filter-head"><div><h2>Relatórios cadastrados</h2><p>Pesquise e filtre pelos dados já cadastrados. As sugestões aparecem conforme você digita.</p></div><span class="tag">'+Number(data?.total||0)+' resultado(s)</span></div>'+
  '<div class="report-registry-filter-grid">'+
   '<label>Relatório / atividade<input id="report-registry-q" list="report-registry-reports" value="'+esc(f.q||'')+'" placeholder="Digite o nome do relatório ou atividade"></label>'+
   '<label>Tipo<input id="report-registry-type" list="report-registry-types" value="'+esc(f.type||'')+'" placeholder="Ex.: Simulado"></label>'+
   '<label>Aluno<input id="report-registry-student" list="report-registry-students" value="'+esc(f.student||'')+'" placeholder="Digite o nome do aluno"></label>'+
   '<label>Turma<input id="report-registry-turma" list="report-registry-classes" value="'+esc(f.turma||'')+'" placeholder="Digite a turma"></label>'+
  '</div>'+
  reportRegistryDatalist('report-registry-reports',s.reports)+
  reportRegistryDatalist('report-registry-types',s.types)+
  reportRegistryDatalist('report-registry-students',s.students)+
  reportRegistryDatalist('report-registry-classes',s.classes)+
  '<div class="actions"><button type="button" class="secondary" data-act="report-registry-clear">Limpar filtros</button><button type="button" class="secondary" data-act="report-registry-refresh">Atualizar</button></div>'+
 '</section>';
}
function reportRegistryDate(value){
 if(!value)return '—';
 const text=String(value);
 if(/^\d{4}-\d{2}-\d{2}/.test(text)){
  const [y,m,d]=text.slice(0,10).split('-');
  return d+'/'+m+'/'+y;
 }
 return text;
}
function reportRegistryCreatedAt(value){
 if(!value)return '—';
 const text=String(value);
 const match=text.match(/^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2})/);
 if(!match)return text;
 return match[3]+'/'+match[2]+'/'+match[1]+' '+match[4]+':'+match[5];
}
function reportRegistryClassesSummary(model){
 const rows=model?.classes||[];
 if(!rows.length)return '<span class="micro">Sem turma vinculada</span>';
 const shown=rows.slice(0,3).map(x=>esc(x.name)+' ('+Number(x.count||0)+')').join(', ');
 const extra=rows.length>3?' +'+(rows.length-3):'';
 return '<span>'+shown+extra+'</span>';
}
function reportRegistryStudentTable(group){
 return '<div class="report-registry-students-table"><table><thead><tr><th>Aluno</th><th>Login</th><th>Relatório</th><th>Link individual</th></tr></thead><tbody>'+
  (group.students||[]).map(student=>
   '<tr><td><strong>'+esc(student.name)+'</strong></td><td>'+esc(student.username||'')+'</td><td>'+esc(student.reportName||'')+'</td><td><a class="secondary report-registry-link" href="'+esc(student.url)+'" target="_blank" rel="noopener noreferrer">Abrir relatório</a></td></tr>'
  ).join('')+
 '</tbody></table></div>';
}
function reportRegistryDetailHtml(modelId){
 const detail=reportRegistryDetailCache.get(modelId);
 if(!detail)return '<div class="report-registry-detail-loading">Carregando turmas vinculadas…</div>';
 const groups=detail.classes||[];
 if(!groups.length)return '<div class="notice">Nenhum aluno possui este relatório.</div>';
 return '<div class="report-registry-class-list">'+groups.map((group,index)=>{
  const key=modelId+'@@'+group.name;
  const open=!!reportRegistryExpandedClass[key];
  return '<section class="report-registry-class'+(open?' open':'')+'">'+
   '<button type="button" class="report-registry-class-button" data-act="report-registry-class-toggle" data-model-id="'+esc(modelId)+'" data-class-name="'+encodeURIComponent(group.name)+'">'+
    '<span><strong>'+esc(group.name)+'</strong><small>'+Number(group.count||0)+' aluno(s) com este relatório</small></span><span class="report-registry-chevron">'+(open?'−':'+')+'</span>'+
   '</button>'+
   (open?reportRegistryStudentTable(group):'')+
  '</section>';
 }).join('')+'</div>';
}
function reportRegistryTableHtml(models){
 if(!(models||[]).length)return '<section class="card"><div class="notice">Nenhum relatório encontrado com os filtros selecionados.</div></section>';
 const body=models.map(model=>{
  const open=reportRegistryExpandedModel===model.id;
  return '<tbody class="report-registry-model-group">'+
   '<tr class="report-registry-row'+(open?' open':'')+'" data-act="report-registry-model-toggle" data-model-id="'+esc(model.id)+'">'+
    '<td><strong>'+esc(model.title||model.activity||'Relatório')+'</strong><br><small>'+esc(model.activity||'')+(model.date?' · '+esc(reportRegistryDate(model.date)):'')+'</small></td>'+
    '<td>'+esc(model.type||'')+'</td>'+
    '<td>'+Number(model.assignments||0)+'</td>'+
    '<td>'+Number(model.classCount||0)+'</td>'+
    '<td>'+reportRegistryClassesSummary(model)+'</td>'+
    '<td>'+esc(reportRegistryCreatedAt(model.createdAt))+'</td>'+
    '<td><button type="button" class="secondary" data-act="report-registry-model-toggle" data-model-id="'+esc(model.id)+'">'+(open?'Fechar':'Ver vínculos')+'</button></td>'+
   '</tr>'+
   (open?'<tr class="report-registry-detail-row"><td colspan="7">'+reportRegistryDetailHtml(model.id)+'</td></tr>':'')+
  '</tbody>';
 }).join('');
 return '<section class="card report-registry-table-card"><div class="table-wrap"><table class="report-registry-table"><thead><tr><th>Relatório / atividade</th><th>Tipo</th><th>Alunos</th><th>Turmas</th><th>Turmas vinculadas</th><th>Cadastrado em</th><th></th></tr></thead>'+body+'</table></div></section>';
}
function reportsRegistryView(){
 if(!reportRegistryCache&&!reportRegistryLoading)queueMicrotask(()=>loadReportRegistry());
 if(reportRegistryLoading||!reportRegistryCache)return head('Meus relatórios','Visão gerencial dos relatórios cadastrados.')+'<section class="card"><p>Carregando relatórios cadastrados…</p></section>';
 if(reportRegistryCache.error)return head('Meus relatórios','Visão gerencial dos relatórios cadastrados.')+'<section class="card"><div class="notice warning">'+esc(reportRegistryCache.error)+'</div></section>';
 return head('Meus relatórios','Pesquise relatórios, turmas e alunos. Clique em um relatório para abrir seus vínculos.')+
  reportRegistryFilterHtml(reportRegistryCache)+
  reportRegistryTableHtml(reportRegistryCache.models||[]);
}
reportsView=function(){
 if(managementDashboardAllowed())return reportsRegistryView();
 return reportsViewStudentV377();
};

acts['report-registry-clear']=()=>{
 reportRegistryFilters={q:'',type:'',student:'',turma:''};
 reportRegistryCache=null;
 reportRegistryExpandedModel='';
 reportRegistryExpandedClass={};
 loadReportRegistry(true);
};
acts['report-registry-refresh']=()=>{reportRegistryCache=null;reportRegistryDetailCache.clear();loadReportRegistry(true);};
acts['report-registry-model-toggle']=async el=>{
 const modelId=el?.dataset?.modelId||'';
 if(!modelId)return;
 if(reportRegistryExpandedModel===modelId){reportRegistryExpandedModel='';render();return;}
 reportRegistryExpandedModel=modelId;
 render();
 try{await loadReportRegistryDetail(modelId);}catch(error){toast(error?.message||'Não foi possível carregar os vínculos.',true);}
 render();
};
acts['report-registry-class-toggle']=el=>{
 const modelId=el?.dataset?.modelId||'',className=decodeURIComponent(el?.dataset?.className||'');
 const key=modelId+'@@'+className;
 reportRegistryExpandedClass[key]=!reportRegistryExpandedClass[key];
 render();
};

document.addEventListener('input',event=>{
 const el=event.target;
 const map={
  'report-registry-q':'q',
  'report-registry-type':'type',
  'report-registry-student':'student',
  'report-registry-turma':'turma'
 };
 const key=map[el?.id];
 if(!key)return;
 reportRegistryFilters[key]=el.value||'';
 clearTimeout(reportRegistryDebounce);
 reportRegistryDebounce=setTimeout(()=>{
  reportRegistryCache=null;
  reportRegistryExpandedModel='';
  reportRegistryExpandedClass={};
  loadReportRegistry(true);
 },280);
},true);

// === MANAGEMENT FILTER FIX V3.7.11 ===
function managementSafeArray(value){return Array.isArray(value)?value:[];}

const managementFiltersHtmlV3711Base=managementFiltersHtml;
managementFiltersHtml=function(d){
 const safe=d&&typeof d==='object'?d:{};
 const f=safe.filters&&typeof safe.filters==='object'?safe.filters:{};
 f.years=managementSafeArray(f.years);
 f.turmas=managementSafeArray(f.turmas);
 f.simulations=managementSafeArray(f.simulations);
 f.selected=f.selected&&typeof f.selected==='object'?f.selected:{};
 safe.filters=f;
 return managementFiltersHtmlV3711Base(safe);
};

const managementAreaHtmlV3711Base=managementAreaHtml;
managementAreaHtml=function(rows){return managementAreaHtmlV3711Base(managementSafeArray(rows));};

const managementSimulationChartV3711Base=managementSimulationChart;
managementSimulationChart=function(rows){return managementSimulationChartV3711Base(managementSafeArray(rows));};

const managementSimulationTableV3711Base=managementSimulationTable;
managementSimulationTable=function(rows){return managementSimulationTableV3711Base(managementSafeArray(rows));};

const managementClassTableV3711Base=managementClassTable;
managementClassTable=function(rows){return managementClassTableV3711Base(managementSafeArray(rows));};

acts['management-dashboard-refresh']=async()=>{
 managementDashboardFilters={
  year:document.getElementById('management-year')?.value||managementDashboardFilters.year||'',
  turma:document.getElementById('management-turma')?.value||managementDashboardFilters.turma||'',
  activityKey:managementDashboardFilters.activityKey||'',
  date:managementDashboardFilters.date||'',
 };
 const sim=document.getElementById('management-simulation');
 if(sim){
  const parts=(sim.value||'').split('@@');
  managementDashboardFilters.activityKey=parts[0]||'';
  managementDashboardFilters.date=parts[1]||'';
 }
 managementDashboardCache=null;
 await loadManagementDashboard(true);
};

document.addEventListener('change',event=>{
 const el=event.target;
 if(!managementDashboardAllowed()||!el)return;
 if(el.id==='management-year'){
  managementDashboardFilters.year=el.value||'';
  managementDashboardCache=null;
  loadManagementDashboard(true);
 }
 if(el.id==='management-turma'){
  managementDashboardFilters.turma=el.value||'';
  managementDashboardCache=null;
  loadManagementDashboard(true);
 }
 if(el.id==='management-simulation'){
  const parts=(el.value||'').split('@@');
  managementDashboardFilters.activityKey=parts[0]||'';
  managementDashboardFilters.date=parts[1]||'';
  managementDashboardCache=null;
  loadManagementDashboard(true);
 }
},true);

// === CLASS ENEM ANALYTICS V3.7.12 ===
let managementClassAnalyticsCache=null;
let managementClassAnalyticsLoading=false;
let managementClassSelectedSims=new Set();
let managementClassOpen='';
let managementClassDetailCache=new Map();
let managementSimulationOpen='';
let managementStudentDetailCache=new Map();

function mgmtAnalyticsQuery(extra={}){
 const q=new URLSearchParams();
 const year=managementDashboardFilters?.year||'';
 if(year)q.set('year',year);
 if(managementClassSelectedSims.size)q.set('sims',[...managementClassSelectedSims].join('||'));
 Object.entries(extra).forEach(([k,v])=>{if(v!==undefined&&v!==null&&String(v)!=='')q.set(k,String(v));});
 return q.toString();
}
async function loadManagementClassAnalytics(force=false){
 if(!managementDashboardAllowed()||managementClassAnalyticsLoading||(!force&&managementClassAnalyticsCache))return;
 managementClassAnalyticsLoading=true;
 try{
  managementClassAnalyticsCache=await api('/api/model-data/management-class-analytics?'+mgmtAnalyticsQuery());
 }catch(error){
  managementClassAnalyticsCache={error:error?.message||'Não foi possível carregar a análise por turma.'};
 }finally{
  managementClassAnalyticsLoading=false;
  if(view==='home')render();
 }
}
async function loadManagementClassDetail(turma){
 const key=turma+'@@'+[...managementClassSelectedSims].sort().join('|')+'@@'+(managementDashboardFilters?.year||'');
 if(managementClassDetailCache.has(key))return managementClassDetailCache.get(key);
 const data=await api('/api/model-data/management-class-detail?'+mgmtAnalyticsQuery({turma}));
 managementClassDetailCache.set(key,data);return data;
}
async function loadManagementStudentDetail(turma,activityKey,date){
 const key=[turma,activityKey,date].join('@@');
 if(managementStudentDetailCache.has(key))return managementStudentDetailCache.get(key);
 const data=await api('/api/model-data/management-simulation-students?'+mgmtAnalyticsQuery({turma,activityKey,date}));
 managementStudentDetailCache.set(key,data);return data;
}
function mgmtVal(v,d=1,suffix=''){return managementFmt(v,d,suffix);}
function mgmtAnalyticsCells(x){
 return '<td>'+mgmtVal(x.enem,1)+'</td><td>'+mgmtVal(x.bonus,1)+'</td>'+
 '<td>'+mgmtVal(x.accuracy,1,'%')+'</td><td>'+mgmtVal(x.lcAccuracy,1,'%')+'</td>'+
 '<td>'+mgmtVal(x.chAccuracy,1,'%')+'</td><td>'+mgmtVal(x.cnAccuracy,1,'%')+'</td>'+
 '<td>'+mgmtVal(x.mtAccuracy,1,'%')+'</td><td>'+mgmtVal(x.c1,1)+'</td><td>'+mgmtVal(x.c2,1)+'</td>'+
 '<td>'+mgmtVal(x.c3,1)+'</td><td>'+mgmtVal(x.c4,1)+'</td><td>'+mgmtVal(x.c5,1)+'</td><td>'+mgmtVal(x.redaction,1)+'</td>';
}
function mgmtAnalyticsHead(first){
 return '<tr><th>'+first+'</th><th>Participantes</th><th>Simulados</th><th>Nota ENEM</th><th>+10%</th><th>Acertos</th><th>LC</th><th>CH</th><th>CN</th><th>MT</th><th>C1</th><th>C2</th><th>C3</th><th>C4</th><th>C5</th><th>Redação</th></tr>';
}
function managementSimulationSelectorHtml(data){
 const options=managementSafeArray(data?.simulations);
 const selected=managementClassSelectedSims;
 return '<div class="management-multi-sims"><div class="management-multi-sims-head"><div><strong>Simulados considerados nas médias</strong><p class="micro">Se nenhum estiver marcado, entram todos os simulados realizados pela turma.</p></div><div class="actions"><button type="button" class="secondary" data-act="management-sims-clear">Limpar seleção</button><button type="button" class="primary" data-act="management-sims-apply">Aplicar seleção</button></div></div><div class="management-sim-checks">'+
 options.map(x=>'<label><input type="checkbox" data-management-sim-token="'+esc(x.token)+'"'+(selected.has(x.token)?' checked':'')+'><span><strong>'+esc(x.activity)+'</strong><small>'+esc(x.date)+'</small></span></label>').join('')+
 '</div></div>';
}
function managementStudentRowsHtml(data){
 const rows=managementSafeArray(data?.students);
 if(!rows.length)return '<div class="notice">Nenhum aluno encontrado neste simulado.</div>';
 return '<div class="table-wrap management-nested-table"><table><thead><tr><th>Ranking</th><th>Aluno</th><th>Nota ENEM</th><th>+10%</th><th>Acertos</th><th>LC</th><th>CH</th><th>CN</th><th>MT</th><th>C1</th><th>C2</th><th>C3</th><th>C4</th><th>C5</th><th>Redação</th></tr></thead><tbody>'+
 rows.map(x=>'<tr><td><strong>'+managementInt(x.ranking)+'</strong></td><td><strong>'+esc(x.name)+'</strong><br><small>'+esc(x.username||'')+'</small></td>'+mgmtAnalyticsCells(x)+'</tr>').join('')+
 '</tbody></table></div>';
}
function managementClassDetailHtml(turma){
 const key=turma+'@@'+[...managementClassSelectedSims].sort().join('|')+'@@'+(managementDashboardFilters?.year||'');
 const data=managementClassDetailCache.get(key);
 if(!data)return '<div class="management-analytics-loading">Carregando simulados da turma…</div>';
 const rows=managementSafeArray(data.simulations);
 if(!rows.length)return '<div class="notice">Nenhum simulado encontrado para esta turma com a seleção atual.</div>';
 return '<div class="table-wrap management-nested-table"><table><thead>'+mgmtAnalyticsHead('Simulado')+'</thead><tbody>'+
 rows.map(x=>{
  const simKey=turma+'@@'+x.activityKey+'@@'+x.date;
  const open=managementSimulationOpen===simKey;
  const detail=managementStudentDetailCache.get(simKey);
  return '<tr class="management-drill-row'+(open?' open':'')+'" data-act="management-simulation-drill" data-turma="'+encodeURIComponent(turma)+'" data-activity-key="'+encodeURIComponent(x.activityKey)+'" data-date="'+esc(x.date)+'"><td><strong>'+esc(x.activity)+'</strong><br><small>'+esc(x.date)+'</small></td><td>'+managementInt(x.participants)+'</td><td>1</td>'+mgmtAnalyticsCells(x)+'</tr>'+
   (open?'<tr class="management-drill-detail"><td colspan="16">'+(detail?managementStudentRowsHtml(detail):'<div class="management-analytics-loading">Carregando alunos e ranking…</div>')+'</td></tr>':'');
 }).join('')+
 '</tbody></table></div>';
}
function managementClassAnalyticsTableHtml(data){
 const rows=managementSafeArray(data?.classes);
 if(!rows.length)return '<div class="notice">Nenhuma turma com resultados para os simulados selecionados.</div>';
 return '<div class="table-wrap management-analytics-main"><table><thead>'+mgmtAnalyticsHead('Turma')+'</thead><tbody>'+
 rows.map(x=>{
  const open=managementClassOpen===x.turma;
  return '<tr class="management-drill-row'+(open?' open':'')+'" data-act="management-class-drill" data-turma="'+encodeURIComponent(x.turma)+'"><td><strong>'+esc(x.turma)+'</strong></td><td>'+managementInt(x.participants)+'</td><td>'+managementInt(x.simulations)+'</td>'+mgmtAnalyticsCells(x)+'</tr>'+
  (open?'<tr class="management-drill-detail"><td colspan="16">'+managementClassDetailHtml(x.turma)+'</td></tr>':'');
 }).join('')+
 '</tbody></table></div>';
}
function managementClassAnalyticsSection(){
 if(!managementClassAnalyticsCache&&!managementClassAnalyticsLoading)queueMicrotask(()=>loadManagementClassAnalytics());
 if(managementClassAnalyticsLoading||!managementClassAnalyticsCache)return '<section class="card"><h2>Médias por turma</h2><p>Carregando análise das turmas…</p></section>';
 if(managementClassAnalyticsCache.error)return '<section class="card"><h2>Médias por turma</h2><div class="notice warning">'+esc(managementClassAnalyticsCache.error)+'</div></section>';
 return '<section class="card management-class-analytics"><h2>Médias por turma</h2><p class="micro">Nota ENEM = média de LC, CH, CN, MT e Redação. O bônus corresponde a 10%. A nota de Redação exibida é C1+C2+C3+C4+C5 pelas médias de competência.</p>'+
 managementSimulationSelectorHtml(managementClassAnalyticsCache)+managementClassAnalyticsTableHtml(managementClassAnalyticsCache)+'</section>';
}
const managementDashboardViewV3712Base=managementDashboardView;
managementDashboardView=function(){
 const base=managementDashboardViewV3712Base();
 if(!managementDashboardAllowed())return base;
 return base+managementClassAnalyticsSection();
};

acts['management-sims-clear']=()=>{
 managementClassSelectedSims.clear();
 document.querySelectorAll('[data-management-sim-token]').forEach(x=>x.checked=false);
 managementClassAnalyticsCache=null;managementClassDetailCache.clear();managementStudentDetailCache.clear();
 managementClassOpen='';managementSimulationOpen='';
 loadManagementClassAnalytics(true);
};
acts['management-sims-apply']=()=>{
 managementClassSelectedSims=new Set([...document.querySelectorAll('[data-management-sim-token]:checked')].map(x=>x.dataset.managementSimToken));
 managementClassAnalyticsCache=null;managementClassDetailCache.clear();managementStudentDetailCache.clear();
 managementClassOpen='';managementSimulationOpen='';
 loadManagementClassAnalytics(true);
};
acts['management-class-drill']=async el=>{
 const turma=decodeURIComponent(el?.dataset?.turma||'');
 if(!turma)return;
 if(managementClassOpen===turma){managementClassOpen='';managementSimulationOpen='';render();return;}
 managementClassOpen=turma;managementSimulationOpen='';render();
 try{await loadManagementClassDetail(turma);}catch(e){toast(e?.message||'Não foi possível abrir os simulados.',true);}
 render();
};
acts['management-simulation-drill']=async el=>{
 const turma=decodeURIComponent(el?.dataset?.turma||'');
 const activityKey=decodeURIComponent(el?.dataset?.activityKey||'');
 const date=el?.dataset?.date||'';
 const key=turma+'@@'+activityKey+'@@'+date;
 if(managementSimulationOpen===key){managementSimulationOpen='';render();return;}
 managementSimulationOpen=key;render();
 try{
  const data=await loadManagementStudentDetail(turma,activityKey,date);
  managementStudentDetailCache.set(key,data);
 }catch(e){toast(e?.message||'Não foi possível abrir os alunos.',true);}
 render();
};

const managementLoadV3712Base=loadManagementDashboard;
loadManagementDashboard=async function(force=false){
 const result=await managementLoadV3712Base(force);
 if(force){
  managementClassAnalyticsCache=null;managementClassDetailCache.clear();managementStudentDetailCache.clear();
  if(view==='home')queueMicrotask(()=>loadManagementClassAnalytics(true));
 }
 return result;
};

// === CLASS ANALYTICS SORTING V3.7.13 ===
let managementAnalyticsSort={
 class:{key:'turma',dir:'asc'},
 simulation:{key:'date',dir:'desc'},
 student:{key:'ranking',dir:'asc'},
};

const managementAnalyticsColumns=[
 ['participants','Participantes'],
 ['simulations','Simulados'],
 ['enem','Nota ENEM'],
 ['bonus','+10%'],
 ['accuracy','Acertos'],
 ['lcAccuracy','LC'],
 ['chAccuracy','CH'],
 ['cnAccuracy','CN'],
 ['mtAccuracy','MT'],
 ['c1','C1'],['c2','C2'],['c3','C3'],['c4','C4'],['c5','C5'],
 ['redaction','Redação'],
];

function managementAnalyticsCompare(a,b,key,dir){
 const av=a?.[key],bv=b?.[key];
 const factor=dir==='desc'?-1:1;
 const aEmpty=av===null||av===undefined||av==='';
 const bEmpty=bv===null||bv===undefined||bv==='';
 if(aEmpty&&bEmpty)return 0;
 if(aEmpty)return 1;
 if(bEmpty)return -1;
 if(typeof av==='number'||typeof bv==='number'){
  const an=Number(av),bn=Number(bv);
  if(Number.isFinite(an)&&Number.isFinite(bn))return (an-bn)*factor;
 }
 return String(av).localeCompare(String(bv),'pt-BR',{sensitivity:'base',numeric:true})*factor;
}
function managementAnalyticsSorted(rows,scope){
 const sort=managementAnalyticsSort[scope]||{key:'',dir:'asc'};
 return [...managementSafeArray(rows)].sort((a,b)=>{
  const primary=managementAnalyticsCompare(a,b,sort.key,sort.dir);
  if(primary)return primary;
  const fallbackKey=scope==='class'?'turma':scope==='simulation'?'activity':'name';
  return managementAnalyticsCompare(a,b,fallbackKey,'asc');
 });
}
function managementSortTh(label,scope,key){
 const sort=managementAnalyticsSort[scope]||{};
 const active=sort.key===key;
 const arrow=active?(sort.dir==='asc'?'▲':'▼'):'↕';
 const title=active
  ?(sort.dir==='asc'?'Ordem crescente. Clique para decrescente.':'Ordem decrescente. Clique para crescente.')
  :'Clique para ordenar.';
 return '<th class="management-sort-th'+(active?' active':'')+'"><button type="button" data-act="management-analytics-sort" data-sort-scope="'+scope+'" data-sort-key="'+key+'" title="'+title+'"><span>'+label+'</span><span class="management-sort-arrow">'+arrow+'</span></button></th>';
}
function managementAnalyticsHead(first,scope='class'){
 const firstKey=scope==='class'?'turma':scope==='simulation'?'activity':'name';
 return '<tr>'+managementSortTh(first,scope,firstKey)+
  managementAnalyticsColumns.map(([key,label])=>managementSortTh(label,scope,key)).join('')+
 '</tr>';
}
function managementStudentRowsHtml(data){
 const rows=managementAnalyticsSorted(data?.students,'student');
 if(!rows.length)return '<div class="notice">Nenhum aluno encontrado neste simulado.</div>';
 return '<div class="table-wrap management-nested-table"><table><thead><tr>'+
  managementSortTh('Ranking','student','ranking')+
  managementSortTh('Aluno','student','name')+
  managementAnalyticsColumns.filter(([key])=>key!=='participants'&&key!=='simulations').map(([key,label])=>managementSortTh(label,'student',key)).join('')+
  '</tr></thead><tbody>'+
  rows.map(x=>'<tr><td><strong>'+managementInt(x.ranking)+'</strong></td><td><strong>'+esc(x.name)+'</strong><br><small>'+esc(x.username||'')+'</small></td>'+mgmtAnalyticsCells(x)+'</tr>').join('')+
 '</tbody></table></div>';
}
function managementClassDetailHtml(turma){
 const key=turma+'@@'+[...managementClassSelectedSims].sort().join('|')+'@@'+(managementDashboardFilters?.year||'');
 const data=managementClassDetailCache.get(key);
 if(!data)return '<div class="management-analytics-loading">Carregando simulados da turma…</div>';
 const rows=managementAnalyticsSorted(data.simulations,'simulation');
 if(!rows.length)return '<div class="notice">Nenhum simulado encontrado para esta turma com a seleção atual.</div>';
 return '<div class="table-wrap management-nested-table"><table><thead>'+managementAnalyticsHead('Simulado','simulation')+'</thead><tbody>'+
 rows.map(x=>{
  const simKey=turma+'@@'+x.activityKey+'@@'+x.date;
  const open=managementSimulationOpen===simKey;
  const detail=managementStudentDetailCache.get(simKey);
  return '<tr class="management-drill-row'+(open?' open':'')+'" data-act="management-simulation-drill" data-turma="'+encodeURIComponent(turma)+'" data-activity-key="'+encodeURIComponent(x.activityKey)+'" data-date="'+esc(x.date)+'"><td><strong>'+esc(x.activity)+'</strong><br><small>'+esc(x.date)+'</small></td><td>'+managementInt(x.participants)+'</td><td>1</td>'+mgmtAnalyticsCells(x)+'</tr>'+
   (open?'<tr class="management-drill-detail"><td colspan="16">'+(detail?managementStudentRowsHtml(detail):'<div class="management-analytics-loading">Carregando alunos e ranking…</div>')+'</td></tr>':'');
 }).join('')+
 '</tbody></table></div>';
}
function managementClassAnalyticsTableHtml(data){
 const rows=managementAnalyticsSorted(data?.classes,'class');
 if(!rows.length)return '<div class="notice">Nenhuma turma com resultados para os simulados selecionados.</div>';
 return '<div class="table-wrap management-analytics-main"><table><thead>'+managementAnalyticsHead('Turma','class')+'</thead><tbody>'+
 rows.map(x=>{
  const open=managementClassOpen===x.turma;
  return '<tr class="management-drill-row'+(open?' open':'')+'" data-act="management-class-drill" data-turma="'+encodeURIComponent(x.turma)+'"><td><strong>'+esc(x.turma)+'</strong></td><td>'+managementInt(x.participants)+'</td><td>'+managementInt(x.simulations)+'</td>'+mgmtAnalyticsCells(x)+'</tr>'+
  (open?'<tr class="management-drill-detail"><td colspan="16">'+managementClassDetailHtml(x.turma)+'</td></tr>':'');
 }).join('')+
 '</tbody></table></div>';
}
acts['management-analytics-sort']=el=>{
 const scope=el?.dataset?.sortScope||'';
 const key=el?.dataset?.sortKey||'';
 if(!managementAnalyticsSort[scope]||!key)return;
 const current=managementAnalyticsSort[scope];
 if(current.key===key)current.dir=current.dir==='asc'?'desc':'asc';
 else{
  current.key=key;
  current.dir=['turma','activity','name'].includes(key)?'asc':'desc';
 }
 render();
};
