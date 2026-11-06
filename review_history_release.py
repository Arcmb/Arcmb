"""Add a global review timeline to the existing Minhas revisões page.

The table is derived from the learner profile: studied/planned contents, review
sessions, feedback and spaced-review parameters. It does not duplicate records
or create automatic evidence. Future dates are explicitly presented as
projections that may change after each recorded review.
"""
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parent
JS_MARKER = '// === GLOBAL REVIEW HISTORY V1 ==='
CSS_MARKER = '/* GLOBAL REVIEW HISTORY V1 */'

REVIEW_HISTORY_JS = r'''\
'use strict';
// === GLOBAL REVIEW HISTORY V1 ===
const reviewHistoryBaseView=reviewsView;
const reviewHistoryMethodNames={questoes:'Questões',correcao:'Correção/refazer erros',resumo:'Resumo',flashcards:'Flashcards',releitura:'Releitura',videoaula:'Videoaula',explicacao:'Explicação',mapa:'Mapa mental',monitoria:'Monitoria',outro:'Outro'};
const reviewHistoryDifficulty={1:'Muito fácil',2:'Fácil',3:'Moderada',4:'Difícil',5:'Muito difícil'};
const reviewHistoryStatusNames={overdue:'Atrasada',scheduled:'Programada',future:'Futura',planned:'Estudo planejado',paused:'Pausada',reviewed:'Já revisada'};

function reviewHistoryLinkedSessions(c){
 return (P.sessions||[]).filter(s=>s.kind==='review'&&(s.contentId===c.id||s.reviewContentId===c.id)).sort((a,b)=>String(a.date).localeCompare(String(b.date))||a.start-b.start);
}
function reviewHistoryFeedback(c){
 return (P.feedback||[]).filter(f=>f.contentId===c.id).sort((a,b)=>String(b.date||'').localeCompare(String(a.date||''))||String(b.at||'').localeCompare(String(a.at||'')));
}
function reviewHistoryDiscipline(c){return c.sourceDiscipline||sub(c.subjectId)||'Não informada';}
function reviewHistoryOrigin(c){return c.sourceType==='exam_error'?'Erro de avaliação importada':'Cadastro do aluno';}
function reviewHistoryCurrentStatus(c,feedback,sessions){
 if(c.status==='planned')return 'planned';
 if(c.paused)return 'paused';
 if(sessions.some(s=>s.status==='planned'&&s.date>=S.serverDate))return 'scheduled';
 if(c.nextDue&&c.nextDue<S.serverDate)return 'overdue';
 if(feedback.some(f=>f.status!=='missed'))return 'reviewed';
 return 'future';
}
function reviewHistoryNextSession(sessions){return sessions.find(s=>s.status==='planned'&&s.date>=S.serverDate)||null;}
function reviewHistoryProjectedDates(c,nextDate){
 if(!nextDate||c.status==='planned'||c.paused)return [];
 const intervals=Array.isArray(P.settings?.intervals)?P.settings.intervals:[];
 let stage=Math.max(0,Math.min(intervals.length-1,Number(c.stage||0)));
 let cursor=nextDate;const result=[];
 for(let i=stage+1;i<intervals.length&&result.length<4;i++){
  cursor=add(cursor,Number(intervals[i]||0));
  result.push(cursor);
 }
 return result;
}
function reviewHistoryModel(c){
 const feedback=reviewHistoryFeedback(c),sessions=reviewHistoryLinkedSessions(c),nextSession=reviewHistoryNextSession(sessions);
 const performed=feedback.filter(f=>f.status==='done'||f.status==='partial');
 const last=performed[0]||null;
 const nextDate=nextSession?.date||c.nextDue||'';
 const nextTime=nextSession?hm(nextSession.start)+'–'+hm(nextSession.end):'';
 const status=reviewHistoryCurrentStatus(c,feedback,sessions);
 const questions=performed.reduce((n,f)=>n+Number(f.total||0),0);
 const correct=performed.reduce((n,f)=>n+Number(f.correct||0),0);
 return {c,discipline:reviewHistoryDiscipline(c),origin:reviewHistoryOrigin(c),feedback,sessions,performed,last,nextSession,nextDate,nextTime,status,questions,correct,projected:reviewHistoryProjectedDates(c,nextDate)};
}
function reviewHistoryModels(){
 return (P.contents||[]).slice().sort((a,b)=>reviewHistoryDiscipline(a).localeCompare(reviewHistoryDiscipline(b))||String(a.title||'').localeCompare(String(b.title||''))).map(reviewHistoryModel);
}
function reviewHistoryStatusTag(model){
 const cls=model.status==='overdue'?'warning':model.status==='scheduled'?'done':model.status==='paused'?'':'review';
 return tag(reviewHistoryStatusNames[model.status]||model.status,cls);
}
function reviewHistoryFeedbackHtml(model){
 const studyLogs=(P.studyLogs||[]).filter(x=>x.contentId===model.c.id).sort((a,b)=>String(b.date||'').localeCompare(String(a.date||'')));
 const studies=studyLogs.length?studyLogs.map(x=>`<li><strong>${br(x.date)}</strong> · estudo registrado · ${minutes(Number(x.minutes||0))}</li>`):[`<li><strong>${br(model.c.studiedOn)}</strong> · ${model.c.status==='planned'?'estudo previsto':'estudo inicial'} · ${minutes(Number(model.c.studyMinutes||0))}</li>`];
 const reviews=model.feedback.length?model.feedback.slice(0,60).map(f=>{
  const methods=(f.methods||[]).map(x=>reviewHistoryMethodNames[x]||x).join(', ');
  const result=f.status==='missed'?'Não realizada':f.status==='partial'?'Parcial':'Concluída';
  const score=f.total?` · ${f.correct}/${f.total} acertos`:'';
  const extra=[methods?`Método: ${methods}`:'',f.monitoring?'Monitoria':'',f.perceivedDifficulty?`Dificuldade: ${reviewHistoryDifficulty[f.perceivedDifficulty]||f.perceivedDifficulty}`:'',f.needsAttention?'Precisa de mais atenção':''].filter(Boolean).join(' · ');
  return `<li><strong>${br(f.date)}</strong> · ${esc(result)} · ${minutes(Number(f.actualMin||0))}${score}${extra?`<br><small>${esc(extra)}</small>`:''}${f.reviewDescription?`<br><small>${esc(f.reviewDescription)}</small>`:''}</li>`;
 }):['<li>Nenhuma revisão registrada.</li>'];
 return `<div class="review-history-events"><h4>Estudo</h4><ul>${studies.join('')}</ul><h4>Revisões e verificações</h4><ul>${reviews.join('')}</ul></div>`;
}
function reviewHistoryRow(model){
 const c=model.c;
 const studied=c.status==='planned'?`Previsto: ${br(c.studiedOn)}`:`${br(c.studiedOn)}`;
 const last=model.last?`${br(model.last.date)}<br><small>${minutes(Number(model.last.actualMin||0))}${model.last.total?' · '+model.last.correct+'/'+model.last.total+' acertos':''}</small>`:'—';
 const next=model.nextDate?`${br(model.nextDate)}${model.nextTime?'<br><small>'+esc(model.nextTime)+'</small>':''}`:'—';
 const projected=model.projected.length?model.projected.map(x=>`<span class="review-date-chip">${br(x)}</span>`).join(''):'<span class="muted">Sem projeção</span>';
 const performance=model.questions?`${model.correct}/${model.questions}<br><small>${Math.round(100*model.correct/model.questions)}%</small>`:'—';
 const source=c.sourceType==='exam_error'?`<small>${esc(model.origin)}${c.errorCount?' · '+c.errorCount+' erro(s)':''}</small>`:`<small>${esc(model.origin)}</small>`;
 return `<tr data-rh-discipline="${esc(model.discipline)}" data-rh-status="${esc(model.status)}" data-rh-origin="${c.sourceType==='exam_error'?'exam':'manual'}"><td><strong>${esc(model.discipline)}</strong></td><td><strong>${esc(c.title)}</strong>${c.topic?`<br><small>${esc(c.topic)}</small>`:''}<br>${source}</td><td>${studied}</td><td>${model.performed.length}<br><small>${performance}</small></td><td>${last}</td><td>${next}</td><td><div class="review-date-chips">${projected}</div><small class="projection-note">Projeção condicionada ao resultado das próximas revisões.</small></td><td>${reviewHistoryStatusTag(model)}</td><td><details class="review-history-detail"><summary>Ver histórico</summary>${reviewHistoryFeedbackHtml(model)}</details><div class="review-history-actions">${c.status==='studied'?button('Registrar revisão','feedback-content','primary',`data-id="${c.id}"`):''}${button('Configurar','study-review-settings','secondary',`data-id="${c.id}"`)}</div></td></tr>`;
}
function reviewHistoryFilterOptions(models){
 const disciplines=[...new Set(models.map(x=>x.discipline))].sort();
 return disciplines.map(x=>`<option value="${esc(x)}">${esc(x)}</option>`).join('');
}
function reviewHistoryVisibleModels(){
 const query=String($('#review-history-search')?.value||'').trim().toLowerCase();
 const discipline=$('#review-history-discipline')?.value||'';
 const status=$('#review-history-status')?.value||'';
 const origin=$('#review-history-origin')?.value||'';
 return reviewHistoryModels().filter(m=>{
  const hay=[m.discipline,m.c.title,m.c.topic,m.origin,...(m.c.sourceSkills||[]),...(m.c.sourceSimulations||[])].join(' ').toLowerCase();
  if(query&&!hay.includes(query))return false;
  if(discipline&&m.discipline!==discipline)return false;
  if(origin&&((origin==='exam')!==(m.c.sourceType==='exam_error')))return false;
  if(status==='reviewed'&&!m.performed.length)return false;
  if(status&&status!=='reviewed'&&m.status!==status)return false;
  return true;
 });
}
function renderReviewHistoryRows(){
 const body=$('#review-history-body');if(!body)return;
 const models=reviewHistoryVisibleModels();
 body.innerHTML=models.length?models.map(reviewHistoryRow).join(''):'<tr><td colspan="9" class="empty">Nenhum conteúdo corresponde aos filtros.</td></tr>';
 const counter=$('#review-history-counter');if(counter)counter.textContent=models.length+' conteúdo(s) exibido(s)';
}
function reviewHistorySection(){
 const models=reviewHistoryModels();
 const reviewed=models.filter(x=>x.performed.length).length;
 const overdue=models.filter(x=>x.status==='overdue').length;
 const inSeven=models.filter(x=>x.nextDate&&x.nextDate>=S.serverDate&&x.nextDate<=add(S.serverDate,7)).length;
 const totalReviews=models.reduce((n,x)=>n+x.performed.length,0);
 return `<section class="card review-history-global"><div class="page-head"><div><p class="eyebrow">VISÃO GLOBAL</p><h2>Histórico e próximas revisões</h2><p>Acompanhe tudo que já foi estudado, as revisões realizadas, a próxima data confirmada e as projeções seguintes.</p></div>${button('Exportar histórico — CSV','review-history-export','secondary')}</div><div class="stats review-history-stats"><div class="stat"><strong>${models.length}</strong><span>conteúdos acompanhados</span></div><div class="stat"><strong>${reviewed}</strong><span>com revisão registrada</span></div><div class="stat"><strong>${totalReviews}</strong><span>revisões realizadas</span></div><div class="stat"><strong>${overdue}</strong><span>revisões atrasadas</span></div><div class="stat"><strong>${inSeven}</strong><span>previstas em 7 dias</span></div></div><div class="review-history-filters"><label>Pesquisar<input id="review-history-search" type="search" placeholder="Disciplina, assunto, habilidade ou simulado"></label><label>Disciplina<select id="review-history-discipline"><option value="">Todas</option>${reviewHistoryFilterOptions(models)}</select></label><label>Situação<select id="review-history-status"><option value="">Todas</option><option value="overdue">Atrasadas</option><option value="scheduled">Programadas</option><option value="future">Futuras</option><option value="reviewed">Já revisadas</option><option value="planned">Estudo planejado</option><option value="paused">Pausadas</option></select></label><label>Origem<select id="review-history-origin"><option value="">Todas</option><option value="manual">Cadastro do aluno</option><option value="exam">Erro de avaliação</option></select></label></div><div class="review-history-caption"><span id="review-history-counter">${models.length} conteúdo(s) exibido(s)</span><span>As datas projetadas são recalculadas depois de cada revisão registrada.</span></div><div class="table-wrap"><table class="review-history-table"><thead><tr><th>Disciplina</th><th>Assunto / conteúdo</th><th>Data do estudo</th><th>Revisões / questões</th><th>Última revisão</th><th>Próxima revisão</th><th>Próximas projeções</th><th>Situação</th><th>Histórico e ajustes</th></tr></thead><tbody id="review-history-body">${models.length?models.map(reviewHistoryRow).join(''):'<tr><td colspan="9" class="empty">Nenhum conteúdo acompanhado.</td></tr>'}</tbody></table></div><p class="micro"><strong>Regra:</strong> a projeção seguinte considera os intervalos configurados e pressupõe que a revisão anterior seja realizada com evidência suficiente. Dificuldade, baixo aproveitamento, ajuda completa ou indicação de atenção podem antecipar a data.</p></section>`;
}
reviewsView=function(){return reviewHistoryBaseView()+reviewHistorySection();};

document.addEventListener('input',event=>{if(['review-history-search','review-history-discipline','review-history-status','review-history-origin'].includes(event.target?.id))renderReviewHistoryRows();});
document.addEventListener('change',event=>{if(['review-history-discipline','review-history-status','review-history-origin'].includes(event.target?.id))renderReviewHistoryRows();});

acts['review-history-export']=()=>{
 const rows=reviewHistoryVisibleModels();
 const header=['DISCIPLINA','ASSUNTO','TÓPICO','ORIGEM','DATA DO ESTUDO','REVISÕES REALIZADAS','QUESTÕES REALIZADAS','ACERTOS','ÚLTIMA REVISÃO','PRÓXIMA REVISÃO','HORÁRIO','PROJEÇÕES SEGUINTES','SITUAÇÃO'];
 const csvCell=value=>'"'+String(value??'').replaceAll('"','""')+'"';
 const lines=[header,...rows.map(m=>[m.discipline,m.c.title,m.c.topic||'',m.origin,m.c.studiedOn||'',m.performed.length,m.questions,m.correct,m.last?.date||'',m.nextDate||'',m.nextTime,m.projected.join(' | '),reviewHistoryStatusNames[m.status]||m.status])].map(row=>row.map(csvCell).join(';')).join('\r\n');
 const blob=new Blob(['\ufeff'+lines],{type:'text/csv;charset=utf-8'});const url=URL.createObjectURL(blob);const a=document.createElement('a');a.href=url;a.download='historico_revisoes_'+String(P.name||'aluno').replace(/[^a-z0-9]+/gi,'_').toLowerCase()+'.csv';document.body.appendChild(a);a.click();a.remove();setTimeout(()=>URL.revokeObjectURL(url),1000);
};
'''

