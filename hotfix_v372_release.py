"""Hotfix v3.7.2: robust report XLSX parsing, canonical class rename propagation and aligned TRI plot."""
from pathlib import Path
import re

ROOT=Path(__file__).resolve().parent
STATIC=ROOT/"static"
BACKEND_MARK="# === HOTFIX V3.7.2 ==="
JS_MARK="// === HOTFIX V3.7.2 ==="
CSS_MARK="/* === HOTFIX V3.7.2 === */"

BACKEND=r'''
# === HOTFIX V3.7.2 ===
import unicodedata as _v372_unicode

def _reports_header_key(value):
    text=str(value or '').strip().lower()
    text=_v372_unicode.normalize('NFKD',text)
    text=''.join(ch for ch in text if not _v372_unicode.combining(ch))
    text=_reports_re.sub(r'[^a-z0-9]+',' ',text).strip()
    return text

_REPORT_HEADER_ALIASES={
    'name':{'nome','aluno','nome do aluno','nome aluno'},
    'activity':{'atividade','simulado','atividade simulado','nome do simulado','simulado atividade'},
    'type':{'tipo','tipo de relatorio','tipo relatorio','categoria'},
    'url':{'link','url','link de acesso','link acesso','link do relatorio','url do relatorio'},
    'reportName':{'nome do relatorio','nome relatorio','titulo','titulo do relatorio'},
    'date':{'data','data de aplicacao','data aplicacao'},
}
_REPORT_HEADER_NORMALIZED={
    field:{_reports_header_key(alias) for alias in aliases}
    for field,aliases in _REPORT_HEADER_ALIASES.items()
}

def _reports_header_map(row):
    result={}
    for i,value in enumerate(row):
        key=_reports_header_key(value)
        for field,aliases in _REPORT_HEADER_NORMALIZED.items():
            if key in aliases:
                result.setdefault(field,i)
    return result

def _reports_normalize_url(value,line):
    url=F.text(value,2000)
    if not url:
        raise ValueError(f'Linha {line}: informe o link do relatório.')
    if url.startswith('www.'):
        url='https://'+url
    elif not (url.startswith('https://') or url.startswith('http://')):
        if _reports_re.match(r'^[A-Za-z0-9.-]+\.[A-Za-z]{2,}(?:/.*)?$',url):
            url='https://'+url
        else:
            raise ValueError(f'Linha {line}: informe um link válido, como https://exemplo.com/relatorio.')
    return url

def _reports_parse(data):
    sheets=_tri_xlsx_rows(data)
    candidate=None
    for sheet_order,sheet in enumerate(sheets):
        for row_index,row in enumerate(sheet.get('rows',[])[:25]):
            columns=_reports_header_map(row)
            score=sum(1 for key in ('name','activity','type','url') if key in columns)
            if score>=4:
                item=(score,-sheet_order,-row_index,sheet,row_index,columns)
                if candidate is None or item[:3]>candidate[:3]:
                    candidate=item
    if not candidate:
        raise ValueError(
            'Não encontrei as colunas obrigatórias do modelo. '
            'Use NOME DO ALUNO, ATIVIDADE/SIMULADO, TIPO DE RELATÓRIO e LINK DE ACESSO.'
        )
    _,_,_,sheet,header_row,columns=candidate
    records=[]
    for line,row in enumerate(sheet.get('rows',[])[header_row+1:],start=header_row+2):
        def value(key):
            idx=columns.get(key)
            return row[idx] if idx is not None and idx<len(row) else ''
        name=F.text(value('name'),250)
        activity=F.text(value('activity'),250)
        type_name=F.text(value('type'),160)
        report_name=F.text(value('reportName'),250)
        date_raw=value('date')
        url_raw=value('url')
        if not any((name,activity,type_name,report_name,F.text(date_raw,80),F.text(url_raw,2000))):
            continue
        if not name:
            raise ValueError(f'Linha {line}: informe o nome do aluno.')
        if not activity:
            raise ValueError(f'Linha {line}: informe a atividade ou simulado.')
        if not type_name:
            raise ValueError(f'Linha {line}: informe o tipo de relatório.')
        url=_reports_normalize_url(url_raw,line)
        date=''
        if date_raw not in (None,''):
            date=_tri_iso_date(date_raw)
        records.append({
            'line':line,'name':name,'activity':activity,'type':type_name,
            'url':url,'reportName':report_name,'date':date
        })
    if not records:
        raise ValueError('O arquivo não possui relatórios preenchidos.')
    if len(records)>5000:
        raise ValueError('O arquivo possui mais de 5.000 linhas de relatórios.')
    return {'sheet':sheet.get('name',''),'records':records}

def _v372_class_variants(app,c):
    counts={}
    for raw in app.db.execute(c,'SELECT metadata FROM hmay_performance').fetchall():
        meta=_rx_json(raw['metadata'])
        name=F.text(meta.get('TURMA'),160) or '(sem turma)'
        counts[name]=counts.get(name,0)+1
    return counts

def _v36_class_payload(app,c):
    rows=_v36_class_rows(app,c,False)
    lookup=_v36_class_lookup(app,c)
    counts=_v372_class_variants(app,c)
    divergents={row['id']:[] for row in rows}
    by_norm={}
    for row in rows:
        by_norm[F.norm(row['name'])]=row
        for alias in row['aliases']:
            by_norm[F.norm(alias)]=row
    unregistered=[]
    for raw_name,count in sorted(counts.items(),key=lambda x:F.norm(x[0])):
        mapped=by_norm.get(F.norm(raw_name))
        if mapped:
            if F.norm(raw_name)!=F.norm(mapped['name']):
                divergents[mapped['id']].append({'name':raw_name,'records':count})
        else:
            unregistered.append({'name':raw_name,'records':count})
    for row in rows:
        row['divergents']=divergents.get(row['id'],[])
    return {'classes':rows,'unregistered':unregistered}

def _v372_update_performance_class(app,c,accepted_names,new_name):
    accepted={F.norm(x) for x in accepted_names if F.text(x,160)}
    rows=app.db.execute(c,'SELECT id,metadata FROM hmay_performance').fetchall()
    updates=[]
    for raw in rows:
        meta=_rx_json(raw['metadata'])
        current=F.text(meta.get('TURMA'),160)
        if not current or F.norm(current) not in accepted:
            continue
        if current==new_name:
            continue
        meta['TURMA']=new_name
        updates.append((raw['id'],_v36_json.dumps(meta,ensure_ascii=False,separators=(',',':'))))
    if not updates:
        return 0
    stamp=P.now().isoformat()
    for offset in range(0,len(updates),200):
        chunk=updates[offset:offset+200]
        cases=' '.join('WHEN ? THEN ?' for _ in chunk)
        placeholders=','.join('?' for _ in chunk)
        params=[]
        for row_id,meta_json in chunk:
            params.extend((row_id,meta_json))
        params.append(stamp)
        params.extend(row_id for row_id,_ in chunk)
        app.db.execute(
            c,
            'UPDATE hmay_performance SET metadata=CASE id '+cases+
            ' ELSE metadata END,version=version+1,updated_at=? WHERE id IN ('+placeholders+')',
            tuple(params),
        )
    return len(updates)

def _v36_save_class(app,c,user,data):
    rows=_v36_class_rows(app,c,False)
    class_id=F.text(data.get('id'),160)
    name=F.text(data.get('name'),160)
    if not name:
        raise ValueError('Informe o nome oficial da turma.')
    aliases_raw=data.get('aliases')
    if isinstance(aliases_raw,str):
        aliases=[F.text(x,160) for x in _v36_re.split(r'[,;\n]+',aliases_raw) if F.text(x,160)]
    elif isinstance(aliases_raw,list):
        aliases=[F.text(x,160) for x in aliases_raw if F.text(x,160)]
    else:
        aliases=[]
    active=1 if data.get('active',True) else 0

    current=None
    if class_id:
        current=next((row for row in rows if row['id']==class_id),None)
        if not current:
            raise ValueError('Turma não encontrada.')

    old_name=current['name'] if current else ''
    old_aliases=list(current['aliases']) if current else []
    if old_name and F.norm(old_name)!=F.norm(name):
        aliases.append(old_name)
    aliases=sorted({x for x in aliases+old_aliases if F.norm(x)!=F.norm(name)},key=F.norm)

    claimed={}
    for row in rows:
        if class_id and row['id']==class_id:
            continue
        if row['active']:
            claimed[F.norm(row['name'])]=row['name']
            for alias in row['aliases']:
                claimed[F.norm(alias)]=row['name']
    for candidate in [name]+aliases:
        owner=claimed.get(F.norm(candidate))
        if owner:
            raise ValueError(f'O nome/alias "{candidate}" já pertence à turma "{owner}".')

    stamp=P.now().isoformat()
    if class_id:
        app.db.execute(
            c,'UPDATE hmay_classes SET name=?,norm=?,aliases=?,active=?,updated_at=? WHERE id=?',
            (name,F.norm(name),_v36_json.dumps(aliases,ensure_ascii=False),active,stamp,class_id),
        )
        accepted=[old_name]+old_aliases+aliases
        updated_results=_v372_update_performance_class(app,c,accepted,name)
    else:
        class_id='cls_'+_v36_uuid.uuid4().hex
        app.db.execute(
            c,'INSERT INTO hmay_classes(id,name,norm,aliases,active,created_at,updated_at) VALUES (?,?,?,?,?,?,?)',
            (class_id,name,F.norm(name),_v36_json.dumps(aliases,ensure_ascii=False),active,stamp,stamp),
        )
        updated_results=0
    _v36_dashboard_cache.clear()
    app.event(c,user,user['id'],'class_registry_update')
    return {
        'id':class_id,'name':name,'aliases':aliases,'active':bool(active),
        'updatedResults':updated_results,'oldName':old_name
    }
'''

