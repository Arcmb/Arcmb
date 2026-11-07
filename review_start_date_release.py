"""Add learner-configurable review cycle start date.

The setting reviewStartDate is stored in learner profile settings. It acts as
an operational floor for pending review scheduling without deleting history.
"""
from pathlib import Path
import re

ROOT=Path(__file__).resolve().parent
PMARK="# === REVIEW START DATE V1 ==="
JMARK="// === REVIEW START DATE V1 ==="
CMARK="/* === REVIEW START DATE V1 === */"

REVIEW_MODEL=r''' function reviewModel(row){
  const events={},feedback=linkedFeedback(row),sessions=linkedSessions(row),studyDate=validDate(row.studiedOn||row.createdOn||row.date||''),floor=reviewCycleStartDate();
  if(studyDate)putEvent(events,studyDate,{kind:'study',label:'Início',detail:'Primeiro estudo',contentId:row.id||row._rowId});
  const currentFeedback=feedback.filter(item=>['done','partial','missed'].includes(item.status)&&(!floor||String(item.date||'')>=floor));
  const historicalFeedback=feedback.filter(item=>['done','partial','missed'].includes(item.status));
  const currentSessions=sessions.filter(item=>item.status==='planned'&&(!floor||String(item.date||'')>=floor));
  const reviewByDate=new Map();
  function remember(date,event,priority){
   date=validDate(date);if(!date)return;if(floor&&date<floor)return;
   const current=reviewByDate.get(date),incoming={...event,_priority:priority};
   if(!current||priority>=current._priority)reviewByDate.set(date,incoming);
  }
  currentFeedback.forEach(item=>{
   const kind=item.status==='done'?'done':item.status==='partial'?'partial':'overdue';
   remember(item.date,{kind,detail:item.status==='done'?'Feita':item.status==='partial'?'Parcial':'Atrasada',contentId:row.id||row._rowId},30);
  });
  const plannedByDate=new Map();
  currentSessions.forEach(session=>{
   const date=validDate(session.date);if(!date)return;
   const group=plannedByDate.get(date)||[];group.push(session);plannedByDate.set(date,group);
  });
  plannedByDate.forEach((group,date)=>{
   const past=date<currentServerDate(),parts=unique(group.map(session=>session.reviewPart==='theory'?'Teoria':session.reviewPart==='exercise'?'Exercícios':'Revisão'));
   remember(date,{kind:past?'overdue':'planned',detail:past?'Atrasada':parts.join(' + ')||'Programada',contentId:row.id||row._rowId,sessionId:group[0]?.id||''},20);
  });
  let dueDate=validDate(row.nextDue);
  if(floor&&(!dueDate||dueDate<floor))dueDate=floor;
  if(dueDate)remember(dueDate,{kind:dueDate<currentServerDate()?'overdue':'planned',detail:dueDate<currentServerDate()?'Atrasada':'Programada',contentId:row.id||row._rowId},10);
  const intervals=asArray(state().settings?.intervals).map(Number).filter(value=>Number.isFinite(value)&&value>0),baseDates=[...reviewByDate.keys()].sort();
  let cursor=baseDates.at(-1)||dueDate||floor||studyDate||'';
  const stage=floor?0:Math.max(0,Math.min(Math.max(0,intervals.length-1),Number(row.stage||0)));
  const startIndex=Math.max(stage+1,baseDates.length),projected=[];
  for(let index=startIndex;index<intervals.length&&cursor&&projected.length<4;index++){
   cursor=addDays(cursor,intervals[index]);if(!cursor)break;if(reviewByDate.has(cursor))continue;
   projected.push(cursor);remember(cursor,{kind:cursor<currentServerDate()?'overdue':'planned',detail:cursor<currentServerDate()?'Atrasada':'Prevista',contentId:row.id||row._rowId,projection:true},0);
  }
  const orderedReviews=[...reviewByDate.entries()].sort((a,b)=>a[0].localeCompare(b[0]));
  orderedReviews.forEach(([date,event],index)=>{
   const clean={...event,label:(index+1)+'ª revisão'};delete clean._priority;putEvent(events,date,clean);
  });
  const eventDates=Object.keys(events).sort(),next=orderedReviews.find(([date,event])=>date>=currentServerDate()&&event.kind==='planned')?.[0]||dueDate||'',lastCompleted=historicalFeedback.filter(item=>item.status==='done'||item.status==='partial').at(-1)||null;
  return {row,events,eventDates,feedback,sessions,currentFeedback,currentSessions,completed:historicalFeedback,projected,next,lastCompleted,discipline:disciplineName(row.subjectId,row.sourceDiscipline),subject:String(row.title||'Conteúdo')};
 }'''

