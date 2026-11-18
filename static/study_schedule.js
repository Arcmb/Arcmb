"use strict";
// Meu Cronograma: prioridade explícita, revisão teoria/exercícios e perfis operacionais.
let studyPresetCache=null,studyPresetRequest='';
const studyReviewPlans={both:'Teoria + exercícios separados',exercise_only:'Somente exercícios',theory_only:'Somente teoria'};
const studyDayOptions=[[-1,'Automático'],[0,'Segunda'],[1,'Terça'],[2,'Quarta'],[3,'Quinta'],[4,'Sexta'],[5,'Sábado'],[6,'Domingo']];
const studyPriorityOptions=[[1,'1 — Prioridade máxima'],[2,'2 — Alta'],[3,'3 — Regular'],[4,'4 — Baixa'],[5,'5 — Mínima']];
const studyReviewPlanOptions=[['both','Teoria + exercícios em momentos separados'],['exercise_only','Somente exercícios (o tempo teórico é incorporado)'],['theory_only','Somente teoria']];

function studyDiscipline(c){return c.sourceDiscipline||sub(c.subjectId)||'Sem disciplina cadastrada';}
function studyLinkedReviewSessions(c){return P.sessions.filter(s=>s.kind==='review'&&(s.contentId===c.id||s.reviewContentId===c.id)&&s.status==='planned').sort((a,b)=>a.date.localeCompare(b.date)||a.start-b.start);}
function studyPartLabel(s){return s.reviewPart==='theory'?'Teoria':s.reviewPart==='exercise'?'Exercícios':'Revisão';}
function studyReviewDuration(c){return Number(c.theoryReviewMin||10)+Number(c.exerciseReviewMin||20);}

subjectForm=function(id){
 const x=P.subjects.find(x=>x.id===id)||{name:'',kind:'study',action:'Estudar e praticar',weeklyMin:120,difficulty:3,importance:3,priority:3,examDate:'',active:true,reviewPlan:P.settings.defaultReviewPlan||'both',theoryReviewMin:P.settings.defaultTheoryMin||10,exerciseReviewMin:P.settings.defaultExerciseMin||20,preferredReviewDay:-1};
 modalForm(id?'Editar disciplina ou ação':'Nova disciplina ou ação',`<div class="form-grid">${input('Nome','name',x.name,'text','required maxlength="150"')}${select('Tipo','kind',x.kind,[['study','Disciplina / estudo'],['personal','Ação pessoal']])}${input('Ação exibida no quadro','action',x.action,'text','maxlength="300"')}${input('Meta semanal (min)','weeklyMin',x.weeklyMin,'number','min="0" max="3000" required')}${select('Prioridade declarada','priority',x.priority||3,studyPriorityOptions)}${select('Dificuldade percebida','difficulty',x.difficulty,[1,2,3,4,5].map(n=>[n,n+' / 5']))}${select('Importância','importance',x.importance,[1,2,3,4,5].map(n=>[n,n+' / 5']))}${input('Data de avaliação ou prazo','examDate',x.examDate,'date')}${select('Plano padrão de revisão','reviewPlan',x.reviewPlan||'both',studyReviewPlanOptions)}${input('Tempo de teoria (min)','theoryReviewMin',x.theoryReviewMin||10,'number','min="5" max="180" required')}${input('Tempo de exercícios (min)','exerciseReviewMin',x.exerciseReviewMin||20,'number','min="5" max="240" required')}${select('Dia preferencial para revisar','preferredReviewDay',x.preferredReviewDay??-1,studyDayOptions)}${check('Meta ativa','active',x.active)}</div><div class="notice"><strong>Prioridade declarada</strong><p>Define a ordem inicial de distribuição. Desempenho, prazos, revisões vencidas e capacidade semanal continuam sendo considerados, sem ultrapassar os limites da rotina.</p></div>`,async(f,d)=>{await save('subject',{...d,...(id?{id}:{}),weeklyMin:+d.weeklyMin,priority:+d.priority,difficulty:+d.difficulty,importance:+d.importance,theoryReviewMin:+d.theoryReviewMin,exerciseReviewMin:+d.exerciseReviewMin,preferredReviewDay:+d.preferredReviewDay,active:f.elements.active.checked});});
};

