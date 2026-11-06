"""Improve learner profiles, discipline ordering and review visibility.

This final build-time patch:
- derives an initial discipline priority from importance and perceived difficulty;
- preserves an explicit manual priority selected by the learner;
- lets the learner sort disciplines by priority, importance, difficulty or alphabetically;
- explains clearly who each operational profile is intended for;
- adds an objective questionnaire that recommends the most suitable profile;
- brings the spreadsheet-style monthly review table to the top of Minhas revisões;
- adds the discipline name to weekly-calendar blocks.
"""
from pathlib import Path
import re

ROOT=Path(__file__).resolve().parent
PY_MARK='# === LEARNER GUIDANCE AND PRIORITY V1 ==='
JS_MARK='// === LEARNER GUIDANCE AND PRIORITY V1 ==='
CSS_MARK='/* LEARNER GUIDANCE AND PRIORITY V1 */'


def patch_planner():
    path=ROOT/'planner.py'
    text=path.read_text(encoding='utf-8')
    if PY_MARK in text:
        return
    anchor="        x.setdefault('priority',3);x.setdefault('reviewPlan',s.get('defaultReviewPlan','both'));x.setdefault('theoryReviewMin',s.get('defaultTheoryMin',10));x.setdefault('exerciseReviewMin',s.get('defaultExerciseMin',20));x.setdefault('preferredReviewDay',-1)"
    replacement="""        if 'priorityManual' not in x:x['priorityManual']=False
        if not x.get('priorityManual'):
            try:_priority_score=.60*float(x.get('importance',3))+.40*float(x.get('difficulty',3))
            except (TypeError,ValueError):_priority_score=3
            x['priority']=1 if _priority_score>=4.5 else 2 if _priority_score>=3.5 else 3 if _priority_score>=2.5 else 4 if _priority_score>=1.5 else 5
        else:x.setdefault('priority',3)
        x.setdefault('reviewPlan',s.get('defaultReviewPlan','both'));x.setdefault('theoryReviewMin',s.get('defaultTheoryMin',10));x.setdefault('exerciseReviewMin',s.get('defaultExerciseMin',20));x.setdefault('preferredReviewDay',-1)"""
    if anchor not in text:
        raise RuntimeError('Priority default anchor not found in planner.py.')
    text=text.replace(anchor,replacement,1)
    validation="        if x.get('reviewPlan') not in ('both','exercise_only','theory_only') or type(x.get('preferredReviewDay')) is not int or not -1<=x['preferredReviewDay']<=6:raise ValueError('Configuração de revisão da disciplina inválida.')"
    validation_new=validation+"\n        if type(x.get('priorityManual')) is not bool:raise ValueError('Modo de prioridade da disciplina inválido.')"
    if validation not in text:
        raise RuntimeError('Priority validation anchor not found in planner.py.')
    text=text.replace(validation,validation_new,1)
    path.write_text(text.rstrip()+'\n\n'+PY_MARK+'\n',encoding='utf-8')
    compile(text,'planner.py','exec')