CSS=r'''
/* === REVIEW START DATE V1 === */
.rt-start-card{display:flex;align-items:end;justify-content:space-between;gap:16px;padding:14px 16px;margin-bottom:14px;border:1px solid #ead7dc;border-radius:14px;background:#fff8f9}
.rt-start-copy{display:grid;gap:4px;max-width:720px}.rt-start-copy strong{color:#5a2630;font-size:13px}.rt-start-copy small{color:#7a6870;line-height:1.35}
.rt-start-actions{display:flex;align-items:end;gap:8px;flex-wrap:wrap}.rt-start-actions label{display:grid;gap:5px;font-size:11px;font-weight:800;color:#6d5860}.rt-start-actions input[type=date]{min-height:38px;padding:7px 9px;background:#fff}.rt-start-actions button{min-height:38px}
@media(max-width:900px){.rt-start-card{align-items:stretch;flex-direction:column}.rt-start-actions{align-items:stretch}.rt-start-actions label{flex:1 1 180px}}
'''

def patch_planner():
    path=ROOT/'planner.py'
    text=path.read_text(encoding='utf-8')
    if PMARK in text:return
    anchor="    s=p['settings'];a=minute(s['sleepStart']);b=minute(s['sleepEnd'])\n"
    if anchor not in text:raise RuntimeError('Âncora das configurações não encontrada em planner.py.')
    text=text.replace(anchor,"    s=p['settings'];s.setdefault('reviewStartDate','')\n    if s.get('reviewStartDate'):date(s['reviewStartDate'])\n    a=minute(s['sleepStart']);b=minute(s['sleepEnd'])\n",1)
    anchor="    for c in due:\n        linked=lambda x:(x.get('contentId')==c['id'] or x.get('reviewContentId')==c['id']) and x['kind']=='review' and x['status']=='planned'\n        existing=[x for x in p['sessions'] if linked(x)]\n"
    if anchor not in text:raise RuntimeError('Âncora do agendamento de revisões não encontrada em planner.py.')
    replacement="    review_start=str(s.get('reviewStartDate') or '').strip()\n    for c in due:\n        if review_start and c.get('nextDue','')<review_start:c=dict(c,nextDue=review_start)\n        linked=lambda x:(x.get('contentId')==c['id'] or x.get('reviewContentId')==c['id']) and x['kind']=='review' and x['status']=='planned'\n        existing=[x for x in p['sessions'] if linked(x) and (not review_start or x.get('date','')>=review_start)]\n"
    text=text.replace(anchor,replacement,1)
    path.write_text(text.rstrip()+"\n\n"+PMARK+"\n",encoding='utf-8')

