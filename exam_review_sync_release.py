from pathlib import Path
import re

ROOT=Path(__file__).resolve().parent
PY_MARKER="# === EXAM ERROR REVIEW SYNC V1 ==="
JS_MARKER="// === EXAM ERROR REVIEW SYNC V1 ==="

PY_EXT=r'''
# === EXAM ERROR REVIEW SYNC V1 ===
import json as _er_json
import hashlib as _er_hash
import unicodedata as _er_ud
from datetime import date as _er_date

def _er_load(value, fallback):
    try:
        out=_er_json.loads(value or '')
    except Exception:
        return fallback
    return out if isinstance(out,type(fallback)) else fallback

def _er_norm(value):
    raw=str(value or '').strip().lower()
    raw=''.join(ch for ch in _er_ud.normalize('NFD',raw) if _er_ud.category(ch)!='Mn')
    return ' '.join(raw.split())

def _er_lang(value):
    n=_er_norm(value)
    if n in ('ingles','english','en','ing'): return 'ingles'
    if n in ('espanhol','espanol','spanish','es','esp'): return 'espanhol'
    return n

def _er_target(app,c,user,target_id,HTTPError=None):
    target_id=str(target_id or user.get('id') or '')
    row=app.db.execute(c,'SELECT id,username,name,role,active FROM hmay_users WHERE id=?',(target_id,)).fetchone()
    if not row:
        raise ValueError('Conta do aluno não encontrada.')
    target=dict(row)
    actor=str(user.get('id') or '')
    role=str(user.get('role') or '')
    target_role=str(target.get('role') or '')
    allowed=(target_id==actor or role=='master' or (role=='coordenador' and target_role in ('user','aluno')))
    if not allowed:
        if HTTPError: raise HTTPError(403,'Sem permissão para atualizar revisões desta conta.')
        raise PermissionError('Sem permissão para atualizar revisões desta conta.')
    return target

def _er_exam_errors(app,c,target_id):
    rows=app.db.execute(c,'SELECT * FROM hmay_performance WHERE user_id=? ORDER BY applied_on,activity,id',(target_id,)).fetchall()
    cache={}
    groups={}
    for src in rows:
        row=dict(src)
        metadata=_er_load(row.get('metadata'),{})
        metrics=_er_load(row.get('metrics'),{})
        exam_id=str(metadata.get('_exam_id') or '')
        if not exam_id: continue
        if exam_id not in cache:
            ex=app.db.execute(c,'SELECT * FROM hmay_exams WHERE id=?',(exam_id,)).fetchone()
            cache[exam_id]=dict(ex) if ex else None
        exam=cache.get(exam_id)
        if not exam: continue
        items=_er_load(exam.get('items'),[])
        student_lang=_er_lang(metadata.get('L.E') or metadata.get('LINGUA ESTRANGEIRA') or '')
        for item in items:
            if not isinstance(item,dict): continue
            try: number=int(item.get('number') or 0)
            except Exception: continue
            if not 1<=number<=180: continue
            item_lang=_er_lang(item.get('language') or '')
            if item_lang and student_lang and item_lang!=student_lang: continue
            answer=str(item.get('answer') or '').strip().upper()
            if not answer or answer=='ANULADA': continue
            metric=metrics.get('questao:%03d'%number,{})
            if not isinstance(metric,dict): continue
            try: result=int(metric.get('correct'))
            except Exception: continue
            if result!=0: continue
            area=str(item.get('area') or '').strip().upper()
            discipline=str(item.get('discipline') or 'Não informado').strip()
            topic=str(item.get('topic') or '').strip()
            subject=str(item.get('subject') or '').strip()
            skill=str(item.get('skill') or '').strip()
            title=subject or topic or skill or ('Erros de '+discipline)
            key='|'.join([_er_norm(area),_er_norm(discipline),_er_norm(topic),_er_norm(title)])
            bucket=groups.setdefault(key,dict(area=area,discipline=discipline,topic=topic,title=title,errors=[]))
            activity=str(row.get('activity') or exam.get('title') or 'Avaliação')
            applied=str(row.get('applied_on') or exam.get('applied_on') or '')
            raw_key=str(row.get('activity_key') or activity)
            err_hash=_er_hash.sha1((raw_key+'|'+applied+'|'+str(number)+'|'+area).encode('utf-8')).hexdigest()[:5].upper()
            error_id='ERR-%s-%s-Q%03d-%s'%((applied.replace('-','') or 'SEM_DATA'),(area or 'GERAL'),number,err_hash)
            response=str(metric.get('response') or metric.get('selected') or metric.get('answer') or '').strip().upper()
            bucket['errors'].append(dict(
                id=error_id,simulation=activity,date=applied,question=number,area=area,
                discipline=discipline,topic=topic,subject=subject,skill=skill,
                answer=answer,response=response,color=str(metadata.get('COR DA PROVA') or ''),
                language=str(metadata.get('L.E') or '')
            ))
    for bucket in groups.values():
        unique={}
        for err in bucket['errors']: unique[err['id']]=err
        bucket['errors']=sorted(unique.values(),key=lambda x:(x.get('date',''),x.get('simulation',''),x.get('question',0)))
    return groups

def _er_sync_target(app,c,user,target_id,HTTPError=None):
    target=_er_target(app,c,user,target_id,HTTPError)
    state=app.db.execute(c,'SELECT profile,version FROM hmay_state WHERE user_id=?',(target['id'],)).fetchone()
    if not state: raise ValueError('Planejamento do aluno não encontrado.')
    profile=_er_load(state['profile'],{})
    contents=profile.get('contents') if isinstance(profile.get('contents'),list) else []
    subjects=profile.get('subjects') if isinstance(profile.get('subjects'),list) else []
    subject_map={_er_norm(x.get('name')):x.get('id') for x in subjects if isinstance(x,dict) and x.get('id')}
    existing={x.get('sourceKey'):x for x in contents if isinstance(x,dict) and x.get('sourceType')=='exam_error' and x.get('sourceKey')}
    groups=_er_exam_errors(app,c,target['id'])
    created=updated=0
    today=str(P.today())
    default_review=20
    try: default_review=max(10,min(180,int(profile.get('settings',{}).get('reviewMin',20))))
    except Exception: pass
    for key,bucket in groups.items():
        stable='examerr_'+_er_hash.sha1(key.encode('utf-8')).hexdigest()[:16]
        errors=bucket['errors']
        latest=max((x.get('date') or '' for x in errors),default='')
        first=min((x.get('date') or '' for x in errors),default='')
        subject_id=subject_map.get(_er_norm(bucket['discipline']),'')
        source_sims=sorted(set(x.get('simulation') for x in errors if x.get('simulation')))
        source_skills=sorted(set(x.get('skill') for x in errors if x.get('skill')))
        source_questions=sorted(set(int(x.get('question') or 0) for x in errors if x.get('question')))
        row=existing.get(stable) or existing.get(key)
        if row is None:
            row=dict(
                id=stable,subjectId=subject_id,title=bucket['title'],topic=bucket['topic'],
                status='studied',paused=False,studyMinutes=0,reviewMinutes=default_review,
                difficulty=3,studiedOn=latest or today,studiedTime='12:00',
                nextDue=today,stage=0,material='',notes='Gerado automaticamente a partir de erros de avaliações importadas.',
                sourceType='exam_error',sourceKey=stable,sourceDiscipline=bucket['discipline'],
                sourceArea=bucket['area'],examErrors=errors,errorCount=len(errors),
                firstErrorDate=first,lastErrorDate=latest,sourceSimulations=source_sims,
                sourceSkills=source_skills,sourceQuestions=source_questions
            )
            contents.append(row);existing[stable]=row;created+=1
        else:
            old_ids={x.get('id') for x in row.get('examErrors',[]) if isinstance(x,dict)}
            new_ids={x.get('id') for x in errors}
            added=bool(new_ids-old_ids)
            before=(row.get('errorCount'),row.get('lastErrorDate'),row.get('subjectId'),row.get('title'),old_ids)
            row.update(sourceKey=stable,sourceDiscipline=bucket['discipline'],sourceArea=bucket['area'],
                       examErrors=errors,errorCount=len(errors),firstErrorDate=first,lastErrorDate=latest,
                       sourceSimulations=source_sims,sourceSkills=source_skills,sourceQuestions=source_questions,
                       title=bucket['title'],topic=bucket['topic'])
            if subject_id: row['subjectId']=subject_id
            if added and not row.get('paused'):
                row['nextDue']=today
                try: row['stage']=max(0,min(1,int(row.get('stage',0))))
                except Exception: row['stage']=0
            after=(row.get('errorCount'),row.get('lastErrorDate'),row.get('subjectId'),row.get('title'),new_ids)
            if added or before!=after: updated+=1
    changed=bool(created or updated)
    if changed:
        profile['contents']=contents
        app.db.execute(c,'UPDATE hmay_state SET profile=?,version=version+1,updated_at=? WHERE user_id=?',
                       (_er_json.dumps(profile,ensure_ascii=False,separators=(',',':')),P.now().isoformat(),target['id']))
        try: app.event(c,user,target['id'],'exam_error_reviews_sync')
        except Exception: pass
    return dict(changed=changed,created=created,updated=updated,groups=len(groups),
                errors=sum(len(x['errors']) for x in groups.values()),targetId=target['id'])

_er_original_handle=handle
def handle(app,c,user,path,method,data,query,start,HTTPError):
    if path=='/api/review-errors/sync' and method=='POST':
        result=_er_sync_target(app,c,user,data.get('targetId') or user.get('id'),HTTPError)
        return app.reply(start,200,result)
    if path=='/api/review-errors/sync-batch' and method=='POST':
        ids=data.get('targetIds') if isinstance(data.get('targetIds'),list) else []
        results=[]
        seen=set()
        for target_id in ids[:500]:
            key=str(target_id or '')
            if not key or key in seen: continue
            seen.add(key)
            results.append(_er_sync_target(app,c,user,key,HTTPError))
        return app.reply(start,200,dict(results=results,changed=sum(1 for x in results if x.get('changed'))))
    return _er_original_handle(app,c,user,path,method,data,query,start,HTTPError)
'''

