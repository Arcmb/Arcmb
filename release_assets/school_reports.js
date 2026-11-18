"use strict";
// === RELATÓRIOS DA ESCOLA V3.10.0 ===
const srState={tab:'atencao',data:{},loading:{},sims:null,flag:'',turma:'',sim:'',exam:'',area:'',scope:'',worst:true};
const SR_TABS=[['atencao','Alunos que pedem atenção'],['questoes','Análise por questão'],['assuntos','Assuntos × turmas'],['redacao','Redação por competência'],['perfis','Perfis por turma']];
const SR_FLAGS={queda:'Queda de nota',falta:'Faltou ao último simulado',recorrencia:'Erros repetidos',horarios:'Sem horários livres',acesso:'Nunca entrou'};

function srManager(){return typeof manages==='function'&&manages();}
function srQuery(){
 const p=new URLSearchParams();
 if(srState.tab==='questoes'){if(srState.sim)p.set('sim',srState.sim);if(srState.exam)p.set('exam',srState.exam);}
 if(['assuntos','redacao'].includes(srState.tab)&&srState.scope)p.set('sims',srState.scope);
 if(srState.tab==='assuntos'&&srState.area)p.set('area',srState.area);
 return p.toString();
}
const SR_PATH={atencao:'attention',questoes:'questions',assuntos:'topics',redacao:'redaction',perfis:'profiles'};
async function srLoad(force=false){
 const key=srState.tab+'?'+srQuery();
 if(!srState.sims){try{srState.sims=(await api('/api/school-reports/simulations')).simulations;}catch(_){srState.sims=[];}}
 if(!force&&(srState.data[key]||srState.loading[key]))return;
 srState.loading[key]=true;
 try{srState.data[key]=await api('/api/school-reports/'+SR_PATH[srState.tab]+(srQuery()?'?'+srQuery():''));}
 catch(e){srState.data[key]={error:e.message||'Não foi possível carregar o relatório.'};}
 finally{delete srState.loading[key];if(view==='school-reports')render();}
}
function srHeat(v){if(v===null||v===undefined)return '<td class="sr-heat sr-na">—</td>';const c=v<40?'sr-h1':v<60?'sr-h2':v<75?'sr-h3':'sr-h4';return `<td class="sr-heat ${c}">${String(v).replace('.',',')}%</td>`;}
function srSimOptions(selected,allLabel){return (allLabel?`<option value="">${allLabel}</option>`:'')+(srState.sims||[]).map(s=>`<option value="${esc(s.token)}" ${s.token===selected?'selected':''}>${esc(s.activity)} · ${esc(s.date)} (${s.participants})</option>`).join('');}
function srTurmaSelect(turmas){return `<label>Turma<select data-sr="turma"><option value="">Todas</option>${turmas.map(t=>`<option ${t===srState.turma?'selected':''}>${esc(t)}</option>`).join('')}</select></label>`;}
function srCsvButton(){return `<button type="button" class="secondary" data-act="sr-csv">Baixar CSV</button>`;}
let srCsvRows=null;

