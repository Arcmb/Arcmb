"""Restore the dedicated review tables and add learner-editable pastel discipline colors.

The two review modules existed in the build but were not in the webapp static
allowlist, so browsers received HTTP 404 and the dedicated page showed its
fallback messages. This final patch serves those modules and adds a color field
to each discipline. Colors are stored per learner profile and applied to weekly
blocks, discipline lists and review tables.
"""
from pathlib import Path
import re

ROOT=Path(__file__).resolve().parent
PY_MARK='# === DISCIPLINE COLORS AND REVIEW RUNTIME V1 ==='
JS_MARK='// === DISCIPLINE COLORS AND REVIEW RUNTIME V1 ==='
CSS_MARK='/* === DISCIPLINE COLORS AND REVIEW RUNTIME V1 === */'

JS=r'''"use strict";
// === DISCIPLINE COLORS AND REVIEW RUNTIME V1 ===
(function(){
 const disciplinePastelPalette=['#f6c8cf','#f8d7bd','#f5e7a9','#cfe7c8','#bfe3dc','#c9dcf4','#d9cff2','#e9cae5','#d4e2e7','#f0d2c5','#c8e7ef','#e5dabd','#d8d1ee','#cce4d5','#f1cddd','#d5e0f3'];
 const validHex=value=>/^#[0-9a-f]{6}$/i.test(String(value||''));
 function hashText(value){let h=0;for(const ch of String(value||'')){h=((h<<5)-h)+ch.charCodeAt(0);h|=0;}return Math.abs(h);}
 function subjectById(id){return (P?.subjects||[]).find(x=>String(x.id)===String(id))||null;}
 function subjectByName(name){const target=String(name||'').trim().toLocaleLowerCase('pt-BR');return (P?.subjects||[]).find(x=>String(x.name||'').trim().toLocaleLowerCase('pt-BR')===target)||null;}
 function fallbackColor(subject){return disciplinePastelPalette[hashText(subject?.id||subject?.name||'disciplina')%disciplinePastelPalette.length];}
 function disciplineColor(subjectOrId){const subject=typeof subjectOrId==='object'?subjectOrId:subjectById(subjectOrId);return validHex(subject?.color)?String(subject.color).toLowerCase():fallbackColor(subject||{id:subjectOrId});}
 function shade(hex,amount=-34){const raw=validHex(hex)?hex.slice(1):'d8d8d8';const n=parseInt(raw,16),r=Math.max(0,Math.min(255,(n>>16)+amount)),g=Math.max(0,Math.min(255,((n>>8)&255)+amount)),b=Math.max(0,Math.min(255,(n&255)+amount));return '#'+[r,g,b].map(x=>x.toString(16).padStart(2,'0')).join('');}
 function setDisciplineStyle(node,subject){if(!node||!subject)return;const color=disciplineColor(subject),edge=shade(color,-38);node.classList.add('discipline-colored');node.style.setProperty('--discipline-color',color);node.style.setProperty('--discipline-edge',edge);node.dataset.subjectId=subject.id||'';}
 function colorControlHtml(value,automatic){return `<div class="discipline-color-field"><label>Cor da disciplina<input type="color" name="color" value="${esc(value)}" aria-label="Cor da disciplina"></label><div class="discipline-color-palette" aria-label="Paleta de cores pastel">${disciplinePastelPalette.map(color=>`<button type="button" class="discipline-color-swatch ${color.toLowerCase()===value.toLowerCase()?'selected':''}" data-discipline-color="${color}" style="--swatch:${color}" title="Usar ${color}"><span class="sr-only">${color}</span></button>`).join('')}</div><button type="button" class="secondary discipline-auto-color" data-discipline-auto-color="${automatic}">Usar cor sugerida</button><small>A cor identifica esta disciplina no quadro semanal, nas revisões e nas tabelas. Ela pode ser alterada a qualquer momento pelo aluno.</small></div>`;}

 if(typeof subjectForm==='function'){
  const baseSubjectForm=subjectForm;
  subjectForm=function(id){
   baseSubjectForm(id);
   const form=document.querySelector('#modal-form');if(!form||form.querySelector('[name=color]'))return;
   const subject=(P.subjects||[]).find(x=>x.id===id)||null;
   const suggested=fallbackColor(subject||{name:form.elements.name?.value||'Nova disciplina'});
   const value=validHex(subject?.color)?subject.color:suggested;
   const grid=form.querySelector('.form-grid')||form;
   const holder=document.createElement('div');holder.className='discipline-color-holder';holder.innerHTML=colorControlHtml(value,suggested);grid.appendChild(holder);
  };
 }

 document.addEventListener('click',event=>{
  const swatch=event.target.closest?.('[data-discipline-color]');
  if(swatch){const form=swatch.closest('form');const input=form?.querySelector('[name=color]');if(input){input.value=swatch.dataset.disciplineColor;form.querySelectorAll('.discipline-color-swatch').forEach(x=>x.classList.toggle('selected',x===swatch));input.dispatchEvent(new Event('input',{bubbles:true}));}return;}
  const automatic=event.target.closest?.('[data-discipline-auto-color]');
  if(automatic){const form=automatic.closest('form');const input=form?.querySelector('[name=color]');if(input){input.value=automatic.dataset.disciplineAutoColor;form.querySelectorAll('.discipline-color-swatch').forEach(x=>x.classList.toggle('selected',x.dataset.disciplineColor.toLowerCase()===input.value.toLowerCase()));input.dispatchEvent(new Event('input',{bubbles:true}));}}
 });

 function findSubjectInText(text){const normalized=String(text||'').toLocaleLowerCase('pt-BR');return (P?.subjects||[]).slice().sort((a,b)=>String(b.name||'').length-String(a.name||'').length).find(subject=>normalized.includes(String(subject.name||'').toLocaleLowerCase('pt-BR')))||null;}
 function calendarBlockFor(node){return node.closest?.('.calendar-session,.calendar-event,.week-event,.session-block,.session,.event,.slot-card,.calendar-block,button')||node;}
 function applySessionColors(root=document){
  const sessions=new Map((P?.sessions||[]).map(session=>[String(session.id),session]));
  root.querySelectorAll?.('#main [data-id]').forEach(node=>{const session=sessions.get(String(node.dataset.id||''));if(!session)return;const subject=subjectById(session.subjectId);setDisciplineStyle(calendarBlockFor(node),subject);});
  const candidates=root.querySelectorAll?.('#main .week-grid button,#main .calendar-grid button,#main .weekly-calendar button,#main .calendar-table button,#main [class*="session"],#main [class*="event"]')||[];
  candidates.forEach(node=>{if(node.classList.contains('discipline-colored'))return;const text=node.textContent||'';if(!/\d{1,2}:\d{2}/.test(text))return;const subject=findSubjectInText(text);if(subject)setDisciplineStyle(node,subject);});
 }
 function applySubjectListColors(root=document){
  root.querySelectorAll?.('.subject-priority-row').forEach(row=>{const subject=findSubjectInText(row.querySelector('.item-main strong')?.textContent||row.textContent);if(!subject)return;setDisciplineStyle(row,subject);const main=row.querySelector('.item-main strong');if(main&&!main.querySelector('.discipline-dot'))main.insertAdjacentHTML('afterbegin',`<span class="discipline-dot" style="--discipline-color:${disciplineColor(subject)}" aria-hidden="true"></span>`);});
 }
 function applyReviewTableColors(root=document){
  root.querySelectorAll?.('.review-calendar-table tbody tr').forEach(row=>{const name=row.querySelector('.review-cal-discipline strong')?.textContent;const subject=subjectByName(name)||findSubjectInText(name);if(!subject)return;setDisciplineStyle(row,subject);row.querySelectorAll('.review-cal-discipline,.review-cal-subject').forEach(cell=>setDisciplineStyle(cell,subject));});
  root.querySelectorAll?.('#review-history-body tr').forEach(row=>{const name=row.querySelector('td:first-child strong')?.textContent;const subject=subjectByName(name)||findSubjectInText(name);if(subject)setDisciplineStyle(row,subject);});
  root.querySelectorAll?.('.review-discipline').forEach(group=>{const subject=findSubjectInText(group.querySelector('summary')?.textContent||'');if(subject)setDisciplineStyle(group,subject);});
 }
 function disciplineLegend(){const subjects=(P?.subjects||[]).filter(x=>x.active!==false&&x.kind==='study');if(!subjects.length)return '';return `<section class="discipline-color-legend"><div><strong>Cores das disciplinas</strong><small>Cada cor identifica os blocos da disciplina. O aluno pode alterar em Disciplinas e metas → Editar.</small></div><div class="discipline-color-chips">${subjects.slice().sort((a,b)=>String(a.name).localeCompare(String(b.name),'pt-BR')).map(subject=>`<span class="discipline-color-chip" style="--discipline-color:${disciplineColor(subject)};--discipline-edge:${shade(disciplineColor(subject),-38)}"><i></i>${esc(subject.name)}</span>`).join('')}</div>${button('Configurar cores','discipline-colors-open','secondary')}</section>`;}
 function injectLegend(){if(typeof view==='undefined'||view!=='calendar')return;const main=document.querySelector('#main');if(!main||main.querySelector('.discipline-color-legend'))return;const head=main.querySelector('.page-head');if(head)head.insertAdjacentHTML('afterend',disciplineLegend());else main.insertAdjacentHTML('afterbegin',disciplineLegend());}
 function applyDisciplineColors(){const main=document.querySelector('#main');if(!main)return;applySessionColors(document);applySubjectListColors(document);applyReviewTableColors(document);injectLegend();}
 globalThis.applyDisciplineColors=applyDisciplineColors;
 globalThis.disciplineColor=disciplineColor;
 acts['discipline-colors-open']=()=>{view='subjects';render();window.scrollTo(0,0);};

 if(typeof render==='function'){
  const baseRender=render;
  render=function(){const result=baseRender.apply(this,arguments);queueMicrotask(applyDisciplineColors);return result;};
 }
 const observer=new MutationObserver(()=>{if(!document.documentElement.dataset.disciplineColorApplying){document.documentElement.dataset.disciplineColorApplying='1';queueMicrotask(()=>{try{applyDisciplineColors();}finally{delete document.documentElement.dataset.disciplineColorApplying;}});}});
 document.addEventListener('DOMContentLoaded',()=>{applyDisciplineColors();observer.observe(document.querySelector('#main')||document.body,{childList:true,subtree:true});},{once:true});
})();
'''

