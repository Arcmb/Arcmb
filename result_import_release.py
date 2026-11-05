"""Add a dedicated two-tab result importer page.

The legacy performance screen keeps support for old formats, while this page
uses DADOS DOS ALUNOS + DADOS DO SIMULADO without manual column mapping.
"""
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parent
STATIC = ROOT / 'static'
JS_MIME = "'result_import.js':'application/javascript; charset=utf-8'"
JS_URL = '/static/result_import.js?v=2.8.4'

JS_SOURCE = r''''use strict';
// Importação dedicada do arquivo de duas abas.
let resultImportDraft=null;
let resultImportLastSummary=null;

function resultImportFileBase64(file){
 return file.arrayBuffer().then(buffer=>{
  const bytes=new Uint8Array(buffer),step=0x8000;
  let binary='';
  for(let i=0;i<bytes.length;i+=step)binary+=String.fromCharCode(...bytes.subarray(i,i+step));
  return btoa(binary);
 });
}

function resultImportView(){
 if(!manages())return head('Importar resultados','Acesso reservado ao Master e à coordenação.');
 const completed=resultImportLastSummary?`<div class="notice"><strong>Importação concluída.</strong> ${resultImportLastSummary.new||0} resultado(s) novo(s) e ${resultImportLastSummary.updated||0} atualizado(s). O simulado já pode ser consultado em Exportar resultados.</div>`:'';
 return head('Importar resultados','Envie o Excel com DADOS DOS ALUNOS e DADOS DO SIMULADO. Não é necessário relacionar colunas manualmente.')+
 completed+
 `<div class="notice"><strong>Fluxo correto:</strong> selecionar o arquivo → conferir o simulado → vincular os alunos às contas → confirmar. As alternativas A–E serão comparadas automaticamente com o gabarito.</div>`+
 `<section class="card"><h2>Importar MODELO DADOS.xlsx</h2><p>O arquivo deve possuir exatamente as abas <strong>DADOS DOS ALUNOS</strong> e <strong>DADOS DO SIMULADO</strong>. Use a cópia salva somente com valores, sem fórmulas, macros, proteção ou vínculos externos.</p><label>Arquivo Excel preenchido (até 3 MB)<input id="result-import-file" type="file" accept=".xlsx"></label><p id="result-import-filename">${esc(resultImportDraft?.filename||'Nenhum arquivo selecionado.')}</p><div class="actions">${button('Ler e conferir arquivo','result-import-inspect','primary')}${button('Gerar novo modelo','result-import-model','secondary')}</div><div id="result-import-inspection">${resultImportDraft?.inspection?resultImportInspection(resultImportDraft.inspection):''}</div><div id="result-import-preview" class="workbook-preview">${resultImportDraft?.preview?resultImportPreview(resultImportDraft.preview):''}</div></section>`+
 `<details class="card"><summary>Outros formatos antigos</summary><p>Arquivos antigos com colunas personalizadas continuam disponíveis na página Desempenho. O arquivo atual de duas abas não deve ser enviado pelo mapeamento manual.</p></details>`;
}

function resultImportInspection(d){
 const warnings=(d.warnings||[]).map(x=>'<li>'+esc(x)+'</li>').join('');
 return `<hr><h3>Arquivo reconhecido</h3><p><strong>${d.rows}</strong> participantes · <strong>${d.mapRows}</strong> linhas no mapa · questões ${String(d.firstQuestion).padStart(2,'0')}–${String(d.lastQuestion).padStart(2,'0')}.</p><p><strong>Simulado:</strong> ${esc(d.title)} · <strong>Cores:</strong> ${(d.colors||[]).map(esc).join(', ')}</p><div class="form-grid">${input('Data de aplicação','result-import-date',resultImportDraft?.date||d.date||'','date','required')}${check('Substituir respostas/resultados existentes','result-import-replace',!!resultImportDraft?.replace)}${check('Substituir classificações existentes do mapa','result-import-replace-map',!!resultImportDraft?.replaceMap)}</div>${warnings?'<div class="notice warning"><strong>Conferências necessárias:</strong><ul>'+warnings+'</ul></div>':''}<p class="micro">O sistema recalcula acertos e percentuais pelas respostas e pelo gabarito. A coluna % ACERTOS da planilha, quando existir, é apenas informativa.</p>${button('Vincular alunos e gerar prévia','result-import-preview','primary')}`;
}

function resultImportPayload(){
 if(!resultImportDraft?.file)throw new Error('Selecione o Excel preenchido.');
 const bindings=Object.fromEntries($$('[data-result-import-student]').map(e=>[e.dataset.resultImportStudent,e.value]));
 return {file:resultImportDraft.file,filename:resultImportDraft.filename,date:document.querySelector('[name=result-import-date]')?.value||resultImportDraft.date||'',replace:document.querySelector('[name=result-import-replace]')?.checked??resultImportDraft.replace??false,replaceMap:document.querySelector('[name=result-import-replace-map]')?.checked??resultImportDraft.replaceMap??false,mapping:Object.keys(bindings).length?bindings:resultImportDraft.mapping||{}};
}

function resultImportPreview(d){
 const s=d.summary,warnings=(s.warnings||[]).map(x=>'<li>'+esc(x)+'</li>').join('');
 return `<hr><h3>Conferência antes de salvar</h3><p><strong>${esc(s.title)}</strong> · ${br(s.date)} · cores: ${(s.colors||[]).map(esc).join(', ')}</p><p>${s.linked} alunos vinculados; ${s.new} resultados novos; ${s.updated} atualizados; ${s.unchanged} sem mudança; ${s.conflicts} divergências preservadas, salvo substituição marcada.</p><p>Mapas: ${s.map.total} questões/versões · ${s.map.new} novas · ${s.map.updated} atualizadas · ${s.map.conflicts} divergências.</p>${warnings?'<div class="notice warning"><ul>'+warnings+'</ul></div>':''}<div class="table-wrap"><table><thead><tr><th>Aluno do arquivo</th><th>Turma</th><th>Cor</th><th>Conta no site</th></tr></thead><tbody>${d.students.map(x=>`<tr><td>${esc(x.name)}</td><td>${esc(x.group)}</td><td>${esc(x.color)}</td><td><select data-result-import-student="${esc(x.key)}"><option value="">Não importar este aluno</option>${d.accounts.map(a=>`<option value="${esc(a.id)}" ${d.mapping[x.key]===a.id?'selected':''}>${esc(a.name)} (${esc(a.username)})</option>`).join('')}</select></td></tr>`).join('')}</tbody></table></div>${s.unresolved?check('Ignorar alunos sem vínculo e importar somente os vinculados','result-import-skip',false):''}${(d.sample||[]).map(x=>'<details><summary>Prévia detalhada de '+esc(x.name)+'</summary>'+workbookAnalysis(x.analysis)+'</details>').join('')}<div class="actions">${button('Atualizar prévia','result-import-preview')}${button('Confirmar importação','result-import-confirm','primary')}</div><p id="result-import-token-state" role="status">Nenhum dado foi gravado até a confirmação.</p>`;
}

acts['result-import-model']=()=>{view='result-model';render();window.scrollTo(0,0);};
acts['model-to-results']=()=>{view='result-import';render();window.scrollTo(0,0);};
acts['result-import-inspect']=async()=>{
 if(!resultImportDraft?.file)throw new Error('Selecione o Excel preenchido.');
 const d=await api('/api/model-data/inspect',{file:resultImportDraft.file,filename:resultImportDraft.filename,date:resultImportDraft.date||''});
 resultImportDraft={...resultImportDraft,inspection:d,date:d.date||resultImportDraft.date||'',token:null,preview:null,mapping:{}};
 $('#result-import-inspection').innerHTML=resultImportInspection(d);$('#result-import-preview').innerHTML='';
};
acts['result-import-preview']=async()=>{
 const p=resultImportPayload(),d=await api('/api/model-data/preview',p);
 resultImportDraft={...p,inspection:resultImportDraft.inspection,preview:d,token:d.token,mapping:d.mapping};
 $('#result-import-preview').innerHTML=resultImportPreview(d);
};
acts['result-import-confirm']=async()=>{
 if(!resultImportDraft?.token)throw new Error('Atualize a prévia após alterar opções ou vínculos.');
 const p=resultImportPayload();p.token=resultImportDraft.token;p.skipUnmapped=document.querySelector('[name=result-import-skip]')?.checked||false;
 if(!confirm('Converter as alternativas pelo gabarito e salvar os resultados nas contas vinculadas?'))return;
 const d=await api('/api/model-data/confirm',p);
 resultImportLastSummary=d.summary||{};resultImportDraft=null;
 if(typeof resultExportSimulations!=='undefined')resultExportSimulations=null;
 render();toast('Importação concluída: '+(d.summary.new||0)+' resultados novos; '+(d.summary.updated||0)+' atualizados.');
};

document.addEventListener('change',async e=>{
 if(e.target.id!=='result-import-file')return;
 const file=e.target.files?.[0];e.target.value='';if(!file)return;
 try{
  if(!/\.xlsx$/i.test(file.name))throw new Error('Selecione um arquivo .xlsx.');
  if(file.size>3000000)throw new Error('O arquivo excede o limite de 3 MB.');
  const encoded=await resultImportFileBase64(file);
  resultImportDraft={file:encoded,filename:file.name,date:'',replace:false,replaceMap:false,inspection:null,preview:null,token:null,mapping:{}};
  resultImportLastSummary=null;
  const name=$('#result-import-filename');if(name)name.textContent=file.name;
  const inspection=$('#result-import-inspection');if(inspection)inspection.innerHTML='';
  const preview=$('#result-import-preview');if(preview)preview.innerHTML='';
  toast('Arquivo selecionado. Clique em Ler e conferir arquivo.');
 }catch(err){toast(err.message,true);}
});
'''


