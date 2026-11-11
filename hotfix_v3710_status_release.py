"""Hotfix v3.7.10: visible result-import progress messages without changing backend import logic."""
from pathlib import Path
import re

ROOT=Path(__file__).resolve().parent
STATIC=ROOT/'static'
JS_MARK='// === RESULT IMPORT LIVE STATUS V3.7.10 ==='
CSS_MARK='/* === RESULT IMPORT LIVE STATUS V3.7.10 === */'

JS=r'''
// === RESULT IMPORT LIVE STATUS V3.7.10 ===
let resultImportLiveTimer=null;

function resultImportLiveStatusHtml(stage,total,message,kind=''){
 const pct={prepare:12,sending:34,processing:68,confirming:88,done:100,error:100}[stage]??0;
 const done=stage==='done',error=stage==='error';
 return '<div class="result-import-live-status '+(kind||'')+'" aria-live="polite">'+
  '<div class="result-import-live-head"><strong>'+esc(message)+'</strong><span>'+Number(total||0)+' resultado(s)</span></div>'+
  '<div class="result-import-live-bar '+(error?'error':'')+'"><span style="width:'+pct+'%"></span></div>'+
  '<p class="micro">'+(
   done?'Importação confirmada pelo servidor.':
   error?'A importação não foi concluída.':
   'Aguarde a confirmação do servidor antes de sair desta página.'
  )+'</p>'+
 '</div>';
}

function resultImportSetLiveStatus(stage,total,message,kind=''){
 const el=document.getElementById('result-import-token-state');
 if(el)el.innerHTML=resultImportLiveStatusHtml(stage,total,message,kind);
}

acts['result-import-confirm']=async()=>{
 if(!resultImportDraft?.token)throw new Error('Atualize a prévia após alterar opções ou vínculos.');
 const p=resultImportPayload();
 p.token=resultImportDraft.token;
 p.skipUnmapped=document.querySelector('[name=result-import-skip]')?.checked||false;
 const summary=resultImportDraft?.preview?.summary||{};
 const total=Number(summary.linked||summary.new+summary.updated+summary.unchanged||resultImportDraft?.inspection?.rows||0);
 if(!confirm('Converter as alternativas pelo gabarito e salvar '+total+' resultado(s) nas contas vinculadas?'))return;

 const button=document.querySelector('[data-act="result-import-confirm"]');
 if(button){button.disabled=true;button.textContent='Importando…';}
 clearTimeout(resultImportLiveTimer);
 resultImportSetLiveStatus('prepare',total,'Preparando '+total+' resultado(s) para cadastro…');

 try{
  await new Promise(resolve=>setTimeout(resolve,180));
  resultImportSetLiveStatus('sending',total,'Enviando '+total+' resultado(s) ao servidor…');
  resultImportLiveTimer=setTimeout(()=>{
   resultImportSetLiveStatus('processing',total,'Servidor processando '+total+' resultado(s)…');
   resultImportLiveTimer=setTimeout(()=>{
    resultImportSetLiveStatus('confirming',total,'Confirmando a gravação dos resultados…');
   },1800);
  },900);

  const d=await api('/api/model-data/confirm',p);
  clearTimeout(resultImportLiveTimer);

  const s=d.summary||{};
  const processed=Number(
   s.processed ?? s.linked ??
   ((Number(s.new||0)+Number(s.updated||0)+Number(s.unchanged||0)) || total)
  );
  resultImportSetLiveStatus(
   'done',processed,
   'Concluído: '+processed+' resultado(s) processado(s) — '+Number(s.new||0)+' novo(s), '+Number(s.updated||0)+' atualizado(s)'+(Number(s.unchanged||0)?', '+Number(s.unchanged||0)+' sem mudança':'')+'.',
   'success'
  );

  resultImportLastSummary=s;
  if(typeof resultExportSimulations!=='undefined')resultExportSimulations=null;

  await new Promise(resolve=>setTimeout(resolve,750));
  resultImportDraft=null;
  render();
  toast('Importação concluída: '+Number(s.new||0)+' resultado(s) novo(s) e '+Number(s.updated||0)+' atualizado(s).');
 }catch(error){
  clearTimeout(resultImportLiveTimer);
  resultImportSetLiveStatus('error',total,error?.message||'Falha ao processar os resultados.','error');
  if(button){button.disabled=false;button.textContent='Confirmar importação';}
  throw error;
 }
};
'''

CSS=r'''
/* === RESULT IMPORT LIVE STATUS V3.7.10 === */
.result-import-live-status{margin-top:.8rem;padding:.85rem .95rem;border:1px solid var(--line);border-radius:12px;background:#fffafb}
.result-import-live-head{display:flex;justify-content:space-between;gap:1rem;align-items:center}
.result-import-live-head span{font-size:.8rem;color:var(--muted);white-space:nowrap}
.result-import-live-bar{height:.48rem;margin:.65rem 0 .3rem;border-radius:999px;background:rgba(182,83,98,.12);overflow:hidden}
.result-import-live-bar span{display:block;height:100%;background:var(--primary,#b65362);border-radius:inherit;transition:width .35s ease}
.result-import-live-status.success{border-color:#b8dcc9;background:#f7fcf9}
.result-import-live-status.error{border-color:#e3aeb7;background:#fff7f8}
.result-import-live-bar.error span{background:#a52828}
@media(max-width:620px){.result-import-live-head{display:grid;gap:.2rem}.result-import-live-head span{white-space:normal}}
'''

def main():
    js=STATIC/'result_import.js'
    source=js.read_text(encoding='utf-8')
    if JS_MARK not in source:
        js.write_text(source.rstrip()+"\n\n"+JS.strip()+"\n",encoding='utf-8')

    css=STATIC/'style.css'
    source=css.read_text(encoding='utf-8')
    if CSS_MARK not in source:
        css.write_text(source.rstrip()+"\n\n"+CSS.strip()+"\n",encoding='utf-8')

    html=STATIC/'app.html'
    source=html.read_text(encoding='utf-8')
    source=re.sub(r'/static/result_import\.js\?v=[^"\']+','/static/result_import.js?v=2.9.5',source)
    html.write_text(source,encoding='utf-8')

    for verifier in ROOT.glob('verify_*.py'):
        source=verifier.read_text(encoding='utf-8')
        source=source.replace('/static/result_import.js?v=2.9.4','/static/result_import.js?v=2.9.5')
        verifier.write_text(source,encoding='utf-8')

    site=ROOT/'site_version_release.py'
    if site.exists():
        source=site.read_text(encoding='utf-8').replace('PUBLIC_VERSION="3.7.9"','PUBLIC_VERSION="3.7.10"')
        site.write_text(source,encoding='utf-8')

    vsite=ROOT/'verify_site_version.py'
    if vsite.exists():
        source=vsite.read_text(encoding='utf-8').replace('v3.7.9','v3.7.10')
        vsite.write_text(source,encoding='utf-8')

    print('MEUCRONOGRAMA_RESULT_IMPORT_STATUS_READY: visible real-total staged import messages installed without backend changes.',flush=True)

if __name__=='__main__':
    main()
