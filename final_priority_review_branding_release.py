"""Final, precedence-safe corrections for priorities, review visibility and Qi branding.

Runs after all previous UI patches so old functions cannot overwrite:
- automatic discipline priority based on importance and difficulty;
- explicit manual-priority preservation;
- a visible monthly review matrix and global review-history table;
- the original Qi visual language: solid red circle, white Qi symbol, pastel-red palette and white background.
"""
from pathlib import Path
import json
import re

ROOT=Path(__file__).resolve().parent
JS_MARK='// === FINAL PRIORITY REVIEW BRANDING V1 ==='
CSS_MARK='/* === FINAL PRIORITY REVIEW BRANDING V1 === */'

QI_LOGO='''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512" role="img" aria-labelledby="qiTitle qiDesc">
<title id="qiTitle">Qi Vestibulares</title><desc id="qiDesc">Círculo vermelho com símbolo Qi branco</desc>
<circle cx="256" cy="256" r="244" fill="#d61f3c"/>
<circle cx="202" cy="252" r="112" fill="none" stroke="#fff" stroke-width="58" stroke-linecap="round"/>
<path d="M268 326 L335 393" fill="none" stroke="#fff" stroke-width="58" stroke-linecap="round"/>
<circle cx="365" cy="154" r="27" fill="#fff"/>
<rect x="338" y="198" width="54" height="158" rx="27" fill="#fff"/>
</svg>'''

