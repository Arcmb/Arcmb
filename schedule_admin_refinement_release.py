"""Expose study-profile assignment and refine review schedule presentation.

This build-time release:
- places profile-base controls at the top of Routine and in Master/Coordinator panels;
- clarifies that the selected account is the association target;
- sorts review disciplines with pt-BR collation;
- reports programmed minutes separately from minutes without a valid slot;
- shows the discipline in the schedule adjustment modal;
- removes the ranking label from the student TRI summary without deleting stored ranking data.
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parent
MARKER = '// === SCHEDULE ADMIN REFINEMENT V1 ==='
CSS_MARKER = '/* SCHEDULE ADMIN REFINEMENT V1 */'

ADMIN_JS = r'''"use strict";
// === SCHEDULE ADMIN REFINEMENT V1 ===
function studyPresetSelectedAccountName(){
 return String(P?.name||S?.profile?.name||'Conta selecionada');
}
function studyPresetAdminAssociation(){
 if(typeof manages!=='function'||!manages())return '';
 const actorId=typeof ME!=='undefined'?String(ME.id||''):'';
 const selectedId=String(typeof target!=='undefined'?target:'');
 const selectedName=studyPresetSelectedAccountName();
 if(actorId&&selectedId===actorId){
  return `<section class="card study-preset-association"><div class="page-head"><div><p class="eyebrow">PERFIS DE ORGANIZAÇÃO</p><h2>Associar perfil-base a um aluno</h2><p>Selecione primeiro uma conta de aluno no campo <strong>Conta</strong>, no topo da página. Depois volte a este painel para escolher e aplicar o perfil.</p></div></div></section>`;
 }
 return `<section class="card study-preset-association-intro"><div class="page-head"><div><p class="eyebrow">ALUNO SELECIONADO</p><h2>${esc(selectedName)}</h2><p>O perfil escolhido abaixo será associado somente a esta conta. Para trocar o aluno, use o campo <strong>Conta</strong> no topo.</p></div>${button('Abrir rotina do aluno','study-preset-open-routine','secondary')}</div></section>`+studyPresetPanel();
}
if(typeof accountsView==='function'){
 const studyPresetAdminBaseAccountsView=accountsView;
 accountsView=function(){return studyPresetAdminAssociation()+studyPresetAdminBaseAccountsView();};
}
if(typeof coordinatorView==='function'){
 const studyPresetAdminBaseCoordinatorView=coordinatorView;
 coordinatorView=function(){return studyPresetAdminAssociation()+studyPresetAdminBaseCoordinatorView();};
}
acts['study-preset-open-routine']=()=>{view='routine';render();window.scrollTo(0,0);};

function removeRankingFromTriSummary(root=document){
 const nodes=root.querySelectorAll?.('small,span,p')||[];
 nodes.forEach(node=>{
  if(node.childElementCount)return;
  const text=String(node.textContent||'');
  if(!/TRI\s*geral/i.test(text)||!/ranking/i.test(text))return;
  node.textContent=text.replace(/\s*[·|—-]\s*ranking\s*[-\d.,ºª]+/ig,'').replace(/\s{2,}/g,' ').trim();
 });
}
const rankingObserver=new MutationObserver(records=>{for(const record of records)for(const node of record.addedNodes)if(node.nodeType===1)removeRankingFromTriSummary(node);});
rankingObserver.observe(document.documentElement,{childList:true,subtree:true});
queueMicrotask(()=>removeRankingFromTriSummary());
'''

CSS = r'''
/* SCHEDULE ADMIN REFINEMENT V1 */
.study-preset-association,.study-preset-association-intro{margin-bottom:14px}
.study-preset-association-intro{background:#fff8f9;border-color:#e9bec5}
.study-preset-association-intro h2{margin:.15rem 0 .35rem}
.review-discipline summary .review-time-warning{color:#9b4f00;font-weight:700}
'''


def replace_once(text, old, new, label):
    if old not in text:
        raise RuntimeError(f'{label}: trecho esperado não encontrado.')
    return text.replace(old, new, 1)


def patch_study_schedule():
    path = ROOT / 'static' / 'study_schedule.js'
    source = path.read_text(encoding='utf-8')

    source = source.replace(
        "if(view==='routine')render();",
        "if(['routine','accounts','coordinator'].includes(view))render();",
        1,
    )
    source = source.replace(
        "routineView=function(){return studyBaseRoutineView()+studyPresetPanel();};",
        "routineView=function(){return studyPresetPanel()+studyBaseRoutineView();};",
        1,
    )
    source = source.replace(
        "Object.keys(groups).sort().map(name=>{",
        "Object.keys(groups).sort((a,b)=>a.localeCompare(b,'pt-BR',{sensitivity:'base'})).map(name=>{",
        1,
    )
    source = replace_once(
        source,
        "  const total=groups[name].reduce((n,c)=>n+studyReviewDuration(c),0);",
        "  const expected=groups[name].reduce((n,c)=>n+studyReviewDuration(c),0);\n  const programmed=groups[name].reduce((n,c)=>n+studyLinkedReviewSessions(c).reduce((sum,s)=>sum+Math.max(0,Number(s.end||0)-Number(s.start||0)),0),0);\n  const missing=Math.max(0,expected-programmed);",
        'cálculo dos minutos programados',
    )
    source = replace_once(
        source,
        "${groups[name].length} conteúdo(s) · ${minutes(total)} previstos",
        "${groups[name].length} conteúdo(s) · ${minutes(programmed)} programados${missing?` · <span class=\"review-time-warning\">${minutes(missing)} sem encaixe</span>`:''}",
        'resumo dos minutos da disciplina',
    )
    source = replace_once(
        source,
        "modalForm('Ajustar horário',`<p>${esc(s.title)}</p>",
        "modalForm('Ajustar horário',`<p><strong>Disciplina: ${esc(sub(s.subjectId)||'Não informada')}</strong><br>${esc(s.title)}</p>",
        'disciplina no ajuste de horário',
    )
    path.write_text(source, encoding='utf-8')


def install_admin_script():
    static = ROOT / 'static'
    (static / 'schedule_admin_refinement.js').write_text(ADMIN_JS, encoding='utf-8')

    html_path = static / 'app.html'
    html = html_path.read_text(encoding='utf-8')
    if '/static/schedule_admin_refinement.js' not in html:
        html = html.replace('</body>', '<script src="/static/schedule_admin_refinement.js?v=3.3.0" defer></script>\n</body>', 1)
    html_path.write_text(html, encoding='utf-8')

    webapp_path = ROOT / 'webapp.py'
    webapp = webapp_path.read_text(encoding='utf-8')
    mime = "'schedule_admin_refinement.js':'application/javascript; charset=utf-8'"
    if mime not in webapp:
        anchor = "'study_schedule.js':'application/javascript; charset=utf-8'"
        if anchor not in webapp:
            raise RuntimeError('Mapa de arquivos estáticos não encontrado.')
        webapp = webapp.replace(anchor, anchor + "," + mime, 1)
    webapp_path.write_text(webapp, encoding='utf-8')

    css_path = static / 'style.css'
    css = css_path.read_text(encoding='utf-8')
    if CSS_MARKER not in css:
        css += '\n' + CSS + '\n'
    css_path.write_text(css, encoding='utf-8')


def main():
    patch_study_schedule()
    install_admin_script()
    print('MEUCRONOGRAMA_SCHEDULE_ADMIN_REFINEMENT_READY: preset association exposed; review minutes and labels corrected.', flush=True)


if __name__ == '__main__':
    main()
