'use strict';
// === CORREÇÃO NA INTERFACE V3.17.0 ===
// Quando uma importação (respostas dos alunos, gabarito ou notas TRI) encontra divergências,
// o servidor devolve a lista completa. Esta janela mostra cada uma e deixa corrigir o valor
// ali mesmo (ou ignorar a linha). As correções valem para aquele arquivo e são reenviadas
// em todas as etapas seguintes (conferência e confirmação); o arquivo original não muda.
const importFixUrls=/^\/api\/(model-data\/(inspect|preview|confirm|tri-inspect|tri-preview)|exams\/(inspect|preview|confirm))$/;
const importFixStore=new Map();   // conteúdo do arquivo (base64) → correções aplicadas
let importFixState=null;
const importFixBaseApi=api;

api=async function(url,data){
 if(data===undefined||!importFixUrls.test(url)||!data||typeof data.file!=='string')return importFixBaseApi(url,data);
 const send=fixes=>importFixBaseApi(url,fixes.length?{...data,fixes}:data);
 const fixes=importFixStore.get(data.file)||[];
 let result;
 try{result=await send(fixes);}
 catch(error){
  const issues=error.data&&error.data.issues;
  if(!Array.isArray(issues)||!issues.length)throw error;
  return importFixOpen(data.file,error.data,send,null);
 }
 // Conferência das notas: nomes sem aluno no simulado não impedem a importação, mas podem ser corrigidos.
 if(Array.isArray(result?.issues)&&result.issues.length&&/tri-preview$/.test(url))return importFixOpen(data.file,result,send,result);
 return result;
};

