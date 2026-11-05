"""Add a progressive academic dashboard to the student home view.

The existing student-summary API is extended with routine/review execution
counts. The home page then presents the latest simulation, area and discipline
results, simulation evolution, learning priorities, revisions and activities.
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parent
STATIC = ROOT / 'static'
BACKEND_MARKER = '# === MEU CRONOGRAMA: TRAJETÓRIA ACADÊMICA NA VISÃO GERAL ==='
JS_MARKER = '// === MEU CRONOGRAMA: TRAJETÓRIA ACADÊMICA NA VISÃO GERAL ==='
CSS_MARKER = '/* MEU CRONOGRAMA: TRAJETÓRIA ACADÊMICA NA VISÃO GERAL */'

BACKEND = r'''

# === MEU CRONOGRAMA: TRAJETÓRIA ACADÊMICA NA VISÃO GERAL ===
_ss_home_original_student_summary = student_summary


def _ss_home_profile_engagement(profile):
    from datetime import date as _ss_home_date_type, timedelta as _ss_home_timedelta

    sessions = profile.get('sessions') if isinstance(profile.get('sessions'), list) else []
    contents = profile.get('contents') if isinstance(profile.get('contents'), list) else []
    feedback = profile.get('feedback') if isinstance(profile.get('feedback'), list) else []

    activity = {'planned': 0, 'done': 0, 'partial': 0, 'missed': 0, 'totalClosed': 0}
    reviews = {'planned': 0, 'done': 0, 'partial': 0, 'missed': 0, 'overdue': 0, 'dueSoon': 0}
    by_kind = {
        'study': {'planned': 0, 'done': 0, 'partial': 0, 'missed': 0},
        'review': {'planned': 0, 'done': 0, 'partial': 0, 'missed': 0},
        'action': {'planned': 0, 'done': 0, 'partial': 0, 'missed': 0},
    }
    for session in sessions:
        if not isinstance(session, dict):
            continue
        status = F.text(session.get('status'), 30).lower()
        kind = F.text(session.get('kind'), 30).lower()
        if status in activity:
            activity[status] += 1
        if kind in by_kind and status in by_kind[kind]:
            by_kind[kind][status] += 1
        if kind == 'review' and status in reviews:
            reviews[status] += 1

    activity['totalClosed'] = activity['done'] + activity['partial'] + activity['missed']
    activity['completionRate'] = (
        None if not activity['totalClosed']
        else round(100 * (activity['done'] + .5 * activity['partial']) / activity['totalClosed'], 2)
    )

    today = _ss_home_date_type.today()
    soon = today + _ss_home_timedelta(days=7)
    for content in contents:
        if not isinstance(content, dict):
            continue
        if F.text(content.get('status'), 30).lower() != 'studied' or content.get('paused'):
            continue
        raw_due = F.text(content.get('nextDue'), 40)
        if not raw_due:
            continue
        try:
            due = _ss_home_date_type.fromisoformat(raw_due[:10])
        except (TypeError, ValueError):
            continue
        if due < today:
            reviews['overdue'] += 1
        elif due <= soon:
            reviews['dueSoon'] += 1

    actual_minutes = 0
    questions = correct = 0
    for item in feedback:
        if not isinstance(item, dict):
            continue
        actual_minutes += max(0, _ss_num(item.get('actualMin')))
        questions += max(0, _ss_num(item.get('total')))
        correct += max(0, _ss_num(item.get('correct')))

    return {
        'activities': activity,
        'reviews': reviews,
        'byKind': by_kind,
        'feedback': {
            'records': len([x for x in feedback if isinstance(x, dict)]),
            'minutes': actual_minutes,
            'questions': questions,
            'correct': correct,
            'accuracy': None if not questions else round(100 * correct / questions, 2),
        },
    }


def student_summary(app, c, user, target):
    result = _ss_home_original_student_summary(app, c, user, target)
    state_row = app.db.execute(c, 'SELECT profile FROM hmay_state WHERE user_id=?', (target['id'],)).fetchone()
    profile = _rx_json(state_row['profile']) if state_row else {}
    result['engagement'] = _ss_home_profile_engagement(profile)
    return result
'''

JS_APPENDIX = r'''

// === MEU CRONOGRAMA: TRAJETÓRIA ACADÊMICA NA VISÃO GERAL ===
const studentHomeAreaLabels={LC:'Linguagens',CH:'Humanas',CN:'Natureza',MT:'Matemática',RED:'Redação'};
function studentHomeNumber(value){const n=Number(value);return Number.isFinite(n)?n:0;}
function studentHomePct(value){return value===null||value===undefined?'—':studentHomeNumber(value).toLocaleString('pt-BR',{minimumFractionDigits:1,maximumFractionDigits:1})+'%';}
function studentHomeAreaName(name){const raw=String(name||'Não informado').trim();return studentHomeAreaLabels[raw.toUpperCase()]||raw;}
function studentHomeAccuracy(item){return item&&item.accuracy!==null&&item.accuracy!==undefined?studentHomeNumber(item.accuracy):null;}
function studentHomeBar(item,label){
 const accuracy=studentHomeAccuracy(item),width=accuracy===null?0:Math.max(0,Math.min(100,accuracy));
 return `<div class="student-home-bar-row"><div class="student-home-bar-label"><strong>${esc(label||item?.name||'Não informado')}</strong><span>${item?.correct||0}/${item?.total||0} · ${studentHomePct(accuracy)}</span></div><div class="student-home-bar"><span style="width:${width}%"></span></div></div>`;
}
function studentHomeEvolution(simulations){
 const rows=[...(simulations||[])].reverse().slice(-10);
 if(!rows.length)return '<div class="notice">O primeiro simulado ainda não foi associado a este perfil.</div>';
 const bars=rows.map((x,index)=>{const accuracy=studentHomeAccuracy(x),height=Math.max(8,Math.min(100,accuracy===null?0:accuracy));return `<div class="student-home-evolution-item" title="${esc(x.activity||'Simulado')} · ${esc(x.date||'')} · ${studentHomePct(accuracy)}"><span class="student-home-evolution-value">${studentHomePct(accuracy)}</span><div class="student-home-evolution-track"><span style="height:${height}%"></span></div><small>${index+1}º</small></div>`;}).join('');
 return `<div class="student-home-evolution">${bars}</div><p class="micro">${rows.length===1?'Este resultado é o ponto de partida. A evolução aparecerá quando novos simulados forem importados.':'Cada coluna representa um simulado, em ordem cronológica.'}</p>`;
}
function studentHomeRankRows(rows,mode='need',limit=5){
 const usable=(rows||[]).filter(x=>studentHomeNumber(x.marked)>0&&studentHomeAccuracy(x)!==null);
 usable.sort((a,b)=>mode==='strength'?(studentHomeAccuracy(b)-studentHomeAccuracy(a)||studentHomeNumber(b.marked)-studentHomeNumber(a.marked)):(studentHomeAccuracy(a)-studentHomeAccuracy(b)||studentHomeNumber(b.marked)-studentHomeNumber(a.marked)));
 return usable.slice(0,limit);
}
function studentHomeDashboard(){
 const id=studentSummaryTarget();
 if(!studentSummaryCache.has(id)&&!studentSummaryLoading.has(id))queueMicrotask(()=>loadStudentSummary());
 if(studentSummaryLoading.has(id)||!studentSummaryCache.has(id))return `<section class="card student-home-dashboard"><h2>Meu desempenho e trajetória</h2><p>Carregando simulados, revisões e atividades…</p></section>`;
 const d=studentSummaryCache.get(id);
 if(d?.error)return `<section class="card student-home-dashboard"><h2>Meu desempenho e trajetória</h2><div class="notice warning">${esc(d.error)}</div>${button('Tentar novamente','student-summary-refresh','secondary')}</section>`;
 const p=d.performance||{},s=d.study||{},e=d.engagement||{},activities=e.activities||{},reviews=e.reviews||{};
 const latest=(d.simulations||[])[0]||null;
 const latestAreas=latest?.areas||[];
 const priorities=studentHomeRankRows(d.aggregates?.discipline||[],'need',5);
 const strengths=studentHomeRankRows(d.aggregates?.discipline||[],'strength',4);
 const latestAccuracy=latest?studentHomeAccuracy(latest):null;
 const ring=latest?`<div class="student-home-ring" style="--student-progress:${Math.max(0,Math.min(100,latestAccuracy||0))}%"><div><strong>${studentHomePct(latestAccuracy)}</strong><span>aproveitamento</span></div></div>`:`<div class="student-home-ring is-empty"><div><strong>—</strong><span>sem simulado</span></div></div>`;
 const latestText=latest?`<p class="eyebrow">Resultado mais recente</p><h3>${esc(latest.activity||'Simulado')}</h3><p>${esc(latest.date||'Data não informada')} · prova ${esc(latest.color||'sem cor')} ${latest.language?'· '+esc(latest.language):''}</p><p class="student-home-score"><strong>${latest.correct||0}</strong><span>acertos em ${latest.valid||0} questões válidas</span></p>`:`<p class="eyebrow">Desempenho acadêmico</p><h3>Nenhum simulado vinculado</h3><p>Quando um resultado for importado para esta conta, ele aparecerá aqui automaticamente.</p>`;
 const areaHtml=latestAreas.length?latestAreas.map(x=>studentHomeBar(x,studentHomeAreaName(x.name))).join(''):'<div class="notice">O simulado atual ainda não possui divisão por área disponível.</div>';
 const priorityHtml=priorities.length?priorities.map(x=>studentHomeBar(x,x.name)).join(''):'<div class="notice">Ainda não há base suficiente para indicar prioridades por disciplina.</div>';
 const strengthHtml=strengths.length?strengths.map(x=>`<span class="student-home-chip"><strong>${esc(x.name)}</strong> ${studentHomePct(x.accuracy)}</span>`).join(''):'<span class="micro">Os destaques aparecerão após a primeira análise por disciplina.</span>';
 const completion=activities.completionRate;
 return `<section class="card student-home-dashboard"><div class="student-home-dashboard-head"><div><p class="eyebrow">Trajetória acadêmica</p><h2>Meu desempenho e progresso</h2><p>Simulados, conteúdos, revisões e atividades registrados neste perfil.</p></div><div class="actions">${button('Atualizar','student-summary-refresh','secondary')}${button('Ver desempenho completo','student-home-performance','primary')}</div></div><div class="student-home-summary-grid"><div class="student-home-latest">${ring}<div>${latestText}</div></div><div class="student-home-kpis"><div><strong>${p.simulations||0}</strong><span>simulado(s)</span></div><div><strong>${p.correct||0}</strong><span>acertos acumulados</span></div><div><strong>${s.studied||0}/${s.contents||0}</strong><span>conteúdos estudados</span></div><div><strong>${studentSummaryMinutes(s.actualMinutes||0)}</strong><span>tempo registrado</span></div></div></div><div class="student-home-columns"><div class="student-home-block"><h3>Desempenho por área</h3>${areaHtml}</div><div class="student-home-block"><h3>Evolução nos simulados</h3>${studentHomeEvolution(d.simulations||[])}</div></div><div class="student-home-columns"><div class="student-home-block"><h3>Trilha de aprendizagem</h3><p class="micro">Disciplinas com menor aproveitamento acumulado aparecem primeiro e orientam a próxima prévia do cronograma.</p>${priorityHtml}<h4>Destaques</h4><div class="student-home-chips">${strengthHtml}</div></div><div class="student-home-block"><h3>Execução da rotina</h3><div class="student-home-mini-stats"><div><strong>${activities.done||0}</strong><span>atividades concluídas</span></div><div><strong>${activities.partial||0}</strong><span>parciais</span></div><div><strong>${activities.missed||0}</strong><span>não realizadas</span></div><div><strong>${studentHomePct(completion)}</strong><span>índice de execução</span></div></div><h4>Revisões</h4><div class="student-home-mini-stats"><div><strong>${(reviews.done||0)+(reviews.partial||0)}</strong><span>realizadas</span></div><div><strong>${reviews.planned||0}</strong><span>programadas</span></div><div><strong>${reviews.overdue||0}</strong><span>vencidas</span></div><div><strong>${reviews.dueSoon||0}</strong><span>nos próximos 7 dias</span></div></div><div class="actions">${button('Abrir revisões','student-home-reviews','secondary')}${button('Abrir quadro semanal','student-home-calendar','secondary')}</div></div></div><p class="micro student-home-footnote">Os resultados acadêmicos orientam prioridades relativas; horários só mudam depois de gerar, conferir e confirmar uma nova proposta.</p></section>`;
}

const studentHomeOriginalHomeView=homeView;
homeView=function(){
 const base=studentHomeOriginalHomeView();
 const panel=studentHomeDashboard();
 const marker='<div class="columns">';
 const pos=base.indexOf(marker);
 return pos>=0?base.slice(0,pos)+panel+base.slice(pos):base+panel;
};

acts['student-home-performance']=()=>{view='performance';render();window.scrollTo(0,0);};
acts['student-home-reviews']=()=>{view='reviews';render();window.scrollTo(0,0);};
acts['student-home-calendar']=()=>{view='calendar';render();window.scrollTo(0,0);};
'''

CSS = r'''
/* MEU CRONOGRAMA: TRAJETÓRIA ACADÊMICA NA VISÃO GERAL */
.student-home-dashboard{margin-top:1rem;display:grid;gap:1rem}
.student-home-dashboard-head{display:flex;justify-content:space-between;gap:1rem;align-items:flex-start}
.student-home-dashboard-head h2{margin:.15rem 0 .35rem}
.student-home-summary-grid{display:grid;grid-template-columns:minmax(260px,1.2fr) minmax(320px,1.8fr);gap:1rem}
.student-home-latest{display:grid;grid-template-columns:auto 1fr;align-items:center;gap:1rem;padding:1rem;border:1px solid #ded8f0;border-radius:16px;background:#faf9fe}
.student-home-latest h3{margin:.15rem 0}
.student-home-score{display:flex;align-items:baseline;gap:.5rem;margin:.65rem 0 0}
.student-home-score strong{font-size:2rem}
.student-home-ring{--student-progress:0%;width:112px;height:112px;border-radius:50%;display:grid;place-items:center;background:conic-gradient(#6b50b5 var(--student-progress),#ebe7f6 0);position:relative;flex:none}
.student-home-ring:before{content:"";position:absolute;inset:10px;border-radius:50%;background:#fff}
.student-home-ring>div{position:relative;display:grid;text-align:center;line-height:1.1}
.student-home-ring strong{font-size:1.35rem}
.student-home-ring span{font-size:.72rem;color:#655f75}
.student-home-ring.is-empty{background:#ebe7f6}
.student-home-kpis{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:.7rem}
.student-home-kpis>div,.student-home-mini-stats>div{border:1px solid #e2ddef;border-radius:14px;padding:.9rem;background:#fff;display:grid;gap:.2rem}
.student-home-kpis strong,.student-home-mini-stats strong{font-size:1.35rem}
.student-home-kpis span,.student-home-mini-stats span{font-size:.78rem;color:#655f75}
.student-home-columns{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:1rem}
.student-home-block{border:1px solid #e2ddef;border-radius:16px;padding:1rem;background:#fff;min-width:0}
.student-home-block h3{margin-top:0}
.student-home-block h4{margin:1rem 0 .5rem}
.student-home-bar-row{display:grid;gap:.35rem;margin:.8rem 0}
.student-home-bar-label{display:flex;justify-content:space-between;gap:1rem;align-items:baseline}
.student-home-bar-label span{font-size:.78rem;color:#655f75;text-align:right}
.student-home-bar{height:9px;border-radius:999px;background:#ece8f6;overflow:hidden}
.student-home-bar span{display:block;height:100%;border-radius:inherit;background:linear-gradient(90deg,#6b50b5,#9278d0)}
.student-home-evolution{height:180px;display:flex;align-items:flex-end;gap:.6rem;padding:.8rem .35rem .2rem;border-bottom:1px solid #ded8f0;overflow-x:auto}
.student-home-evolution-item{height:100%;min-width:42px;display:grid;grid-template-rows:auto 1fr auto;gap:.3rem;justify-items:center}
.student-home-evolution-value{font-size:.7rem;color:#655f75;white-space:nowrap}
.student-home-evolution-track{height:100%;width:22px;border-radius:8px 8px 3px 3px;background:#eeeaf7;display:flex;align-items:flex-end;overflow:hidden}
.student-home-evolution-track span{display:block;width:100%;min-height:5px;background:#6b50b5;border-radius:7px 7px 2px 2px}
.student-home-chips{display:flex;flex-wrap:wrap;gap:.45rem}
.student-home-chip{display:inline-flex;gap:.35rem;align-items:center;padding:.4rem .65rem;border-radius:999px;background:#eee9fb;font-size:.78rem}
.student-home-mini-stats{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:.55rem}
.student-home-footnote{margin:0;padding-top:.2rem;border-top:1px solid #eeeaf6}
@media(max-width:900px){.student-home-summary-grid,.student-home-columns{grid-template-columns:1fr}.student-home-dashboard-head{display:grid}.student-home-latest{grid-template-columns:1fr;text-align:center}.student-home-ring{margin:auto}.student-home-score{justify-content:center}}
@media(max-width:560px){.student-home-kpis,.student-home-mini-stats{grid-template-columns:1fr}.student-home-bar-label{align-items:flex-start}.student-home-ring{width:96px;height:96px}}
'''


def main():
    model_path = ROOT / 'model_data.py'
    model = model_path.read_text(encoding='utf-8')
    if BACKEND_MARKER not in model:
        model = model.rstrip() + BACKEND + '\n'
    model_path.write_text(model, encoding='utf-8')

    js_path = STATIC / 'student_summary.js'
    js = js_path.read_text(encoding='utf-8')
    js = js.replace("if(view==='performance')render();", "if(view==='performance'||view==='home')render();")
    if JS_MARKER not in js:
        js = js.rstrip() + JS_APPENDIX + '\n'
    js_path.write_text(js, encoding='utf-8')

    css_path = STATIC / 'style.css'
    css = css_path.read_text(encoding='utf-8')
    if CSS_MARKER not in css:
        css = css.rstrip() + '\n' + CSS + '\n'
    css_path.write_text(css, encoding='utf-8')

    html_path = STATIC / 'app.html'
    html = html_path.read_text(encoding='utf-8')
    html = html.replace('/static/student_summary.js?v=2.8.7', '/static/student_summary.js?v=2.9.1')
    html = html.replace('/static/style.css?v=2.6', '/static/style.css?v=2.9.1')
    html_path.write_text(html, encoding='utf-8')
    print('MEUCRONOGRAMA_STUDENT_HOME_READY: simulations, evolution, revisions and activities now appear on the home dashboard.', flush=True)


if __name__ == '__main__':
    main()
