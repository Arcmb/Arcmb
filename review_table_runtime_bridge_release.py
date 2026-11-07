"""Make the dedicated review-table page consume the already-built review model.

The calendar/history assets are classic scripts, but their rendering helpers are
not guaranteed to become properties of window in every browser. The dedicated
page therefore saw both files with HTTP 200 and still rendered its contingency
messages. This final bridge exposes the consolidated Qi review renderer and
uses it directly, while retaining extraction and legacy fallbacks.
"""
from pathlib import Path
import re

ROOT=Path(__file__).resolve().parent
MARK='// === REVIEW TABLE RUNTIME BRIDGE V1 ==='

JS=r'''"use strict";
// === REVIEW TABLE RUNTIME BRIDGE V1 ===
(function(){
 const sourceReviewView=typeof reviewsView==='function'?reviewsView:null;

 function installNavigation(){
  if(typeof navItems==='undefined'||!Array.isArray(navItems))return;
  if(navItems.some(item=>item&&item[0]==='review-table'))return;
  const index=navItems.findIndex(item=>item&&item[0]==='reviews');
  navItems.splice(index>=0?index+1:navItems.length,0,['review-table','Tabela de revisões']);
 }
 installNavigation();

 function stripTables(html){
  const template=document.createElement('template');
  template.innerHTML=String(html||'');
  template.content.querySelectorAll('.review-calendar-card,.review-history-global,.qi-review-overview').forEach(node=>node.remove());
  return template.innerHTML;
 }

 function extractExistingTables(){
  if(typeof sourceReviewView!=='function')return '';
  try{
   const template=document.createElement('template');
   template.innerHTML=String(sourceReviewView()||'');
   const combined=template.content.querySelector('.qi-review-overview');
   if(combined)return combined.outerHTML;
   const calendar=template.content.querySelector('.review-calendar-card');
   const history=template.content.querySelector('.review-history-global');
   return [calendar&&calendar.outerHTML,history&&history.outerHTML].filter(Boolean).join('');
  }catch(error){
   console.error('Falha ao recuperar as tabelas de revisão existentes.',error);
   return '';
  }
 }

 function reviewTablesHtml(){
  try{
   if(typeof globalThis.qiReviewOverviewHtml==='function'){
    const html=globalThis.qiReviewOverviewHtml();
    if(html)return html;
   }
  }catch(error){console.error('Falha ao gerar a visão consolidada de revisões.',error);}
  const extracted=extractExistingTables();
  if(extracted)return extracted;
  const pieces=[];
  try{if(typeof reviewCalendarSection==='function')pieces.push(reviewCalendarSection());}catch(error){console.error(error);}
  try{if(typeof reviewHistorySection==='function')pieces.push(reviewHistorySection());}catch(error){console.error(error);}
  if(pieces.length)return pieces.join('');
  return '<section class="card review-table-error"><h2>Tabela temporariamente indisponível</h2><p>Os dados do aluno permanecem salvos, mas o componente de visualização não foi inicializado. Recarregue a página.</p></section>';
 }

 function viewHtml(){
  return head('Tabela de revisões','Visão global de disciplinas, conteúdos estudados, revisões realizadas e próximas datas programadas.')+
   '<div class="notice review-table-intro"><strong>Como usar:</strong> consulte o mês, clique numa revisão para ajustar ou registrar o resultado e use o histórico para acompanhar a evolução do conteúdo.</div>'+
   '<div class="review-table-page">'+reviewTablesHtml()+'</div>';
 }
 globalThis.reviewTableView=viewHtml;

 function refreshConsolidatedMonth(delta){
  if(typeof globalThis.qiReviewOverviewMonth!=='function')return false;
  const page=document.querySelector('.review-table-page');
  const current=page&&page.querySelector('.qi-review-overview');
  if(!page||!current)return false;
  try{
   const html=globalThis.qiReviewOverviewMonth(delta);
   if(!html)return false;
   current.outerHTML=html;
   bindPageActions();
   if(typeof globalThis.applyDisciplineColors==='function')globalThis.applyDisciplineColors();
   return true;
  }catch(error){console.error('Falha ao trocar o mês das revisões.',error);return false;}
 }

 function bindPageActions(){
  const prev=document.getElementById('qi-review-prev');
  const current=document.getElementById('qi-review-current');
  const next=document.getElementById('qi-review-next');
  if(prev)prev.onclick=()=>refreshConsolidatedMonth(-1);
  if(current)current.onclick=()=>refreshConsolidatedMonth('current');
  if(next)next.onclick=()=>refreshConsolidatedMonth(1);
 }

 if(typeof reviewsView==='function')reviewsView=function(){return stripTables(sourceReviewView());};

 if(typeof render==='function'){
  const baseRender=render;
  render=function(){
   installNavigation();
   if(typeof view!=='undefined'&&view==='review-table'&&!(typeof ME!=='undefined'&&ME.must_change)){
    const desired=view;
    view='home';
    baseRender.apply(this,arguments);
    view=desired;
    if(typeof renderNav==='function')renderNav();
    const main=document.querySelector('#main');
    if(main)main.innerHTML=viewHtml();
    queueMicrotask(()=>{
     bindPageActions();
     if(typeof globalThis.renderReviewHistoryRows==='function')globalThis.renderReviewHistoryRows();
     if(typeof globalThis.applyDisciplineColors==='function')globalThis.applyDisciplineColors();
    });
    return;
   }
   return baseRender.apply(this,arguments);
  };
 }

 document.addEventListener('DOMContentLoaded',()=>{
  installNavigation();
  if(typeof renderNav==='function')renderNav();
 },{once:true});
})();
'''


def patch_guidance():
    path=ROOT/'static'/'student_guidance.js'
    text=path.read_text(encoding='utf-8')
    bridge=""" globalThis.qiReviewOverviewHtml=qiReviewOverviewHtml;
 globalThis.qiReviewOverviewMonth=function(delta){
  if(delta==='current')qiReviewMonth=((typeof S!=='undefined'&&S.serverDate)||new Date().toISOString().slice(0,10)).slice(0,7)+'-01';
  else qiReviewMonth=qiMonthShift(qiReviewMonth,Number(delta||0));
  return qiReviewOverviewHtml();
 };
"""
    anchor=' function qiInstallReviewOverview(){'
    if 'globalThis.qiReviewOverviewMonth' not in text:
        if anchor not in text:raise RuntimeError('Consolidated review renderer anchor not found in student_guidance.js.')
        text=text.replace(anchor,bridge+anchor,1)
    path.write_text(text,encoding='utf-8')


def patch_static():
    static=ROOT/'static'
    patch_guidance()
    (static/'review_table_page.js').write_text(JS,encoding='utf-8')
    html_path=static/'app.html'
    html=html_path.read_text(encoding='utf-8')
    html=re.sub(r'/static/student_guidance\.js\?v=[^"\']+','/static/student_guidance.js?v=4.1.0',html)
    html=re.sub(r'/static/review_table_page\.js\?v=[^"\']+','/static/review_table_page.js?v=5.3.0',html)
    html_path.write_text(html,encoding='utf-8')


def main():
    patch_static()
    print('MEUCRONOGRAMA_REVIEW_TABLE_BRIDGE_READY: dedicated page now renders the consolidated calendar and history directly.',flush=True)


if __name__=='__main__':main()