JS=r'''
// === FINAL PRIORITY REVIEW BRANDING V1 ===
(function(){
 'use strict';
 const qiPriorityLabel={1:'Máxima',2:'Alta',3:'Regular',4:'Baixa',5:'Mínima'};
 function qiNum(value,fallback){const n=Number(value);return Number.isFinite(n)?n:fallback;}
 function qiSuggestedPriority(subject){
  const importance=Math.max(1,Math.min(5,qiNum(subject&&subject.importance,3)));
  const difficulty=Math.max(1,Math.min(5,qiNum(subject&&subject.difficulty,3)));
  const score=.60*importance+.40*difficulty;
  return score>=4.5?1:score>=3.5?2:score>=2.5?3:score>=1.5?4:5;
 }
 function qiEffectivePriority(subject){
  if(subject&&subject.priorityManual===true)return Math.max(1,Math.min(5,qiNum(subject.priority,3)));
  return qiSuggestedPriority(subject||{});
 }
 // Replace previous helpers so every later call sees the correct priority.
 try{learnerSuggestedPriority=qiSuggestedPriority;learnerEffectivePriority=qiEffectivePriority;}catch(e){}

 function qiAlpha(a,b){return String(a&&a.name||'').localeCompare(String(b&&b.name||''),'pt-BR',{sensitivity:'base'});}
 function qiSortSubjects(list){
  const order=(typeof learnerSubjectOrder!=='undefined'&&learnerSubjectOrder)||localStorage.getItem('meucronograma:subject-order')||'priority';
  const rows=(list||[]).slice();
  if(order==='alphabetical')return rows.sort(qiAlpha);
  if(order==='importance')return rows.sort((a,b)=>qiNum(b.importance,3)-qiNum(a.importance,3)||qiEffectivePriority(a)-qiEffectivePriority(b)||qiAlpha(a,b));
  if(order==='difficulty')return rows.sort((a,b)=>qiNum(b.difficulty,3)-qiNum(a.difficulty,3)||qiEffectivePriority(a)-qiEffectivePriority(b)||qiAlpha(a,b));
  return rows.sort((a,b)=>qiEffectivePriority(a)-qiEffectivePriority(b)||qiNum(b.importance,3)-qiNum(a.importance,3)||qiNum(b.difficulty,3)-qiNum(a.difficulty,3)||qiAlpha(a,b));
 }

 if(typeof subjectsView==='function'){
  subjectsView=function(){
   const ordered=qiSortSubjects(P.subjects||[]);
   const currentOrder=(typeof learnerSubjectOrder!=='undefined'&&learnerSubjectOrder)||localStorage.getItem('meucronograma:subject-order')||'priority';
   const controls=`<section class="card subject-order-card qi-priority-explainer"><div class="page-head"><div><h2>Ordem das disciplinas</h2><p>A prioridade automática usa <strong>60% da importância</strong> e <strong>40% da dificuldade</strong>. Se o aluno escolher prioridade manual, essa escolha prevalece.</p></div><label>Exibir por<select id="learner-subject-order"><option value="priority" ${currentOrder==='priority'?'selected':''}>Prioridade</option><option value="importance" ${currentOrder==='importance'?'selected':''}>Maior importância</option><option value="difficulty" ${currentOrder==='difficulty'?'selected':''}>Maior dificuldade</option><option value="alphabetical" ${currentOrder==='alphabetical'?'selected':''}>Ordem alfabética</option></select></label></div></section>`;
   const rows=items(ordered.map(x=>{
    const priority=qiEffectivePriority(x),automatic=x.priorityManual!==true;
    const score=(.60*qiNum(x.importance,3)+.40*qiNum(x.difficulty,3)).toFixed(1).replace('.',',');
    const origin=automatic?`calculada automaticamente · índice ${score}`:'definida manualmente pelo aluno';
    return `<div class="item subject-priority-row"><div class="item-main"><strong>${esc(x.name)} ${tag(x.active?'Ativa':'Pausada',x.active?'done':'')} ${tag('Prioridade '+priority+' · '+qiPriorityLabel[priority],priority<=2?'warning':'')}</strong><p>${minutes(x.weeklyMin)} por semana · dificuldade ${x.difficulty}/5 · importância ${x.importance}/5</p><small>${esc(x.action)}${x.examDate?' · Prova em '+br(x.examDate):''} · revisão: ${esc(studyReviewPlans[x.reviewPlan||'both'])}<br><strong>Origem da prioridade:</strong> ${esc(origin)}</small></div><div class="item-actions">${button('Editar','edit-subject','secondary',`data-id="${x.id}"`)}${button('Excluir','delete','danger-button',`data-collection="subjects" data-id="${x.id}"`)}</div></div>`;
   }));
   return head('Disciplinas e metas','A prioridade define a ordem inicial; prazos, revisões vencidas, desempenho e disponibilidade refinam a programação.',button('Adicionar','new-subject','primary'))+controls+`<div class="card">${rows}</div><div class="notice"><strong>Exemplo:</strong> dificuldade 1 e importância 1 resultam em prioridade 5; dificuldade 5 e importância 5 resultam em prioridade 1. Portanto, Inglês e Matemática não permanecem iguais quando seus atributos são diferentes.</div>`;
  };
 }

 let qiReviewMonth=((typeof S!=='undefined'&&S.serverDate)||new Date().toISOString().slice(0,10)).slice(0,7)+'-01';
 function qiISODate(value){return /^\d{4}-\d{2}-\d{2}$/.test(String(value||''))?String(value):'';}
 function qiDate(value){const iso=qiISODate(value);return iso?new Date(iso+'T12:00:00'):null;}
 function qiAddDays(value,days){const d=qiDate(value);if(!d)return '';d.setDate(d.getDate()+Number(days||0));return d.toISOString().slice(0,10);}
 function qiMonthShift(value,delta){const d=qiDate(value)||new Date();d.setDate(1);d.setMonth(d.getMonth()+delta);return d.toISOString().slice(0,7)+'-01';}
 function qiMonthLabel(value){const d=qiDate(value)||new Date();const label=d.toLocaleDateString('pt-BR',{month:'long',year:'numeric'});return label.charAt(0).toUpperCase()+label.slice(1);}
 function qiDays(value){const d=qiDate(value)||new Date();return new Date(d.getFullYear(),d.getMonth()+1,0).getDate();}
 function qiDiscipline(content){return content.sourceDiscipline||(typeof sub==='function'?sub(content.subjectId):'')||'Sem disciplina';}
 function qiFeedback(content){return (P.feedback||[]).filter(f=>f.contentId===content.id).slice().sort((a,b)=>String(a.date||'').localeCompare(String(b.date||'')));}
 function qiSessions(content){return (P.sessions||[]).filter(s=>s.kind==='review'&&(s.contentId===content.id||s.reviewContentId===content.id)).slice().sort((a,b)=>String(a.date||'').localeCompare(String(b.date||''))||qiNum(a.start,0)-qiNum(b.start,0));}
 function qiReviewData(content){
  const events={},put=(date,item)=>{date=qiISODate(date);if(!date)return;(events[date]||(events[date]=[])).push(item);};
  const feedback=qiFeedback(content),completed=feedback.filter(f=>['done','partial','missed'].includes(f.status));
  let ordinal=0;
  completed.forEach(f=>{ordinal++;put(f.date,{label:ordinal+'ª revisão',kind:f.status==='done'?'done':f.status==='partial'?'partial':'missed',contentId:content.id,title:f.status==='done'?'Concluída':f.status==='partial'?'Parcial':'Não realizada'});});
  const planned=qiSessions(content).filter(s=>s.status==='planned');
  const cycles=new Map();
  planned.forEach(s=>{const key=s.reviewCycleId||('session:'+s.id);if(!cycles.has(key))cycles.set(key,++ordinal);const number=cycles.get(key),part=s.reviewPart==='theory'?'Teoria':s.reviewPart==='exercise'?'Exercícios':'Revisão';put(s.date,{label:number+'ª · '+part,kind:s.reviewPart==='exercise'?'exercise':'planned',contentId:content.id,sessionId:s.id,title:(typeof hm==='function'?hm(s.start)+'–'+hm(s.end):'Programada')});});
  if(content.nextDue&&!planned.some(s=>s.date===content.nextDue)){ordinal++;put(content.nextDue,{label:ordinal+'ª revisão',kind:content.nextDue<((S&&S.serverDate)||'')?'overdue':'due',contentId:content.id,title:'Próxima revisão'});}
  const intervals=Array.isArray(P.settings&&P.settings.intervals)?P.settings.intervals:[];
  let cursor=(planned.length?planned[planned.length-1].date:content.nextDue)||'';
  let stage=Math.max(0,Math.min(Math.max(0,intervals.length-1),qiNum(content.stage,0)));
  const projected=[];
  for(let i=stage+1;i<intervals.length&&cursor&&projected.length<3;i++){
   cursor=qiAddDays(cursor,intervals[i]);if(!cursor)break;ordinal++;projected.push(cursor);put(cursor,{label:ordinal+'ª revisão',kind:'projection',contentId:content.id,title:'Data projetada'});
  }
  const last=completed.length?completed[completed.length-1].date:'';
  const next=(planned[0]&&planned[0].date)||content.nextDue||'';
  return {events,feedback,planned,last,next,projected};
 }
 function qiContents(){return (P.contents||[]).filter(c=>c.status==='studied'||c.status==='planned').slice().sort((a,b)=>qiDiscipline(a).localeCompare(qiDiscipline(b),'pt-BR',{sensitivity:'base'})||String(a.title||'').localeCompare(String(b.title||''),'pt-BR',{sensitivity:'base'}));}
 function qiStatus(content,data){if(content.paused)return 'Pausada';if(data.next&&data.next<((S&&S.serverDate)||''))return 'Atrasada';if(data.next)return 'Programada';if(data.feedback.length)return 'Em acompanhamento';return 'Sem data';}
 function qiReviewOverviewHtml(){
  const contents=qiContents(),monthKey=qiReviewMonth.slice(0,7),days=qiDays(qiReviewMonth);
  const headers=Array.from({length:days},(_,i)=>{const day=i+1,date=`${monthKey}-${String(day).padStart(2,'0')}`;const d=qiDate(date);return `<th><span>${day}</span><small>${d.toLocaleDateString('pt-BR',{weekday:'short'}).replace('.','')}</small></th>`;}).join('');
  const monthlyRows=contents.map(content=>{const data=qiReviewData(content);const cells=Array.from({length:days},(_,i)=>{const date=`${monthKey}-${String(i+1).padStart(2,'0')}`,events=data.events[date]||[];return `<td>${events.map(e=>`<button type="button" class="qi-review-chip qi-review-${e.kind}" data-act="${e.sessionId?'edit-session':'feedback-content'}" data-id="${esc(e.sessionId||e.contentId)}" title="${esc(e.title)}">${esc(e.label)}</button>`).join('')}</td>`;}).join('');return `<tr><td class="qi-sticky qi-discipline"><strong>${esc(qiDiscipline(content))}</strong></td><td class="qi-sticky qi-content"><strong>${esc(content.title||'Conteúdo')}</strong>${content.topic?`<small>${esc(content.topic)}</small>`:''}${content.sourceType==='exam_error'?`<small>${content.errorCount||0} erro(s) de avaliação</small>`:''}</td><td class="qi-study-date">${content.studiedOn?br(content.studiedOn):'—'}</td>${cells}</tr>`;}).join('');
  const globalRows=contents.map(content=>{const data=qiReviewData(content),future=[data.next,...data.projected].filter(Boolean);return `<tr><td><strong>${esc(qiDiscipline(content))}</strong></td><td><strong>${esc(content.title||'Conteúdo')}</strong>${content.topic?`<small>${esc(content.topic)}</small>`:''}</td><td>${content.studiedOn?br(content.studiedOn):'—'}</td><td>${data.last?br(data.last):'—'}</td><td>${data.next?br(data.next):'—'}</td><td>${future.length?future.map((x,i)=>`<span class="qi-date-pill">${i+1}ª: ${br(x)}</span>`).join(' '):'—'}</td><td>${data.feedback.length}</td><td>${esc(qiStatus(content,data))}</td><td>${button('Registrar','feedback-content','secondary',`data-id="${content.id}"`)}</td></tr>`;}).join('');
  return `<section class="card qi-review-overview"><div class="qi-review-head"><div><p class="eyebrow">PLANEJAMENTO E HISTÓRICO</p><h2>Calendário mensal de revisões</h2><p>Visão global por disciplina, conteúdo e data, no formato da planilha de acompanhamento.</p></div><div class="actions"><button type="button" class="secondary" id="qi-review-prev">← Mês anterior</button><button type="button" class="secondary" id="qi-review-current">Mês atual</button><button type="button" class="secondary" id="qi-review-next">Próximo mês →</button></div></div><h3>${esc(qiMonthLabel(qiReviewMonth))}</h3><div class="qi-review-legend"><span class="planned">Programada</span><span class="exercise">Exercícios</span><span class="done">Concluída</span><span class="partial">Parcial</span><span class="overdue">Atrasada/não realizada</span><span class="projection">Projeção</span></div><div class="qi-review-scroll"><table class="qi-review-matrix"><thead><tr><th class="qi-sticky qi-discipline">Disciplina</th><th class="qi-sticky qi-content">Assunto / conteúdo</th><th>Estudado em</th>${headers}</tr></thead><tbody>${monthlyRows||`<tr><td colspan="${days+3}" class="empty">Nenhum conteúdo estudado ou programado neste perfil.</td></tr>`}</tbody></table></div><details open class="qi-global-history"><summary>Visão global e histórico das revisões</summary><div class="table-wrap"><table><thead><tr><th>Disciplina</th><th>Conteúdo</th><th>Data do estudo</th><th>Última revisão</th><th>Próxima revisão</th><th>Próximas datas</th><th>Registros</th><th>Situação</th><th>Ação</th></tr></thead><tbody>${globalRows||'<tr><td colspan="9" class="empty">Nenhuma revisão registrada ou programada.</td></tr>'}</tbody></table></div></details></section>`;
 }
 function qiInstallReviewOverview(){
  const main=document.querySelector('main')||document.querySelector('.main')||document.body;
  const heading=[...main.querySelectorAll('h1,h2')].find(el=>String(el.textContent||'').trim()==='Minhas revisões');
  if(!heading)return;
  main.querySelectorAll('.review-calendar-card,.qi-review-overview').forEach(el=>el.remove());
  const anchor=heading.closest('.page-head')||heading.parentElement;
  anchor.insertAdjacentHTML('afterend',qiReviewOverviewHtml());
  const prev=document.getElementById('qi-review-prev'),current=document.getElementById('qi-review-current'),next=document.getElementById('qi-review-next');
  if(prev)prev.onclick=()=>{qiReviewMonth=qiMonthShift(qiReviewMonth,-1);qiInstallReviewOverview();};
  if(current)current.onclick=()=>{qiReviewMonth=((S&&S.serverDate)||new Date().toISOString().slice(0,10)).slice(0,7)+'-01';qiInstallReviewOverview();};
  if(next)next.onclick=()=>{qiReviewMonth=qiMonthShift(qiReviewMonth,1);qiInstallReviewOverview();};
 }
 if(typeof render==='function'){
  const qiBaseRender=render;
  render=function(){const result=qiBaseRender.apply(this,arguments);queueMicrotask(qiInstallReviewOverview);return result;};
  queueMicrotask(qiInstallReviewOverview);
 }
})();
'''