JS=r'''
// === HOTFIX V3.7.2 ===
classRegistryPanel=function(){
 if(!classRegistryCache&&!classRegistryLoading)queueMicrotask(()=>loadClassRegistry());
 if(classRegistryLoading||!classRegistryCache)return '<section class="card"><h2>Cadastro de turmas</h2><p>Carregando…</p></section>';
 if(classRegistryCache.error)return '<section class="card"><h2>Cadastro de turmas</h2><div class="notice warning">'+esc(classRegistryCache.error)+'</div></section>';
 const classes=classRegistryCache.classes||[];
 const rows=classes.map(x=>{
  const divergent=(x.divergents||[]);
  const divergentHtml=divergent.length?divergent.map(d=>'<span class="class-divergent-chip">'+esc(d.name)+' · '+managementInt(d.records)+'</span>').join(''):'<span class="micro">Nenhuma divergência</span>';
  return '<tr><td><strong>'+esc(x.name)+'</strong></td><td><div class="class-divergent-list">'+divergentHtml+'</div></td><td><input data-class-name="'+esc(x.id)+'" value="'+esc(x.name)+'" aria-label="Novo nome oficial"><input type="hidden" data-class-aliases="'+esc(x.id)+'" value="'+esc((x.aliases||[]).join('; '))+'"></td><td><label class="check"><input type="checkbox" data-class-active="'+esc(x.id)+'"'+(x.active?' checked':'')+'> Ativa</label></td><td><button type="button" class="primary" data-act="class-registry-save" data-class-id="'+esc(x.id)+'">Salvar correção</button></td></tr>';
 }).join('');
 const missing=classRegistryCache.unregistered||[];
 const missingHtml=missing.length?'<div class="notice warning"><strong>Turmas ainda não vinculadas a um cadastro:</strong><ul>'+missing.map(x=>'<li>'+esc(x.name)+' · '+managementInt(x.records)+' registro(s)</li>').join('')+'</ul></div>':'<div class="notice success">Nenhuma turma sem cadastro encontrada.</div>';
 return '<section class="card class-registry-card"><h2>Cadastro e correção de turmas</h2><p>Ao alterar o nome oficial e salvar, o sistema atualiza também todos os resultados históricos que usam o nome anterior ou uma variação já reconhecida.</p><div class="class-new-grid"><label>Nova turma<input id="class-new-name" placeholder="Ex.: Qi Med 01"></label><label>Aliases autorizados<input id="class-new-aliases" placeholder="Ex.: 01 Qi Med 01; MED 01"></label><button type="button" class="primary" data-act="class-registry-new">Cadastrar turma</button></div>'+missingHtml+'<div class="table-wrap"><table><thead><tr><th>Turma cadastrada</th><th>Turmas divergentes</th><th>Correção</th><th>Ativa</th><th>Salvar correção</th></tr></thead><tbody>'+rows+'</tbody></table></div></section>';
};

acts['class-registry-save']=async el=>{
 const id=el?.dataset?.classId||'';
 const name=document.querySelector('[data-class-name="'+CSS.escape(id)+'"]')?.value||'';
 const aliases=document.querySelector('[data-class-aliases="'+CSS.escape(id)+'"]')?.value||'';
 const active=!!document.querySelector('[data-class-active="'+CSS.escape(id)+'"]')?.checked;
 const current=(classRegistryCache?.classes||[]).find(x=>x.id===id);
 if(!name.trim())throw new Error('Informe o nome oficial da turma.');
 const changed=current&&current.name!==name.trim();
 const question=changed?'Alterar a turma "'+current.name+'" para "'+name.trim()+'" e atualizar todos os registros vinculados?':'Normalizar as divergências desta turma para "'+name.trim()+'"?';
 if(!confirm(question))return;
 const d=await api('/api/model-data/classes',{id,name,aliases,active});
 classRegistryCache={classes:d.classes||[],unregistered:d.unregistered||[]};
 managementDashboardCache=null;
 const updated=Number(d.saved?.updatedResults||0);
 toast('Turma salva. '+updated+' registro(s) histórico(s) atualizado(s).');
 render();
};

managementSimulationChart=function(rows){
 const ordered=[...(rows||[])].sort((a,b)=>String(a.date||'').localeCompare(String(b.date||'')));
 if(!ordered.length)return '<div class="notice">Nenhum simulado com resultados nos filtros selecionados.</div>';
 const cols=ordered.map(x=>{
  const tri=Number(x.triGeneral),hasTri=Number.isFinite(tri),height=hasTri?Math.max(0,Math.min(100,tri/10)):0;
  return '<div class="management-score-col"><div class="management-score-plot"><div class="management-score-track"><span class="management-score-fill" style="height:'+height+'%"></span><span class="management-score-marker" style="bottom:'+height+'%">'+(hasTri?managementFmt(tri,1):'—')+'</span></div></div><strong>'+esc(x.activity||'Simulado')+'</strong><small>'+esc(x.date||'')+'</small><em>'+managementInt(x.participants)+' participantes · % acertos '+managementFmt(x.accuracy,1,'%')+'</em></div>';
 }).join('');
 return '<div class="management-score-axis"><div class="management-scale"><span>1000</span><span>750</span><span>500</span><span>250</span><span>0</span></div><div class="management-score-columns">'+cols+'</div></div><p class="micro">A base das colunas coincide com o zero da escala. A área pintada corresponde à nota TRI média em 0–1000.</p>';
};
'''