JS=r'''\
'use strict';
// === LEARNER GUIDANCE AND PRIORITY V1 ===
let learnerSubjectOrder=localStorage.getItem('meucronograma:subject-order')||'priority';
let learnerProfileRecommendation=localStorage.getItem('meucronograma:profile-recommendation:'+String(typeof target!=='undefined'?target:''))||'';

const learnerProfileGuidance={
 'builtin:guided':{forWhom:'Aluno iniciante, irregular ou que ainda depende de orientação para começar e concluir as tarefas.',why:'Blocos curtos, mais previsibilidade, revisões frequentes e carga diária moderada.',attention:'Não é necessário manter este perfil quando o aluno já executa a rotina com autonomia.'},
 'builtin:restart':{forWhom:'Aluno que ficou um período sem estudar, está sobrecarregado ou precisa reconstruir o hábito sem uma carga inicial alta.',why:'Começa com pouca carga, maior reserva para imprevistos e progressão conservadora.',attention:'Perfil de transição; deve ser revisto quando a regularidade melhorar.'},
 'builtin:strategy':{forWhom:'Aluno que já estuda, mas ainda precisa organizar melhor teoria, exercícios, revisões e acompanhamento semanal.',why:'Equilibra compreensão, prática e controle da execução.',attention:'É o perfil geral mais indicado quando ainda não há evidências suficientes para uma configuração mais específica.'},
 'builtin:autonomous':{forWhom:'Aluno regular, responsável pelos próprios registros e capaz de sustentar blocos maiores com pouca supervisão.',why:'Permite blocos mais longos, maior prática independente e menor intervenção externa.',attention:'Não é indicado quando há muitos blocos não realizados ou dificuldade para iniciar.'},
 'builtin:exam':{forWhom:'Aluno em período temporário de prova, simulado, ENEM ou vestibular nas próximas semanas.',why:'Aumenta a prática de recuperação e prioriza exercícios e correção.',attention:'Deve ser usado por período limitado; não é uma rotina permanente.'},
 'builtin:short':{forWhom:'Aluno com escola integral, trabalho, cursos ou pouca disponibilidade diária.',why:'Usa sessões objetivas e aproveita janelas menores, sem tentar preencher todo o dia.',attention:'A meta precisa ser compatível com o tempo real; não deve acumular carga inviável.'},
 'builtin:math':{forWhom:'Aluno que precisa dar prioridade especial a Matemática e Exatas ou que apresenta dificuldade recorrente nessas áreas.',why:'Prioriza resolução progressiva, correção dos erros e prática frequente, mantendo teoria e exercícios separados.',attention:'As demais disciplinas continuam ativas; o foco em Exatas não deve eliminá-las.'}
};

function learnerSuggestedPriority(subject){
 const importance=Math.max(1,Math.min(5,Number(subject?.importance||3)));
 const difficulty=Math.max(1,Math.min(5,Number(subject?.difficulty||3)));
 const score=.60*importance+.40*difficulty;
 return score>=4.5?1:score>=3.5?2:score>=2.5?3:score>=1.5?4:5;
}
function learnerEffectivePriority(subject){return subject?.priorityManual?Number(subject.priority||3):learnerSuggestedPriority(subject);}
function learnerPriorityName(value){return ({1:'Prioridade máxima',2:'Alta',3:'Regular',4:'Baixa',5:'Mínima'})[Number(value)]||'Regular';}

subjectForm=function(id){
 const found=P.subjects.find(x=>x.id===id);
 const x=found||{name:'',kind:'study',action:'Estudar e praticar',weeklyMin:120,difficulty:3,importance:3,priority:3,priorityManual:false,examDate:'',active:true,reviewPlan:P.settings.defaultReviewPlan||'both',theoryReviewMin:P.settings.defaultTheoryMin||10,exerciseReviewMin:P.settings.defaultExerciseMin||20,preferredReviewDay:-1};
 const suggested=learnerSuggestedPriority(x);
 const mode=x.priorityManual?'manual':'automatic';
 modalForm(id?'Editar disciplina ou ação':'Nova disciplina ou ação',`<div class="form-grid">${input('Nome','name',x.name,'text','required maxlength="150"')}${select('Tipo','kind',x.kind,[['study','Disciplina / estudo'],['personal','Ação pessoal']])}${input('Ação exibida no quadro','action',x.action,'text','maxlength="300"')}${input('Meta semanal (min)','weeklyMin',x.weeklyMin,'number','min="0" max="3000" required')}${select('Definição da prioridade','priorityMode',mode,[['automatic','Automática — calcular por importância e dificuldade'],['manual','Manual — definida pelo aluno']])}${select('Prioridade','priority',x.priorityManual?(x.priority||3):suggested,studyPriorityOptions)}${select('Dificuldade percebida','difficulty',x.difficulty,[1,2,3,4,5].map(n=>[n,n+' / 5']))}${select('Importância','importance',x.importance,[1,2,3,4,5].map(n=>[n,n+' / 5']))}${input('Data de avaliação ou prazo','examDate',x.examDate,'date')}${select('Plano padrão de revisão','reviewPlan',x.reviewPlan||'both',studyReviewPlanOptions)}${input('Tempo de teoria (min)','theoryReviewMin',x.theoryReviewMin||10,'number','min="5" max="180" required')}${input('Tempo de exercícios (min)','exerciseReviewMin',x.exerciseReviewMin||20,'number','min="5" max="240" required')}${select('Dia preferencial para revisar','preferredReviewDay',x.preferredReviewDay??-1,studyDayOptions)}${check('Meta ativa','active',x.active)}</div><div class="notice"><strong>Prioridade sugerida atualmente: ${suggested} — ${learnerPriorityName(suggested)}</strong><p>O cálculo usa 60% da importância e 40% da dificuldade percebida. No modo manual, a escolha do aluno prevalece. Revisões vencidas, prazos e erros recorrentes ainda refinam o encaixe.</p></div>`,async(f,d)=>{const automatic=d.priorityMode==='automatic';const calculated=learnerSuggestedPriority({difficulty:+d.difficulty,importance:+d.importance});const payload={...d,...(id?{id}:{}),weeklyMin:+d.weeklyMin,priority:automatic?calculated:+d.priority,priorityManual:!automatic,difficulty:+d.difficulty,importance:+d.importance,theoryReviewMin:+d.theoryReviewMin,exerciseReviewMin:+d.exerciseReviewMin,preferredReviewDay:+d.preferredReviewDay,active:f.elements.active.checked};delete payload.priorityMode;await save('subject',payload);});
};

function learnerSortSubjects(list){
 const items=list.slice();
 const alpha=(a,b)=>String(a.name||'').localeCompare(String(b.name||''),'pt-BR',{sensitivity:'base'});
 if(learnerSubjectOrder==='alphabetical')return items.sort(alpha);
 if(learnerSubjectOrder==='importance')return items.sort((a,b)=>Number(b.importance||3)-Number(a.importance||3)||learnerEffectivePriority(a)-learnerEffectivePriority(b)||alpha(a,b));
 if(learnerSubjectOrder==='difficulty')return items.sort((a,b)=>Number(b.difficulty||3)-Number(a.difficulty||3)||learnerEffectivePriority(a)-learnerEffectivePriority(b)||alpha(a,b));
 return items.sort((a,b)=>learnerEffectivePriority(a)-learnerEffectivePriority(b)||Number(b.importance||3)-Number(a.importance||3)||Number(b.difficulty||3)-Number(a.difficulty||3)||alpha(a,b));
}
subjectsView=function(){
 const ordered=learnerSortSubjects(P.subjects||[]);
 const controls=`<section class="card subject-order-card"><div class="page-head"><div><h2>Ordenação das disciplinas</h2><p>A prioridade automática considera importância e dificuldade. O aluno também pode definir manualmente a prioridade de cada disciplina.</p></div><label>Exibir por<select id="learner-subject-order"><option value="priority" ${learnerSubjectOrder==='priority'?'selected':''}>Prioridade</option><option value="importance" ${learnerSubjectOrder==='importance'?'selected':''}>Maior importância</option><option value="difficulty" ${learnerSubjectOrder==='difficulty'?'selected':''}>Maior dificuldade</option><option value="alphabetical" ${learnerSubjectOrder==='alphabetical'?'selected':''}>Ordem alfabética</option></select></label></div></section>`;
 const rows=items(ordered.map(x=>{const priority=learnerEffectivePriority(x);const mode=x.priorityManual?'definida pelo aluno':'calculada automaticamente';return `<div class="item subject-priority-row"><div class="item-main"><strong>${esc(x.name)} ${tag(x.active?'Ativa':'Pausada',x.active?'done':'')} ${tag('Prioridade '+priority,priority<=2?'warning':'')}</strong><p>${minutes(x.weeklyMin)} por semana · dificuldade ${x.difficulty}/5 · importância ${x.importance}/5</p><small>${esc(x.action)}${x.examDate?' · Prova em '+br(x.examDate):''} · revisão: ${esc(studyReviewPlans[x.reviewPlan||'both'])}<br>Prioridade ${mode}: ${priority} — ${learnerPriorityName(priority)}</small></div><div class="item-actions">${button('Editar','edit-subject','secondary',`data-id="${x.id}"`)}${button('Excluir','delete','danger-button',`data-collection="subjects" data-id="${x.id}"`)}</div></div>`;}));
 return head('Disciplinas e metas','Organize por prioridade, importância, dificuldade ou ordem alfabética. A prioridade manual do aluno prevalece.',button('Adicionar','new-subject','primary'))+controls+`<div class="card">${rows}</div><div class="notice"><strong>Ordem utilizada pelo motor</strong><p>1) prioridade declarada ou calculada; 2) revisão vencida ou próxima; 3) prazo; 4) desempenho e erros recorrentes; 5) dificuldade e importância; 6) encaixe real na disponibilidade.</p></div>`;
};
document.addEventListener('change',event=>{if(event.target?.id==='learner-subject-order'){learnerSubjectOrder=event.target.value;localStorage.setItem('meucronograma:subject-order',learnerSubjectOrder);render();}});

function learnerProfileInfo(item){
 const known=learnerProfileGuidance[item.id];
 return known||{forWhom:item.description||'Perfil personalizado criado pela coordenação.',why:'As configurações foram definidas pelo Master ou pela coordenação.',attention:'Revise os limites e a carga antes de aplicar.'};
}
function learnerProfileCards(presets){return (presets||[]).map(item=>{const g=learnerProfileInfo(item);return `<article class="learner-profile-card ${learnerProfileRecommendation===item.id?'recommended':''}"><div class="learner-profile-title"><strong>${esc(item.name)}</strong>${learnerProfileRecommendation===item.id?tag('Recomendado','done'):''}${item.custom?tag('Personalizado'):''}</div><p><strong>Indicado para:</strong> ${esc(g.forWhom)}</p><p><strong>Como funciona:</strong> ${esc(g.why)}</p><p class="micro"><strong>Atenção:</strong> ${esc(g.attention)}</p><small>Blocos ${item.config.sessionMin}–${item.config.sessionMax} min · limite diário ${minutes(item.config.dailyMax)} · meta semanal ${minutes(item.config.weeklyGoal)} · reserva ${item.config.reservePct}% · ${esc(studyReviewPlans[item.config.defaultReviewPlan])}</small></article>`;}).join('');}

studyPresetPanel=function(){
 const d=studyPresetCache?.key===target+':'+S.version?studyPresetCache.data:null;
 if(!d){queueMicrotask(studyLoadPresets);return '<section class="card"><h2>Perfil-base de organização</h2><p>Carregando perfis…</p></section>';}
 const current=d.current?.name||P.settings.studyPresetName||'Configuração individual';
 const options=(d.presets||[]).map(x=>`<option value="${esc(x.id)}" ${learnerProfileRecommendation===x.id?'selected':''}>${esc(x.name)}${x.custom?' · personalizado':''}</option>`).join('');
 return `<section class="card learner-profile-section"><div class="page-head"><div><p class="eyebrow">CONFIGURAÇÃO OPERACIONAL</p><h2>Perfil-base de organização</h2><p>Atual: <strong>${esc(current)}</strong>. O perfil é um ponto de partida ajustável, não um rótulo permanente do aluno.</p></div><div class="actions">${button('Descobrir perfil indicado','learner-profile-questionnaire','secondary')}${d.canManage?button('Criar perfil-base','study-preset-new','primary'):''}</div></div>${d.canManage?`<div class="form-grid"><label>Perfil a associar<select id="study-preset-select">${options}</select></label><label class="check"><input id="study-preset-existing" type="checkbox" checked> Aplicar também aos conteúdos já cadastrados</label></div><div class="actions">${button('Aplicar ao aluno selecionado','study-preset-apply','primary')}</div>`:'<div class="notice">O questionário pode indicar o perfil mais compatível. A associação é feita pelo Master ou pela coordenação, e todas as configurações continuam editáveis.</div>'}<details open><summary>Para qual aluno cada perfil é indicado?</summary><div class="learner-profile-grid">${learnerProfileCards(d.presets)}</div></details></section>`;
};

function learnerProfileQuestionnaire(){
 modal('Questionário de perfil de organização',`<form id="learner-profile-form"><p>Responda com base na rotina real do aluno, não na rotina ideal.</p><div class="form-grid">${select('Como está a regularidade atual?','regularity','irregular',[['none','Não está estudando'],['irregular','Muito irregular'],['some','Estuda alguns dias'],['regular','Regular e constante']])}${select('Quanto tempo livre costuma existir por dia?','time','medium',[['short','Até 60 minutos'],['medium','Entre 60 e 120 minutos'],['long','Mais de 120 minutos']])}${select('Quanto apoio precisa para começar?','guidance','some',[['high','Precisa de orientação frequente'],['some','Precisa de algum acompanhamento'],['low','Começa e se organiza sozinho']])}${select('Está retomando após uma pausa?','restart','no',[['yes','Sim'],['no','Não']])}${select('Há prova importante nas próximas semanas?','exam','no',[['yes','Sim'],['no','Não']])}${select('Matemática e Exatas precisam de atenção especial?','math','no',[['yes','Sim'],['no','Não']])}${select('Por quanto tempo mantém atenção produtiva?','focus','medium',[['short','Até 25 minutos'],['medium','De 25 a 45 minutos'],['long','Mais de 45 minutos']])}</div><button class="primary" type="submit">Calcular perfil indicado</button><div id="learner-profile-result"></div></form>`,null);
 queueMicrotask(()=>$('#learner-profile-form')?.addEventListener('submit',event=>{event.preventDefault();const d=Object.fromEntries(new FormData(event.currentTarget));const score={'builtin:guided':0,'builtin:restart':0,'builtin:strategy':0,'builtin:autonomous':0,'builtin:exam':0,'builtin:short':0,'builtin:math':0};
  if(d.regularity==='none'){score['builtin:restart']+=5;score['builtin:guided']+=2;}else if(d.regularity==='irregular'){score['builtin:guided']+=4;score['builtin:restart']+=2;}else if(d.regularity==='some'){score['builtin:strategy']+=4;}else score['builtin:autonomous']+=5;
  if(d.time==='short'){score['builtin:short']+=6;score['builtin:guided']+=1;}else if(d.time==='medium')score['builtin:strategy']+=2;else score['builtin:autonomous']+=3;
  if(d.guidance==='high')score['builtin:guided']+=5;else if(d.guidance==='some')score['builtin:strategy']+=3;else score['builtin:autonomous']+=5;
  if(d.restart==='yes')score['builtin:restart']+=6;
  if(d.exam==='yes')score['builtin:exam']+=7;
  if(d.math==='yes')score['builtin:math']+=7;
  if(d.focus==='short'){score['builtin:guided']+=3;score['builtin:short']+=2;}else if(d.focus==='medium'){score['builtin:strategy']+=2;score['builtin:math']+=1;}else score['builtin:autonomous']+=3;
  const ranked=Object.entries(score).sort((a,b)=>b[1]-a[1]);learnerProfileRecommendation=ranked[0][0];localStorage.setItem('meucronograma:profile-recommendation:'+String(target),learnerProfileRecommendation);const preset=(studyPresetCache?.data?.presets||[]).find(x=>x.id===learnerProfileRecommendation);const info=learnerProfileInfo(preset||{id:learnerProfileRecommendation,name:'Perfil indicado'});const alternative=(studyPresetCache?.data?.presets||[]).find(x=>x.id===ranked[1][0]);const result=$('#learner-profile-result');if(result)result.innerHTML=`<div class="notice learner-profile-result"><strong>Perfil indicado: ${esc(preset?.name||learnerProfileRecommendation)}</strong><p>${esc(info.forWhom)}</p>${alternative?`<p><strong>Alternativa próxima:</strong> ${esc(alternative.name)}</p>`:''}<p class="micro">A recomendação orienta o ponto de partida. O Master, a coordenação e o aluno devem conferir disponibilidade, cumprimento e resultados antes de manter o perfil.</p></div>`;const selectBox=$('#study-preset-select');if(selectBox)selectBox.value=learnerProfileRecommendation;}));
}
acts['learner-profile-questionnaire']=learnerProfileQuestionnaire;

// Bring the monthly spreadsheet table to the top of Minhas revisões.
if(typeof reviewsView==='function'){
 const learnerBaseReviewsView=reviewsView;
 reviewsView=function(){let html=learnerBaseReviewsView();if(typeof reviewCalendarSection==='function'){const calendar=reviewCalendarSection();while(html.includes(calendar))html=html.replace(calendar,'');const anchor='<div class="notice">';const at=html.indexOf(anchor);html=at>=0?html.slice(0,at)+calendar+html.slice(at):calendar+html;}return html;};
}

function learnerCalendarDiscipline(){
 if(typeof view==='undefined'||view!=='calendar'||!Array.isArray(P?.sessions))return;
 const root=document.querySelector('main')||document.body;
 P.sessions.forEach(session=>{const discipline=sub(session.subjectId)||'Disciplina não informada';let targets=[];try{targets=[...root.querySelectorAll(`[data-id="${CSS.escape(String(session.id))}"]`)];}catch(e){}
  if(!targets.length){const time=typeof hm==='function'?hm(session.start):'';targets=[...root.querySelectorAll('div,article,button')].filter(el=>{const text=String(el.textContent||'');return text.length<500&&text.includes(session.title)&&(!time||text.includes(time));}).sort((a,b)=>String(a.textContent||'').length-String(b.textContent||'').length).slice(0,1);}
  targets.forEach(node=>{let box=node.closest('.calendar-event,.calendar-session,.session-card,.week-session,.slot-card,.item')||node.parentElement||node;if(box.querySelector?.('.learner-session-discipline'))return;const label=document.createElement('div');label.className='learner-session-discipline';label.textContent='Disciplina: '+discipline;box.insertBefore(label,box.firstChild);});
 });
}
if(typeof render==='function'){const learnerBaseRender=render;render=function(){const out=learnerBaseRender.apply(this,arguments);queueMicrotask(learnerCalendarDiscipline);return out;};queueMicrotask(learnerCalendarDiscipline);}
'''