CSS=r'''
/* === FINAL PRIORITY REVIEW BRANDING V1 === */
:root{--ink:#342126;--muted:#765b61;--line:#ead0d5;--paper:#fff;--bg:#fff;--primary:#c25c69;--purple:#c25c69;--soft:#fae9ec;--rose:#f7dce1;--amber:#fff0d7;--border:#ead0d5;--text:#342126}
html,body{background:#fff!important;color:var(--ink)}body{background-image:none!important}main,.main,.content,.app-content,.page-content,#app{background:#fff}.card{background:#fff;border-color:var(--line);box-shadow:0 5px 18px rgba(125,47,61,.055)}
aside{background:linear-gradient(180deg,#93404d 0%,#782f3b 100%);color:#fff}nav button.active{background:#c25c69;color:#fff;box-shadow:inset 3px 0 #ffe3e7}.primary{background:#c25c69;color:#fff}.primary:hover{background:#aa4b58}.secondary{background:#fae9ec;color:#77323d}.secondary:hover{background:#f4d7dc}.notice,.hero{background:#fdf0f2;border-color:#efcfd5}
.logo{width:54px;height:54px;padding:2px;border-radius:50%;background:#fff;display:grid;place-items:center;box-shadow:0 8px 22px rgba(61,11,24,.25)}.logo img{width:100%;height:100%;display:block;object-fit:contain;border-radius:50%}
.qi-priority-explainer{border-left:4px solid var(--primary)}.subject-priority-row .tag{white-space:nowrap}.subject-priority-row small{line-height:1.55}
.qi-review-overview{margin:18px 0 22px}.qi-review-head{display:flex;justify-content:space-between;align-items:flex-start;gap:16px;flex-wrap:wrap}.qi-review-head h2{margin:.2rem 0}.qi-review-legend{display:flex;gap:8px;flex-wrap:wrap;margin:12px 0}.qi-review-legend span{padding:5px 9px;border-radius:999px;font-size:11px;border:1px solid var(--line)}.qi-review-legend .planned{background:#dcecff}.qi-review-legend .exercise{background:#e0f2e2}.qi-review-legend .done{background:#cee9d5}.qi-review-legend .partial{background:#fff0bd}.qi-review-legend .overdue{background:#f7d0d5}.qi-review-legend .projection{background:#edf4d8;border-style:dashed}
.qi-review-scroll{overflow:auto;max-width:100%;border:1px solid var(--line);border-radius:14px;background:#fff}.qi-review-matrix{border-collapse:separate;border-spacing:0;min-width:max-content;background:#fff}.qi-review-matrix th,.qi-review-matrix td{border-right:1px solid var(--line);border-bottom:1px solid var(--line);padding:7px;min-width:74px;vertical-align:top}.qi-review-matrix th{background:#fcf3f5;text-align:center;font-size:11px}.qi-review-matrix th small{display:block;color:var(--muted);font-weight:500}.qi-review-matrix .qi-sticky{position:sticky;z-index:4;text-align:left}.qi-review-matrix .qi-discipline{left:0;min-width:145px}.qi-review-matrix .qi-content{left:145px;min-width:245px}.qi-review-matrix td.qi-sticky{background:#fff;z-index:3}.qi-review-matrix .qi-content small{display:block;color:var(--muted);margin-top:3px}.qi-study-date{white-space:nowrap}.qi-review-chip{display:block;width:100%;border:0;border-radius:7px;padding:6px;margin:0 0 4px;font-size:10px;line-height:1.2;text-align:left;cursor:pointer;color:var(--ink)}.qi-review-planned,.qi-review-due{background:#dcecff}.qi-review-exercise{background:#e0f2e2}.qi-review-done{background:#cee9d5}.qi-review-partial{background:#fff0bd}.qi-review-missed,.qi-review-overdue{background:#f7d0d5}.qi-review-projection{background:#edf4d8;border:1px dashed #9caf74}.qi-global-history{margin-top:16px}.qi-global-history summary{font-weight:800;cursor:pointer;padding:10px 0}.qi-global-history table small{display:block;color:var(--muted)}.qi-date-pill{display:inline-block;background:#fae9ec;border-radius:999px;padding:4px 7px;margin:2px;font-size:10px;white-space:nowrap}
@media(max-width:760px){.qi-review-matrix .qi-discipline{min-width:115px}.qi-review-matrix .qi-content{left:115px;min-width:210px}.qi-review-head .actions{width:100%}}
'''