def patch_review_js():
    path=ROOT/'static'/'review_table_page.js'
    text=path.read_text(encoding='utf-8')
    if JMARK in text:return
    anchor=" function state(){return typeof P==='object'&&P?P:{subjects:[],contents:[],sessions:[],feedback:[],settings:{}};}\n"
    if anchor not in text:raise RuntimeError('Âncora state() não encontrada.')
    text=text.replace(anchor,anchor+" function reviewCycleStartDate(){return validDate(state().settings?.reviewStartDate||'');}\n",1)
    start=text.find(' function reviewModel(row){')
    end=text.find(' function models(){return reviewRows().map(reviewModel);}',start)
    if start<0 or end<0:raise RuntimeError('reviewModel não encontrado.')
    text=text[:start]+REVIEW_MODEL+"\n"+text[end:]
    needle='return `<section class="card rt-matrix-card"><div class="rt-panel-head">'
    if needle not in text:raise RuntimeError('Template principal da tabela não encontrado.')
    start_card=(
        'return `<section class="card rt-matrix-card">'
        '<div class="rt-start-card"><div class="rt-start-copy"><strong>Iniciar minhas revisões em</strong>'
        '<small>Define a data-base do ciclo atual. O histórico anterior é preservado, mas pendências anteriores a essa data deixam de acumular e o sistema volta a calcular as revisões a partir dela.</small></div>'
        '<div class="rt-start-actions"><label>Data de início<input id="rt-review-start" type="date" value="${escapeHtml(reviewCycleStartDate())}"></label>'
        '<button type="button" class="primary" id="rt-review-start-save">Aplicar e recalcular</button>'
        '<button type="button" class="secondary" id="rt-review-start-clear">Usar ciclo original</button></div></div>'
        '<div class="rt-panel-head">'
    )
    text=text.replace(needle,start_card,1)
    anchor=" function bindPageActions(){const sort=document.getElementById('rt-sort'),discipline=document.getElementById('rt-discipline'),date=document.getElementById('rt-date');"
    if anchor not in text:raise RuntimeError('bindPageActions não encontrado.')
    replacement=" async function persistReviewStartDate(value){\n  value=String(value||'').trim();if(value&&!validDate(value))return;\n  const next={...(state().settings||{}),reviewStartDate:value};\n  try{\n   if(typeof save!=='function')throw new Error('Função de salvamento indisponível.');\n   await save('settings',next);\n   if(state().settings)state().settings.reviewStartDate=value;\n   reviewTableDate='';refreshPage();\n   if(typeof toast==='function')toast(value?'Novo ciclo de revisões iniciado em '+formatDate(value)+'.':'Data-base removida. Ciclo original restaurado.');\n  }catch(error){console.error(error);if(typeof toast==='function')toast(error?.message||'Não foi possível salvar a data.');else alert(error?.message||'Não foi possível salvar a data.');}\n }\n function bindPageActions(){const sort=document.getElementById('rt-sort'),discipline=document.getElementById('rt-discipline'),date=document.getElementById('rt-date');"
    text=text.replace(anchor,replacement,1)
    anchor="if(print)print.onclick=()=>window.print();}"
    if anchor not in text:raise RuntimeError('Final de bindPageActions não encontrado.')
    text=text.replace(anchor,"if(print)print.onclick=()=>window.print();const startInput=document.getElementById('rt-review-start'),startSave=document.getElementById('rt-review-start-save'),startClear=document.getElementById('rt-review-start-clear');if(startSave)startSave.onclick=()=>persistReviewStartDate(startInput?.value||'');if(startClear)startClear.onclick=()=>persistReviewStartDate('');}",1)
    text=text.replace('// === CHRONOLOGICAL REVIEW ORDER V4 ===','// === CHRONOLOGICAL REVIEW ORDER V4 ===\n'+JMARK,1)
    path.write_text(text,encoding='utf-8')

def patch_css_and_cache():
    css_path=ROOT/'static'/'style.css'
    css=css_path.read_text(encoding='utf-8')
    if CMARK not in css:css=css.rstrip()+"\n\n"+CSS.rstrip()+"\n"
    css_path.write_text(css,encoding='utf-8')
    html_path=ROOT/'static'/'app.html'
    html=html_path.read_text(encoding='utf-8')
    html=re.sub(r'/static/review_table_page\.js\?v=5\.4\.0-layout4[^"\']*','/static/review_table_page.js?v=5.4.0-layout4&start=1',html)
    html=re.sub(r'/static/style\.css\?v=5\.1\.0-layout4[^"\']*','/static/style.css?v=5.1.0-layout4&start=1',html)
    html_path.write_text(html,encoding='utf-8')

def main():
    patch_planner();patch_review_js();patch_css_and_cache()
    print('MEUCRONOGRAMA_REVIEW_START_DATE_READY: learner review start date, preserved history and scheduling floor installed.',flush=True)

if __name__=='__main__':main()