subjectsView=function(){
 const ordered=P.subjects.slice().sort((a,b)=>(a.priority||3)-(b.priority||3)||a.name.localeCompare(b.name));
 return head('Disciplinas e metas','A prioridade declarada define a ordem inicial; dificuldade, prazo e desempenho refinam a distribuição.',button('Adicionar','new-subject','primary'))+`<div class="card">${items(ordered.map(x=>`<div class="item"><div class="item-main"><strong>${esc(x.name)} ${tag(x.active?'Ativa':'Pausada',x.active?'done':'')} ${tag('Prioridade '+(x.priority||3),(x.priority||3)<=2?'warning':'')}</strong><p>${minutes(x.weeklyMin)} por semana · dificuldade ${x.difficulty}/5 · importância ${x.importance}/5</p><small>${esc(x.action)}${x.examDate?' · Prazo: '+br(x.examDate):''} · revisão: ${esc(studyReviewPlans[x.reviewPlan||'both'])}</small></div><div class="item-actions">${button('Editar','edit-subject','secondary',`data-id="${x.id}"`)}${button('Excluir','delete','danger-button',`data-collection="subjects" data-id="${x.id}"`)}</div></div>`))}</div><div class="notice"><strong>Como o motor ordena</strong><p>1) prioridade indicada; 2) revisão vencida ou próxima; 3) prazo; 4) desempenho e erros recorrentes; 5) dificuldade e importância; 6) encaixe real na disponibilidade.</p></div>`;
};

contentForm=function(){
 if(!P.subjects.length){toast('Cadastre primeiro uma disciplina.');view='subjects';render();return;}
 const first=P.subjects.find(x=>x.active)||P.subjects[0];
 modalForm('Registrar conteúdo',`<div class="form-grid">${select('Disciplina','subjectId',first.id,P.subjects.filter(x=>x.active).map(x=>[x.id,x.name]))}${input('Conteúdo','title','','text','required maxlength="300"')}${input('Tópico geral','topic','','text','maxlength="300"')}${select('Situação','status','studied',[['studied','Já estudei'],['planned','Pretendo estudar']])}${input('Data','studiedOn',S.serverDate,'date','required')}${input('Horário de início','studiedTime','09:00','time','required')}${input('Tempo de estudo (min)','studyMinutes',40,'number','min="0" max="720" required')}${select('Plano de revisão','reviewPlan',first.reviewPlan||P.settings.defaultReviewPlan||'both',studyReviewPlanOptions)}${input('Teoria (min)','theoryReviewMin',first.theoryReviewMin||P.settings.defaultTheoryMin||10,'number','min="5" max="180" required')}${input('Exercícios (min)','exerciseReviewMin',first.exerciseReviewMin||P.settings.defaultExerciseMin||20,'number','min="5" max="240" required')}${select('Dia preferencial','preferredReviewDay',first.preferredReviewDay??-1,studyDayOptions)}${select('Dificuldade percebida','difficulty',3,[1,2,3,4,5].map(n=>[n,n+' / 5']))}${input('Material, páginas ou referência','material','','text','maxlength="5000"')}${area('Observações','notes','')}</div><p class="micro">Quando “somente exercícios” for escolhido, o tempo reservado à teoria será incorporado ao bloco de exercícios, preservando a carga prevista.</p>`,async(f,d)=>save('content',{...d,studyMinutes:+d.studyMinutes,reviewMinutes:+d.theoryReviewMin+ +d.exerciseReviewMin,theoryReviewMin:+d.theoryReviewMin,exerciseReviewMin:+d.exerciseReviewMin,preferredReviewDay:+d.preferredReviewDay,difficulty:+d.difficulty}));
};

