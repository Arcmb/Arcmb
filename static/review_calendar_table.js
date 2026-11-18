'use strict';
// === REVIEW CALENDAR TABLE V1 ===
let reviewCalendarMonth=(S?.serverDate||new Date().toISOString().slice(0,10)).slice(0,7)+'-01';
const reviewCalendarBaseReviewsView=reviewsView;

function reviewCalendarDateParts(iso){const d=new Date(iso+'T12:00:00');return {year:d.getFullYear(),month:d.getMonth(),day:d.getDate()};}
function reviewCalendarDaysInMonth(iso){const p=reviewCalendarDateParts(iso);return new Date(p.year,p.month+1,0).getDate();}
function reviewCalendarMonthLabel(iso){return new Date(iso+'T12:00:00').toLocaleDateString('pt-BR',{month:'long',year:'numeric'}).replace(/^./,c=>c.toUpperCase());}
function reviewCalendarShift(month,delta){const p=reviewCalendarDateParts(month);const d=new Date(p.year,p.month+delta,1,12);return d.toISOString().slice(0,10);}
function reviewCalendarDiscipline(c){return c.sourceDiscipline||sub(c.subjectId)||'Sem disciplina';}
function reviewCalendarFeedback(c){return (P.feedback||[]).filter(f=>f.contentId===c.id).sort((a,b)=>String(a.date||'').localeCompare(String(b.date||''))||String(a.at||'').localeCompare(String(b.at||'')));}
function reviewCalendarSessions(c){return (P.sessions||[]).filter(s=>s.kind==='review'&&(s.contentId===c.id||s.reviewContentId===c.id)).sort((a,b)=>String(a.date||'').localeCompare(String(b.date||''))||a.start-b.start);}
function reviewCalendarOrdinal(n){return n+'ª revisão';}
function reviewCalendarEvent(label,kind,contentId,sessionId,title){return {label,kind,contentId,sessionId:sessionId||'',title:title||label};}
function reviewCalendarEvents(c){
 const byDate={};const put=(date,event)=>{if(!date)return;(byDate[date]||(byDate[date]=[])).push(event);};
 const feedback=reviewCalendarFeedback(c),performed=feedback.filter(f=>f.status==='done'||f.status==='partial'||f.status==='missed');
 let count=0;
 performed.forEach(f=>{count+=1;const kind=f.status==='missed'?'missed':f.status==='partial'?'partial':'done';put(f.date,reviewCalendarEvent(reviewCalendarOrdinal(count),kind,c.id,'',kind==='done'?'Revisão concluída':kind==='partial'?'Revisão parcial':'Revisão não realizada'));});
 const sessions=reviewCalendarSessions(c).filter(s=>s.status==='planned');
 const cycles=new Map();
 sessions.forEach(s=>{const key=s.reviewCycleId||('session:'+s.id);if(!cycles.has(key))cycles.set(key,{number:++count,dates:new Set()});const cycle=cycles.get(key);const part=s.reviewPart==='theory'?'Teoria':s.reviewPart==='exercise'?'Exercícios':'Revisão';const label=reviewCalendarOrdinal(cycle.number)+' · '+part;put(s.date,reviewCalendarEvent(label,s.reviewPart==='exercise'?'exercise':'planned',c.id,s.id,'Programada '+hm(s.start)+'–'+hm(s.end)));cycle.dates.add(s.date);});
 if(!sessions.length&&c.status==='studied'&&c.nextDue){count+=1;put(c.nextDue,reviewCalendarEvent(reviewCalendarOrdinal(count),c.nextDue<S.serverDate?'overdue':'due',c.id,'','Data-alvo da próxima revisão'));}
 const intervals=Array.isArray(P.settings?.intervals)?P.settings.intervals:[];
 let cursor=(sessions.length?sessions[sessions.length-1].date:c.nextDue)||'';
 let stage=Math.max(0,Math.min(intervals.length-1,Number(c.stage||0)));
 for(let i=stage+1;i<intervals.length&&cursor&&i<stage+4;i++){cursor=add(cursor,Number(intervals[i]||0));count+=1;put(cursor,reviewCalendarEvent(reviewCalendarOrdinal(count),'projection',c.id,'','Projeção sujeita ao resultado das revisões anteriores'));}
 return byDate;
}
function reviewCalendarModels(){return (P.contents||[]).filter(c=>c.status==='studied'||c.status==='planned').slice().sort((a,b)=>reviewCalendarDiscipline(a).localeCompare(reviewCalendarDiscipline(b))||String(a.title||'').localeCompare(String(b.title||''))).map(c=>({c,discipline:reviewCalendarDiscipline(c),events:reviewCalendarEvents(c)}));}
function reviewCalendarCell(model,date){const events=model.events[date]||[];if(!events.length)return '<td class="review-cal-empty"></td>';return `<td class="review-cal-day">${events.map(e=>`<button type="button" class="review-cal-chip review-cal-${e.kind}" data-act="${e.sessionId?'edit-session':'feedback-content'}" data-id="${esc(e.sessionId||e.contentId)}" title="${esc(e.title)}">${esc(e.label)}</button>`).join('')}</td>`;}
function reviewCalendarSection(){
 const models=reviewCalendarModels(),daysCount=reviewCalendarDaysInMonth(reviewCalendarMonth),monthKey=reviewCalendarMonth.slice(0,7);
 const headers=Array.from({length:daysCount},(_,i)=>`<th><span>${i+1}</span><small>${new Date(`${monthKey}-${String(i+1).padStart(2,'0')}T12:00:00`).toLocaleDateString('pt-BR',{weekday:'short'}).replace('.','')}</small></th>`).join('');
 const rows=models.map(model=>`<tr><td class="review-cal-discipline"><strong>${esc(model.discipline)}</strong></td><td class="review-cal-subject"><strong>${esc(model.c.title)}</strong>${model.c.topic?`<small>${esc(model.c.topic)}</small>`:''}${model.c.sourceType==='exam_error'?`<small>${model.c.errorCount||0} erro(s) importado(s)</small>`:''}</td>${Array.from({length:daysCount},(_,i)=>reviewCalendarCell(model,`${monthKey}-${String(i+1).padStart(2,'0')}`)).join('')}</tr>`).join('');
 return `<section class="card review-calendar-card"><div class="review-calendar-head"><div><p class="eyebrow">CALENDÁRIO DE REVISÕES</p><h2>${esc(reviewCalendarMonthLabel(reviewCalendarMonth))}</h2><p>Disciplina e assunto ficam fixos à esquerda; as revisões aparecem nos respectivos dias do mês.</p></div><div class="actions">${button('← Mês anterior','review-calendar-prev','secondary')}${button('Mês atual','review-calendar-current','secondary')}${button('Próximo mês →','review-calendar-next','secondary')}</div></div><div class="review-calendar-legend"><span><i class="planned"></i>Programada</span><span><i class="exercise"></i>Exercícios</span><span><i class="done"></i>Concluída</span><span><i class="partial"></i>Parcial</span><span><i class="overdue"></i>Atrasada/não realizada</span><span><i class="projection"></i>Projeção</span></div><div class="review-calendar-wrap"><table class="review-calendar-table"><thead><tr><th class="sticky discipline">Disciplina</th><th class="sticky subject">Assunto</th>${headers}</tr></thead><tbody>${rows||`<tr><td colspan="${daysCount+2}" class="empty">Nenhum conteúdo acompanhado neste perfil.</td></tr>`}</tbody></table></div><p class="micro">Clique em uma revisão programada para ajustar o horário. Clique nas demais marcações para registrar o resultado. As projeções são recalculadas depois de cada revisão.</p></section>`;
}
reviewsView=function(){return reviewCalendarBaseReviewsView()+reviewCalendarSection();};
acts['review-calendar-prev']=()=>{reviewCalendarMonth=reviewCalendarShift(reviewCalendarMonth,-1);render();window.scrollTo(0,0);};
acts['review-calendar-current']=()=>{reviewCalendarMonth=(S.serverDate||new Date().toISOString().slice(0,10)).slice(0,7)+'-01';render();window.scrollTo(0,0);};
acts['review-calendar-next']=()=>{reviewCalendarMonth=reviewCalendarShift(reviewCalendarMonth,1);render();window.scrollTo(0,0);};
