"""Correct review numbering and compact the review matrix.

The previous renderer assigned ordinals by source order: feedback first, then
planned sessions, then content.nextDue. A due date earlier than a future session
could therefore be labelled 2nd review while the later session was labelled 1st.
This patch consolidates every review occurrence by date, applies actual-result
precedence, sorts chronologically, and only then assigns 1st, 2nd, 3rd...
It also reduces row, cell and marker dimensions without sacrificing legibility.
"""
from pathlib import Path
import re

ROOT=Path(__file__).resolve().parent
JS_MARK='// === CHRONOLOGICAL REVIEW ORDER V4 ==='
CSS_MARK='/* === REVIEW MATRIX COMPACT DENSITY V4 === */'

REVIEW_MODEL=r''' function reviewModel(row){
  const events={},feedback=linkedFeedback(row),sessions=linkedSessions(row),completed=feedback.filter(item=>['done','partial','missed'].includes(item.status)),studyDate=validDate(row.studiedOn||row.createdOn||row.date||'');
  if(studyDate)putEvent(events,studyDate,{kind:'study',label:'Início',detail:'Primeiro estudo',contentId:row.id||row._rowId});

  // Every review source is consolidated by date before numbering.
  const reviewByDate=new Map();
  function remember(date,event,priority){
   date=validDate(date);if(!date)return;
   const current=reviewByDate.get(date),incoming={...event,_priority:priority};
   if(!current||priority>current._priority||priority===current._priority)reviewByDate.set(date,incoming);
  }

  // A recorded result is authoritative when it shares a date with a plan.
  completed.forEach(item=>{
   const kind=item.status==='done'?'done':item.status==='partial'?'partial':'overdue';
   remember(item.date,{kind,detail:item.status==='done'?'Feita':item.status==='partial'?'Parcial':'Atrasada',contentId:row.id||row._rowId},30);
  });

  // Theory and exercises on the same date form one review occurrence.
  const plannedByDate=new Map();
  sessions.filter(item=>item.status==='planned').forEach(session=>{
   const date=validDate(session.date);if(!date)return;
   const group=plannedByDate.get(date)||[];group.push(session);plannedByDate.set(date,group);
  });
  plannedByDate.forEach((group,date)=>{
   const past=date<currentServerDate(),parts=unique(group.map(session=>session.reviewPart==='theory'?'Teoria':session.reviewPart==='exercise'?'Exercícios':'Revisão'));
   remember(date,{kind:past?'overdue':'planned',detail:past?'Atrasada':parts.join(' + ')||'Programada',contentId:row.id||row._rowId,sessionId:group[0]?.id||''},20);
  });

  // nextDue is used only when no stronger event already exists on that date.
  const dueDate=validDate(row.nextDue);
  if(dueDate)remember(dueDate,{kind:dueDate<currentServerDate()?'overdue':'planned',detail:dueDate<currentServerDate()?'Atrasada':'Programada',contentId:row.id||row._rowId},10);

  // Projections continue after the latest known review date.
  const intervals=asArray(state().settings?.intervals).map(Number).filter(value=>Number.isFinite(value)&&value>0),baseDates=[...reviewByDate.keys()].sort();
  let cursor=baseDates.at(-1)||studyDate||'';
  const stage=Math.max(0,Math.min(Math.max(0,intervals.length-1),Number(row.stage||0))),startIndex=Math.max(stage+1,baseDates.length),projected=[];
  for(let index=startIndex;index<intervals.length&&cursor&&projected.length<4;index++){
   cursor=addDays(cursor,intervals[index]);if(!cursor)break;if(reviewByDate.has(cursor))continue;
   projected.push(cursor);remember(cursor,{kind:cursor<currentServerDate()?'overdue':'planned',detail:cursor<currentServerDate()?'Atrasada':'Prevista',contentId:row.id||row._rowId,projection:true},0);
  }

  // Ordinals are assigned only after every occurrence is chronologically sorted.
  const orderedReviews=[...reviewByDate.entries()].sort((a,b)=>a[0].localeCompare(b[0]));
  orderedReviews.forEach(([date,event],index)=>{
   const clean={...event,label:(index+1)+'ª revisão'};delete clean._priority;putEvent(events,date,clean);
  });

  const eventDates=Object.keys(events).sort(),next=orderedReviews.find(([date,event])=>date>=currentServerDate()&&event.kind==='planned')?.[0]||dueDate||'',lastCompleted=completed.filter(item=>item.status==='done'||item.status==='partial').at(-1)||null;
  return {row,events,eventDates,feedback,sessions,completed,projected,next,lastCompleted,discipline:disciplineName(row.subjectId,row.sourceDiscipline),subject:String(row.title||'Conteúdo')};
 }'''