JS_APPEND=r'''
// === EXAM ERROR REVIEW SYNC V1 ===
let reviewErrorSyncKey='';
let reviewErrorSyncBusy=false;

function examReviewCurrentTarget(){
 return String((typeof target!=='undefined'&&target)||ME.id||'');
}
async function syncExamErrorReviews(force){
 const id=examReviewCurrentTarget();
 if(!id||reviewErrorSyncBusy||(!force&&reviewErrorSyncKey===id))return;
 reviewErrorSyncBusy=true;
 try{
  const d=await api('/api/review-errors/sync',{targetId:id});
  reviewErrorSyncKey=id;
  if(d.changed){
   await load();
   if(d.created)toast(d.created+' conteúdo(s) de revisão criado(s) a partir dos erros dos simulados.');
  }else render();
 }catch(err){
  console.error(err);
  toast('Não foi possível sincronizar os erros dos simulados: '+err.message,true);
 }finally{reviewErrorSyncBusy=false;}
}
function examReviewCard(c){
 const imported=c.sourceType==='exam_error';
 const errs=Array.isArray(c.examErrors)?c.examErrors:[];
 const discipline=imported?(c.sourceDiscipline||sub(c.subjectId)):sub(c.subjectId);
 const meta=(imported?((c.errorCount||errs.length)+' erro(s) importado(s)'):'Conteúdo cadastrado')+
  ' · '+minutes(c.reviewMinutes)+' · '+(c.paused?'Pausada':'Data-alvo: '+br(c.nextDue));
 let detail='';
 if(imported&&errs.length){
  const rows=errs.slice().reverse().map(function(e){
   let txt=(e.id||'Erro')+' · '+(e.simulation||'Avaliação')+' · Q'+String(e.question||'').padStart(3,'0');
   if(e.skill)txt+=' · '+e.skill;
   if(e.answer)txt+=' · gabarito '+e.answer;
   if(e.response)txt+=' · resposta '+e.response;
   return '<li>'+esc(txt)+'</li>';
  }).join('');
  detail='<details><summary>Ver '+errs.length+' erro(s) vinculado(s)</summary><ul>'+rows+'</ul></details>';
 }
 return '<div class="item"><div class="item-main"><strong>'+esc(c.title)+'</strong><p>'+esc(discipline)+(c.topic?' → '+esc(c.topic):'')+'</p><small>'+esc(meta)+'</small>'+detail+'</div><div class="item-actions">'+button('Registrar revisão','feedback-content','primary','data-id="'+c.id+'"')+button('Ajustar / pausar','edit-review','secondary','data-id="'+c.id+'"')+'</div></div>';
}
reviewsView=function(){
 const id=examReviewCurrentTarget();
 if(!reviewErrorSyncBusy&&reviewErrorSyncKey!==id)queueMicrotask(function(){syncExamErrorReviews(false);});
 const studied=P.contents.filter(function(x){return x.status==='studied';});
 const imported=studied.filter(function(x){return x.sourceType==='exam_error';}).sort(function(a,b){return String(a.sourceDiscipline||'').localeCompare(String(b.sourceDiscipline||''))||String(a.nextDue||'').localeCompare(String(b.nextDue||''));});
 const manual=studied.filter(function(x){return x.sourceType!=='exam_error';}).sort(function(a,b){return String(a.nextDue||'').localeCompare(String(b.nextDue||''));});
 const groups={};
 imported.forEach(function(c){const k=c.sourceDiscipline||'Não informado';(groups[k]||(groups[k]=[])).push(c);});
 let importedHtml='';
 Object.keys(groups).sort().forEach(function(name){
  importedHtml+='<section class="card"><h2>'+esc(name)+'</h2><p class="micro">Erros identificados automaticamente em simulados, testes e treinos importados.</p>'+items(groups[name].map(examReviewCard))+'</section>';
 });
 const manualHtml=manual.length?'<section class="card"><h2>Conteúdos cadastrados pelo aluno</h2>'+items(manual.map(examReviewCard))+'</section>':'';
 const emptyHtml=(!imported.length&&!manual.length)?'<section class="card">'+(reviewErrorSyncBusy?'Verificando os erros dos simulados…':'Nenhum conteúdo de revisão encontrado.')+'</section>':'';
 return head('Minhas revisões','Revisões periódicas com conteúdos estudados e erros de avaliações importadas.')+
  '<div class="notice"><strong>Erros de avaliações:</strong> questões erradas são agrupadas por disciplina, tópico e assunto. Cada questão mantém um identificador ERR próprio e entra na revisão espaçada.</div>'+
  '<div class="actions">'+button('Atualizar erros dos simulados','review-errors-refresh','secondary')+'</div>'+
  importedHtml+manualHtml+emptyHtml;
};
acts['review-errors-refresh']=function(){reviewErrorSyncKey='';return syncExamErrorReviews(true);};
'''

