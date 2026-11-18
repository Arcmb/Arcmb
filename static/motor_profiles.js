"use strict";
// === PERFIS DE FOCO DO MOTOR V3.9.0 ===
// Aluno (e visão do aluno): card "Meu foco de estudos" na Visão geral, com troca manual.
// Master e coordenação: aba "Motor de estudos" com limites, parâmetros e distribuição atual.
const mpCache=new Map();
let mpConfig=null,mpDefaults=null,mpOverview=null,mpBusy=false;
const MP_PLAN=[['both','Teoria + exercícios'],['exercise_only','Só exercícios'],['theory_only','Só teoria']];

function mpManager(){return typeof manages==='function'&&manages();}
function mpTarget(){return (typeof target!=='undefined'&&target)||(typeof ME!=='undefined'&&ME?.id)||'';}
async function mpLoad(force=false){
 const id=mpTarget();if(!id||(!force&&mpCache.has(id)))return;
 mpCache.set(id,{loading:true});
 try{mpCache.set(id,await api('/api/motor/profile?user='+encodeURIComponent(id)));}
 catch(e){mpCache.set(id,{error:e.message||'Não foi possível carregar o foco.'});}
 if(view==='home')mpEnsureCard();
}
function mpCardHtml(){
 const d=mpCache.get(mpTarget());
 if(!d||d.loading)return '<section class="card mp-card" data-mp-card="loading"><h2>Meu foco de estudos</h2><p class="micro">Carregando…</p></section>';
 if(d.error)return `<section class="card mp-card" data-mp-card="error"><h2>Meu foco de estudos</h2><div class="notice warning">${esc(d.error)}</div></section>`;
 if(!d.available)return '';
 const cur=d.current?d.profiles[d.current]:null,sug=d.suggested?d.profiles[d.suggested]:null;
 const options=[`<option value="auto" ${d.mode==='auto'?'selected':''}>Automático${sug?' (sugestão: '+esc(sug.label)+')':''}</option>`].concat(d.order.map(k=>`<option value="${k}" ${d.mode==='manual'&&d.current===k?'selected':''}>${esc(d.profiles[k].label)} — ${esc(d.profiles[k].description)}</option>`)).join('');
 const suggestion=d.mode==='manual'&&d.suggested&&d.suggested!==d.current?`<div class="notice"><strong>Sugestão pelos seus simulados: ${esc(sug.label)}.</strong> ${esc(d.reason||'')} <button type="button" class="secondary" data-act="mp-use-suggestion">Usar sugestão</button></div>`:'';
 const head=cur?`<p class="mp-current"><strong>${esc(cur.label)}</strong> · ${esc(cur.description)} <span class="tag">${d.mode==='auto'?'escolhido pelo motor':'escolhido por você'}</span></p>${d.mode==='auto'&&d.reason?`<p class="micro">${esc(d.reason)}</p>`:''}`:`<p class="micro">${esc(d.reason||'O foco será definido depois do primeiro simulado completo.')}</p>`;
 const signals=d.signals&&mpManager()===false&&typeof ME!=='undefined'&&ME._studentView?`<p class="micro">Para a gestão: ${d.signals.sims} simulado(s) completo(s) · média ${d.signals.media??'—'} · acerto ${d.signals.accuracy!=null?Math.round(d.signals.accuracy*100)+'%':'—'} · recorrência ${Math.round((d.signals.recurrence||0)*100)}%.</p>`:'';
 return `<section class="card mp-card" data-mp-card="${esc(mpTarget()+'|'+d.mode+'|'+d.current)}"><h2>Meu foco de estudos</h2>${head}${d.provisional?'<p class="micro">Definido com um único simulado completo; pode mudar depois do próximo.</p>':''}${suggestion}<div class="mp-choose"><label>Trocar foco<select id="mp-choice">${options}</select></label><button type="button" class="primary" data-act="mp-save">Salvar foco</button></div><p class="micro">O foco define como as revisões entram na sua semana. Vale a partir da próxima vez que a semana for organizada.</p>${signals}</section>`;
}
function mpEnsureCard(){
 const main=document.getElementById('main');if(!main)return;
 const old=main.querySelector('.mp-card');
 if(view!=='home'||mpManager()){if(old)old.remove();return;}
 const id=mpTarget();if(!mpCache.has(id)){mpLoad();}
 const html=mpCardHtml();
 const tmp=document.createElement('div');tmp.innerHTML=html;const card=tmp.firstElementChild;
 if(!card){if(old)old.remove();return;}
 if(old&&old.dataset.mpCard===card.dataset.mpCard)return;
 if(old){old.replaceWith(card);return;}
 const anchor=main.querySelector('.page-head, header, h1');
 const host=anchor&&anchor.closest('#main > *')||null;
 if(host&&host.nextSibling)main.insertBefore(card,host.nextSibling);else main.prepend(card);
}
acts['mp-save']=async()=>{
 const value=document.getElementById('mp-choice')?.value||'auto';
 const body=value==='auto'?{user:mpTarget(),mode:'auto'}:{user:mpTarget(),mode:'manual',key:value};
 mpCache.set(mpTarget(),await api('/api/motor/profile',body));mpEnsureCard();toast('Foco salvo. Organize a semana para aplicar.');
};
acts['mp-use-suggestion']=async()=>{
 mpCache.set(mpTarget(),await api('/api/motor/profile',{user:mpTarget(),mode:'auto'}));mpEnsureCard();toast('Voltou ao foco automático.');
};