CSS=r'''
/* === REVIEW MATRIX COMPACT DENSITY V4 === */
.rt-matrix-card,.rt-history-card{padding:18px!important}
.rt-matrix th,.rt-matrix td{padding:6px 7px!important;min-width:90px!important}
.rt-matrix tbody td{height:48px!important}
.rt-matrix thead th:first-child{min-width:255px!important}
.rt-matrix td.rt-subject{min-width:255px!important;max-width:300px!important;padding:7px 12px!important}
.rt-matrix td.rt-subject strong{font-size:12px!important;line-height:1.22!important}
.rt-matrix td.rt-subject small{font-size:10px!important;line-height:1.15!important;margin-top:2px!important}
.rt-event{min-width:52px!important;min-height:38px!important;border-radius:8px!important;padding:5px 4px!important;box-shadow:inset 0 0 0 1px rgba(41,70,95,.035)}
.rt-event strong{font-size:11px!important;line-height:1.1!important}
.rt-event small{font-size:9px!important;line-height:1.12!important;margin-top:2px!important}
.rt-matrix th span{font-size:12px!important}.rt-matrix th small{font-size:9px!important;margin-top:1px!important}
@media(max-width:1200px){.rt-matrix thead th:first-child,.rt-matrix td.rt-subject{min-width:220px!important;max-width:255px!important}.rt-matrix th,.rt-matrix td{min-width:82px!important}}
@media(max-width:760px){.rt-matrix-card,.rt-history-card{padding:12px!important}.rt-matrix thead th:first-child,.rt-matrix td.rt-subject{min-width:180px!important;max-width:205px!important}.rt-matrix th,.rt-matrix td{min-width:76px!important;padding:5px!important}.rt-event{min-width:48px!important;min-height:36px!important;padding:4px 3px!important}}
'''


def patch_js():
    path=ROOT/'static'/'review_table_page.js'
    text=path.read_text(encoding='utf-8')
    start=text.find(' function reviewModel(row){')
    model_end=text.find(' function models(){return reviewRows().map(reviewModel);}',start)
    if start<0 or model_end<0:
        raise RuntimeError('Não foi possível localizar reviewModel no renderizador da tabela.')
    text=text[:start]+REVIEW_MODEL+'\n'+text[model_end:]
    if JS_MARK not in text:
        text=text.replace('// === REVIEW MATRIX AND HISTORY LAYOUT V3 ===','// === REVIEW MATRIX AND HISTORY LAYOUT V3 ===\n'+JS_MARK,1)
    path.write_text(text,encoding='utf-8')


def patch_css():
    path=ROOT/'static'/'style.css'
    text=path.read_text(encoding='utf-8')
    if CSS_MARK not in text:text=text.rstrip()+'\n\n'+CSS.rstrip()+'\n'
    path.write_text(text,encoding='utf-8')


def bump_cache():
    path=ROOT/'static'/'app.html'
    text=path.read_text(encoding='utf-8')
    text=re.sub(r'/static/review_table_page\.js\?v=[^"\']+','/static/review_table_page.js?v=5.4.0-layout4',text)
    text=re.sub(r'/static/style\.css\?v=[^"\']+','/static/style.css?v=5.1.0-layout4',text)
    path.write_text(text,encoding='utf-8')


def main():
    patch_js();patch_css();bump_cache()
    print('MEUCRONOGRAMA_REVIEW_SEQUENCE_DENSITY_READY: chronological numbering and compact rows installed.',flush=True)


if __name__=='__main__':main()
