"""Hotfix v3.7.5: paper-style student report cards with cover-first layout."""
from pathlib import Path
import re

ROOT=Path(__file__).resolve().parent
STATIC=ROOT/"static"
JS_MARK="// === REPORT PAPER LAYOUT V3.7.5 ==="
CSS_MARK="/* === REPORT PAPER LAYOUT V3.7.5 === */"

JS=r'''
// === REPORT PAPER LAYOUT V3.7.5 ===
function reportPaperCoverHtml(report){
 const cover=String(report?.cover||'').trim();
 if(cover){
  return '<div class="report-paper-cover-wrap"><img class="report-paper-cover" src="'+esc(cover)+'" alt="Capa de '+esc(report.name||report.title||'relatório')+'"></div>';
 }
 return '<div class="report-paper-cover-wrap"><div class="report-paper-cover report-paper-placeholder"><div class="report-paper-placeholder-mark">Qi</div><span>Relatório</span></div></div>';
}
function reportPaperCardHtml(group,report){
 const name=report?.name||report?.title||report?.activity||'Relatório';
 const activity=String(report?.activity||'').trim();
 const showActivity=activity&&activity.toLocaleLowerCase('pt-BR')!==String(name).trim().toLocaleLowerCase('pt-BR');
 return '<article class="student-report-card report-paper-card">'+
  reportPaperCoverHtml(report)+
  '<div class="report-paper-info">'+
   '<span class="report-paper-type">'+esc(group?.name||'Relatório')+'</span>'+
   '<h3 class="report-paper-title">'+esc(name)+'</h3>'+
   (showActivity?'<p class="report-paper-activity">'+esc(activity)+'</p>':'')+
   (report?.date?'<time class="report-paper-date">'+esc(report.date)+'</time>':'')+
   (report?.description?'<p class="report-paper-description">'+esc(report.description)+'</p>':'')+
   '<a class="primary report-open-link report-paper-open" href="'+esc(report.url)+'" target="_blank" rel="noopener noreferrer">Abrir relatório</a>'+
  '</div>'+
 '</article>';
}
reportsView=function(){
 const id=reportTargetId(),key=id||'__none__';
 if(!studentReportsCache.has(key))queueMicrotask(()=>loadStudentReports());
 const d=studentReportsCache.get(key);
 if(!d)return head('Meus relatórios','Relatórios individuais disponibilizados pela coordenação.')+'<section class="card"><p>Carregando relatórios…</p></section>';
 if(d.error)return head('Meus relatórios','Relatórios individuais disponibilizados pela coordenação.')+'<section class="card"><div class="notice warning">'+esc(d.error)+'</div></section>';
 if(!d.student&&['master','coordenador'].includes(ME.role))return head('Meus relatórios','Selecione um aluno no campo de pesquisa para visualizar os relatórios dele.')+'<section class="card"><div class="notice">Nenhum aluno selecionado.</div></section>';
 const groups=d.groups||[];
 const body=groups.length?groups.map(group=>
  '<section class="card student-report-group report-paper-group">'+
   '<div class="student-report-group-head"><div><p class="eyebrow">RELATÓRIOS</p><h2>'+esc(group.name)+'</h2></div><span>'+group.reports.length+' relatório(s)</span></div>'+
   '<div class="student-report-row report-paper-grid">'+group.reports.map(report=>reportPaperCardHtml(group,report)).join('')+'</div>'+
  '</section>'
 ).join(''):'<section class="card"><div class="notice">Ainda não há relatórios publicados para este aluno.</div></section>';
 return head('Meus relatórios',d.student?'Relatórios disponíveis para '+esc(d.student.name)+'.':'Relatórios individuais disponibilizados pela coordenação.')+body;
};
'''

