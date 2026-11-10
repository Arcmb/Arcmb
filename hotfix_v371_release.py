"""Hotfix v3.7.1: report template bytes, report-type deletion, exact TRI fill and cache alignment."""
from pathlib import Path
import re

ROOT=Path(__file__).resolve().parent
STATIC=ROOT/"static"
BACKEND_MARK="# === HOTFIX V3.7.1 ==="
JS_MARK="// === HOTFIX V3.7.1 ==="
CSS_MARK="/* === HOTFIX V3.7.1 === */"

BACKEND=r'''
# === HOTFIX V3.7.1 ===
_v371_handle_base=handle

def _reports_template():
    headers=['NOME DO ALUNO','ATIVIDADE/SIMULADO','TIPO DE RELATÓRIO','NOME DO RELATÓRIO (opcional)','DATA (opcional)','LINK DE ACESSO']
    rows=[['' for _ in headers] for _ in range(200)]
    help_headers=['Campo','Orientação']
    help_rows=[
        ['NOME DO ALUNO','Deve corresponder ao nome cadastrado no sistema.'],
        ['ATIVIDADE/SIMULADO','Nome do simulado, treino, teste ou atividade.'],
        ['TIPO DE RELATÓRIO','Use um tipo previamente criado pelo Master, como Simulado, Treino ou Mapa de Metas.'],
        ['NOME DO RELATÓRIO','Opcional. Se vazio, usa o nome geral do modelo.'],
        ['DATA','Opcional. Use dd/mm/aaaa ou aaaa-mm-dd.'],
        ['LINK DE ACESSO','URL individual do PDF/relatório online. Deve começar com http:// ou https://.'],
    ]
    output=T.export(headers,rows,first_name='RELATORIOS',extra_sheets=[('Como preencher',help_headers,help_rows)])
    if isinstance(output,tuple):
        output=next((item for item in output if isinstance(item,(bytes,bytearray))),None)
    if not isinstance(output,(bytes,bytearray)):
        raise ValueError('Não foi possível gerar o arquivo-modelo de relatórios.')
    return bytes(output)

def _reports_delete_type(app,c,user,type_id):
    type_id=F.text(type_id,160)
    if not type_id:
        raise ValueError('Tipo de relatório não informado.')
    row=app.db.execute(c,'SELECT id,name FROM hmay_report_types WHERE id=?',(type_id,)).fetchone()
    if not row:
        raise ValueError('Tipo de relatório não encontrado.')
    models=app.db.execute(c,'SELECT id FROM hmay_report_models WHERE type_id=?',(type_id,)).fetchall()
    model_ids=[x['id'] for x in models]
    links=0
    if model_ids:
        placeholders=','.join('?' for _ in model_ids)
        count=app.db.execute(c,'SELECT COUNT(*) AS n FROM hmay_student_reports WHERE model_id IN ('+placeholders+')',tuple(model_ids)).fetchone()
        links=int(count['n'] or 0)
        app.db.execute(c,'DELETE FROM hmay_student_reports WHERE model_id IN ('+placeholders+')',tuple(model_ids))
        app.db.execute(c,'DELETE FROM hmay_report_models WHERE id IN ('+placeholders+')',tuple(model_ids))
    app.db.execute(c,'DELETE FROM hmay_report_types WHERE id=?',(type_id,))
    app.event(c,user,user['id'],'report_type_delete')
    return {'deletedType':row['name'],'deletedModels':len(model_ids),'deletedReports':links,**_reports_admin_data(app,c)}

def handle(app,c,user,path,method,data,query,start,HTTPError):
    if path=='/api/model-data/report-type-delete':
        if user.get('role') not in ('master','coordenador'):
            raise HTTPError(403,'Acesso reservado ao Master e à coordenação.')
        if method!='POST':
            raise HTTPError(405,'Use POST para excluir o tipo.')
        return app.reply(start,200,_reports_delete_type(app,c,user,data.get('id')))
    return _v371_handle_base(app,c,user,path,method,data,query,start,HTTPError)
'''