function studyReviewPreferences(id){
 const c=P.contents.find(x=>x.id===id);if(!c)return;
 modalForm('Ajustar programação da revisão',`<p><strong>${esc(studyDiscipline(c))}</strong> · ${esc(c.title)}</p><div class="form-grid">${input('Data-alvo','nextDue',c.nextDue||S.serverDate,'date','required')}${select('Dia preferencial','preferredReviewDay',c.preferredReviewDay??-1,studyDayOptions)}${select('Como revisar','reviewPlan',c.reviewPlan||'both',studyReviewPlanOptions)}${input('Revisão de teoria (min)','theoryReviewMin',c.theoryReviewMin||10,'number','min="5" max="180" required')}${input('Exercícios (min)','exerciseReviewMin',c.exerciseReviewMin||20,'number','min="5" max="240" required')}${check('Pausar esta revisão','paused',!!c.paused)}</div><div class="notice"><p>Ao salvar, blocos futuros não fixados desse conteúdo serão retirados e uma nova prévia do cronograma será aberta para confirmação.</p></div>`,async(f,d)=>{await save('review_preferences',{id:c.id,nextDue:d.nextDue,preferredReviewDay:+d.preferredReviewDay,reviewPlan:d.reviewPlan,theoryReviewMin:+d.theoryReviewMin,exerciseReviewMin:+d.exerciseReviewMin,paused:f.elements.paused.checked});setTimeout(()=>{view='calendar';render();acts['generate']();},0);});
}
acts['study-review-settings']=el=>studyReviewPreferences(el.dataset.id);

function studyReviewRow(c,s,index){
 const date=s?.date||c.nextDue||'';const duration=s?s.end-s.start:studyReviewDuration(c);const plan=c.reviewPlan||'both';
 const action=s?studyPartLabel(s):(plan==='both'?'Teoria + exercícios':plan==='exercise_only'?'Exercícios':'Teoria');
 return `<tr><td>${esc(studyDiscipline(c))}</td><td><strong>${esc(c.title)}</strong>${c.topic?'<br><small>'+esc(c.topic)+'</small>':''}${c.sourceType==='exam_error'?'<br>'+tag((c.errorCount||0)+' erro(s)','warning'):''}</td><td>${date?br(date):'—'}${date?'<br><small>'+esc(days[new Date(date+'T12:00:00').getDay()===0?6:new Date(date+'T12:00:00').getDay()-1])+'</small>':''}</td><td>${s?hm(s.start)+'–'+hm(s.end):'Aguardando geração'}</td><td>${esc(action)}</td><td>${minutes(duration)}</td><td>${c.paused?tag('Pausada','warning'):s?tag('Programada','review'):tag('Data-alvo definida')}</td><td><div class="item-actions">${button('Configurar','study-review-settings','secondary',`data-id="${c.id}"`)}${s?button('Ajustar horário','edit-session','secondary',`data-id="${s.id}"`):''}${button('Registrar','feedback-content','primary',`data-id="${c.id}"`)}</div></td></tr>`;
}

reviewsView=function(){
 const contents=P.contents.filter(c=>c.status==='studied').sort((a,b)=>studyDiscipline(a).localeCompare(studyDiscipline(b))||(a.nextDue||'').localeCompare(b.nextDue||''));
 const groups={};contents.forEach(c=>(groups[studyDiscipline(c)]||(groups[studyDiscipline(c)]=[])).push(c));
 const sections=Object.keys(groups).sort((a,b)=>a.localeCompare(b,'pt-BR',{sensitivity:'base'})).map(name=>{
  const rows=[];groups[name].forEach(c=>{const sessions=studyLinkedReviewSessions(c);if(sessions.length)sessions.forEach((s,i)=>rows.push(studyReviewRow(c,s,i)));else rows.push(studyReviewRow(c,null,0));});
  const expected=groups[name].reduce((n,c)=>n+studyReviewDuration(c),0);
  const programmed=groups[name].reduce((n,c)=>n+studyLinkedReviewSessions(c).reduce((sum,s)=>sum+Math.max(0,Number(s.end||0)-Number(s.start||0)),0),0);
  const missing=Math.max(0,expected-programmed);
  return `<details class="review-discipline"><summary><span><strong>${esc(name)}</strong><small>${groups[name].length} conteúdo(s) · ${minutes(programmed)} programados${missing?` · <span class="review-time-warning">${minutes(missing)} sem encaixe</span>`:''}</small></span><span>Mostrar programação</span></summary><div class="table-wrap"><table class="review-plan-table"><thead><tr><th>Disciplina</th><th>Assunto / conteúdo</th><th>Data / dia</th><th>Horário</th><th>Ação</th><th>Tempo</th><th>Situação</th><th>Ajustes</th></tr></thead><tbody>${rows.join('')}</tbody></table></div></details>`;
 }).join('');
 return head('Minhas revisões','Programação por disciplina, com teoria e exercícios em momentos separados e tempos ajustáveis.')+`<div class="notice"><strong>Revisão ativa</strong><p>Recupere o conteúdo sem consulta, confira e corrija. O intervalo seguinte será ajustado pelo resultado registrado, não apenas pela passagem do tempo.</p></div><div class="actions">${button('Atualizar erros dos simulados','review-errors-refresh','secondary')}${button('Abrir quadro semanal','go-calendar','primary')}</div>${sections||'<section class="card">Nenhum conteúdo de revisão encontrado.</section>'}`;
};

