"""Render the dedicated review page directly from the learner profile.

The previous bridge still depended on helper functions created by other scripts.
A runtime error in any earlier extension could therefore leave the page without
a renderer even though the learner had valid sessions and contents. This patch
removes that dependency: the dedicated page reads P.contents, P.sessions,
P.feedback and P.settings itself and always builds its own monthly calendar and
history table.
"""
from pathlib import Path
import re

ROOT=Path(__file__).resolve().parent
MARK='// === REVIEW TABLE DIRECT RENDERER V2 ==='

JS=r'''"use strict";
// === REVIEW TABLE DIRECT RENDERER V2 ===
(function(){
 const sourceReviewView=typeof reviewsView==='function'?reviewsView:null;
 let reviewTableMonth=((typeof S!=='undefined'&&S.serverDate)||new Date().toISOString().slice(0,10)).slice(0,7)+'-01';

 const asArray=value=>Array.isArray(value)?value:[];
 const escapeHtml=value=>typeof esc==='function'?esc(String(value??'')):String(value??'').replace(/[&<>"']/g,ch=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[ch]));
 const pad=value=>String(value).padStart(2,'0');
 function currentServerDate(){return (typeof S!=='undefined'&&S.serverDate)||new Date().toISOString().slice(0,10);}
 function validDate(value){return /^\d{4}-\d{2}-\d{2}$/.test(String(value||''))?String(value):'';}
 function dateObject(value){const iso=validDate(value);return iso?new Date(iso+'T12:00:00'):null;}
 function addDays(value,days){const d=dateObject(value);if(!d)return '';d.setDate(d.getDate()+Number(days||0));return d.toISOString().slice(0,10);}
 function shiftMonth(value,delta){const d=dateObject(value)||new Date();d.setDate(1);d.setMonth(d.getMonth()+Number(delta||0));return d.toISOString().slice(0,7)+'-01';}
 function daysInMonth(value){const d=dateObject(value)||new Date();return new Date(d.getFullYear(),d.getMonth()+1,0).getDate();}
 function monthLabel(value){const d=dateObject(value)||new Date();const text=d.toLocaleDateString('pt-BR',{month:'long',year:'numeric'});return text.charAt(0).toUpperCase()+text.slice(1);}
 function formatDate(value){const d=dateObject(value);return d?d.toLocaleDateString('pt-BR'):'—';}
 function formatTime(value){const minutes=Number(value);if(!Number.isFinite(minutes))return '';return pad(Math.floor(minutes/60))+':'+pad(minutes%60);}
 function state(){return typeof P==='object'&&P?P:{subjects:[],contents:[],sessions:[],feedback:[],settings:{}};}
 function subjectById(id){return asArray(state().subjects).find(item=>String(item.id)===String(id))||null;}
 function disciplineName(subjectId,fallback){return String(fallback||subjectById(subjectId)?.name||'Sem disciplina');}
 function cleanSessionTitle(session,discipline){
  let title=String(session.title||'Conteúdo de revisão');
  const prefix=discipline+' · ';
  if(title.startsWith(prefix))title=title.slice(prefix.length);
  title=title.replace(/^Revisão de teoria:\s*/i,'').replace(/^Exercícios:\s*/i,'').replace(/^Revisar:\s*/i,'').trim();
  return title||'Conteúdo de revisão';
 }

 function reviewRows(){
  const profile=state();
  const rows=[];
  const byId=new Map();
  asArray(profile.contents).filter(content=>content&&['studied','planned'].includes(content.status)).forEach(content=>{
   const copy={...content,_rowId:String(content.id||'content:'+rows.length),_synthetic:false};
   rows.push(copy);if(content.id)byId.set(String(content.id),copy);
  });
  asArray(profile.sessions).filter(session=>session&&session.kind==='review').forEach(session=>{
   const linked=String(session.reviewContentId||session.contentId||'');
   if(linked&&byId.has(linked))return;
   const key=linked||('session:'+String(session.id||rows.length));
   if(byId.has(key))return;
   const discipline=disciplineName(session.subjectId,session.subjectName);
   const synthetic={
    id:key,_rowId:key,_synthetic:true,subjectId:session.subjectId||'',sourceDiscipline:discipline,
    title:cleanSessionTitle(session,discipline),topic:'',status:'planned',studiedOn:'',nextDue:session.date||'',stage:0,
    sourceType:'scheduled_review',errorCount:0
   };
   rows.push(synthetic);byId.set(key,synthetic);
  });
  return rows.sort((a,b)=>disciplineName(a.subjectId,a.sourceDiscipline).localeCompare(disciplineName(b.subjectId,b.sourceDiscipline),'pt-BR',{sensitivity:'base'})||String(a.title||'').localeCompare(String(b.title||''),'pt-BR',{sensitivity:'base'}));
 }
 function linkedSessions(row){
  const ids=new Set([row.id,row._rowId].filter(Boolean).map(String));
  return asArray(state().sessions).filter(session=>session&&session.kind==='review'&&(
   ids.has(String(session.reviewContentId||''))||ids.has(String(session.contentId||''))||
   (row._synthetic&&String(session.subjectId||'')===String(row.subjectId||'')&&cleanSessionTitle(session,disciplineName(row.subjectId,row.sourceDiscipline))===String(row.title||''))
  )).slice().sort((a,b)=>String(a.date||'').localeCompare(String(b.date||''))||Number(a.start||0)-Number(b.start||0));
 }
 function linkedFeedback(row){
  const ids=new Set([row.id,row._rowId].filter(Boolean).map(String));
  return asArray(state().feedback).filter(item=>item&&ids.has(String(item.contentId||''))).slice().sort((a,b)=>String(a.date||'').localeCompare(String(b.date||''))||String(a.at||'').localeCompare(String(b.at||'')));
 }
 function reviewModel(row){
  const events={};const put=(date,event)=>{date=validDate(date);if(!date)return;(events[date]||(events[date]=[])).push(event);};
  const feedback=linkedFeedback(row),sessions=linkedSessions(row),performed=feedback.filter(item=>['done','partial','missed'].includes(item.status));
  let ordinal=0;
  performed.forEach(item=>{
   ordinal+=1;
   const kind=item.status==='done'?'done':item.status==='partial'?'partial':'missed';
   put(item.date,{label:ordinal+'ª revisão',kind,contentId:row.id||row._rowId,title:kind==='done'?'Revisão concluída':kind==='partial'?'Revisão parcial':'Revisão não realizada'});
  });
  const planned=sessions.filter(item=>item.status==='planned');
  const cycles=new Map();
  planned.forEach(session=>{
   const key=session.reviewCycleId||('session:'+session.id);
   if(!cycles.has(key))cycles.set(key,++ordinal);
   const number=cycles.get(key),part=session.reviewPart==='theory'?'Teoria':session.reviewPart==='exercise'?'Exercícios':'Revisão';
   put(session.date,{label:number+'ª · '+part,kind:session.reviewPart==='exercise'?'exercise':'planned',contentId:row.id||row._rowId,sessionId:session.id,title:'Programada '+formatTime(session.start)+'–'+formatTime(session.end)});
  });
  if(row.nextDue&&!planned.some(item=>item.date===row.nextDue)){
   ordinal+=1;put(row.nextDue,{label:ordinal+'ª revisão',kind:row.nextDue<currentServerDate()?'overdue':'due',contentId:row.id||row._rowId,title:'Data-alvo da próxima revisão'});
  }
  const intervals=asArray(state().settings?.intervals).map(Number).filter(Number.isFinite);
  let cursor=(planned.length?planned[planned.length-1].date:row.nextDue)||'';
  const stage=Math.max(0,Math.min(Math.max(0,intervals.length-1),Number(row.stage||0)));
  const projected=[];
  for(let index=stage+1;index<intervals.length&&cursor&&projected.length<4;index++){
   cursor=addDays(cursor,intervals[index]);if(!cursor)break;ordinal+=1;projected.push(cursor);put(cursor,{label:ordinal+'ª revisão',kind:'projection',contentId:row.id||row._rowId,title:'Projeção sujeita ao resultado anterior'});
  }
  const completed=feedback.filter(item=>item.status==='done'||item.status==='partial');
  const last=completed.length?completed[completed.length-1].date:'';
  const nextSession=planned.find(item=>item.date>=currentServerDate())||planned[0]||null;
  const next=(nextSession&&nextSession.date)||row.nextDue||'';
  const questions=completed.reduce((sum,item)=>sum+Number(item.total||0),0);
  const correct=completed.reduce((sum,item)=>sum+Number(item.correct||0),0);
  return {row,events,feedback,sessions,planned,completed,last,next,projected,questions,correct};
 }
 function models(){return reviewRows().map(reviewModel);}
 function statusName(model){
  if(model.row.paused)return 'Pausada';
  if(model.next&&model.next<currentServerDate())return 'Atrasada';
  if(model.next)return 'Programada';
  if(model.completed.length)return 'Em acompanhamento';
  return 'Sem data';
 }
 function eventButton(event){
  const action=event.sessionId?'edit-session':'feedback-content';
  return `<button type="button" class="qi-review-chip qi-review-${escapeHtml(event.kind)}" data-act="${action}" data-id="${escapeHtml(event.sessionId||event.contentId)}" title="${escapeHtml(event.title)}">${escapeHtml(event.label)}</button>`;
 }
 function monthlyTable(allModels){
  const monthKey=reviewTableMonth.slice(0,7),days=daysInMonth(reviewTableMonth);
  const headers=Array.from({length:days},(_,index)=>{const day=index+1,date=`${monthKey}-${pad(day)}`,d=dateObject(date);return `<th><span>${day}</span><small>${d.toLocaleDateString('pt-BR',{weekday:'short'}).replace('.','')}</small></th>`;}).join('');
  const rows=allModels.map(model=>{
   const discipline=disciplineName(model.row.subjectId,model.row.sourceDiscipline);
   const cells=Array.from({length:days},(_,index)=>{const date=`${monthKey}-${pad(index+1)}`,events=model.events[date]||[];return `<td>${events.map(eventButton).join('')}</td>`;}).join('');
   return `<tr><td class="qi-sticky qi-discipline"><strong>${escapeHtml(discipline)}</strong></td><td class="qi-sticky qi-content"><strong>${escapeHtml(model.row.title||'Conteúdo')}</strong>${model.row.topic?`<small>${escapeHtml(model.row.topic)}</small>`:''}${model.row.sourceType==='exam_error'?`<small>${Number(model.row.errorCount||0)} erro(s) de avaliação</small>`:''}</td><td class="qi-study-date">${formatDate(model.row.studiedOn)}</td>${cells}</tr>`;
  }).join('');
  return `<div class="qi-review-head"><div><p class="eyebrow">PLANEJAMENTO E HISTÓRICO</p><h2>Calendário mensal de revisões</h2><p>Disciplina, conteúdo e revisões distribuídos pelas datas programadas.</p></div><div class="actions"><button type="button" class="secondary" id="review-table-prev">← Mês anterior</button><button type="button" class="secondary" id="review-table-current">Mês atual</button><button type="button" class="secondary" id="review-table-next">Próximo mês →</button></div></div><h3>${escapeHtml(monthLabel(reviewTableMonth))}</h3><div class="qi-review-legend"><span class="planned">Programada</span><span class="exercise">Exercícios</span><span class="done">Concluída</span><span class="partial">Parcial</span><span class="overdue">Atrasada/não realizada</span><span class="projection">Projeção</span></div><div class="qi-review-scroll"><table class="qi-review-matrix"><thead><tr><th class="qi-sticky qi-discipline">Disciplina</th><th class="qi-sticky qi-content">Assunto / conteúdo</th><th>Estudado em</th>${headers}</tr></thead><tbody>${rows||`<tr><td colspan="${days+3}" class="empty">Nenhum conteúdo ou bloco de revisão foi encontrado neste perfil.</td></tr>`}</tbody></table></div>`;
 }
 function historyTable(allModels){
  const rows=allModels.map(model=>{
   const discipline=disciplineName(model.row.subjectId,model.row.sourceDiscipline),future=[model.next,...model.projected].filter(Boolean);
   const performance=model.questions?`${model.correct}/${model.questions} (${Math.round(100*model.correct/model.questions)}%)`:'—';
   return `<tr><td><strong>${escapeHtml(discipline)}</strong></td><td><strong>${escapeHtml(model.row.title||'Conteúdo')}</strong>${model.row.topic?`<small>${escapeHtml(model.row.topic)}</small>`:''}</td><td>${formatDate(model.row.studiedOn)}</td><td>${model.completed.length}<small>${performance}</small></td><td>${formatDate(model.last)}</td><td>${formatDate(model.next)}</td><td>${future.length?future.map((date,index)=>`<span class="qi-date-pill">${index+1}ª: ${formatDate(date)}</span>`).join(' '):'—'}</td><td>${escapeHtml(statusName(model))}</td><td>${model.row._synthetic?'—':`<button type="button" class="secondary" data-act="feedback-content" data-id="${escapeHtml(model.row.id)}">Registrar</button>`}</td></tr>`;
  }).join('');
  return `<details open class="qi-global-history"><summary>Visão global e histórico das revisões</summary><div class="table-wrap"><table><thead><tr><th>Disciplina</th><th>Conteúdo</th><th>Data do estudo</th><th>Revisões / questões</th><th>Última revisão</th><th>Próxima revisão</th><th>Próximas datas</th><th>Situação</th><th>Ação</th></tr></thead><tbody>${rows||'<tr><td colspan="9" class="empty">Nenhum conteúdo ou revisão registrada.</td></tr>'}</tbody></table></div></details>`;
 }
 function directTablesHtml(){
  try{const allModels=models();return `<section class="card qi-review-overview">${monthlyTable(allModels)}${historyTable(allModels)}</section>`;}
  catch(error){console.error('Falha no renderizador direto da tabela de revisões.',error);return `<section class="card review-table-error"><h2>Não foi possível montar a tabela</h2><p>${escapeHtml(error&&error.message?error.message:'Erro de visualização não identificado.')}</p></section>`;}
 }
 globalThis.reviewTableDirectHtml=directTablesHtml;

 function installNavigation(){
  if(typeof navItems==='undefined'||!Array.isArray(navItems))return;
  if(navItems.some(item=>item&&item[0]==='review-table'))return;
  const index=navItems.findIndex(item=>item&&item[0]==='reviews');
  navItems.splice(index>=0?index+1:navItems.length,0,['review-table','Tabela de revisões']);
 }
 function stripTables(html){
  const template=document.createElement('template');template.innerHTML=String(html||'');
  template.content.querySelectorAll('.review-calendar-card,.review-history-global,.qi-review-overview').forEach(node=>node.remove());
  return template.innerHTML;
 }
 function viewHtml(){return head('Tabela de revisões','Visão global de disciplinas, conteúdos estudados, revisões realizadas e próximas datas programadas.')+'<div class="notice review-table-intro"><strong>Como usar:</strong> consulte o mês, clique numa revisão para ajustar ou registrar o resultado e use o histórico para acompanhar a evolução do conteúdo.</div><div class="review-table-page">'+directTablesHtml()+'</div>';}
 globalThis.reviewTableView=viewHtml;
 function refreshMonth(delta){
  reviewTableMonth=delta==='current'?currentServerDate().slice(0,7)+'-01':shiftMonth(reviewTableMonth,delta);
  const page=document.querySelector('.review-table-page');if(page)page.innerHTML=directTablesHtml();
  bindPageActions();if(typeof globalThis.applyDisciplineColors==='function')globalThis.applyDisciplineColors();
 }
 function bindPageActions(){
  const prev=document.getElementById('review-table-prev'),current=document.getElementById('review-table-current'),next=document.getElementById('review-table-next');
  if(prev)prev.onclick=()=>refreshMonth(-1);if(current)current.onclick=()=>refreshMonth('current');if(next)next.onclick=()=>refreshMonth(1);
 }

 installNavigation();
 if(typeof reviewsView==='function'&&sourceReviewView)reviewsView=function(){try{return stripTables(sourceReviewView());}catch(error){console.error(error);return sourceReviewView();}};
 if(typeof render==='function'){
  const baseRender=render;
  render=function(){
   installNavigation();
   if(typeof view!=='undefined'&&view==='review-table'&&!(typeof ME!=='undefined'&&ME.must_change)){
    const desired=view;view='home';baseRender.apply(this,arguments);view=desired;
    if(typeof renderNav==='function')renderNav();
    const main=document.querySelector('#main');if(main)main.innerHTML=viewHtml();
    queueMicrotask(()=>{bindPageActions();if(typeof globalThis.applyDisciplineColors==='function')globalThis.applyDisciplineColors();});
    return;
   }
   return baseRender.apply(this,arguments);
  };
 }
 document.addEventListener('DOMContentLoaded',()=>{installNavigation();if(typeof renderNav==='function')renderNav();},{once:true});
})();
'''


def patch_static():
    static=ROOT/'static'
    (static/'review_table_page.js').write_text(JS,encoding='utf-8')
    html_path=static/'app.html';html=html_path.read_text(encoding='utf-8')
    html=re.sub(r'/static/review_table_page\.js\?v=[^"\']+','/static/review_table_page.js?v=5.4.0',html)
    html_path.write_text(html,encoding='utf-8')


def main():
    patch_static()
    print('MEUCRONOGRAMA_REVIEW_TABLE_DIRECT_READY: dedicated page renders directly from contents, sessions and feedback.',flush=True)


if __name__=='__main__':main()