def _insert_js_mime(source: str) -> str:
    if JS_MIME in source:
        return source
    entries = list(re.finditer(r"'[^'\n]+\.js'\s*:\s*'application/javascript; charset=utf-8'", source))
    if not entries:
        raise RuntimeError('JavaScript static MIME allowlist was not found.')
    anchor = entries[-1]
    return source[:anchor.end()] + ',' + JS_MIME + source[anchor.end():]


def _patch_app_js(source: str) -> str:
    if "['result-import','Importar resultados']" not in source:
        anchor = "['result-model','Modelo de resultados'],"
        if anchor not in source:
            raise RuntimeError('Result-model navigation anchor not found.')
        source = source.replace(anchor, anchor + "['result-import','Importar resultados'],", 1)
    if "'result-import':resultImportView" not in source:
        anchor = "'result-model':resultModelView"
        if anchor not in source:
            raise RuntimeError('Result-model page anchor not found.')
        source = source.replace(anchor, anchor + ",'result-import':resultImportView", 1)
    source = re.sub(
        r"!\[([^\]]*)\]\.includes\(x\[0\]\)\|\|manages\(\)",
        lambda m: "![" + (m.group(1) + ",'result-import'" if "'result-import'" not in m.group(1) else m.group(1)) + "].includes(x[0])||manages()",
        source,
        count=1,
    )
    return source


def prepare():
    STATIC.mkdir(parents=True, exist_ok=True)
    (STATIC / 'result_import.js').write_text(JS_SOURCE, encoding='utf-8')

    app_js_path = STATIC / 'app.js'
    app_js_path.write_text(_patch_app_js(app_js_path.read_text(encoding='utf-8')), encoding='utf-8')

    html_path = STATIC / 'app.html'
    html = html_path.read_text(encoding='utf-8')
    if JS_URL not in html:
        html = html.replace('</body>', f'<script src="{JS_URL}" defer></script>\n</body>', 1)
    html_path.write_text(html, encoding='utf-8')

    webapp_path = ROOT / 'webapp.py'
    webapp_path.write_text(_insert_js_mime(webapp_path.read_text(encoding='utf-8')), encoding='utf-8')

    print('MEUCRONOGRAMA_RESULT_IMPORT_READY: dedicated two-tab importer page prepared.', flush=True)


if __name__ == '__main__':
    prepare()