def main():
    model=ROOT/'model_data.py'
    text=model.read_text(encoding='utf-8')
    if PY_MARKER not in text:
        text=text.rstrip()+"\n\n"+PY_EXT+"\n"
        model.write_text(text,encoding='utf-8')

    app=ROOT/'static'/'app.js'
    text=app.read_text(encoding='utf-8')
    if JS_MARKER not in text:
        text=text.rstrip()+"\n\n"+JS_APPEND+"\n"
        app.write_text(text,encoding='utf-8')

    imp=ROOT/'static'/'result_import.js'
    if imp.exists():
        text=imp.read_text(encoding='utf-8')
        anchor="const d=await api('/api/model-data/confirm',p);\n resultImportLastSummary=d.summary||{};resultImportDraft=null;"
        repl="const d=await api('/api/model-data/confirm',p);\n const syncIds=[...new Set(Object.values(p.mapping||{}).filter(Boolean))];\n try{if(syncIds.length)await api('/api/review-errors/sync-batch',{targetIds:syncIds});}catch(err){console.warn('Falha ao sincronizar revisões de erros',err);}\n resultImportLastSummary=d.summary||{};resultImportDraft=null;"
        if anchor in text and "sync-batch" not in text:
            text=text.replace(anchor,repl,1)
            imp.write_text(text,encoding='utf-8')

    html=ROOT/'static'/'app.html'
    text=html.read_text(encoding='utf-8')
    text=re.sub(r'/static/app\.js\?v=[^"\']+','/static/app.js?v=2.9.4',text)
    text=re.sub(r'/static/result_import\.js\?v=[^"\']+','/static/result_import.js?v=2.9.4',text)
    html.write_text(text,encoding='utf-8')
    print('MEUCRONOGRAMA_EXAM_REVIEW_SYNC_READY: imported errors feed spaced reviews, including retroactive sync.',flush=True)

if __name__=='__main__':
    main()