/* ---------- aba Motor de estudos (Master e coordenação) ---------- */
function mpNum(id,value,attrs){return `<input id="${id}" type="number" value="${esc(value)}" ${attrs}>`;}
function mpConfigView(){
 if(!mpConfig){if(!mpBusy){mpBusy=true;api('/api/motor/config').then(d=>{mpConfig=d.config;mpDefaults=d.defaults;}).catch(e=>{mpConfig={error:e.message};}).finally(()=>{mpBusy=false;if(view==='motor')render();});}
  return head('Motor de estudos','Carregando configuração…');}
 if(mpConfig.error)return head('Motor de estudos','')+`<div class="notice warning">${esc(mpConfig.error)}</div>`;
 const t=mpConfig.thresholds,p=mpConfig.profiles;
 const rows=['base','pratica','intensiva','precisao'].map(k=>`<tr><td><input id="mp-${k}-label" value="${esc(p[k].label)}" maxlength="40"><br><input id="mp-${k}-desc" value="${esc(p[k].description)}" maxlength="160" class="mp-desc"></td><td><select id="mp-${k}-plan">${MP_PLAN.map(([v,l])=>`<option value="${v}" ${p[k].reviewPlan===v?'selected':''}>${l}</option>`).join('')}</select></td><td>${mpNum('mp-'+k+'-theory',p[k].theoryMin,'min="5" max="120"')}</td><td>${mpNum('mp-'+k+'-exercise',p[k].exerciseMin,'min="5" max="180"')}</td><td><input id="mp-${k}-intervals" value="${esc(p[k].intervals.join(', '))}"></td><td>${mpNum('mp-'+k+'-share',Math.round(p[k].reviewShare*100),'min="20" max="90"')}</td></tr>`).join('');
 const ov=mpOverview?(mpOverview.error?`<div class="notice warning">${esc(mpOverview.error)}</div>`:`<div class="table-wrap"><table><thead><tr><th>Perfil</th><th>Indicado pelos dados</th><th>Atual dos alunos</th><th>Escolha manual</th><th>Provisórios (1 simulado)</th><th>Média TRI</th><th>Acerto</th><th>Erros recorrentes</th></tr></thead><tbody>${mpOverview.rows.map(r=>`<tr><td><strong>${esc(r.label)}</strong></td><td>${r.suggested}</td><td>${r.current}</td><td>${r.manual}</td><td>${r.provisional}</td><td>${r.media??'—'}</td><td>${r.accuracy!=null?r.accuracy+'%':'—'}</td><td>${r.recurrence!=null?r.recurrence+'%':'—'}</td></tr>`).join('')}</tbody></table></div><p class="micro">${mpOverview.students} alunos ativos · ${mpOverview.withoutData} sem simulado completo no período. "Atual dos alunos" conta quem já abriu o foco ou organizou a semana desde a ativação.</p>`):'<p class="micro">Clique em "Calcular distribuição" para ver quantos alunos caem em cada perfil com os limites salvos.</p>';
 return head('Motor de estudos','Defina como o motor escolhe e aplica o foco de cada aluno. O aluno vê apenas o nome e a descrição do perfil, nunca a faixa de nota.')+
 `<section class="card"><h2>Como o perfil é escolhido</h2><p>Média ENEM sem bônus, só simulados completos (quatro áreas). A ordem de decisão é: <strong>1)</strong> média ≥ alto desempenho e pouca recorrência → ${esc(p.precisao.label)}; <strong>2)</strong> recorrência ≥ limite → ${esc(p.intensiva.label)}; <strong>3)</strong> média abaixo da base ou acerto abaixo do mínimo → ${esc(p.base.label)}; <strong>4)</strong> demais → ${esc(p.pratica.label)}. A troca automática só acontece quando 2 atualizações seguidas de simulados indicam o mesmo perfil novo.</p>
 <div class="form-grid"><label>Limite da faixa de base (média abaixo de)${mpNum('mp-t-base',t.base,'min="300" max="900"')}</label><label>Alto desempenho (média a partir de)${mpNum('mp-t-high',t.high,'min="301" max="1000"')}</label><label>Recorrência de erros (%)${mpNum('mp-t-rec',Math.round(t.recurrence*100),'min="5" max="90"')}</label><label>Acerto mínimo fora da base (%)${mpNum('mp-t-acc',Math.round(t.accuracyBase*100),'min="20" max="90"')}</label><label>Simulados para sair do provisório${mpNum('mp-t-sims',t.minSims,'min="1" max="5"')}</label><label>Período considerado (dias)${mpNum('mp-t-days',t.windowDays,'min="90" max="730"')}</label></div></section>
 <section class="card"><h2>Perfis</h2><div class="table-wrap"><table class="mp-table"><thead><tr><th>Nome e frase para o aluno</th><th>Como revisar</th><th>Teoria (min)</th><th>Exercícios (min)</th><th>Intervalos (dias)</th><th>Fatia de revisões na semana (%)</th></tr></thead><tbody>${rows}</tbody></table></div>
 <div class="actions"><button type="button" class="primary" data-act="mp-config-save">Salvar configuração</button><button type="button" class="secondary" data-act="mp-config-defaults">Restaurar padrão</button></div><p class="micro">Ajustes manuais que o aluno fez em uma revisão específica são respeitados. Os intervalos do perfil passam a valer quando a semana do aluno é organizada.</p></section>
 <section class="card"><div class="actions" style="justify-content:space-between"><h2>Distribuição atual</h2><button type="button" class="secondary" data-act="mp-overview">Calcular distribuição</button></div>${ov}</section>`;
}
function mpReadConfig(){
 const v=id=>document.getElementById(id)?.value;
 const profiles={};
 for(const k of ['base','pratica','intensiva','precisao'])profiles[k]={label:v(`mp-${k}-label`),description:v(`mp-${k}-desc`),reviewPlan:v(`mp-${k}-plan`),theoryMin:Number(v(`mp-${k}-theory`)),exerciseMin:Number(v(`mp-${k}-exercise`)),intervals:v(`mp-${k}-intervals`),reviewShare:Number(v(`mp-${k}-share`))/100};
 return {thresholds:{base:Number(v('mp-t-base')),high:Number(v('mp-t-high')),recurrence:Number(v('mp-t-rec'))/100,accuracyBase:Number(v('mp-t-acc'))/100,minSims:Number(v('mp-t-sims')),windowDays:Number(v('mp-t-days'))},profiles};
}
acts['mp-config-save']=async()=>{const d=await api('/api/motor/config',{config:mpReadConfig()});mpConfig=d.config;mpOverview=null;mpCache.clear();render();toast('Configuração do motor salva.');};
acts['mp-config-defaults']=async()=>{if(!mpDefaults)return;const d=await api('/api/motor/config',{config:mpDefaults});mpConfig=d.config;mpOverview=null;mpCache.clear();render();toast('Configuração padrão restaurada.');};
acts['mp-overview']=async()=>{mpOverview={rows:[],students:0,withoutData:0};const box=document.querySelector('[data-act="mp-overview"]');if(box)box.textContent='Calculando…';try{mpOverview=await api('/api/motor/overview');}catch(e){mpOverview={error:e.message};}render();};