CSS = r'''
/* GLOBAL REVIEW HISTORY V1 */
.review-history-global{margin-top:22px}
.review-history-stats{grid-template-columns:repeat(5,minmax(120px,1fr));margin:18px 0}
.review-history-filters{display:grid;grid-template-columns:minmax(260px,2fr) repeat(3,minmax(170px,1fr));gap:12px;margin:16px 0}
.review-history-filters label{display:grid;gap:6px;font-size:12px;font-weight:700;color:var(--muted)}
.review-history-filters input,.review-history-filters select{width:100%;min-height:42px}
.review-history-caption{display:flex;justify-content:space-between;gap:20px;align-items:center;color:var(--muted);font-size:12px;margin:8px 0 12px}
.review-history-table{min-width:1650px}
.review-history-table th{position:sticky;top:0;z-index:1}
.review-history-table td{vertical-align:top;min-width:130px}
.review-history-table td:nth-child(2){min-width:240px}
.review-history-table td:nth-child(7){min-width:230px}
.review-history-table td:last-child{min-width:280px}
.review-date-chips{display:flex;gap:5px;flex-wrap:wrap}
.review-date-chip{display:inline-flex;padding:4px 7px;border-radius:999px;background:#fbecee;border:1px solid #efc8ce;font-size:11px;white-space:nowrap}
.projection-note{display:block;margin-top:6px;max-width:220px}
.review-history-detail summary{cursor:pointer;font-weight:700;color:var(--primary);margin-bottom:7px}
.review-history-events{min-width:310px;max-height:360px;overflow:auto;padding:10px 12px;background:#fff7f8;border:1px solid var(--line);border-radius:12px}
.review-history-events h4{margin:7px 0}.review-history-events ul{margin:0 0 12px;padding-left:20px}.review-history-events li{margin:7px 0;line-height:1.35}
.review-history-actions{display:flex;gap:6px;flex-wrap:wrap;margin-top:9px}
@media(max-width:1050px){.review-history-stats{grid-template-columns:repeat(2,minmax(140px,1fr))}.review-history-filters{grid-template-columns:1fr 1fr}.review-history-caption{align-items:flex-start;flex-direction:column}}
@media(max-width:650px){.review-history-stats,.review-history-filters{grid-template-columns:1fr}.review-history-table{min-width:1400px}}
'''


def main():
    static = ROOT / 'static'
    js_path = static / 'review_history.js'
    js_path.write_text(REVIEW_HISTORY_JS, encoding='utf-8')

    html_path = static / 'app.html'
    html = html_path.read_text(encoding='utf-8')
    if '/static/review_history.js' not in html:
        pattern = r'(<script src="/static/study_schedule\.js\?v=[^"]+" defer></script>)'
        replacement = r'\1\n<script src="/static/review_history.js?v=3.2.0" defer></script>'
        html, count = re.subn(pattern, replacement, html, count=1)
        if not count:
            html = html.replace('</body>', '<script src="/static/review_history.js?v=3.2.0" defer></script>\n</body>', 1)
    html_path.write_text(html, encoding='utf-8')

    css_path = static / 'style.css'
    css = css_path.read_text(encoding='utf-8')
    if CSS_MARKER not in css:
        css = css.rstrip() + '\n\n' + CSS.strip() + '\n'
    css_path.write_text(css, encoding='utf-8')
    print('MEUCRONOGRAMA_REVIEW_HISTORY_READY: global review history, next dates, projections, filters and CSV export prepared.', flush=True)


if __name__ == '__main__':
    main()
