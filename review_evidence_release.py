from pathlib import Path

ROOT=Path(__file__).resolve().parent
PMARK="# === REVIEW EVIDENCE V1 ==="
JMARK="// === REVIEW EVIDENCE V1 ==="

p=ROOT/"planner.py"
t=p.read_text(encoding="utf-8")
if PMARK not in t:
    old="f=dict(id=uid(),sessionId=session['id']if session else '',subjectId=session['subjectId']if session else c['subjectId'],contentId=c['id']if c else '',date=d,status=data['status'],actualMin=int(data['actualMin']),total=int(data.get('total',0)),correct=int(data.get('correct',0)),help=data.get('help','none'),confidence=data.get('confidence','medium'),reason=data.get('reason',''),detail=data.get('detail',''),notes=data.get('notes',''),at=now().isoformat())"
    new="f=dict(id=uid(),sessionId=session['id']if session else '',subjectId=session['subjectId']if session else c['subjectId'],contentId=c['id']if c else '',date=d,status=data['status'],actualMin=int(data['actualMin']),total=int(data.get('total',0)),correct=int(data.get('correct',0)),help=data.get('help','none'),confidence=data.get('confidence','medium'),reason=data.get('reason',''),detail=data.get('detail',''),notes=str(data.get('notes',''))[:1200],methods=[str(x) for x in data.get('methods',[]) if str(x) in ('questoes','correcao','resumo','flashcards','releitura','videoaula','explicacao','mapa','monitoria','outro')][:12],monitoring=bool(data.get('monitoring',False)),monitoringNotes=str(data.get('monitoringNotes',''))[:500],reviewDescription=str(data.get('reviewDescription',''))[:1200],perceivedDifficulty=max(1,min(5,int(data.get('perceivedDifficulty',3) or 3))),needsAttention=bool(data.get('needsAttention',False)),at=now().isoformat())"
    if old not in t: raise RuntimeError("feedback anchor")
    t=t.replace(old,new,1)
    a="if f['status']=='done' and rate is not None and rate>=.8 and f['help']=='none' and ev['total']>=6 and ev['days']>=2 and ev['rate']>=.8:"
    b="if f['status']=='done' and rate is not None and rate>=.8 and f['help']=='none' and not f.get('needsAttention') and f.get('perceivedDifficulty',3)<=3 and ev['total']>=6 and ev['days']>=2 and ev['rate']>=.8:"
    if a not in t: raise RuntimeError("advance anchor")
    t=t.replace(a,b,1)
    a="elif rate is not None and(rate<.6 or f['help']=='full'):"
    b="elif (rate is not None and rate<.6) or f['help']=='full' or f.get('needsAttention') or f.get('perceivedDifficulty',3)>=4:"
    if a not in t: raise RuntimeError("attention anchor")
    t=t.replace(a,b,1)
    p.write_text(t.rstrip()+"\n\n"+PMARK+"\n",encoding="utf-8")

p=ROOT/"static"/"app.js"
t=p.read_text(encoding="utf-8")
if JMARK not in t:
    a="\${select('Confiança nas respostas','confidence','medium',[['low','Baixa'],['medium','Média'],['high','Alta']])}\${select('Obstáculo, quando houver','reason'"
    b="\${select('Confiança nas respostas','confidence','medium',[['low','Baixa'],['medium','Média'],['high','Alta']])}\${select('Dificuldade percebida','perceivedDifficulty','3',[['1','Muito fácil'],['2','Fácil'],['3','Moderada'],['4','Difícil'],['5','Muito difícil']])}\${select('Fez atendimento de monitoria?','monitoring','no',[['no','Não'],['yes','Sim']])}\${select('Obstáculo, quando houver','reason'"
    if a not in t: raise RuntimeError("form select anchor")
    t=t.replace(a,b,1)
    a='</div><div id="follow-up"></div>\${area(\'Observações\',\'notes\',\'\')}'
    b='</div><h3>Como você revisou?</h3><div class="check-list"><label><input type="checkbox" name="method_questoes"> Questões</label><label><input type="checkbox" name="method_correcao"> Refiz questões erradas / correção</label><label><input type="checkbox" name="method_resumo"> Resumo ou fichamento</label><label><input type="checkbox" name="method_flashcards"> Flashcards</label><label><input type="checkbox" name="method_releitura"> Releitura</label><label><input type="checkbox" name="method_videoaula"> Videoaula</label><label><input type="checkbox" name="method_explicacao"> Expliquei o conteúdo</label><label><input type="checkbox" name="method_mapa"> Mapa mental</label><label><input type="checkbox" name="method_monitoria"> Monitoria</label><label><input type="checkbox" name="method_outro"> Outro</label></div><div class="check-list"><label><input type="checkbox" name="needsAttention"> Este conteúdo precisa de mais atenção</label></div><div id="follow-up"></div>\${input(\'Observação sobre a monitoria\',\'monitoringNotes\',\'\',\'text\',\'maxlength="500"\')}\${area(\'Descreva como você revisou\',\'reviewDescription\',\'\')}\${area(\'Outras observações\',\'notes\',\'\')}'
    if a not in t: raise RuntimeError("form details anchor")
    t=t.replace(a,b,1)
    a="await save('feedback',{...d,sessionId:sessionId||'',contentId:contentId||'',actualMin:+d.actualMin,total:+d.total,correct:+d.correct});"
    b="const methods=['questoes','correcao','resumo','flashcards','releitura','videoaula','explicacao','mapa','monitoria','outro'].filter(k=>f.elements['method_'+k]?.checked);await save('feedback',{...d,sessionId:sessionId||'',contentId:contentId||'',actualMin:+d.actualMin,total:+d.total,correct:+d.correct,perceivedDifficulty:+d.perceivedDifficulty,monitoring:d.monitoring==='yes',needsAttention:!!f.elements.needsAttention?.checked,methods});"
    if a not in t: raise RuntimeError("save anchor")
    t=t.replace(a,b,1)
    a="return head('Minhas revisões','Uma fila por conteúdo, sem criar cópias diárias da mesma pendência.')"
    b="return head('Minhas revisões','Revisões periódicas com registro de questões, monitoria, método utilizado e percepção de dificuldade.')"
    t=t.replace(a,b,1)
    a="<p>\${esc(f.message||'Resultado registrado.')}</p>"
    b="<p>\${esc(f.message||'Resultado registrado.')}</p>\${f.perceivedDifficulty?'<p>Dificuldade percebida: '+esc({1:'Muito fácil',2:'Fácil',3:'Moderada',4:'Difícil',5:'Muito difícil'}[f.perceivedDifficulty]||f.perceivedDifficulty)+(f.needsAttention?' · Precisa de mais atenção':'')+(f.monitoring?' · Fez monitoria':'')+'</p>':''}\${f.reviewDescription?'<small>Como revisou: '+esc(f.reviewDescription)+'</small>':''}"
    if a not in t: raise RuntimeError("checks anchor")
    t=t.replace(a,b,1)
    p.write_text(t.rstrip()+"\n\n"+JMARK+"\n",encoding="utf-8")

print("MEUCRONOGRAMA_REVIEW_EVIDENCE_READY",flush=True)