function srAttention(d){
 const list=d.students.filter(s=>(!srState.flag||s.flags.some(f=>f.kind===srState.flag))&&(!srState.turma||s.turma===srState.turma));
 const turmas=[...new Set(d.students.map(s=>s.turma))].sort();
 srCsvRows=[['Aluno','Login','Turma','Última média TRI','Variação','Sinais'],...list.map(s=>[s.name,s.username,s.turma,s.lastTri??'',s.delta??'',s.flags.map(f=>f.text).join(' | ')])];
 const chips=Object.entries(SR_FLAGS).map(([k,l])=>`<button type="button" class="${srState.flag===k?'primary':'secondary'}" data-act="sr-flag" data-flag="${k}">${l} · ${d.counts[k]||0}</button>`).join('');
 return `<p class="micro">${d.students.length} de ${d.total} alunos com pelo menos um sinal${d.latest?' · último simulado considerado: '+esc(d.latest.activity)+' ('+esc(d.latest.date)+')':''}. Ordem: queda de nota, faltas, erros repetidos, sem horários, sem acesso.</p>
 <div class="actions sr-chips">${chips}${srState.flag?'<button type="button" class="secondary" data-act="sr-flag" data-flag="">Todos os sinais</button>':''}</div>
 <div class="actions">${srTurmaSelect(turmas)}${srCsvButton()}</div>
 <div class="table-wrap"><table><thead><tr><th>Aluno</th><th>Turma</th><th>Última média</th><th>Variação</th><th>Sinais</th><th></th></tr></thead><tbody>${list.slice(0,300).map(s=>`<tr><td><strong>${esc(s.name)}</strong><br><small>${esc(s.username)}</small></td><td>${esc(s.turma)}</td><td>${s.lastTri??'—'}</td><td>${s.delta==null?'—':(s.delta>0?'+':'')+s.delta}</td><td>${s.flags.map(f=>`<span class="tag sr-flag-${f.kind}">${esc(f.text)}</span>`).join(' ')}</td><td><button type="button" class="secondary" data-act="open-account" data-id="${esc(s.id)}">Ver como aluno</button></td></tr>`).join('')}</tbody></table></div>${list.length>300?'<p class="micro">Mostrando 300. Use os filtros ou o CSV para ver todos.</p>':''}`;
}
function srQuestions(d){
 if(!d.simulation)return '<div class="notice">Nenhum simulado importado nos últimos 12 meses.</div>';
 let qs=d.questions.filter(q=>!srState.area||String(q.area).toUpperCase()===srState.area);
 qs=[...qs].sort((a,b)=>(a.accuracy??999)-(b.accuracy??999));
 if(srState.worst)qs=qs.slice(0,20);
 const turmas=srState.turma?[srState.turma]:d.turmas;
 srCsvRows=[['Questão','Área','Disciplina','Assunto','Habilidade','Gabarito','Acerto geral (%)',...turmas.map(t=>t+' (%)'),'Erro mais marcado'],...qs.map(q=>[q.number,q.area,q.discipline,q.subject||q.topic,q.skill,q.answer,q.accuracy??'',...turmas.map(t=>q.turmas[t]??''),q.distractor?q.distractor.letter+' ('+q.distractor.share+'%)':''])];
 const hasLetters=d.questions.some(q=>q.distractor);
 return `<div class="actions sr-filters"><label>Simulado<select data-sr="sim">${srSimOptions(d.simulation.token)}</select></label><label>Cor da prova<select data-sr="exam">${d.colors.map(c=>`<option value="${esc(c.examId)}" ${c.examId===d.examId?'selected':''}>${esc(c.color)} (${c.participants})</option>`).join('')}</select></label><label>Área<select data-sr="area"><option value="">Todas</option>${['LC','CH','CN','MT'].map(a=>`<option ${a===srState.area?'selected':''}>${a}</option>`).join('')}</select></label>${srTurmaSelect(d.turmas)}<label class="check"><input type="checkbox" data-sr="worst" ${srState.worst?'checked':''}> Só as 20 com menor acerto</label>${srCsvButton()}</div>
 ${hasLetters?'':'<p class="micro">"Erro mais marcado" aparece para simulados importados a partir desta versão, que passa a guardar a alternativa escolhida.</p>'}
 <div class="table-wrap"><table class="sr-table"><thead><tr><th>Questão</th><th>Disciplina · assunto</th><th>Gab.</th><th>Geral</th>${turmas.map(t=>`<th>${esc(t)}</th>`).join('')}<th>Erro mais marcado</th></tr></thead><tbody>${qs.map(q=>`<tr><td><strong>${q.number}</strong><br><small>${esc(q.area)} ${esc(q.skill||'')}</small></td><td>${esc(q.discipline)}<br><small>${esc(q.subject||q.topic||'')}</small></td><td>${esc(q.answer||'—')}</td>${srHeat(q.accuracy)}${turmas.map(t=>srHeat(q.turmas[t])).join('')}<td>${q.distractor?`<strong>${q.distractor.letter}</strong> · ${String(q.distractor.share).replace('.',',')}% dos erros`:'—'}</td></tr>`).join('')}</tbody></table></div>`;
}
function srTopics(d){
 const turmas=srState.turma?[srState.turma]:d.turmas;
 srCsvRows=[['Área','Disciplina','Assunto','Respostas','Acerto geral (%)',...turmas.map(t=>t+' (%)')],...d.rows.map(r=>[r.area,r.discipline,r.subject,r.answers,r.accuracy??'',...turmas.map(t=>r.turmas[t]??'')])];
 return `<div class="actions sr-filters"><label>Simulados<select data-sr="scope">${srSimOptions(srState.scope,'Todos dos últimos 12 meses')}</select></label><label>Área<select data-sr="area"><option value="">Todas</option>${['LC','CH','CN','MT'].map(a=>`<option ${a===srState.area?'selected':''}>${a}</option>`).join('')}</select></label>${srTurmaSelect(d.turmas)}${srCsvButton()}</div>
 <p class="micro">Assuntos do menor para o maior acerto. Cores: vermelho abaixo de 40%, laranja de 40% a 59%, verde-claro de 60% a 74%, verde a partir de 75%.</p>
 <div class="table-wrap"><table class="sr-table"><thead><tr><th>Disciplina · assunto</th><th>Respostas</th><th>Geral</th>${turmas.map(t=>`<th>${esc(t)}</th>`).join('')}</tr></thead><tbody>${d.rows.slice(0,400).map(r=>`<tr><td>${esc(r.discipline)}<br><small>${esc(r.subject)}</small></td><td>${r.answers}</td>${srHeat(r.accuracy)}${turmas.map(t=>srHeat(r.turmas[t])).join('')}</tr>`).join('')}</tbody></table></div>`;
}
function srRedaction(d){
 srCsvRows=[['Turma','Redações','C1','C2','C3','C4','C5','Média total','Competência mais baixa'],...d.rows.map(r=>[r.turma,r.essays,...r.competencies,r.total,r.weakest])];
 return `<div class="actions sr-filters"><label>Simulados<select data-sr="scope">${srSimOptions(srState.scope,'Todos dos últimos 12 meses')}</select></label>${srCsvButton()}</div>
 <p class="micro">Médias de 0 a 200 por competência. A competência mais baixa de cada turma aparece destacada.</p>
 <div class="table-wrap"><table class="sr-table"><thead><tr><th>Turma</th><th>Redações</th><th>C1</th><th>C2</th><th>C3</th><th>C4</th><th>C5</th><th>Média</th></tr></thead><tbody>${d.rows.map(r=>`<tr${r.turma==='Todas as turmas'?' class="sr-total"':''}><td><strong>${esc(r.turma)}</strong></td><td>${r.essays}</td>${r.competencies.map((v,i)=>`<td class="${'C'+(i+1)===r.weakest?'sr-weak':''}">${String(v).replace('.',',')}</td>`).join('')}<td><strong>${String(r.total).replace('.',',')}</strong></td></tr>`).join('')}</tbody></table></div>`;
}
function srProfiles(d){
 srCsvRows=[['Turma',...d.order.map(k=>d.labels[k]),'Sem simulado completo','Total'],...d.rows.map(r=>[r.turma,...d.order.map(k=>r[k]),r.sem,r.students])];
 return `<div class="actions">${srCsvButton()}</div><p class="micro">Perfil indicado pelos dados de cada aluno com os limites atuais da aba Motor de estudos.</p>
 <div class="table-wrap"><table class="sr-table"><thead><tr><th>Turma</th>${d.order.map(k=>`<th>${esc(d.labels[k])}</th>`).join('')}<th>Sem simulado</th><th>Total</th><th>Distribuição</th></tr></thead><tbody>${d.rows.map(r=>`<tr><td><strong>${esc(r.turma)}</strong></td>${d.order.map(k=>`<td>${r[k]}</td>`).join('')}<td>${r.sem}</td><td>${r.students}</td><td><div class="sr-bar">${d.order.map((k,i)=>r[k]?`<span class="sr-p${i}" data-w="${(100*r[k]/Math.max(1,r.students)).toFixed(1)}" title="${esc(d.labels[k])}: ${r[k]}"></span>`:'').join('')}</div></td></tr>`).join('')}</tbody></table></div>
 <p class="micro">${d.order.map((k,i)=>`<span class="sr-key sr-p${i}"></span> ${esc(d.labels[k])}`).join(' &nbsp; ')}</p>`;
}
function srView(){
 srLoad();
 const key=srState.tab+'?'+srQuery(),d=srState.data[key];
 const tabs=`<div class="sr-tabs" role="tablist">${SR_TABS.map(([k,l])=>`<button type="button" role="tab" class="${srState.tab===k?'active':''}" data-act="sr-tab" data-tab="${k}">${l}</button>`).join('')}</div>`;
 let body='<section class="card"><p>Carregando relatório…</p></section>';
 if(d&&d.error)body=`<div class="notice warning">${esc(d.error)}</div>`;
 else if(d)body='<section class="card">'+({atencao:srAttention,questoes:srQuestions,assuntos:srTopics,redacao:srRedaction,perfis:srProfiles}[srState.tab])(d)+'</section>';
 return head('Relatórios da escola','Relatórios para coordenação e professores, com os simulados dos últimos 12 meses.')+tabs+body;
}
acts['sr-tab']=el=>{srState.tab=el.dataset.tab;srState.turma='';srState.area='';render();};
acts['sr-flag']=el=>{srState.flag=el.dataset.flag||'';render();};
acts['sr-csv']=()=>{if(!srCsvRows||srCsvRows.length<2)throw new Error('Não há linhas para exportar.');csv('Relatorio_'+srState.tab+'.csv',srCsvRows);};
document.addEventListener('change',e=>{
 const el=e.target;if(!el.dataset||!el.dataset.sr||view!=='school-reports')return;
 const k=el.dataset.sr;
 if(k==='worst')srState.worst=el.checked;else srState[k]=el.value;
 if(k==='sim')srState.exam='';
 render();
});