CSS=r'''
/* === DISCIPLINE COLORS AND REVIEW RUNTIME V1 === */
.discipline-color-holder{grid-column:1/-1}.discipline-color-field{display:grid;grid-template-columns:minmax(170px,220px) 1fr auto;gap:10px 14px;align-items:end;padding:14px;border:1px solid var(--line);border-radius:14px;background:#fffafb}.discipline-color-field>label{display:grid;gap:6px;font-weight:700}.discipline-color-field input[type=color]{width:100%;height:44px;padding:3px;border-radius:10px;background:#fff}.discipline-color-field small{grid-column:1/-1;color:var(--muted)}.discipline-color-palette{display:flex;gap:7px;flex-wrap:wrap;align-items:center}.discipline-color-swatch{width:31px;height:31px;min-width:31px;padding:0;border-radius:50%;background:var(--swatch);border:2px solid #fff;box-shadow:0 0 0 1px rgba(83,45,54,.2);cursor:pointer}.discipline-color-swatch.selected{box-shadow:0 0 0 3px #8f3545;transform:scale(1.05)}.discipline-auto-color{white-space:nowrap}.discipline-dot{display:inline-block;width:12px;height:12px;border-radius:50%;background:var(--discipline-color);border:1px solid rgba(55,35,40,.2);margin-right:7px;vertical-align:-1px}.subject-priority-row.discipline-colored{border-left:6px solid var(--discipline-edge)!important;background:linear-gradient(90deg,var(--discipline-color),#fff 23%)!important}.discipline-colored.calendar-session,.discipline-colored.calendar-event,.discipline-colored.week-event,.discipline-colored.session-block,.discipline-colored.session,.discipline-colored.event,.discipline-colored.slot-card,.discipline-colored.calendar-block,button.discipline-colored{background:var(--discipline-color)!important;border-color:var(--discipline-edge)!important;color:#2f2025!important;box-shadow:inset 4px 0 0 var(--discipline-edge)!important}.discipline-colored button{color:inherit}.discipline-color-legend{display:grid;gap:10px;margin:12px 0 16px;padding:14px 16px;border:1px solid var(--line);border-radius:14px;background:#fff}.discipline-color-legend>div:first-child{display:grid;gap:3px}.discipline-color-legend small{color:var(--muted)}.discipline-color-chips{display:flex;gap:8px;flex-wrap:wrap}.discipline-color-chip{display:inline-flex;align-items:center;gap:6px;padding:6px 9px;border-radius:999px;background:var(--discipline-color);border:1px solid var(--discipline-edge);font-size:12px;font-weight:700;color:#342329}.discipline-color-chip i{width:9px;height:9px;border-radius:50%;background:var(--discipline-edge)}.review-calendar-table tr.discipline-colored td.review-cal-discipline,.review-calendar-table tr.discipline-colored td.review-cal-subject{background:var(--discipline-color)!important;border-left-color:var(--discipline-edge)!important}.review-history-table tr.discipline-colored td:first-child{background:var(--discipline-color);box-shadow:inset 5px 0 0 var(--discipline-edge)}.review-discipline.discipline-colored>summary{background:linear-gradient(90deg,var(--discipline-color),#fff 45%);border-left:5px solid var(--discipline-edge)}
@media(max-width:760px){.discipline-color-field{grid-template-columns:1fr}.discipline-color-field small{grid-column:auto}.discipline-auto-color{justify-self:start}.discipline-color-legend{padding:12px}.discipline-color-chip{font-size:11px}}
'''


