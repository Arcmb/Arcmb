"use strict";
// === BANCO DE ITENS DO ENEM (TRI) V3.13.0 ===
const enState={file:null,preview:null,mode:'add',ignore:false,level:'subject',area:'',discipline:'',year:'',data:null,loading:false,error:''};
const EN_DIFF=['Fácil','Média','Difícil','Muito difícil'];
const EN_LEVELS=[['discipline','Disciplina'],['topic','Tópico'],['subject','Conteúdo'],['skill','Habilidade']];
function enManager(){return typeof ME!=='undefined'&&ME&&!ME._studentView&&['master','coordenador'].includes(ME.role);}
function enQuery(){const p=new URLSearchParams({level:enState.level});if(enState.area)p.set('area',enState.area);if(enState.discipline)p.set('discipline',enState.discipline);if(enState.year)p.set('year',enState.year);return p.toString();}
async function enLoad(){
 if(enState.loading)return;enState.loading=true;enState.error='';
 try{enState.data=await api('/api/enem-items/summary?'+enQuery());}
 catch(e){enState.error=e.message||'Não foi possível carregar o banco de itens.';}
 finally{enState.loading=false;if(view==='enem-items')enPaint();}
}
function enNum(v){return String(v).replace('.',',');}
function enBar(dist,total){return `<div class="en-bar" title="${EN_DIFF.map(d=>d+': '+(dist[d]||0)).join(' · ')}">${EN_DIFF.map((d,i)=>dist[d]?`<span class="en-d${i}" data-w="${(100*dist[d]/Math.max(1,total)).toFixed(1)}"></span>`:'').join('')}</div>`;}
function enLevelTag(l){const i=EN_DIFF.indexOf(l);return `<span class="tag en-t${i}">${esc(l)}</span>`;}
let enCsvRows=null;
function enImportCard(){
 const p=enState.preview;
 return `<section class="card"><h2>Importar itens do ENEM</h2>
 <p>Uma linha por questão do ENEM, com disciplina, tópico, conteúdo, habilidade e os parâmetros a, b e c da TRI. O sistema calcula a dificuldade cobrada e a complexidade de resolução de cada item e mostra quais conteúdos mais caem.</p>
 <div class="actions"><button type="button" class="secondary" data-act="en-template">Baixar planilha modelo</button>
 <label class="en-file">Planilha preenchida (.xlsx ou .csv)<input type="file" id="en-file" accept=".xlsx,.csv"></label>
 <button type="button" class="primary" data-act="en-preview" ${enState.file?'':'disabled'}>Conferir</button></div>
 ${p?`<div class="en-preview"><h3>Conferência</h3>
  <p><strong>${p.valid}</strong> itens válidos${p.errorCount?` · <strong>${p.errorCount}</strong> linha(s) com erro`:''}${p.years.length?' · anos '+p.years.join(', '):''} · ${p.disciplines.length} disciplina(s).</p>
  <p>Dificuldade: ${EN_DIFF.map(d=>`${d} ${p.difficulty[d]||0}`).join(' · ')}. Complexidade: ${['Baixa','Média','Alta'].map(d=>`${d} ${p.complexity[d]||0}`).join(' · ')}.</p>
  ${p.errorCount?`<details><summary>Ver linhas com erro</summary><ul>${p.errors.map(e=>`<li>${esc(e)}</li>`).join('')}</ul>${p.errorCount>p.errors.length?'<p class="micro">Mostrando as 50 primeiras.</p>':''}</details>`:''}
  <div class="actions"><label>Como importar<select data-en="mode"><option value="add" ${enState.mode==='add'?'selected':''}>Adicionar ao banco (ignora itens repetidos)</option><option value="replace" ${enState.mode==='replace'?'selected':''}>Substituir todo o banco por esta planilha</option></select></label>
  ${p.errorCount?`<label class="check"><input type="checkbox" data-en="ignore" ${enState.ignore?'checked':''}> Importar só as linhas válidas</label>`:''}
  <button type="button" class="primary" data-act="en-confirm" ${p.valid&&(!p.errorCount||enState.ignore)?'':'disabled'}>Importar ${p.valid} itens</button></div></div>`:''}
 </section>`;
}
function enSummaryCard(){
 if(enState.error)return `<div class="notice warning">${esc(enState.error)}</div>`;
 const d=enState.data;if(!d)return '<section class="card"><p>Carregando banco de itens…</p></section>';
 if(!d.all)return '<section class="card"><h2>Conteúdos mais cobrados</h2><p>O banco ainda está vazio. Baixe a planilha modelo, preencha e importe acima.</p></section>';
 const lvl=EN_LEVELS.find(x=>x[0]===enState.level)[1],perDisc=enState.level!=='discipline';
 enCsvRows=[[...(perDisc?['Disciplina']:[]),lvl,'Itens','% '+(perDisc?'da disciplina':'do banco'),'Dificuldade média (escala ENEM)','Nível',...EN_DIFF,'Complexidade alta (%)','Anos',enState.level==='subject'||enState.level==='topic'?'Habilidades':'Conteúdos'],
  ...d.rows.map(r=>[...(perDisc?[r.discipline]:[]),r.label,r.items,r.share,r.meanB,r.level,...EN_DIFF.map(x=>r.difficulty[x]),r.highComplexity,r.years.join(' '),r.related.join(' | ')])];
 return `<section class="card"><h2>Conteúdos mais cobrados</h2>
 <div class="actions sr-filters"><label>Agrupar por<select data-en="level">${EN_LEVELS.map(([k,l])=>`<option value="${k}" ${k===enState.level?'selected':''}>${l}</option>`).join('')}</select></label>
 <label>Área<select data-en="area"><option value="">Todas</option>${['LC','CH','CN','MT'].map(a=>`<option ${a===enState.area?'selected':''}>${a}</option>`).join('')}</select></label>
 <label>Disciplina<select data-en="discipline"><option value="">Todas</option>${d.disciplines.map(x=>`<option ${x===enState.discipline?'selected':''}>${esc(x)}</option>`).join('')}</select></label>
 <label>Ano<select data-en="year"><option value="">Todos</option>${d.years.map(y=>`<option ${String(y)===enState.year?'selected':''}>${y}</option>`).join('')}</select></label>
 <button type="button" class="secondary" data-act="en-csv">Baixar CSV</button></div>
 <p class="micro">${d.total} de ${d.all} itens no filtro. Ordem: mais cobrados primeiro. Dificuldade pela média do parâmetro b na escala do ENEM: fácil abaixo de 600, média de 600 a 699, difícil de 700 a 799, muito difícil a partir de 800. Complexidade alta: item que discrimina bem (a ≥ 2,5) e quase não se acerta no chute (c ≤ 0,20).</p>
 <div class="table-wrap"><table class="sr-table"><thead><tr><th>${perDisc?'Disciplina · ':''}${lvl}</th><th>Itens</th><th>% ${perDisc?'da disciplina':'do banco'}</th><th>Dificuldade média</th><th>Distribuição</th><th>Complexidade alta</th><th>${enState.level==='subject'||enState.level==='topic'?'Habilidades':'Conteúdos'}</th></tr></thead>
 <tbody>${d.rows.slice(0,400).map(r=>`<tr><td>${perDisc?`<small>${esc(r.discipline)}</small><br>`:''}<strong>${esc(r.label)}</strong></td><td>${r.items}</td><td>${enNum(r.share)}%</td><td>${enLevelTag(r.level)} <small>${enNum(r.meanB)}</small></td><td>${enBar(r.difficulty,r.items)}</td><td>${enNum(r.highComplexity)}%</td><td><small>${r.related.map(esc).join(' · ')}</small></td></tr>`).join('')}</tbody></table></div>
 <p class="micro">${EN_DIFF.map((x,i)=>`<span class="sr-key en-d${i}"></span> ${x}`).join(' &nbsp; ')}</p></section>`;
}
function enView(){if(!enState.data&&!enState.loading&&!enState.error)enLoad();return head('ENEM (TRI)','Banco de itens do ENEM: dificuldade cobrada, complexidade de resolução e conteúdos que mais caem.')+'<div id="en-root">'+enImportCard()+enSummaryCard()+'</div>';}
function enPaint(){const root=document.getElementById('en-root');if(!root)return;root.innerHTML=enImportCard()+enSummaryCard();enWidths(root);}
function enWidths(root){root.querySelectorAll('[data-w]').forEach(e=>{e.style.width=e.dataset.w+'%';});}
document.addEventListener('change',async e=>{
 const el=e.target;if(view!=='enem-items')return;
 if(el.id==='en-file'){
  try{const f=el.files[0];if(!f)return;if(f.size>3000000)throw new Error('Limite de 3 MB.');
   const b64=await new Promise((resolve,reject)=>{const r=new FileReader();r.onload=()=>resolve(String(r.result).split(',')[1]);r.onerror=()=>reject(new Error('Não foi possível ler o arquivo.'));r.readAsDataURL(f);});
   enState.file={filename:f.name,file:b64};enState.preview=null;enState.ignore=false;enPaint();}
  catch(err){toast(err.message,true);}
  return;
 }
 if(!el.dataset||!el.dataset.en)return;
 const k=el.dataset.en;
 if(k==='ignore'){enState.ignore=el.checked;enPaint();return;}
 if(k==='mode'){enState.mode=el.value;return;}
 enState[k]=el.value;enLoad();
});
acts['en-template']=async()=>{await downloadPost('/api/enem-items/template',{},'Modelo_itens_ENEM_TRI.xlsx');};
acts['en-preview']=async()=>{if(!enState.file)throw new Error('Selecione a planilha.');enState.preview=await api('/api/enem-items/preview',enState.file);enPaint();};
acts['en-confirm']=async()=>{
 const p=enState.preview;if(!p)return;
 if(enState.mode==='replace'&&!confirm('Substituir todo o banco de itens do ENEM por esta planilha?'))return;
 const r=await api('/api/enem-items/confirm',{...enState.file,mode:enState.mode,ignoreErrors:enState.ignore});
 enState.file=null;enState.preview=null;enState.data=null;
 toast(`${r.added} itens importados${r.skipped?` · ${r.skipped} repetidos ignorados`:''}.`);
 enPaint();enLoad();
};
acts['en-csv']=()=>{if(!enCsvRows||enCsvRows.length<2)throw new Error('Não há linhas para exportar.');csv('Itens_ENEM_'+enState.level+'.csv',enCsvRows);};
function enNavFix(){
 const nav=document.getElementById('nav');if(!nav)return;
 let b=nav.querySelector('[data-view="enem-items"]');
 if(!enManager()){if(b)b.remove();return;}
 if(!b){const ref=nav.querySelector('[data-view="exams"]');b=document.createElement('button');b.dataset.view='enem-items';b.innerHTML='<span class="nav-number"></span>ENEM (TRI)';if(ref)ref.after(b);else nav.appendChild(b);}
 b.classList.toggle('active',view==='enem-items');
 nav.querySelectorAll('button .nav-number').forEach((n,i)=>{n.textContent=String(i+1).padStart(2,'0');});
}
(function enInstall(){
 if(typeof render!=='function'||typeof acts==='undefined')return;
 if(typeof renderNav==='function'){const baseNav=renderNav;renderNav=function(){const out=baseNav.apply(this,arguments);try{enNavFix();}catch(_){}return out;};}
 const baseRender=render;
 render=function(){
  if(view==='enem-items'&&!enManager())view='home';
  const out=baseRender.apply(this,arguments);
  try{if(view==='enem-items'){const main=document.getElementById('main');if(main){main.innerHTML=enView();enWidths(main);}}enNavFix();}catch(_){}
  return out;
 };
})();