function mpNavFix(){
 const nav=document.getElementById('nav');if(!nav)return;
 const has=nav.querySelector('[data-view="motor"]');
 if(!mpManager()){if(has)has.remove();return;}
 if(!has){
  const ref=nav.querySelector('[data-view="accounts"]');
  const b=document.createElement('button');b.dataset.view='motor';b.innerHTML='<span class="nav-number"></span>Motor de estudos';
  if(ref)nav.insertBefore(b,ref);else nav.appendChild(b);
 }
 nav.querySelector('[data-view="motor"]').classList.toggle('active',view==='motor');
 nav.querySelectorAll('button .nav-number').forEach((n,i)=>{n.textContent=String(i+1).padStart(2,'0');});
}

(function mpInstall(){
 if(typeof render!=='function'||typeof acts==='undefined')return;
 const style=document.createElement('style');
 style.textContent='.mp-card .mp-current{margin:.25rem 0}.mp-choose{display:flex;gap:12px;align-items:flex-end;flex-wrap:wrap;margin-top:8px}.mp-choose label{flex:1 1 320px}.mp-table input,.mp-table select{width:100%;min-width:70px}.mp-table .mp-desc{margin-top:6px;font-size:.85em}';
 document.head.appendChild(style);
 if(typeof renderNav==='function'){const baseNav=renderNav;renderNav=function(){const out=baseNav.apply(this,arguments);try{mpNavFix();}catch(_){}return out;};}
 const baseRender=render;
 render=function(){
  if(view==='motor'&&!mpManager())view='home';
  const out=baseRender.apply(this,arguments);
  try{
   if(view==='motor'){const main=document.getElementById('main');if(main)main.innerHTML=mpConfigView();}
   mpNavFix();mpEnsureCard();
  }catch(_){}
  return out;
 };
 const start=()=>{const main=document.getElementById('main');if(main)new MutationObserver(()=>{try{mpEnsureCard();}catch(_){}}).observe(main,{childList:true});};
 if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',start,{once:true});else start();
})();
