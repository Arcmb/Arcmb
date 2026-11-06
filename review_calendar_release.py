"""Add a monthly spreadsheet-style review calendar to Minhas revisões."""
from pathlib import Path
import re

ROOT=Path(__file__).resolve().parent
JS_MARK='// === REVIEW CALENDAR TABLE V1 ==='
CSS_MARK='/* REVIEW CALENDAR TABLE V1 */'

JS=r'''\
'use strict';
// === REVIEW CALENDAR TABLE V1 ===
let reviewCalendarMonth=(S.serverDate||new Date().toISOString().slice(0,10)).slice(0,7)+'-01';
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
'''

CSS=r'''
/* REVIEW CALENDAR TABLE V1 */
.review-calendar-card{margin-top:22px}.review-calendar-head{display:flex;justify-content:space-between;gap:18px;align-items:flex-start;flex-wrap:wrap}.review-calendar-head h2{margin:0}.review-calendar-legend{display:flex;gap:14px;flex-wrap:wrap;margin:14px 0;color:var(--muted);font-size:12px}.review-calendar-legend span{display:inline-flex;align-items:center;gap:6px}.review-calendar-legend i{width:16px;height:12px;border-radius:4px;border:1px solid var(--line)}.review-calendar-legend .planned{background:#dceeff}.review-calendar-legend .exercise{background:#dff3df}.review-calendar-legend .done{background:#cce9d3}.review-calendar-legend .partial{background:#fff0bd}.review-calendar-legend .overdue{background:#f7cccc}.review-calendar-legend .projection{background:#edf5d6;border-style:dashed}.review-calendar-wrap{overflow:auto;max-width:100%;border:1px solid var(--line);border-radius:14px}.review-calendar-table{border-collapse:separate;border-spacing:0;min-width:max-content;background:#fff}.review-calendar-table th,.review-calendar-table td{border-right:1px solid var(--line);border-bottom:1px solid var(--line);padding:7px;min-width:72px;vertical-align:top}.review-calendar-table th{background:#fbf4f5;text-align:center;font-size:12px}.review-calendar-table th small{display:block;color:var(--muted);font-weight:500}.review-calendar-table .sticky{position:sticky;z-index:4;text-align:left}.review-calendar-table .discipline{left:0;min-width:150px}.review-calendar-table .subject{left:150px;min-width:260px}.review-calendar-table td.review-cal-discipline,.review-calendar-table td.review-cal-subject{position:sticky;background:#fff;z-index:3}.review-calendar-table td.review-cal-discipline{left:0;min-width:150px}.review-calendar-table td.review-cal-subject{left:150px;min-width:260px}.review-calendar-table td.review-cal-subject small{display:block;color:var(--muted);margin-top:3px}.review-cal-empty{background:#fff}.review-cal-chip{display:block;width:100%;border:0;border-radius:6px;padding:6px 7px;margin:0 0 4px;font-size:11px;line-height:1.2;text-align:left;cursor:pointer;color:var(--ink)}.review-cal-planned,.review-cal-due{background:#dceeff}.review-cal-exercise{background:#dff3df}.review-cal-done{background:#cce9d3}.review-cal-partial{background:#fff0bd}.review-cal-missed,.review-cal-overdue{background:#f7cccc}.review-cal-projection{background:#edf5d6;border:1px dashed #9db36a}.review-cal-chip:hover{filter:brightness(.97);transform:translateY(-1px)}
@media(max-width:760px){.review-calendar-table .discipline{min-width:120px}.review-calendar-table .subject{left:120px;min-width:220px}.review-calendar-table td.review-cal-discipline{min-width:120px}.review-calendar-table td.review-cal-subject{left:120px;min-width:220px}.review-calendar-head .actions{width:100%}}
'''

def main():
    static=ROOT/'static'
    js_path=static/'review_calendar_table.js'
    js_path.write_text(JS,encoding='utf-8')
    html_path=static/'app.html';html=html_path.read_text(encoding='utf-8')
    if '/static/review_calendar_table.js' not in html:
        pattern=r'(<script src="/static/study_schedule\.js\?v=[^"]+" defer></script>)'
        if re.search(pattern,html):html=re.sub(pattern,r'\1\n<script src="/static/review_calendar_table.js?v=3.2.0" defer></script>',html,count=1)
        else:html=html.replace('</body>','<script src="/static/review_calendar_table.js?v=3.2.0" defer></script>\n</body>',1)
        html_path.write_text(html,encoding='utf-8')
    css_path=static/'style.css';css=css_path.read_text(encoding='utf-8')
    if CSS_MARK not in css:css_path.write_text(css.rstrip()+'\n\n'+CSS+'\n',encoding='utf-8')
    print('MEUCRONOGRAMA_REVIEW_CALENDAR_READY: monthly spreadsheet-style review calendar prepared.',flush=True)

if __name__=='__main__':main()
