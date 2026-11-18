"use strict";
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