def patch_planner():
    path=ROOT/'planner.py'
    text=path.read_text(encoding='utf-8')
    if PY_MARK in text:return
    anchor="        if 'priorityManual' not in x:x['priorityManual']=False"
    replacement="""        x.setdefault('color','')
        _subject_color=str(x.get('color') or '').strip().lower()
        if _subject_color and (len(_subject_color)!=7 or _subject_color[0]!='#' or any(ch not in '0123456789abcdef' for ch in _subject_color[1:])):raise ValueError('Cor da disciplina inválida.')
        x['color']=_subject_color
        if 'priorityManual' not in x:x['priorityManual']=False"""
    if anchor not in text:raise RuntimeError('Subject validation anchor not found in planner.py.')
    text=text.replace(anchor,replacement,1)
    path.write_text(text.rstrip()+'\n\n'+PY_MARK+'\n',encoding='utf-8')
    compile(text,'planner.py','exec')


def install_assets():
    static=ROOT/'static'
    (static/'discipline_colors.js').write_text(JS,encoding='utf-8')
    css_path=static/'style.css';css=css_path.read_text(encoding='utf-8')
    if CSS_MARK not in css:css=css.rstrip()+'\n\n'+CSS+'\n'
    css_path.write_text(css,encoding='utf-8')

    html_path=static/'app.html';html=html_path.read_text(encoding='utf-8')
    html=re.sub(r'/static/review_history\.js\?v=[^"\']+','/static/review_history.js?v=5.1.0',html)
    html=re.sub(r'/static/review_calendar_table\.js\?v=[^"\']+','/static/review_calendar_table.js?v=5.1.0',html)
    html=re.sub(r'/static/review_table_page\.js\?v=[^"\']+','/static/review_table_page.js?v=5.1.0',html)
    html=re.sub(r'/static/style\.css\?v=[^"\']+','/static/style.css?v=5.1.0',html)
    if '/static/discipline_colors.js' not in html:
        html=html.replace('</body>','<script src="/static/discipline_colors.js?v=5.1.0" defer></script>\n</body>',1)
    html_path.write_text(html,encoding='utf-8')

    webapp_path=ROOT/'webapp.py';webapp=webapp_path.read_text(encoding='utf-8')
    entries=['review_history.js','review_calendar_table.js','discipline_colors.js']
    anchor="'review_table_page.js':'application/javascript; charset=utf-8'"
    if anchor not in webapp:
        anchor="'study_schedule.js':'application/javascript; charset=utf-8'"
    if anchor not in webapp:raise RuntimeError('Static JavaScript allowlist anchor not found in webapp.py.')
    for name in entries:
        mime=f"'{name}':'application/javascript; charset=utf-8'"
        if mime not in webapp:
            webapp=webapp.replace(anchor,anchor+','+mime,1)
            anchor=mime
    webapp_path.write_text(webapp,encoding='utf-8')


def main():
    patch_planner();install_assets()
    print('MEUCRONOGRAMA_DISCIPLINE_COLORS_REVIEW_RUNTIME_READY: review assets served and learner-editable pastel discipline colors prepared.',flush=True)

if __name__=='__main__':main()
