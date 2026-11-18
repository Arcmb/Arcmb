"use strict";
// === CADASTRO DE DISCIPLINAS V3.12.0 ===
const dcState={data:null,draft:null,dirty:false,loading:false,error:''};
const DC_AREAS=['LC','CH','CN','MT'];
function dcKey(v){return String(v||'').normalize('NFKD').replace(/[̀-ͯ]/g,'').toLowerCase().replace(/[^a-z0-9]+/g,' ').trim();}
function dcManagerOwn(){return typeof ME!=='undefined'&&ME&&!ME._studentView&&['master','coordenador'].includes(ME.role);}
async function dcLoad(){
 if(dcState.loading)return;dcState.loading=true;dcState.error='';
 try{dcState.data=await api('/api/disciplines/catalog');dcState.draft=JSON.parse(JSON.stringify(dcState.data.catalog.disciplines));dcState.dirty=false;}
 catch(e){dcState.error=e.message||'Não foi possível carregar o cadastro.';}
 finally{dcState.loading=false;dcPaint();}
}
function dcIndex(){const idx={};(dcState.draft||[]).forEach(d=>{idx[dcKey(d.name)]=d.name;(d.aliases||[]).forEach(a=>{idx[dcKey(a)]=d.name;});});return idx;}
function dcCard(){
 if(dcState.error)return `<div class="notice warning">${esc(dcState.error)}</div>`;
 if(!dcState.data)return '<p>Carregando disciplinas…</p>';
 const idx=dcIndex(),draft=dcState.draft,found=dcState.data.found,pend=dcState.data.pending;
 const names=draft.map(d=>d.name);
 const rows=draft.map((d,i)=>`<tr><td><input data-dc="name" data-i="${i}" value="${esc(d.name)}" aria-label="Nome oficial"></td><td><select data-dc="area" data-i="${i}" aria-label="Área">${DC_AREAS.map(a=>`<option ${a===d.area?'selected':''}>${a}</option>`).join('')}</select></td><td><input data-dc="aliases" data-i="${i}" value="${esc((d.aliases||[]).join('; '))}" placeholder="Ex.: L. Corporal; Ed. Física" aria-label="Variações aceitas"></td><td><button type="button" class="secondary" data-act="dc-remove" data-i="${i}">Remover</button></td></tr>`).join('');
 const foundRows=found.map(f=>{const off=idx[dcKey(f.name)];
  const status=!off?`<select data-dc="assign" data-name="${esc(f.name)}" data-area="${esc(f.area)}" aria-label="Associar ${esc(f.name)}"><option value="">Sem cadastro: escolher…</option><option value="__new__">Criar como disciplina oficial</option>${names.map(n=>`<option value="${esc(n)}">Variação de ${esc(n)}</option>`).join('')}</select>`
   :off===f.name?'<span class="tag dc-ok">Nome oficial</span>':`<span class="tag dc-change">Vira ${esc(off)}</span>`;
  return `<tr><td><strong>${esc(f.name)}</strong></td><td>${esc(f.area)}</td><td>${f.questions}</td><td>${status}</td></tr>`;}).join('');
 const unmatched=found.filter(f=>!idx[dcKey(f.name)]).length;
 return `<h2>Disciplinas oficiais</h2>
 <p>Toda importação de mapa de simulado grava o nome oficial da disciplina. Diferenças só de maiúsculas, acentos, pontos ou espaços já são reconhecidas sozinhas (ESPANHOL vira Espanhol). Cadastre em "Variações aceitas" os outros nomes que aparecem nas planilhas, separados por ponto e vírgula.</p>
 <div class="table-wrap"><table class="dc-table"><thead><tr><th>Nome oficial</th><th>Área</th><th>Variações aceitas</th><th></th></tr></thead><tbody>${rows}</tbody></table></div>
 <div class="actions"><button type="button" class="secondary" data-act="dc-add">Adicionar disciplina</button><button type="button" class="primary" data-act="dc-save" ${dcState.dirty?'':'disabled'}>Salvar cadastro</button>${dcState.dirty?'<span class="micro">Há alterações não salvas.</span>':''}</div>
 <h3>Nomes encontrados nos mapas já importados</h3>
 ${unmatched?`<p class="notice warning">${unmatched} nome${unmatched>1?'s':''} sem cadastro. Escolha abaixo se é uma disciplina nova ou uma variação de outra, e salve.</p>`:''}
 <div class="table-wrap"><table class="dc-table"><thead><tr><th>Como está na planilha</th><th>Área</th><th>Questões</th><th>Situação</th></tr></thead><tbody>${foundRows||'<tr><td colspan="4">Nenhum mapa importado.</td></tr>'}</tbody></table></div>
 <div class="actions">${pend.questions?`<p>Pelo cadastro salvo, <strong>${pend.questions} questões</strong> em <strong>${pend.exams} mapa${pend.exams>1?'s':''}</strong> ainda estão com o nome antigo.</p><button type="button" class="primary" data-act="dc-apply" ${dcState.dirty?'disabled title="Salve o cadastro antes"':''}>Aplicar às provas já importadas</button>`:'<p class="micro">Todos os mapas já importados usam os nomes oficiais.</p>'}</div>`;
}
function dcPaint(){const box=document.getElementById('dc-card');if(box)box.innerHTML=dcCard();}
function dcMount(){
 if(view!=='exams'||!dcManagerOwn())return;
 const main=document.getElementById('main');if(!main||document.getElementById('dc-card'))return;
 const sec=document.createElement('section');sec.className='card';sec.id='dc-card';main.appendChild(sec);
 dcPaint();if(!dcState.data)dcLoad();
}
document.addEventListener('change',e=>{
 const el=e.target;if(!el.dataset||!el.dataset.dc||!dcState.draft)return;
 const k=el.dataset.dc,i=+el.dataset.i;
 if(k==='name')dcState.draft[i].name=el.value.trim();
 else if(k==='area')dcState.draft[i].area=el.value;
 else if(k==='aliases')dcState.draft[i].aliases=el.value.split(';').map(x=>x.trim()).filter(Boolean);
 else if(k==='assign'){
  const v=el.value,name=el.dataset.name;if(!v)return;
  if(v==='__new__')dcState.draft.push({name,area:DC_AREAS.includes(el.dataset.area)?el.dataset.area:'LC',aliases:[]});
  else{const d=dcState.draft.find(x=>x.name===v);if(d)d.aliases=[...(d.aliases||[]),name];}
 }
 dcState.dirty=true;dcPaint();
});
acts['dc-add']=()=>{dcState.draft.push({name:'',area:'LC',aliases:[]});dcState.dirty=true;dcPaint();const ins=document.querySelectorAll('#dc-card [data-dc="name"]');if(ins.length)ins[ins.length-1].focus();};
acts['dc-remove']=el=>{const d=dcState.draft[+el.dataset.i];if(!confirm('Remover '+(d.name||'esta linha')+' do cadastro? As questões já importadas não mudam.'))return;dcState.draft.splice(+el.dataset.i,1);dcState.dirty=true;dcPaint();};
acts['dc-save']=async()=>{
 const disciplines=dcState.draft.filter(d=>d.name||d.aliases.length);
 dcState.data=await api('/api/disciplines/catalog',{catalog:{disciplines},version:dcState.data.version});
 dcState.draft=JSON.parse(JSON.stringify(dcState.data.catalog.disciplines));dcState.dirty=false;dcPaint();
 if(typeof toast==='function')toast('Cadastro de disciplinas salvo.');
};
acts['dc-apply']=async()=>{
 const p=dcState.data.pending;
 if(!confirm(`Trocar o nome da disciplina em ${p.questions} questões de ${p.exams} mapa(s) pelo nome oficial? Relatórios e revisões passam a juntar essas questões na mesma disciplina.`))return;
 const r=await api('/api/disciplines/apply',{});
 await dcLoad();
 if(typeof toast==='function')toast(`${r.questions} questões atualizadas em ${r.exams} mapa(s).`);
};
(function dcInstall(){
 if(typeof render!=='function'||typeof acts==='undefined')return;
 const baseRender=render;
 render=function(){const out=baseRender.apply(this,arguments);try{dcMount();}catch(_){}return out;};
})();
