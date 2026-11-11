// Dados cadastrais do caderno, editáveis independentemente do arquivo de questões.
async function loadExamMapList(seq){
 try{
  const data=await api('/api/model-data/exam-edit-list');
  if(view!=='exams'||seq!==examSeq)return;
  examCatalogue=data.exams;
  const box=$('#exam-list');
  if(!box)return;
  box.innerHTML=items(examCatalogue.map(exam=>{
   const attrs='data-id="'+esc(exam.id)+'"';
   const edit=button(exam.canEdit?'Editar dados':'Editar data','exam-metadata-edit','secondary',attrs);
   const complement=exam.canEdit?button('Complementar mapa','exam-edit','secondary',attrs):'';
   return '<div class="item"><div><strong>'+esc(exam.title)+'</strong><p>'+
     br(exam.applied_on)+' · '+esc(exam.color)+' · '+esc(exam.area||'Sem área padrão')+
     ' · '+Number(exam.linkedResults)+' resultado(s) vinculado(s) · versão '+Number(exam.version)+
     '</p></div><div class="actions">'+edit+complement+'</div></div>';
  }));
 }catch(error){
  const box=$('#exam-list');
  if(box&&view==='exams'&&seq===examSeq)box.textContent=error.message;
 }
}

acts['exam-metadata-edit']=el=>{
 const exam=examCatalogue.find(row=>row.id===el.dataset.id);
 if(!exam)throw new Error('Atualize a lista para localizar este caderno.');
 const full=exam.canEdit;
 const fields=input('Nome do simulado','title',exam.title,'text','required maxlength="200"')+
  input('Data de aplicação','date',exam.applied_on,'date','required min="1900-01-01" max="2100-12-31"')+
  input('Cor da prova','color',exam.color,'text','required maxlength="80"')+
  select('Área padrão das questões','area',exam.area||'',[['','Sem área padrão'],...areaOptions.slice(1)]);
 const help='A alteração vale para este caderno e seus resultados vinculados. A área padrão será usada ao complementar o mapa com questões sem área informada.';
 modalForm(full?'Editar dados do simulado':'Editar data do caderno',
  '<p>'+esc(exam.title)+' · '+esc(exam.color)+' · '+br(exam.applied_on)+'</p><div class="form-grid">'+fields+'</div><p class="micro">'+help+'</p>',
  async(form,values)=>{
   const data={examId:exam.id,version:exam.version,title:exam.title,color:exam.color,area:exam.area||'',...values};
   let result;
   try{result=await api('/api/model-data/exam-metadata-update',data);}
   catch(error){await loadExamMapList(++examSeq);throw error;}
   if(examDraft?.examId===exam.id){
    Object.assign(examDraft,{title:result.title,date:result.newDate,color:result.color,area:result.area,token:null});
    const editor=$('#exam-editor');
    if(editor)editor.innerHTML=examEditor();
   }
   if(typeof resultExportSimulations!=='undefined')resultExportSimulations=null;
   if(typeof studentSummaryCache!=='undefined')studentSummaryCache.clear();
   if(typeof managementDashboardCache!=='undefined')managementDashboardCache=null;
   if(typeof managementClassAnalyticsCache!=='undefined'){
    managementClassAnalyticsCache=null;
    managementClassDetailCache.clear();
    managementStudentDetailCache.clear();
   }
   if(typeof triCoverage!=='undefined')triCoverage=null;
   await loadExamMapList(++examSeq);
   toast(result.unchanged?'Os dados já estavam atualizados.':'Caderno salvo. Resultados vinculados atualizados: '+result.updatedResults+'.');
  },'Salvar alterações');
 if(!full){
  const fields=$('#modal-form').elements;
  for(const key of ['title','color','area'])fields.namedItem(key).disabled=true;
 }
};