const studyBaseCalendarView=calendarView;
calendarView=function(){
 let html=studyBaseCalendarView();
 const nav=`<div class="study-week-nav">${button('← Semana anterior','study-week-prev','secondary')}${button('Semana atual','study-week-current','secondary')}${button('Próxima semana →','study-week-next','secondary')}<span>Você pode navegar e gerar a programação das próximas semanas.</span></div>`;
 return html.replace('<div class="card"><div class="actions">','<div class="card">'+nav+'<div class="actions">');
};
acts['study-week-prev']=async()=>{week=add(week,-7);await loadCalendar();render();window.scrollTo(0,0);};
acts['study-week-current']=async()=>{week=weekOf(S.serverDate);await loadCalendar();render();window.scrollTo(0,0);};
acts['study-week-next']=async()=>{week=add(week,7);await loadCalendar();render();window.scrollTo(0,0);};

acts['generate']=()=>{
 if(!safeLeave())return;planPreview=null;
 modal('Prévia do cronograma',`<form id="objective-preview-form"><p>O sistema usa somente a disponibilidade cadastrada. Sono, compromissos, pausas, reservas e limites continuam obrigatórios.</p>${input('Semana inicial','week',week||S.serverDate,'date','required')}${select('Programar quantas semanas?','weeks','1',[['1','1 semana'],['2','2 semanas'],['3','3 semanas'],['4','4 semanas']])}${select('Como organizar?','mode','fill',[['fill','Completar espaços livres sem retirar os períodos existentes'],['reorganize','Reorganizar períodos futuros não fixados']])}<p>Prioridades declaradas, revisões vencidas, prazos e resultados acadêmicos entram no cálculo. Nada é salvo antes da confirmação.</p><button class="primary" type="submit">Gerar prévia</button><p id="objective-error" class="form-error" role="alert"></p></form>`,null);
};

acts['edit-session']=el=>{
 const s=P.sessions.find(x=>x.id===el.dataset.id);if(!s)return;
 modalForm('Ajustar horário',`<p><strong>Disciplina: ${esc(sub(s.subjectId)||'Não informada')}</strong><br>${esc(s.title)}</p><div class="form-grid">${input('Data','date',s.date,'date','required')}${input('Início','start',hm(s.start),'time','required')}${input('Duração (min)','duration',s.end-s.start,'number','min="5" max="240" required')}${check('Fixar este período no recálculo','locked',!!s.locked)}${select('Motivo do ajuste','reason','not_informed',typeof objectiveReasons!=='undefined'?objectiveReasons:[['not_informed','Não informado']])}</div><p class="micro">O término será calculado pelo início + duração. Ao alterar um bloco, os demais horários não são movidos automaticamente.</p>`,async(f,d)=>{const [h,m]=d.start.split(':').map(Number),start=h*60+m,duration=+d.duration,end=start+duration;if(end>1440)throw new Error('O bloco não pode ultrapassar meia-noite.');await save('session',{id:s.id,date:d.date,start:d.start,end:hm(end),locked:f.elements.locked.checked,reason:d.reason});});
};