JS=r'''
// === HOTFIX V3.7.1 ===
managementSimulationChart=function(rows){
 const ordered=[...(rows||[])].sort((a,b)=>String(a.date||'').localeCompare(String(b.date||'')));
 if(!ordered.length)return '<div class="notice">Nenhum simulado com resultados nos filtros selecionados.</div>';
 const cols=ordered.map(x=>{
  const tri=Number(x.triGeneral),hasTri=Number.isFinite(tri),height=hasTri?Math.max(0,Math.min(100,tri/10)):0;
  return '<div class="management-score-col"><div class="management-score-plot"><div class="management-score-track"><span class="management-score-fill" style="height:'+height+'%"></span><span class="management-score-marker" style="bottom:'+height+'%">'+(hasTri?managementFmt(tri,1):'—')+'</span></div></div><strong>'+esc(x.activity||'Simulado')+'</strong><small>'+esc(x.date||'')+'</small><em>'+managementInt(x.participants)+' participantes · % acertos '+managementFmt(x.accuracy,1,'%')+'</em></div>';
 }).join('');
 return '<div class="management-score-chart"><div class="management-scale"><span>1000</span><span>750</span><span>500</span><span>250</span><span>0</span></div><div class="management-score-columns">'+cols+'</div></div><p class="micro">A área pintada corresponde exatamente à nota TRI geral média na escala de 0 a 1000.</p>';
};

reportTypesAdminHtml=function(types){
 const rows=(types||[]).map(t=>'<tr><td><input data-report-type-name="'+esc(t.id)+'" value="'+esc(t.name)+'"></td><td><input type="number" data-report-type-order="'+esc(t.id)+'" value="'+Number(t.sort_order||0)+'"></td><td><label class="check"><input type="checkbox" data-report-type-active="'+esc(t.id)+'"'+(t.active?' checked':'')+'> Ativo</label></td><td><div class="actions"><button type="button" class="secondary" data-act="report-type-save" data-type-id="'+esc(t.id)+'">Salvar</button><button type="button" class="secondary danger" data-act="report-type-delete" data-type-id="'+esc(t.id)+'" data-type-name="'+esc(t.name)+'">Excluir</button></div></td></tr>').join('');
 return '<section class="card"><h2>Tipos de relatório</h2><p>Os tipos definem as linhas/seções que o aluno verá em “Meus relatórios”.</p><div class="report-type-new"><label>Novo tipo<input id="report-type-new-name" placeholder="Ex.: Diagnóstico"></label><label>Ordem<input id="report-type-new-order" type="number" value="10"></label><button type="button" class="primary" data-act="report-type-new">Criar tipo</button></div><div class="table-wrap"><table><thead><tr><th>Tipo</th><th>Ordem</th><th>Status</th><th>Ações</th></tr></thead><tbody>'+rows+'</tbody></table></div></section>';
};
acts['report-type-delete']=async el=>{
 const id=el?.dataset?.typeId||'',name=el?.dataset?.typeName||'este tipo';
 if(!id)throw new Error('Tipo não informado.');
 if(!confirm('Excluir "'+name+'"? Se houver modelos e relatórios individuais vinculados a este tipo, eles também serão excluídos.'))return;
 const d=await api('/api/model-data/report-type-delete',{id});
 reportAdminCache={types:d.types||[],models:d.models||[]};studentReportsCache.clear();render();
 toast('Tipo excluído: '+String(d.deletedType||name)+'.');
};

acts['report-batch-template']=async()=>{
 try{
  const d=await api('/api/model-data/report-batch-template',{});
  reportsDownload(d.filename,d.mime,d.file);
  toast('Modelo XLSX gerado e disponibilizado para download.');
 }catch(error){
  toast('Não foi possível gerar o modelo XLSX: '+(error?.message||'erro inesperado'),true);
  throw error;
 }
};
'''

CSS=r'''
/* === HOTFIX V3.7.1 === */
.management-score-chart{height:330px}.management-score-columns{align-items:flex-end}.management-score-col{height:100%;grid-template-rows:240px auto auto auto;align-items:end}.management-score-plot{height:240px;width:64px;display:flex;align-items:flex-end;justify-content:center}.management-score-track{position:relative!important;height:220px!important;min-height:220px!important;width:36px!important;background:transparent!important;border:1px solid #eadde1!important;border-radius:8px 8px 3px 3px!important;overflow:visible!important;display:block!important}.management-score-track:before{content:'';position:absolute;inset:0;background:linear-gradient(to top,transparent 24.6%,#eee4e7 25%,transparent 25.4%,transparent 49.6%,#eee4e7 50%,transparent 50.4%,transparent 74.6%,#eee4e7 75%,transparent 75.4%);pointer-events:none}.management-score-fill{position:absolute!important;left:0!important;right:0!important;bottom:0!important;width:100%!important;background:#bd5364!important;border-radius:7px 7px 2px 2px!important;opacity:1!important;z-index:2}.management-score-marker{position:absolute;left:50%;transform:translate(-50%,50%);font-size:.75rem;font-weight:800;color:#9f4351;white-space:nowrap;z-index:3;background:#fff;padding:0 .2rem}.secondary.danger{color:#9f3244;border-color:#e6aeb7;background:#fff}
'''

def main():
    model=ROOT/"model_data.py"
    text=model.read_text(encoding="utf-8")
    if BACKEND_MARK not in text:
        model.write_text(text.rstrip()+"\n\n"+BACKEND.strip()+"\n",encoding="utf-8")

    js=STATIC/"student_summary.js"
    text=js.read_text(encoding="utf-8")
    if JS_MARK not in text:
        js.write_text(text.rstrip()+"\n\n"+JS.strip()+"\n",encoding="utf-8")

    css=STATIC/"style.css"
    text=css.read_text(encoding="utf-8")
    if CSS_MARK not in text:
        css.write_text(text.rstrip()+"\n\n"+CSS.strip()+"\n",encoding="utf-8")

    html=STATIC/"app.html"
    text=html.read_text(encoding="utf-8")
    text=re.sub(r'/static/student_summary\.js\?v=[^"\']+','/static/student_summary.js?v=3.7.1',text)
    html.write_text(text,encoding="utf-8")

    for verifier in ROOT.glob('verify_*.py'):
        source=verifier.read_text(encoding='utf-8')
        source=source.replace('/static/student_summary.js?v=3.7.0','/static/student_summary.js?v=3.7.1')
        verifier.write_text(source,encoding='utf-8')

    site=ROOT/'site_version_release.py'
    source=site.read_text(encoding='utf-8').replace('PUBLIC_VERSION="3.7.0"','PUBLIC_VERSION="3.7.1"')
    site.write_text(source,encoding='utf-8')
    vsite=ROOT/'verify_site_version.py'
    source=vsite.read_text(encoding='utf-8').replace('v3.7.0','v3.7.1')
    vsite.write_text(source,encoding='utf-8')

    print("MEUCRONOGRAMA_HOTFIX_371_READY: report XLSX bytes, type deletion, exact dynamic TRI fill and v3.7.1 cache installed.",flush=True)

if __name__=="__main__":
    main()