CSS=r'''
/* LEARNER GUIDANCE AND PRIORITY V1 */
.subject-order-card{margin-bottom:14px}.subject-order-card .page-head{align-items:end}.subject-order-card label{display:grid;gap:6px;min-width:230px;font-weight:700;font-size:12px}.subject-priority-row small{line-height:1.55}
.learner-profile-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(290px,1fr));gap:12px;margin-top:14px}.learner-profile-card{border:1px solid var(--line);border-radius:14px;padding:16px;background:#fff}.learner-profile-card.recommended{border:2px solid var(--primary);background:#fff7f8}.learner-profile-title{display:flex;justify-content:space-between;align-items:center;gap:8px}.learner-profile-card p{margin:.55rem 0}.learner-profile-card small{display:block;color:var(--muted);line-height:1.45}.learner-profile-result{margin-top:16px}.learner-session-discipline{font-size:10px;font-weight:800;line-height:1.2;margin-bottom:3px;color:var(--primary);letter-spacing:.02em}.review-calendar-card{order:-1}
@media(max-width:760px){.subject-order-card .page-head{align-items:stretch}.subject-order-card label{min-width:0;width:100%}.learner-profile-grid{grid-template-columns:1fr}}
'''


def install_frontend():
    static=ROOT/'static'
    js_path=static/'student_guidance.js'
    js_path.write_text(JS,encoding='utf-8')
    html_path=static/'app.html'
    html=html_path.read_text(encoding='utf-8')
    if '/static/student_guidance.js' not in html:
        html=html.replace('</body>','<script src="/static/student_guidance.js?v=3.4.0" defer></script>\n</body>',1)
    html=re.sub(r'/static/style\.css\?v=[^"\']+','/static/style.css?v=3.4.0',html)
    html_path.write_text(html,encoding='utf-8')
    webapp_path=ROOT/'webapp.py'
    webapp=webapp_path.read_text(encoding='utf-8')
    mime="'student_guidance.js':'application/javascript; charset=utf-8'"
    if mime not in webapp:
        anchor="'schedule_admin_refinement.js':'application/javascript; charset=utf-8'"
        if anchor not in webapp:
            raise RuntimeError('Static-file map anchor not found.')
        webapp=webapp.replace(anchor,anchor+','+mime,1)
    webapp_path.write_text(webapp,encoding='utf-8')
    css_path=static/'style.css'
    css=css_path.read_text(encoding='utf-8')
    if CSS_MARK not in css:
        css=css.rstrip()+'\n\n'+CSS+'\n'
    css_path.write_text(css,encoding='utf-8')


def main():
    patch_planner()
    install_frontend()
    print('MEUCRONOGRAMA_STUDENT_GUIDANCE_READY: automatic/manual priorities, sorting, profile questionnaire, visible review calendar and discipline labels prepared.',flush=True)


if __name__=='__main__':main()