def patch_logo_and_branding():
    static=ROOT/'static'
    (static/'qi-logo.svg').write_text(QI_LOGO,encoding='utf-8')
    (static/'icon.svg').write_text(QI_LOGO,encoding='utf-8')
    css_path=static/'style.css'
    css=css_path.read_text(encoding='utf-8')
    if CSS_MARK not in css:
        css=css.rstrip()+'\n\n'+CSS+'\n'
    css_path.write_text(css,encoding='utf-8')
    for filename in ('app.html','login.html','setup.html'):
        path=static/filename
        if not path.exists():continue
        html=path.read_text(encoding='utf-8')
        html=re.sub(r'<span class="logo">.*?</span>','<span class="logo"><img src="/static/qi-logo.svg" alt="Qi Vestibulares"></span>',html,count=1,flags=re.S)
        html=html.replace('/static/qi-logo.svg?v=3.0.0','/static/qi-logo.svg?v=4.0.0')
        html=re.sub(r'/static/style\.css(?:\?v=[^"\']+)?','/static/style.css?v=4.0.0',html)
        if filename=='app.html':html=re.sub(r'/static/student_guidance\.js\?v=[^"\']+','/static/student_guidance.js?v=4.0.0',html)
        path.write_text(html,encoding='utf-8')
    manifest=static/'manifest.webmanifest'
    if manifest.exists():
        try:
            data=json.loads(manifest.read_text(encoding='utf-8'))
            data['theme_color']='#93404d';data['background_color']='#ffffff'
            manifest.write_text(json.dumps(data,ensure_ascii=False,separators=(',',':')),encoding='utf-8')
        except Exception:pass


def patch_final_js():
    path=ROOT/'static'/'student_guidance.js'
    text=path.read_text(encoding='utf-8')
    if JS_MARK not in text:text=text.rstrip()+'\n\n'+JS+'\n'
    path.write_text(text,encoding='utf-8')


def main():
    patch_final_js();patch_logo_and_branding()
    print('MEUCRONOGRAMA_FINAL_PRIORITY_REVIEW_BRANDING_READY: priorities differ by attributes, review tables are forcibly visible, Qi logo/palette and white background applied.',flush=True)

if __name__=='__main__':main()
