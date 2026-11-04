"""Write the final collective-result export interface after the backend release."""
from pathlib import Path

ROOT = Path(__file__).resolve().parent

JS_SOURCE = r"""'use strict';
// Exportação coletiva dos resultados já convertidos pelo gabarito.
let resultExportSimulations=null;
let resultExportLoading=false;
let resultExportSelected='';

async function loadResultExportSimulations(force=false){
 if(resultExportLoading)return;
 if(resultExportSimulations!==null&&!force)return;
 resultExportLoading=true;
 try{
  const data=await api('/api/model-data/simulations');
  resultExportSimulations=Array.isArray(data.simulations)?data.simulations:[];
  if(!resultExportSimulations.some(x=>x.id===resultExportSelected))resultExportSelected=resultExportSimulations[0]?.id||'';
 }finally{
  resultExportLoading=false;
  if(view==='result-export')render();
 }
}

function resultExportView(){
 if(!manages())return head('Exportar resultados','Acesso reservado ao Master e à coordenação.');
 if(resultExportSimulations===null&&!resultExportLoading)queueMicrotask(()=>loadResultExportSimulations());
 if(resultExportLoading||resultExportSimulations===null)return head('Exportar resultados','Resultados convertidos por simulado.')+'<section class="card">Carregando simulados importados…</section>';
 if(!resultExportSimulations.length)return head('Exportar resultados','Resultados convertidos por simulado.')+
  '<section class="card"><h2>Nenhum simulado importado</h2><p>Depois de confirmar uma importação em Desempenho, o simulado aparecerá aqui.</p><div class="actions">'+button('Atualizar lista','result-export-refresh','secondary')+'</div></section>';
 const selected=resultExportSimulations.find(x=>x.id===resultExportSelected)||resultExportSimulations[0];
 resultExportSelected=selected.id;
 const options=resultExportSimulations.map(x=>`<option value="${esc(x.id)}" ${x.id===selected.id?'selected':''}>${esc(x.activity)} · ${esc(x.date)} · ${x.participants} aluno(s)</option>`).join('');
 return head('Exportar resultados','Escolha um simulado importado e baixe os resultados convertidos dos alunos.')+
 `<section class="card"><h2>Selecionar simulado</h2><label>Simulado<select name="result-export-simulation">${options}</select></label><div class="stats"><div class="stat"><strong>${selected.participants}</strong><span>aluno(s)</span></div><div class="stat"><strong>${esc(selected.date)}</strong><span>data de aplicação</span></div><div class="stat"><strong>${esc((selected.colors||[]).join(', ')||'—')}</strong><span>cores encontradas</span></div></div><div class="actions">${button('Exportar resultados convertidos','result-export-download','primary')}${button('Atualizar lista','result-export-refresh','secondary')}</div><p class="micro">O Excel terá Resumo dos alunos, Por área, Por disciplina, Por tópico, Por assunto e Por habilidade. Habilidades iguais permanecem separadas por área.</p></section>`+
 `<section class="card"><h2>Regra utilizada</h2><p>Resposta igual ao gabarito = 1 acerto. Resposta diferente ou vazia = 0. Questão anulada ou sem gabarito fica fora do cálculo.</p><p>Nas questões 01–05 de Linguagens, o sistema utiliza a versão de Inglês ou Espanhol indicada para cada aluno.</p></section>`;
}

acts['result-export-refresh']=async()=>{resultExportSimulations=null;await loadResultExportSimulations(true);};
acts['result-export-download']=async()=>{
 const selected=resultExportSimulations?.find(x=>x.id===resultExportSelected);
 if(!selected)throw new Error('Selecione um simulado.');
 const safe=String(selected.activity||'simulado').normalize('NFD').replace(/[\u0300-\u036f]/g,'').replace(/[^A-Za-z0-9_-]+/g,'_').replace(/^_+|_+$/g,'')||'simulado';
 await downloadPost('/api/model-data/export-results',{activityKey:selected.activityKey,date:selected.date},`Resultados_convertidos_${safe}_${selected.date}.xlsx`);
 toast('Resultados convertidos exportados.');
};

document.addEventListener('change',event=>{
 if(event.target?.name!=='result-export-simulation')return;
 resultExportSelected=event.target.value;
 render();
});
"""


def prepare():
    path = ROOT / 'static' / 'result_export.js'
    path.write_text(JS_SOURCE, encoding='utf-8')
    print('MEUCRONOGRAMA_RESULT_EXPORT_ASSET_READY: collective export interface written.', flush=True)


if __name__ == '__main__':
    prepare()
