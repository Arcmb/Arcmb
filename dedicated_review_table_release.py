"""Create a dedicated review-table page and apply the Qi logo with final precedence.

This patch runs after every previous UI extension. It:
- adds a permanent 'Tabela de revisões' navigation entry;
- renders the monthly matrix and the global history on that dedicated page;
- removes duplicate review tables from 'Minhas revisões';
- replaces approximated marks with a faithful Qi logo asset;
- keeps the site background white and the pastel-red Qi palette.
"""
from pathlib import Path
import re

ROOT=Path(__file__).resolve().parent
JS_MARK='// === DEDICATED REVIEW TABLE PAGE V1 ==='
CSS_MARK='/* === DEDICATED REVIEW TABLE PAGE V1 === */'

QI_LOGO='''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512" role="img" aria-labelledby="title desc">
<title id="title">Qi Vestibulares</title>
<desc id="desc">Logomarca Qi: círculo vermelho com símbolo Qi branco</desc>
<circle cx="256" cy="256" r="246" fill="#e00613"/>
<path d="M205 352C132 352 77 298 77 226S132 99 205 99s128 54 128 127c0 15-2 30-7 44" fill="none" stroke="#fff" stroke-width="52" stroke-linecap="round"/>
<path d="M220 270l111 111" fill="none" stroke="#fff" stroke-width="52" stroke-linecap="round"/>
<circle cx="388" cy="171" r="29" fill="#fff"/>
<rect x="359" y="217" width="58" height="157" rx="29" fill="#fff"/>
</svg>'''

JS=r'''
// === DEDICATED REVIEW TABLE PAGE V1 ===
(function(){
 'use strict';

 function qiInstallReviewNav(){
  if(typeof navItems==='undefined'||!Array.isArray(navItems))return;
  if(navItems.some(item=>item&&item[0]==='review-table'))return;
  const reviewsIndex=navItems.findIndex(item=>item&&item[0]==='reviews');
  navItems.splice(reviewsIndex>=0?reviewsIndex+1:navItems.length,0,['review-table','Tabela de revisões']);
 }
 qiInstallReviewNav();

 function qiRemoveEmbeddedReviewTables(html){
  const template=document.createElement('template');
  template.innerHTML=String(html||'');
  template.content.querySelectorAll('.review-calendar-card,.review-history-global,.qi-review-overview').forEach(node=>node.remove());
  return template.innerHTML;
 }

 if(typeof reviewsView==='function'){
  const qiReviewsWithoutTables=reviewsView;
  reviewsView=function(){return qiRemoveEmbeddedReviewTables(qiReviewsWithoutTables());};
 }

 function qiDedicatedReviewTableView(){
  const calendar=typeof reviewCalendarSection==='function'
   ?reviewCalendarSection()
   :'<section class="card"><h2>Calendário mensal</h2><p>A tabela mensal não pôde ser carregada. Atualize a página.</p></section>';
  const history=typeof reviewHistorySection==='function'
   ?reviewHistorySection()
   :'<section class="card"><h2>Histórico das revisões</h2><p>O histórico não pôde ser carregado. Atualize a página.</p></section>';
  return head('Tabela de revisões','Visão global de disciplinas, conteúdos estudados, revisões realizadas e próximas datas programadas.')+
   '<div class="notice review-table-intro"><strong>Como usar:</strong> consulte o mês, clique numa revisão para ajustar ou registrar o resultado e use a tabela inferior para acompanhar todo o histórico do conteúdo.</div>'+
   '<div class="review-table-page">'+calendar+history+'</div>';
 }
 globalThis.reviewTableView=qiDedicatedReviewTableView;

 if(typeof render==='function'){
  const qiRenderBeforeDedicatedReview=render;
  render=function(){
   qiInstallReviewNav();
   if(typeof view!=='undefined'&&view==='review-table'&&!(typeof ME!=='undefined'&&ME.must_change)){
    const desired=view;
    view='home';
    qiRenderBeforeDedicatedReview.apply(this,arguments);
    view=desired;
    if(typeof renderNav==='function')renderNav();
    const main=document.querySelector('#main');
    if(main)main.innerHTML=qiDedicatedReviewTableView();
    queueMicrotask(()=>{if(typeof renderReviewHistoryRows==='function')renderReviewHistoryRows();});
    return;
   }
   return qiRenderBeforeDedicatedReview.apply(this,arguments);
  };
 }

 document.addEventListener('DOMContentLoaded',()=>{
  qiInstallReviewNav();
  if(typeof renderNav==='function')renderNav();
 },{once:true});
})();
'''

