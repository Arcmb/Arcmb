'use strict';
// All decisions are computed and authorized by the server; no external scripts.
let mappingCache=null,mappingRequest='',planPreview=null;
const objectivePeriods={manha:'Manhã',tarde:'Tarde',noite:'Noite',qualquer:'Sem preferência'};
const objectiveReasons=[['not_informed','Selecionar motivo (opcional)'],['preference','Preferência de horário'],['availability','Disponibilidade mudou'],['duration','Ajuste de duração'],['priority','Mudança de prioridade'],['fatigue','Ajuste de carga / descanso'],['support','Orientação do responsável'],['exception','Imprevisto pontual'],['correction','Correção de cadastro']];
const objectiveValue=(key,v)=>key==='preferred'?(objectivePeriods[v]||v):typeof v==='boolean'?(v?'Sim':'Não'):String(v);
function mappingView(){
 const key=target+':'+S.version;
 if(!mappingCache||mappingCache.key!==key){
  if(mappingRequest!==key){mappingRequest=key;const requestedTarget=target;api('/api/adaptive?user='+encodeURIComponent(target)).then(d=>{if(target!==requestedTarget||target+':'+S.version!==key)return;mappingCache={key,data:d};mappingRequest='';if(view==='mapping')render();}).catch(e=>{if(target!==requestedTarget)return;mappingRequest='';const box=$('#mapping-loading');if(box)box.textContent=e.message;});}
  return head('Mapeamento objetivo','Alternativas que se transformam em sugestões verificáveis.')+'<section class="card" id="mapping-loading">Carregando perguntas e histórico…</section>';
 }
 const d=mappingCache.data,groups=[...new Set(d.questions.map(q=>q.group))];
 const questionForm=groups.map(g=>`<section class="card"><h2>${esc(g)}</h2><div class="form-grid">${d.questions.filter(q=>q.group===g).map(q=>select(esc(q.label),q.key,d.answers[q.key]||'',[['','Não informado / ainda não sei'],...q.options])).join('')}</div></section>`).join('');
 const recommendations=d.suggestions.changes.map(x=>`<div class="item"><div class="item-main"><strong>${esc(x.label)}: ${esc(objectiveValue(x.key,x.before))} → ${esc(objectiveValue(x.key,x.after))}</strong><p>${esc(x.reason)}</p></div></div>`).join('');
 const stats=d.personal.stats.map(x=>`<div class="item"><div><strong>${esc(objectivePeriods[x.period])}</strong><p>${x.observations} registros em ${x.days} dias · índice de execução ${Math.round(x.completion*100)}%${x.used?' · pode orientar a prévia':' · amostra insuficiente'}</p></div></div>`).join('');
 const history=d.history.map(x=>`<div class="item"><div><strong>${esc(x.actor)} · ${esc(x.reason)}</strong><p>${esc(new Date(x.at).toLocaleString('pt-BR'))} · ${esc(x.kind)}</p><small>${x.details.added} blocos acrescentados; ${x.details.removed} retirados; ${x.details.changed} alterados. Minutos no histórico: ${x.details.minutesBefore} → ${x.details.minutesAfter}.</small></div></div>`).join('');
 return head('Mapeamento objetivo','Responda o que consegue informar. Campos em branco não se tornam conclusões sobre você.')+
 `<div class="notice">${d.suggestions.answered} de ${d.suggestions.total} respostas informadas. As respostas são relatos iniciais, não diagnósticos. O sistema não ocupa sono ou horários desconhecidos.</div>`+
 `<form id="objective-form">${questionForm}<section class="card"><button class="primary" type="submit">Salvar respostas</button><p class="micro">Salvar o questionário não muda os horários nem os parâmetros automaticamente.</p></section></form>`+
 `<section class="card"><h2>Parâmetros sugeridos</h2>${recommendations||empty('Não há mudança de parâmetro proposta com as respostas atuais.')}${d.suggestions.changes.length?button('Conferir e aplicar parâmetros','objective-settings','primary'):''}<p class="micro">${esc(d.suggestions.notice)}</p>${d.suggestions.tips.map(t=>'<p>'+esc(t)+'</p>').join('')}</section>`+
 `<section class="card"><h2>O que o histórico indica</h2>${stats||empty('Ainda não há execuções suficientes registradas.')}<p>${esc(d.personal.notice)}</p><p class="micro">Amostra individual mínima por período: 6 registros em 3 dias. O índice é suavizado e não equivale a nota, domínio ou diagnóstico.</p></section>`+
 `<section class="card"><h2>Contribuição coletiva opcional</h2><p>${esc(d.collective.notice)}</p><p>Quando autorizada, somente registros futuros de execução de contas Aluno contribuem para estatísticas de foco e estabilidade de rotina. Nomes, textos pessoais e notas não são exibidos a outros participantes. O titular pode revogar e retirar suas contribuições. Contas especiais não participam.</p>${d.canConsent?button(d.collective.enabled?'Revogar e retirar minhas contribuições':'Autorizar contribuição agregada','objective-consent','secondary',`data-enabled="${d.collective.enabled?'0':'1'}"`):'<p class="micro">A autorização só pode ser dada pelo titular de uma conta Aluno. Master e coordenador não autorizam em nome de outra pessoa.</p>'}<p class="micro">Só há influência coletiva com pelo menos 10 outros participantes e 30 registros por período. Editar um horário não é evidência de melhoria; os resultados continuam sujeitos a diferenças entre tarefas e autorrelato.</p></section>`+
 `<section class="card"><h2>Alterações quantificadas</h2><p>Registro de quem alterou, motivo, quantidade de blocos e duração. Esta tela mostra as 30 alterações mais recentes.</p>${history||empty('Nenhuma alteração registrada pelo novo módulo.')}</section>`;
}
async function objectiveRefreshState(){await load();mappingCache=null;if(view==='mapping')render();}
acts['objective-settings']=async()=>{
 if(!safeLeave())return;
 const data=(await api('/api/adaptive?user='+encodeURIComponent(target))).suggestions;
 if(!data.changes.length){toast('Não há parâmetros novos para aplicar.');return;}
 modal('Conferir parâmetros sugeridos',`<p>Estas mudanças afetam as próximas propostas. Horários existentes serão preservados até você confirmar uma nova prévia.</p>${data.changes.map(x=>'<p><strong>'+esc(x.label)+':</strong> '+esc(objectiveValue(x.key,x.before))+' → '+esc(objectiveValue(x.key,x.after))+'</p>').join('')}${button('Aplicar estes parâmetros','objective-apply','primary')}`,null);
};
acts['objective-apply']=async()=>{
 const d=await api('/api/adaptive?user='+encodeURIComponent(target));
 await save('objective_settings',{keys:d.suggestions.changes.map(x=>x.key),reason:'proposal'});mappingCache=null;closeModal(true);render();
};
acts['objective-consent']=async el=>{
 if(!safeLeave())return;
 const enabled=el.dataset.enabled==='1';
 if(!confirm(enabled?'Autoriza o uso agregado de seus próximos registros de execução para orientar participantes com respostas semelhantes? Você poderá revogar.':'Revogar a autorização e excluir suas contribuições coletivas? Seu planejamento e histórico individual serão preservados.'))return;
 await api('/api/adaptive/consent',{user:target,version:S.version,enabled});await objectiveRefreshState();toast(enabled?'Autorização registrada.':'Contribuições retiradas.');
};
acts['generate']=()=>{
 if(!safeLeave())return;
 planPreview=null;
 modal('Prévia do cronograma',`<form id="objective-preview-form"><p>O sistema usa somente a disponibilidade cadastrada. Sono, compromissos, pausas, reservas e limites continuam obrigatórios.</p>${input('Semana','week',week||S.serverDate,'date','required')}${select('Como organizar?','mode','fill',[['fill','Completar espaços livres sem retirar os blocos existentes'],['reorganize','Reorganizar blocos futuros não fixados']])}<p>Blocos fixados e resultados registrados serão preservados. Nada é salvo antes da confirmação.</p><button class="primary" type="submit">Gerar prévia</button><p id="objective-error" class="form-error" role="alert"></p></form>`,null);
};
function showObjectivePreview(r){
 const s=r.summary;
 modal('Conferir a proposta',`<p>${esc(r.notice)}</p><div class="notice">${s.added} blocos novos · ${s.removed} retirados · ${s.changed} alterados. Semana de ${br(s.week)}.</div><p>${esc(s.own.notice)}</p><p>${esc(s.collective.notice)}</p><div class="table-wrap"><table><thead><tr><th>Data</th><th>Horário</th><th>Atividade</th><th>Estado</th></tr></thead><tbody>${r.sessions.map(x=>`<tr><td>${br(x.date)}</td><td>${hm(x.start)}–${hm(x.end)}</td><td>${esc(x.title)}</td><td>${x.locked?'Fixado · ':''}${esc(names[x.status])}</td></tr>`).join('')}</tbody></table></div>${r.pending.length?'<h3>Pendências</h3>'+r.pending.map(x=>'<p>'+esc(x.title)+': '+esc(x.reason)+'</p>').join(''):''}<div class="actions">${button('Confirmar e salvar esta proposta','objective-confirm','primary')}${button('Descartar prévia','objective-discard')}</div>`,null);
}
acts['objective-discard']=()=>{planPreview=null;closeModal(true);};
acts['objective-confirm']=async()=>{
 if(!planPreview||planPreview.target!==target)throw new Error('Gere uma nova prévia para esta conta.');
 const result=await api('/api/adaptive/confirm',{user:target,version:planPreview.version,token:planPreview.data.token});
 S=result;P=result.profile;CSRF=result.csrf;dirty=false;mappingCache=null;planPreview=null;closeModal(true);await loadCalendar();render();status('Proposta salva no servidor · versão '+S.version);toast('Cronograma confirmado e salvo.');
};
acts['edit-session']=el=>{
 const s=P.sessions.find(x=>x.id===el.dataset.id);
 modalForm('Ajustar horário',`<p>${esc(s.title)}</p><div class="form-grid">${input('Data','date',s.date,'date','required')}${input('Início','start',hm(s.start),'time','required')}${input('Fim','end',hm(s.end),'time','required')}${check('Fixar este bloco no recálculo','locked',!!s.locked)}${select('Motivo do ajuste','reason','not_informed',objectiveReasons)}</div><p class="micro">O sistema quantifica o ajuste. Só o registro posterior da execução pode indicar se a mudança ajudou.</p>`,async(f,d)=>save('session',{...d,id:s.id,locked:f.elements.locked.checked}));
};
document.addEventListener('submit',async event=>{
 const f=event.target;if(!['objective-form','objective-preview-form'].includes(f.id))return;event.preventDefault();if(!f.reportValidity()||saving)return;
 const b=f.querySelector('button[type=submit]');b.disabled=true;
 try{
  const data=fd(f);
  if(f.id==='objective-form'){await save('objective',{answers:data,reason:'correction'});mappingCache=null;render();}
  else{const requested=target,version=S.version;const r=await api('/api/adaptive/preview',{user:target,version,mode:data.mode,week:data.week});if(target!==requested||S.version!==version)throw new Error('A conta ou o planejamento mudou. Gere outra prévia.');planPreview={target,version,data:r};dirty=false;showObjectivePreview(r);}
 }catch(e){toast(e.message,true);if($('#objective-error'))$('#objective-error').textContent=e.message;}finally{if(b.isConnected)b.disabled=false;}
});
