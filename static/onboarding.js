"use strict";
// === PRIMEIRO ACESSO GUIADO V3.14.0 ===
// Para o aluno no próprio usuário, enquanto não informou nenhum horário livre e não concluiu este passo a passo.
const OB_DAYS=[[6,'Dom'],[0,'Seg'],[1,'Ter'],[2,'Qua'],[3,'Qui'],[4,'Sex'],[5,'Sáb']];
const OB_PERIODS=[['m','Manhã','08:00','12:00',240],['t','Tarde','14:00','18:00',240],['n','Noite','19:00','22:30',210]];
const OB_GOALS=['Medicina','Engenharias','Direito','Saúde (outros cursos)','Exatas e tecnologia','Humanas','Ainda estou decidindo'];
const OB_ENERGY=[['manha','Manhã','Rendo melhor cedo'],['tarde','Tarde','Depois do almoço'],['noite','Noite','Quando a casa acalma'],['qualquer','Tanto faz','Me adapto']];
const OB_DISC=['Matemática','Física','Química','Biologia','Português','Literatura','Redação','História','Geografia','Filosofia','Sociologia','Inglês','Espanhol'];
const ob={open:false,step:0,goal:'',goalOther:'',energy:'',slots:new Set(),hard:new Set(),busy:false,error:''};
function obKey(v){return String(v||'').normalize('NFKD').replace(/[̀-ͯ]/g,'').toLowerCase().trim();}
function obEligible(){
 try{
  if(typeof ME==='undefined'||!ME||ME._studentView||ME.must_change)return false;
  if(!['aluno','user','especial'].includes(ME.role))return false;
  if(typeof P==='undefined'||!P||!P.settings||!Array.isArray(P.availability))return false;
  if(P.settings.onboardedAt)return false;
  if(P.availability.some(a=>a.status!=='unknown'))return false;
  return sessionStorage.getItem('qi:onboarding:later:'+ME.id)!=='1';
 }catch(_){return false;}
}
function obMinutes(){let t=0;ob.slots.forEach(k=>{const p=OB_PERIODS.find(x=>x[0]===k.split(':')[1]);if(p)t+=p[4];});return t;}
function obHours(min){const h=Math.floor(min/60),m=min%60;return h+'h'+(m?String(m).padStart(2,'0'):'');}
function obName(){return String((typeof P!=='undefined'&&P&&P.name)||ME.name||'').split(' ')[0];}
function obStepWelcome(){
 return `<div class="ob-hero"><div class="ob-badge">Primeiro acesso</div><h1>Oi, ${esc(obName())}!</h1><p>Em uns 2 minutos o seu cronograma fica pronto. É só tocar nas opções.</p></div>
 <div class="ob-perks"><div class="ob-perk"><span class="ob-ico">🗓️</span><strong>Semana montada</strong><small>Os estudos encaixados nos horários que você tem.</small></div>
 <div class="ob-perk"><span class="ob-ico">🔁</span><strong>Revisões na hora certa</strong><small>O que você estudou volta antes de ser esquecido.</small></div>
 <div class="ob-perk"><span class="ob-ico">🎯</span><strong>Foco nos seus erros</strong><small>Os simulados mostram onde vale a pena insistir.</small></div></div>`;
}
function obStepGoal(){
 return `<h2>Qual é o seu objetivo?</h2><p class="ob-sub">Ajuda a dar sentido à rotina. Dá para mudar depois.</p>
 <div class="ob-chips">${OB_GOALS.map(g=>`<button type="button" class="ob-chip ${ob.goal===g?'on':''}" data-act="ob-goal" data-v="${esc(g)}">${esc(g)}</button>`).join('')}</div>
 <label class="ob-other">Ou escreva o curso<input type="text" maxlength="80" data-ob="goalOther" value="${esc(ob.goalOther)}" placeholder="Ex.: Arquitetura na UFPE"></label>
 <h2 class="ob-mt">Quando você rende mais?</h2>
 <div class="ob-cards">${OB_ENERGY.map(([k,l,s])=>`<button type="button" class="ob-card ${ob.energy===k?'on':''}" data-act="ob-energy" data-v="${k}"><strong>${l}</strong><small>${s}</small></button>`).join('')}</div>`;
}
function obStepTime(){
 const total=obMinutes();
 return `<h2>Quando você tem tempo livre para estudar?</h2><p class="ob-sub">Toque nos períodos livres da sua semana, fora da escola e de outros compromissos.</p>
 <div class="ob-grid" role="grid"><div></div>${OB_DAYS.map(([,l])=>`<div class="ob-day">${l}</div>`).join('')}
 ${OB_PERIODS.map(([k,l,a,b])=>`<div class="ob-period">${l}<small>${a}–${b}</small></div>${OB_DAYS.map(([d,dl])=>{const id=d+':'+k,on=ob.slots.has(id);return `<button type="button" class="ob-slot ${on?'on':''}" data-act="ob-slot" data-v="${id}" aria-pressed="${on}" aria-label="${dl} ${l}">${on?'✓':''}</button>`;}).join('')}`).join('')}</div>
 <div class="ob-quick"><button type="button" class="ob-link" data-act="ob-preset" data-v="noites">Noites de segunda a sexta</button><button type="button" class="ob-link" data-act="ob-preset" data-v="tardes">Tardes de segunda a sexta</button><button type="button" class="ob-link" data-act="ob-preset" data-v="limpar">Limpar</button></div>
 <div class="ob-total ${total?'on':''}">${total?`<strong>${obHours(total)}</strong> livres por semana`:'Nenhum período marcado ainda'}</div>`;
}
function obStepHard(){
 const own=(P.subjects||[]).filter(s=>s.kind==='study').map(s=>s.name);
 const list=[...new Set([...OB_DISC,...own])];
 return `<h2>Em quais disciplinas você sente mais dificuldade?</h2><p class="ob-sub">Escolha até 5. Elas ganham mais espaço na semana. Os simulados importados pela escola vão ajustando isso com o tempo.</p>
 <div class="ob-chips">${list.map(n=>`<button type="button" class="ob-chip ${ob.hard.has(n)?'on':''}" data-act="ob-hard" data-v="${esc(n)}">${esc(n)}</button>`).join('')}</div>
 <p class="ob-count">${ob.hard.size} de 5</p>`;
}
function obStepDone(){
 const total=obMinutes();
 return `<div class="ob-hero ob-done"><div class="ob-burst" aria-hidden="true">${Array.from({length:14},(_,i)=>`<i data-i="${i}"></i>`).join('')}</div><h1>Tudo pronto!</h1>
 <p>${total?`${obHours(total)} livres por semana`:'Horários a definir'}${ob.hard.size?' · foco em '+esc([...ob.hard].join(', ')):''}.</p></div>
 <ul class="ob-next"><li><strong>Quadro semanal:</strong> sua semana já montada. Marque o que fizer.</li><li><strong>Revisões:</strong> o que precisa voltar e quando.</li><li><strong>Mapeamento objetivo:</strong> quando puder, responda em 5 minutos para afinar o plano.</li></ul>`;
}
const OB_STEPS=[obStepWelcome,obStepGoal,obStepTime,obStepHard,obStepDone];
function obCanNext(){if(ob.step===2)return ob.slots.size>0;return true;}
function obRender(){
 let box=document.getElementById('ob-overlay');
 if(!ob.open){if(box)box.remove();document.body.classList.remove('ob-lock');return;}
 if(!box){box=document.createElement('div');box.id='ob-overlay';box.setAttribute('role','dialog');box.setAttribute('aria-modal','true');box.setAttribute('aria-label','Primeiro acesso');document.body.appendChild(box);document.body.classList.add('ob-lock');}
 const last=OB_STEPS.length-1,s=ob.step;
 const nextLabel=s===0?'Vamos lá':s===3?'Montar meu cronograma':s===last?'Ver minha semana':'Continuar';
 box.innerHTML=`<div class="ob-panel">
  <div class="ob-progress" aria-hidden="true"><span data-w="${Math.round(100*s/last)}"></span></div>
  <div class="ob-body" data-step="${s}">${OB_STEPS[s]()}</div>
  ${ob.error?`<p class="ob-error" role="alert">${esc(ob.error)}</p>`:''}
  <div class="ob-actions">${s>0&&s<last?'<button type="button" class="ob-back" data-act="ob-back">Voltar</button>':s===0?'<button type="button" class="ob-back" data-act="ob-later">Fazer depois</button>':'<span></span>'}
  ${s===3?'<button type="button" class="ob-back" data-act="ob-skip-hard">Pular</button>':''}
  <button type="button" class="ob-next" data-act="ob-next" ${obCanNext()&&!ob.busy?'':'disabled'}>${ob.busy?'Salvando…':nextLabel}</button></div></div>`;
 box.querySelectorAll('[data-w]').forEach(e=>{e.style.width=e.dataset.w+'%';});
 box.querySelectorAll('.ob-burst i').forEach(e=>{e.style.setProperty('--i',e.dataset.i);});
 const focus=box.querySelector('.ob-next');if(focus&&!ob.busy)focus.focus({preventScroll:true});
}
async function obCall(op,data){const r=await api('/api/action',{user:target,version:S.version,op,data});S=r;P=r.profile;return r;}
async function obFinish(){
 ob.busy=true;ob.error='';obRender();
 try{
  const goal=ob.goalOther.trim()||ob.goal;
  const availability=[0,1,2,3,4,5,6].map(d=>{const ranges=OB_PERIODS.filter(([k])=>ob.slots.has(d+':'+k)).map(([,,a,b])=>({start:a,end:b}));return {day:d,status:ranges.length?'available':'unavailable',ranges};});
  const settings={...P.settings,onboardedAt:new Date().toISOString().slice(0,10),onboardingGoal:goal.slice(0,80)};
  if(ob.energy)settings.preferred=ob.energy;
  const total=obMinutes();
  if(total&&settings.weeklyGoal>Math.round(total*0.8))settings.weeklyGoal=Math.max(60,Math.round(total*0.8/10)*10);
  await obCall('routine',{settings,availability});
  for(const name of ob.hard){
   const old=(P.subjects||[]).find(s=>obKey(s.name)===obKey(name));
   if(old)await obCall('subject',{id:old.id,difficulty:4,importance:Math.max(4,Number(old.importance)||3),active:true});
   else await obCall('subject',{name,kind:'study',action:'Estudar e praticar',weeklyMin:120,difficulty:4,importance:4,examDate:'',active:true});
  }
  if((P.subjects||[]).some(s=>s.active&&s.kind==='study')){
   try{await obCall('generate',{week:typeof weekOf==='function'?weekOf(S.serverDate):undefined});}catch(_){/* a semana pode ser gerada depois no Quadro semanal */}
  }
  ob.step=OB_STEPS.length-1;
 }catch(e){ob.error=(e&&e.message)||'Não foi possível salvar. Tente de novo.';}
 finally{ob.busy=false;obRender();}
}
acts['ob-goal']=el=>{ob.goal=ob.goal===el.dataset.v?'':el.dataset.v;obRender();};
acts['ob-energy']=el=>{ob.energy=el.dataset.v;obRender();};
acts['ob-slot']=el=>{const v=el.dataset.v;ob.slots.has(v)?ob.slots.delete(v):ob.slots.add(v);obRender();};
acts['ob-preset']=el=>{const v=el.dataset.v;if(v==='limpar')ob.slots.clear();else{const k=v==='noites'?'n':'t';[0,1,2,3,4].forEach(d=>ob.slots.add(d+':'+k));}obRender();};
acts['ob-hard']=el=>{const v=el.dataset.v;if(ob.hard.has(v))ob.hard.delete(v);else if(ob.hard.size<5)ob.hard.add(v);obRender();};
acts['ob-back']=()=>{ob.error='';ob.step=Math.max(0,ob.step-1);obRender();};
acts['ob-later']=()=>{try{sessionStorage.setItem('qi:onboarding:later:'+ME.id,'1');}catch(_){}ob.open=false;obRender();};
acts['ob-skip-hard']=async()=>{ob.hard.clear();await obFinish();};
acts['ob-next']=async()=>{
 if(ob.busy||!obCanNext())return;
 if(ob.step===3)return obFinish();
 if(ob.step===OB_STEPS.length-1){ob.open=false;obRender();view=(P.sessions||[]).length?'calendar':'home';render();return;}
 ob.error='';ob.step++;obRender();
};
document.addEventListener('input',e=>{if(e.target&&e.target.dataset&&e.target.dataset.ob==='goalOther'){ob.goalOther=e.target.value;if(ob.goalOther)ob.goal='';
 document.querySelectorAll('#ob-overlay .ob-chip[data-act="ob-goal"]').forEach(b=>b.classList.remove('on'));}});
document.addEventListener('keydown',e=>{if(ob.open&&e.key==='Escape'&&ob.step===0)acts['ob-later']();});
// O guia rápido de cada aba espera o primeiro acesso terminar, para não abrir duas janelas ao mesmo tempo.
window.qiOnboardingPending=()=>ob.open||obEligible();
(function obInstall(){
 if(typeof render!=='function'||typeof acts==='undefined')return;
 const baseRender=render;
 render=function(){const out=baseRender.apply(this,arguments);try{if(!ob.open&&obEligible()){ob.open=true;ob.step=0;obRender();}}catch(_){}return out;};
})();