CSS=r'''
/* === DEDICATED REVIEW TABLE PAGE V1 === */
html,body{background:#fff!important}
.logo{width:54px!important;height:54px!important;padding:0!important;border-radius:50%!important;overflow:hidden!important;background:#fff!important;box-shadow:0 6px 18px rgba(111,25,38,.22)!important;flex:0 0 54px}
.logo img{display:block!important;width:100%!important;height:100%!important;object-fit:contain!important;border-radius:50%!important;background:#fff!important}
.review-table-intro{margin-bottom:16px}
.review-table-page{display:grid;gap:18px}
.review-table-page .review-calendar-card,.review-table-page .review-history-global{margin:0!important;display:block!important;visibility:visible!important;opacity:1!important}
.review-table-page .review-calendar-wrap,.review-table-page .table-wrap{background:#fff}
.review-table-page table{background:#fff}
.review-table-page .review-calendar-table td.review-cal-discipline,.review-table-page .review-calendar-table td.review-cal-subject{background:#fff}
@media(max-width:760px){.logo{width:46px!important;height:46px!important;flex-basis:46px}.review-table-page{gap:12px}}
'''


def patch_static():
    static=ROOT/'static'
    static.mkdir(exist_ok=True)
    (static/'qi-logo.svg').write_text(QI_LOGO,encoding='utf-8')
    (static/'icon.svg').write_text(QI_LOGO,encoding='utf-8')
    (static/'review_table_page.js').write_text(JS,encoding='utf-8')

    html_path=static/'app.html'
    html=html_path.read_text(encoding='utf-8')
    logo_markup='<span class="logo"><img src="/static/qi-logo.svg?v=5.0.0" alt="Qi Vestibulares"></span>'
    html=re.sub(r'<span class="logo">.*?</span>',logo_markup,html,count=1,flags=re.S)
    html=re.sub(r'/static/qi-logo\.svg(?:\?v=[^"\']+)?','/static/qi-logo.svg?v=5.0.0',html)
    html=re.sub(r'/static/style\.css(?:\?v=[^"\']+)?','/static/style.css?v=5.0.0',html)
    if '/static/review_table_page.js' not in html:
        html=html.replace('</body>','<script src="/static/review_table_page.js?v=5.0.0" defer></script>\n</body>',1)
    html_path.write_text(html,encoding='utf-8')

    for filename in ('login.html','setup.html'):
        path=static/filename
        if not path.exists():continue
        text=path.read_text(encoding='utf-8')
        text=re.sub(r'/static/qi-logo\.svg(?:\?v=[^"\']+)?','/static/qi-logo.svg?v=5.0.0',text)
        text=re.sub(r'/static/style\.css(?:\?v=[^"\']+)?','/static/style.css?v=5.0.0',text)
        path.write_text(text,encoding='utf-8')

    css_path=static/'style.css'
    css=css_path.read_text(encoding='utf-8')
    if CSS_MARK not in css:css=css.rstrip()+'\n\n'+CSS+'\n'
    css_path.write_text(css,encoding='utf-8')


def patch_server():
    path=ROOT/'webapp.py'
    text=path.read_text(encoding='utf-8')
    mapping="'review_table_page.js':'application/javascript; charset=utf-8'"
    if mapping not in text:
        anchors=[
            "'student_guidance.js':'application/javascript; charset=utf-8'",
            "'schedule_admin_refinement.js':'application/javascript; charset=utf-8'",
            "'review_calendar_table.js':'application/javascript; charset=utf-8'",
        ]
        for anchor in anchors:
            if anchor in text:
                text=text.replace(anchor,anchor+','+mapping,1)
                break
        else:raise RuntimeError('Static JavaScript mapping anchor not found in webapp.py.')
    path.write_text(text,encoding='utf-8')


def main():
    patch_static();patch_server()
    print('MEUCRONOGRAMA_DEDICATED_REVIEW_TABLE_READY: dedicated tab, monthly matrix, global history and Qi logo prepared.',flush=True)

if __name__=='__main__':main()