function srNavFix(){
 const nav=document.getElementById('nav');if(!nav)return;
 let b=nav.querySelector('[data-view="school-reports"]');
 if(!srManager()){if(b)b.remove();return;}
 if(!b){const ref=nav.querySelector('[data-view="motor"]')||nav.querySelector('[data-view="accounts"]');b=document.createElement('button');b.dataset.view='school-reports';b.innerHTML='<span class="nav-number"></span>Relatórios da escola';if(ref)nav.insertBefore(b,ref);else nav.appendChild(b);}
 b.classList.toggle('active',view==='school-reports');
 nav.querySelectorAll('button .nav-number').forEach((n,i)=>{n.textContent=String(i+1).padStart(2,'0');});
}
(function srInstall(){
 if(typeof render!=='function'||typeof acts==='undefined')return;
 const style=document.createElement('style');
 style.textContent='.sr-tabs{display:flex;gap:4px;flex-wrap:wrap;border-bottom:1px solid var(--line,#ecd2d7);margin:0 0 16px}.sr-tabs button{border:0;background:transparent;color:var(--muted,#7b5c62);padding:8px 14px;border-bottom:3px solid transparent;font:inherit;font-weight:600;cursor:pointer;border-radius:0}.sr-tabs button.active{color:var(--ink,#3b2026);border-bottom-color:var(--primary,#b65362)}'
 +'.sr-filters{align-items:flex-end;flex-wrap:wrap}.sr-filters label{min-width:180px}.sr-chips{flex-wrap:wrap}'
 +'.sr-table td,.sr-table th{white-space:nowrap}.sr-heat{text-align:center;font-variant-numeric:tabular-nums;font-weight:600}#main table td.sr-h1{background:#f8d2d7!important;color:#8a1f33!important}#main table td.sr-h2{background:#fde5c4!important;color:#7a4a05!important}#main table td.sr-h3{background:#e2f1e2!important;color:#2c5e2e!important}#main table td.sr-h4{background:#c9e8cf!important;color:#1d4d26!important}#main table td.sr-na{color:#999!important}'
 +'#main table td.sr-weak{background:#f8d2d7!important;color:#8a1f33!important;font-weight:700}#main table tr.sr-total td{background:#fbf2f4!important;font-weight:600}'
 +'.sr-bar{display:flex;height:12px;width:220px;border-radius:6px;overflow:hidden;background:#eee}.sr-bar span{display:block;height:100%}.sr-key{display:inline-block;width:12px;height:12px;border-radius:3px;vertical-align:middle}'
 +'.sr-p0{background:#c25c69}.sr-p1{background:#4f6fb0}.sr-p2{background:#d39a2c}.sr-p3{background:#2f7d5b}'
 +'.sr-flag-queda{background:#f8d2d7;color:#8a1f33}.sr-flag-falta{background:#fde5c4;color:#7a4a05}.sr-flag-recorrencia{background:#e6defa;color:#4b2f8a}';
 document.head.appendChild(style);
 if(typeof renderNav==='function'){const baseNav=renderNav;renderNav=function(){const out=baseNav.apply(this,arguments);try{srNavFix();}catch(_){}return out;};}
 const baseRender=render;
 render=function(){
  if(view==='school-reports'&&!srManager())view='home';
  const out=baseRender.apply(this,arguments);
  try{if(view==='school-reports'){const main=document.getElementById('main');if(main){main.innerHTML=srView();main.querySelectorAll('[data-w]').forEach(e=>{e.style.width=e.dataset.w+'%';});}}srNavFix();}catch(_){}
  return out;
 };
})();