function importFixKey(fix){return fix.skip?fix.sheet+'|'+fix.line+'|skip':'from' in fix?fix.sheet+'|*|'+fix.col+'|'+fix.from:fix.sheet+'|'+fix.line+'|'+fix.col;}
function importFixMerge(old,added){
 const out=new Map(old.map(f=>[importFixKey(f),f]));
 for(const f of added){
  if(f.skip)for(const k of [...out.keys()])if(k.startsWith(f.sheet+'|'+f.line+'|'))out.delete(k);
  out.set(importFixKey(f),f);
 }
 return [...out.values()];
}
function importFixWhere(issue){
 if(issue.kind==='general')return 'Arquivo';
 return esc(issue.sheet||'')+(issue.line?' · linha '+issue.line:' · todas as linhas');
}
function importFixMessage(issue){
 // "Onde" já mostra aba e linha: tira esse prefixo da mensagem.
 return String(issue.message||'').replace(/^.*?linha \d+(?: \([^)]*\))?(?: · [^:]*)?:\s*/i,'');
}
function importFixInput(issue,index){
 if(issue.kind==='general'||issue.col===null||issue.col===undefined)return '<small>Corrija no arquivo e envie de novo.</small>';
 const options=issue.options||[];
 const label='Correção de '+esc(issue.header||'valor')+' ('+importFixWhere(issue)+')';
 if(options.length&&options.length<=8){
  const preset=issue.suggest!==undefined?issue.suggest:null;  // só palpites explícitos do servidor
  return '<select name="fix-'+index+'" aria-label="'+label+'"><option value="__keep__">Escolha…</option>'+
   options.map(o=>'<option value="'+esc(o)+'"'+(preset!==null&&o===preset?' selected':'')+'>'+(o===''?'(vazio)':esc(o))+'</option>').join('')+'</select>';
 }
 const list=options.length?' list="fix-list-'+index+'"':'';
 return '<input name="fix-'+index+'" value="'+esc(issue.suggest!==undefined?issue.suggest:issue.value)+'" aria-label="'+label+'" autocomplete="off"'+list+'>'+
  (options.length?'<datalist id="fix-list-'+index+'">'+options.slice(0,300).map(o=>'<option value="'+esc(o)+'">').join('')+'</datalist>':'');
}
function importFixBody(){
 const st=importFixState,issues=st.issues;
 const optional=Boolean(st.fallback);
 const intro=optional
  ?'<p>A conferência encontrou <strong>'+st.total+'</strong> divergência(s) que não impedem a importação, mas deixam alunos de fora. Corrija aqui ou siga sem corrigir.</p>'
  :'<p>O arquivo tem <strong>'+st.total+'</strong> divergência(s). Corrija os valores abaixo ou marque "Ignorar linha". As correções valem só para esta importação; o arquivo no seu computador não muda.</p>';
 const applied=st.fixes.length?'<p class="micro">'+st.fixes.length+' correção(ões) já aplicada(s) a este arquivo.</p>':'';
 const more=st.total>issues.length?'<p class="micro">Mostrando as primeiras '+issues.length+'. Depois de corrigir, as demais aparecem.</p>':'';
 const rows=issues.map((issue,i)=>'<tr><td>'+importFixWhere(issue)+'</td><td>'+esc(issue.header||'—')+'</td><td>'+(issue.value===''?'<small>(vazio)</small>':esc(issue.value))+'</td><td class="import-fix-message">'+esc(importFixMessage(issue))+'</td><td>'+importFixInput(issue,i)+'</td><td>'+
  (issue.line?'<label class="check"><input type="checkbox" name="skip-'+i+'"> Ignorar</label>':'')+'</td></tr>').join('');
 return intro+applied+more+
  '<div class="table-wrap exam-detail-table"><table class="import-fix-table"><thead><tr><th>Onde</th><th>Campo</th><th>No arquivo</th><th>Problema</th><th>Correção</th><th>Linha</th></tr></thead><tbody>'+rows+'</tbody></table></div>'+
  '<p id="modal-error" class="form-error" role="alert"></p><div class="actions"><button class="primary" type="submit">Aplicar correções e conferir de novo</button>'+
  (optional?'<button type="button" class="secondary" data-act="import-fix-skip">Seguir sem corrigir</button>':'')+'</div>';
}
function importFixRender(){
 $('#dialog-body').innerHTML='<form id="modal-form" data-import-fix="1">'+importFixBody()+'</form>';
 $('#dialog').classList.add('dialog-wide');
}
function importFixOpen(file,payload,send,fallback){
 return new Promise((resolve,reject)=>{
  importFixState={file,send,fallback,resolve,reject,done:false,issues:payload.issues,total:payload.total||payload.issues.length,fixes:importFixStore.get(file)||[]};
  modal(fallback?'Divergências na conferência':'Corrigir divergências do arquivo','',async form=>{
   const st=importFixState;
   const added=[];
   st.issues.forEach((issue,i)=>{
    const skip=form.elements['skip-'+i]?.checked;
    if(skip&&issue.line){added.push({sheet:issue.sheet,line:issue.line,skip:true});return;}
    const field=form.elements['fix-'+i];
    if(!field||field.value==='__keep__')return;
    const value=field.value;
    if(issue.kind==='replace'){if(value!==issue.value)added.push({sheet:issue.sheet,col:issue.col,from:issue.value,to:value});return;}
    if(value!==issue.value||issue.options)added.push({sheet:issue.sheet,line:issue.line,col:issue.col,value});
   });
   if(!added.length)throw new Error('Nenhuma correção foi preenchida. Corrija ao menos uma divergência, ignore a linha ou feche a janela.');
   const merged=importFixMerge(st.fixes,added);
   let result;
   try{result=await st.send(merged);}
   catch(error){
    const issues=error.data&&error.data.issues;
    if(!Array.isArray(issues)||!issues.length)throw error;
    importFixStore.set(st.file,merged);
    Object.assign(st,{fixes:merged,issues,total:error.data.total||issues.length});
    importFixRender();
    throw new Error('Correções aplicadas. Ainda faltam '+st.total+' divergência(s): confira a lista atualizada.');
   }
   importFixStore.set(st.file,merged);
   if(st.fallback&&Array.isArray(result?.issues)&&result.issues.length){
    Object.assign(st,{fixes:merged,issues:result.issues,total:result.issues.length,fallback:result});
    importFixRender();
    throw new Error('Correções aplicadas. Ainda há '+result.issues.length+' divergência(s) na conferência.');
   }
   st.done=true;st.resolve(result);
   toast(merged.length+' correção(ões) aplicada(s) a este arquivo. Conferência atualizada.');
  });
  importFixRender();
 });
}
acts['import-fix-skip']=()=>{
 const st=importFixState;
 if(!st||!st.fallback)return;
 st.done=true;st.resolve(st.fallback);closeModal(true);
};
$('#dialog').addEventListener('close',()=>{
 const st=importFixState;
 if(!st)return;
 importFixState=null;
 $('#dialog').classList.remove('dialog-wide');
 if(!st.done)st.reject(new Error('Importação interrompida: há divergências no arquivo. Corrija-as na janela de correção ou ajuste o arquivo e envie de novo.'));
});