async function studyLoadPresets(){
 const key=target+':'+S.version;if(studyPresetRequest===key)return;if(studyPresetCache?.key===key)return;
 studyPresetRequest=key;
 try{const data=await api('/api/adaptive/presets?user='+encodeURIComponent(target));if(target+':'+S.version!==key)return;studyPresetCache={key,data};if(['routine','accounts','coordinator'].includes(view))render();}catch(e){console.error(e);}finally{studyPresetRequest='';}
}
function studyPresetPanel(){
 const d=studyPresetCache?.key===target+':'+S.version?studyPresetCache.data:null;
 if(!d){queueMicrotask(studyLoadPresets);return '<section class="card"><h2>Perfil-base de organização</h2><p>Carregando perfis…</p></section>';}
 const current=d.current?.name||P.settings.studyPresetName||'Configuração individual';
 const options=(d.presets||[]).map(x=>`<option value="${esc(x.id)}">${esc(x.name)}${x.custom?' · personalizado':''}</option>`).join('');
 const descriptions=(d.presets||[]).map(x=>`<div class="item"><div><strong>${esc(x.name)}</strong><p>${esc(x.description)}</p><small>Blocos ${x.config.sessionMin}–${x.config.sessionMax} min · reserva ${x.config.reservePct}% · ${esc(studyReviewPlans[x.config.defaultReviewPlan])}</small></div></div>`).join('');
 return `<section class="card"><div class="page-head"><div><p class="eyebrow">CONFIGURAÇÃO OPERACIONAL</p><h2>Perfil-base de organização</h2><p>Atual: <strong>${esc(current)}</strong>. É apenas um ponto de partida; o aluno pode alterar horários, tempos e prioridades.</p></div>${d.canManage?button('Criar perfil-base','study-preset-new','primary'):''}</div>${d.canManage?`<div class="form-grid"><label>Aplicar ao aluno<select id="study-preset-select">${options}</select></label><label class="check"><input id="study-preset-existing" type="checkbox" checked> Aplicar também aos conteúdos já cadastrados</label></div><div class="actions">${button('Aplicar perfil selecionado','study-preset-apply','primary')}</div>`:'<div class="notice">O Master ou a coordenação define o perfil-base. Todas as configurações continuam editáveis nesta conta.</div>'}<details><summary>Ver perfis disponíveis</summary>${descriptions}</details></section>`;
}
const studyBaseRoutineView=routineView;
routineView=function(){return studyPresetPanel()+studyBaseRoutineView();};

acts['study-preset-apply']=async()=>{
 const presetId=document.querySelector('#study-preset-select')?.value;if(!presetId)throw new Error('Selecione um perfil-base.');
 const applyExisting=!!document.querySelector('#study-preset-existing')?.checked;
 if(!confirm('Aplicar este perfil-base? Os horários atuais serão preservados até uma nova prévia.'))return;
 const result=await api('/api/adaptive/preset-apply',{user:target,version:S.version,presetId,applyExisting});S=result;P=result.profile;CSRF=result.csrf;studyPresetCache=null;mappingCache=null;await loadCalendar();render();toast('Perfil-base aplicado. Confira prioridades e gere uma nova prévia.');
};
acts['study-preset-new']=()=>{
 modalForm('Criar perfil-base',`<div class="form-grid">${input('Nome','name','','text','required maxlength="100"')}${input('Descrição','description','','text','maxlength="500"')}${input('Bloco mínimo (min)','sessionMin',20,'number','min="10" max="120" required')}${input('Bloco máximo (min)','sessionMax',40,'number','min="10" max="180" required')}${input('Pausa (min)','breakMin',10,'number','min="0" max="60" required')}${input('Limite diário (min)','dailyMax',120,'number','min="10" max="720" required')}${input('Meta semanal (min)','weeklyGoal',480,'number','min="10" max="5040" required')}${input('Reserva para imprevistos (%)','reservePct',25,'number','min="0" max="80" required')}${input('Intervalos de revisão (dias)','intervals','1, 3, 7, 14, 30','text','required')}${select('Plano padrão de revisão','defaultReviewPlan','both',studyReviewPlanOptions)}${input('Teoria padrão (min)','defaultTheoryMin',10,'number','min="5" max="180" required')}${input('Exercícios padrão (min)','defaultExerciseMin',20,'number','min="5" max="240" required')}</div>`,async(f,d)=>{await api('/api/adaptive/preset-save',{user:target,name:d.name,description:d.description,config:{sessionMin:+d.sessionMin,sessionMax:+d.sessionMax,breakMin:+d.breakMin,dailyMax:+d.dailyMax,weeklyGoal:+d.weeklyGoal,reservePct:+d.reservePct,intervals:d.intervals,reviewMin:+d.defaultTheoryMin+ +d.defaultExerciseMin,defaultReviewPlan:d.defaultReviewPlan,defaultTheoryMin:+d.defaultTheoryMin,defaultExerciseMin:+d.defaultExerciseMin}});studyPresetCache=null;closeModal(true);render();toast('Perfil-base criado.');});
};

// === REVIEW CHANGE REPREVIEW V1 ===
