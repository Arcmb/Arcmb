'use strict';
// Explicit start/end/activity fields. One save for the whole routine form.
function routineEntryRow(){
 return `<tr data-routine-entry><td><input type="time" data-entry-start aria-label="Horário de início"></td><td><input type="time" data-entry-end aria-label="Horário de término"></td><td><input type="text" data-entry-title aria-label="Atividade" maxlength="250" placeholder="Ex.: trabalho, aula, almoço, cuidar da família"></td><td><button type="button" class="danger-button" data-act="routine-remove-entry" aria-label="Remover esta linha">Remover</button></td></tr>`;
}
function routineFreeRow(day, range={start:'',end:''}){
 return `<div class="routine-free-range" data-free-range>${input('Horário de início','freeStart'+day,range.start,'time')}${input('Horário de término','freeEnd'+day,range.end,'time')}<button type="button" class="secondary" data-act="routine-remove-range" aria-label="Remover faixa livre de ${esc(days[day])}">Remover</button></div>`;
}
function routineFreeDay(item,i){
 return `<section class="routine-free-day" data-free-day="${i}"><div class="routine-day-title"><h3>${esc(days[i])}</h3>${select('Disponibilidade','freeStatus'+i,item.status,[['unknown','Não informado'],['available','Disponível para estudar'],['unavailable','Sem horário disponível']])}</div><div data-free-editor ${item.status==='available'?'':'hidden'}><div data-free-ranges>${(item.ranges.length?item.ranges:[{start:'',end:''}]).map(r=>routineFreeRow(i,r)).join('')}</div><button type="button" class="secondary" data-act="routine-add-range">Adicionar outro horário livre</button></div></section>`;
}
function routineSavedTable(){
 if(!P.fixed.length)return '<p class="muted">Nenhuma atividade da rotina cadastrada. Preencha as linhas abaixo e salve.</p>';
 return `<div class="table-wrap"><table class="routine-saved-table"><thead><tr><th>Horário de início</th><th>Horário de término</th><th>Atividade</th><th>Dias e repetição</th><th>Ações</th></tr></thead><tbody>${[...P.fixed].sort((a,b)=>a.start.localeCompare(b.start)||a.title.localeCompare(b.title)).map(x=>`<tr><td>${esc(x.start)}</td><td>${esc(x.end)}${x.end<x.start?' <small>(dia seguinte)</small>':''}</td><td><strong>${esc(x.title)}</strong>${x.before||x.after?`<small class="routine-subline">Deslocamentos: ${x.before} min antes / ${x.after} min depois</small>`:''}</td><td>${x.recurrence==='once'?br(x.anchor):x.days.map(d=>days[d]).join(', ')}<small class="routine-subline">${{weekly:'Toda semana',biweekly:'A cada 15 dias',once:'Somente nesta data'}[x.recurrence]}${x.recurrence!=='once'?' · a partir de '+br(x.anchor):''}${x.until?' · até '+br(x.until):''}</small></td><td><div class="actions">${button('Editar','edit-fixed','secondary',`data-id="${x.id}"`)}${button('Excluir','delete','danger-button',`data-collection="fixed" data-id="${x.id}"`)}</div></td></tr>`).join('')}</tbody></table></div>`;
}
routineView=function(){
 const s=P.settings;
 return head('Rotina e horários','Informe o que já ocupa o seu dia e os horários em que está disponível para estudar.')+
 `<section class="card"><div class="page-head"><h2>Atividades já cadastradas</h2>${button('Compromisso detalhado','new-fixed','secondary')}</div>${routineSavedTable()}<p class="micro">Use Compromisso detalhado para deslocamentos, fim de repetição ou atividades que atravessam a meia-noite. Editar ou excluir muda somente a atividade escolhida.</p></section>`+
 `<form id="routine-table-form"><section class="card"><h2>Preencher atividades da rotina</h2><p>Uma linha para cada atividade que já acontece no seu dia. <strong>Horário de início | Horário de término | Atividade.</strong></p><p class="micro">Exemplo de preenchimento: 08:00 | 12:00 | Trabalho. Os exemplos não são salvos automaticamente.</p><div class="form-grid">${select('Repetição das novas atividades','routineRecurrence','weekly',[['weekly','Toda semana'],['biweekly','A cada 15 dias'],['once','Somente na data indicada']])}${input('A partir desta data / data da atividade','routineAnchor',S.serverDate,'date','required')}</div><fieldset class="routine-days" id="routine-days"><legend>Em quais dias as novas atividades acontecem?</legend><div class="check-list">${days.map((d,i)=>check(esc(d),'routineDay'+i,false)).join('')}</div><button type="button" class="secondary" data-act="routine-weekdays">Marcar segunda a sexta</button></fieldset><div class="table-wrap"><table class="routine-entry-table"><thead><tr><th>Horário de início</th><th>Horário de término</th><th>Atividade</th><th></th></tr></thead><tbody id="routine-entry-rows">${routineEntryRow()}</tbody></table></div><div class="actions"><button type="button" class="secondary" data-act="routine-add-entry">Adicionar linha de atividade</button></div><p class="micro">Os dias e a repetição acima valem para todas as novas linhas deste envio. Para outra combinação de dias, salve e acrescente um novo grupo. Os horários cadastrados aqui são ocupados, não sugestões de estudo.</p></section>`+
 `<section class="card"><h2>Horários disponíveis para estudar</h2><p>Indique início e término dos períodos livres em cada dia. Você pode acrescentar mais de um período. Não informado <strong>não</strong> significa livre.</p>${P.availability.map(routineFreeDay).join('')}</section>`+
 `<section class="card"><h2>Limites do planejamento</h2><div class="form-grid">${input('Horário de dormir','sleepStart',s.sleepStart,'time','required')}${input('Horário de acordar','sleepEnd',s.sleepEnd,'time','required')}${input('Período mínimo de estudo (min)','sessionMin',s.sessionMin,'number','min="10" max="120" required')}${input('Período máximo de estudo (min)','sessionMax',s.sessionMax,'number','min="10" max="180" required')}${input('Pausa entre períodos de estudo (min)','breakMin',s.breakMin,'number','min="0" max="60" required')}${input('Limite diário de estudo (min)','dailyMax',s.dailyMax,'number','min="10" max="720" required')}${input('Limite semanal de estudo (min)','weeklyGoal',s.weeklyGoal,'number','min="10" max="5040" required')}${input('Reserva para imprevistos (%)','reservePct',s.reservePct,'number','min="0" max="80" required')}${input('Duração padrão da revisão (min)','reviewMin',s.reviewMin,'number','min="10" max="180" required')}${input('Intervalos de revisão (dias)','intervals',s.intervals.join(', '),'text','required')}${select('Preferência de horário','preferred',s.preferred,[['manha','Manhã'],['tarde','Tarde'],['noite','Noite'],['qualquer','Sem preferência']])}${check('Permitir primeira revisão no mesmo dia','sameDay',s.sameDay)}</div><p class="micro">Intervalos de revisão são configuráveis. A retomada no mesmo dia respeita pelo menos duas horas desde o início do estudo e ocorre depois do seu término.</p></section>`+
 `<section class="card"><div class="notice">O sistema desconta atividades ocupadas, sono, pausas e reserva ao gerar novas propostas. Salvar esta rotina não move automaticamente estudos já agendados; depois, confira a prévia no Quadro semanal.</div><button type="submit" class="primary">Salvar rotina, horários e atividades</button><p id="routine-table-error" class="form-error" role="alert"></p></section></form>`+
 `<section class="card"><div class="page-head"><h2>Bloqueios em datas específicas</h2>${button('Adicionar bloqueio','new-exception')}</div>${items(P.exceptions.map(x=>`<div class="item"><div><strong>${esc(x.title)}</strong><p>${br(x.date)} · ${esc(x.start)}–${esc(x.end)}</p></div>${button('Excluir','delete','danger-button',`data-collection="exceptions" data-id="${x.id}"`)}</div>`))}</section>`;
};
acts['routine-add-entry']=()=>{
 const rows=$('#routine-entry-rows');if(rows.children.length>=50)throw new Error('Cadastre até 50 atividades por envio.');
 rows.insertAdjacentHTML('beforeend',routineEntryRow());rows.lastElementChild.querySelector('input').focus();
};
acts['routine-remove-entry']=el=>{const row=el.closest('[data-routine-entry]');if([...row.querySelectorAll('input')].some(i=>i.value))dirty=true;row.remove();if(!$('#routine-entry-rows').children.length)$('#routine-entry-rows').insertAdjacentHTML('beforeend',routineEntryRow());};
acts['routine-weekdays']=()=>{days.forEach((_,i)=>document.querySelector('[name=routineDay'+i+']').checked=i<5);dirty=true;status('Alterações pendentes · clique em Salvar',true);};
acts['routine-add-range']=el=>{const day=el.closest('[data-free-day]'),list=day.querySelector('[data-free-ranges]');if(list.children.length>=12)throw new Error('Limite de 12 faixas livres por dia.');list.insertAdjacentHTML('beforeend',routineFreeRow(Number(day.dataset.freeDay)));list.lastElementChild.querySelector('input').focus();};
acts['routine-remove-range']=el=>{const day=el.closest('[data-free-day]');el.closest('[data-free-range]').remove();if(!day.querySelector('[data-free-range]'))day.querySelector('[data-free-ranges]').innerHTML=routineFreeRow(Number(day.dataset.freeDay));dirty=true;status('Alterações pendentes · clique em Salvar',true);};
for(const action of ['new-fixed','edit-fixed','new-exception','delete']){
 const original=acts[action];acts[action]=async el=>{if(view==='routine'&&dirty&&!safeLeave())return;return original(el);};
}
document.addEventListener('change',event=>{
 const el=event.target;
 if(el.name?.startsWith('freeStatus')){const day=el.closest('[data-free-day]');if(day)day.querySelector('[data-free-editor]').hidden=el.value!=='available';}
 if(el.name==='routineRecurrence')$('#routine-days').hidden=el.value==='once';
});
document.addEventListener('submit',async event=>{
 const f=event.target;if(f.id!=='routine-table-form')return;event.preventDefault();if(saving||!f.reportValidity())return;
 const b=f.querySelector('button[type=submit]'),error=$('#routine-table-error');b.disabled=true;error.textContent='';
 try{
  const d=fd(f),settings={...P.settings,...Object.fromEntries(['sleepStart','sleepEnd','preferred'].map(k=>[k,d[k]])),sameDay:f.elements.sameDay.checked,intervals:d.intervals.split(',').map(x=>Number(x.trim()))};
  for(const k of ['sessionMin','sessionMax','breakMin','dailyMax','weeklyGoal','reservePct','reviewMin'])settings[k]=Number(d[k]);
  const availability=$$('[data-free-day]').map(day=>{
   const i=Number(day.dataset.freeDay),status=day.querySelector('select').value;
   // Retain previously entered ranges while unknown/unavailable; the motor ignores them.
   const ranges=[...day.querySelectorAll('[data-free-range]')].map(row=>({start:row.querySelector('input[name=freeStart'+i+']').value,end:row.querySelector('input[name=freeEnd'+i+']').value})).filter(r=>r.start||r.end);
   if(status==='available'&&!ranges.length)throw new Error(days[i]+': informe um horário livre ou selecione Não informado.');
   if(ranges.some(r=>!r.start||!r.end))throw new Error(days[i]+': preencha início e término de cada faixa livre.');
   return {day:i,status,ranges};
  });
  const entries=$$('[data-routine-entry]').map(row=>({start:row.querySelector('[data-entry-start]').value,end:row.querySelector('[data-entry-end]').value,title:row.querySelector('[data-entry-title]').value.trim()})).filter(r=>r.start||r.end||r.title);
  if(entries.some(r=>!r.start||!r.end||!r.title))throw new Error('Em cada linha de atividade, preencha horário de início, horário de término e atividade.');
  const selectedDays=days.map((_,i)=>i).filter(i=>f.elements['routineDay'+i].checked);
  if(entries.length&&d.routineRecurrence!=='once'&&!selectedDays.length)throw new Error('Marque os dias em que as atividades acontecem.');
  await save('routine_table',{settings,availability,entries,days:selectedDays,recurrence:d.routineRecurrence,anchor:d.routineAnchor});
  toast('Rotina salva. Os horários ocupados serão considerados nas próximas propostas.');
 }catch(e){if(error.isConnected)error.textContent=e.message;toast(e.message,true);}finally{if(b.isConnected)b.disabled=false;}
});