CSS=r'''
/* === HOTFIX V3.7.2 === */
.class-divergent-list{display:flex;gap:.35rem;flex-wrap:wrap}.class-divergent-chip{display:inline-flex;padding:.3rem .5rem;border-radius:999px;background:#fff0df;border:1px solid #f0cf91;font-size:.76rem}.management-score-axis{display:grid;grid-template-columns:48px minmax(0,1fr);gap:.7rem}.management-score-axis .management-scale{height:240px;align-self:start;padding:0;display:flex;flex-direction:column;justify-content:space-between;align-items:flex-end}.management-score-axis .management-score-columns{height:auto;display:flex;align-items:flex-start;gap:1rem;overflow-x:auto;padding:0 .4rem}.management-score-axis .management-score-col{height:auto;min-width:125px;display:grid;grid-template-rows:240px auto auto auto;gap:.2rem;justify-items:center;text-align:center}.management-score-axis .management-score-plot{height:240px;display:flex;align-items:flex-end;justify-content:center}.management-score-axis .management-score-track{height:240px!important;min-height:240px!important}.management-score-axis .management-score-marker{transform:translate(-50%,50%)}@media(max-width:800px){.management-score-axis{grid-template-columns:40px minmax(0,1fr)}}
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
    text=re.sub(r'/static/student_summary\.js\?v=[^"\']+','/static/student_summary.js?v=3.7.2',text)
    html.write_text(text,encoding="utf-8")

    for verifier in ROOT.glob('verify_*.py'):
        source=verifier.read_text(encoding='utf-8')
        source=source.replace('/static/student_summary.js?v=3.7.1','/static/student_summary.js?v=3.7.2')
        verifier.write_text(source,encoding='utf-8')

    site=ROOT/'site_version_release.py'
    source=site.read_text(encoding='utf-8').replace('PUBLIC_VERSION="3.7.1"','PUBLIC_VERSION="3.7.2"')
    site.write_text(source,encoding='utf-8')
    vsite=ROOT/'verify_site_version.py'
    source=vsite.read_text(encoding='utf-8').replace('v3.7.1','v3.7.2')
    vsite.write_text(source,encoding='utf-8')

    print("MEUCRONOGRAMA_HOTFIX_372_READY: report model parser matches generated XLSX, URLs normalized, class rename propagates and TRI axis aligned.",flush=True)

if __name__=="__main__":
    main()