CSS=r'''
/* === REPORT PAPER LAYOUT V3.7.5 === */
.report-paper-group{gap:1rem}.report-paper-group .student-report-group-head{align-items:flex-end}.report-paper-group .student-report-group-head h2{margin:.05rem 0 0}.report-paper-grid{display:grid!important;grid-template-columns:repeat(auto-fill,minmax(220px,260px));gap:1.35rem!important;align-items:start;overflow:visible!important;padding:.35rem!important}.student-report-card.report-paper-card{position:relative;display:flex!important;flex-direction:column!important;width:100%!important;min-width:0!important;max-width:260px!important;min-height:0!important;padding:10px 10px 14px!important;gap:0!important;background:#fff!important;border:1px solid #e5d9dc!important;border-radius:4px!important;box-shadow:0 8px 22px rgba(74,35,43,.10)!important;overflow:hidden}.student-report-card.report-paper-card:before{content:'';position:absolute;top:0;right:0;width:22px;height:22px;background:linear-gradient(225deg,#f7ecee 49%,transparent 51%);pointer-events:none;z-index:2}.report-paper-cover-wrap{width:100%;padding:0;margin:0;background:#f8f4f5;border:1px solid #eee4e7;overflow:hidden}.report-paper-cover{display:block;width:100%!important;height:auto!important;aspect-ratio:210/297;object-fit:cover!important;border:0!important;border-radius:0!important;background:#fff!important}.report-paper-placeholder{display:flex!important;flex-direction:column;align-items:center;justify-content:center;gap:.7rem;color:#9f4351}.report-paper-placeholder-mark{width:72px;height:72px;border-radius:50%;display:grid;place-items:center;background:#d90818;color:#fff;font-size:1.6rem;font-weight:800}.report-paper-placeholder span{font-size:.8rem;text-transform:uppercase;letter-spacing:.12em}.report-paper-info{display:flex;flex-direction:column;align-items:stretch;min-height:150px;padding:12px 6px 2px}.report-paper-type{font-size:.68rem;font-weight:800;text-transform:uppercase;letter-spacing:.14em;color:#b65362;margin-bottom:.45rem}.report-paper-title{font-size:1rem;line-height:1.28;margin:0 0 .45rem!important;color:#20191b;min-height:2.55em}.report-paper-activity{font-size:.78rem;line-height:1.3;margin:0 0 .3rem;color:#57484c}.report-paper-date{font-size:.75rem;color:#7b686d;margin-bottom:.45rem}.report-paper-description{font-size:.75rem;line-height:1.35;color:#6d5b60;margin:.25rem 0 .65rem}.report-paper-open{display:block;width:100%;box-sizing:border-box;text-align:center;margin-top:auto!important;padding:.62rem .75rem!important;text-decoration:none;border-radius:8px!important;font-size:.82rem}.student-report-cover,.student-report-content{transition:none}
@media(max-width:700px){.report-paper-grid{grid-template-columns:repeat(auto-fill,minmax(185px,1fr))}.student-report-card.report-paper-card{max-width:none!important}.report-paper-info{min-height:140px}}
@media(max-width:430px){.report-paper-grid{grid-template-columns:1fr}.student-report-card.report-paper-card{max-width:260px!important;margin:0 auto}}
'''

def main():
    js=STATIC/'student_summary.js'
    source=js.read_text(encoding='utf-8')
    if JS_MARK not in source:
        js.write_text(source.rstrip()+"\n\n"+JS.strip()+"\n",encoding='utf-8')

    css=STATIC/'style.css'
    source=css.read_text(encoding='utf-8')
    if CSS_MARK not in source:
        css.write_text(source.rstrip()+"\n\n"+CSS.strip()+"\n",encoding='utf-8')

    html=STATIC/'app.html'
    source=html.read_text(encoding='utf-8')
    source=re.sub(r'/static/student_summary\.js\?v=[^"\']+','/static/student_summary.js?v=3.7.5',source)
    html.write_text(source,encoding='utf-8')

    for verifier in ROOT.glob('verify_*.py'):
        source=verifier.read_text(encoding='utf-8')
        source=source.replace('/static/student_summary.js?v=3.7.4','/static/student_summary.js?v=3.7.5')
        source=source.replace('/static/student_summary.js?v=3.7.3','/static/student_summary.js?v=3.7.5')
        verifier.write_text(source,encoding='utf-8')

    site=ROOT/'site_version_release.py'
    source=site.read_text(encoding='utf-8').replace('PUBLIC_VERSION="3.7.4"','PUBLIC_VERSION="3.7.5"')
    site.write_text(source,encoding='utf-8')
    vsite=ROOT/'verify_site_version.py'
    source=vsite.read_text(encoding='utf-8').replace('v3.7.4','v3.7.5')
    vsite.write_text(source,encoding='utf-8')

    print("MEUCRONOGRAMA_REPORT_PAPER_LAYOUT_READY: report cards now render as document sheets with cover above and title below.",flush=True)

if __name__=='__main__':
    main()
