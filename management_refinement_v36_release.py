"""Management refinement v3.6: fast aggregation, TRI 0-1000, class registry and import validation."""
from pathlib import Path
import re

ROOT=Path(__file__).resolve().parent
STATIC=ROOT/"static"
BACKEND_MARK="# === MANAGEMENT REFINEMENT V3.6 ==="
TRI_MODEL_MARK="# === TRI MODEL WITHOUT BONUS V3.6 ==="
JS_MARK="// === MANAGEMENT REFINEMENT V3.6 ==="
CSS_MARK="/* === MANAGEMENT REFINEMENT V3.6 === */"

BACKEND=r'''
# === MANAGEMENT REFINEMENT V3.6 ===
import json as _v36_json
import re as _v36_re
import time as _v36_time
import uuid as _v36_uuid

_v36_classes_ready=False
_v36_dashboard_cache={}

def _v36_classes_ensure(app,c):
    global _v36_classes_ready
    if _v36_classes_ready:
        return
    app.db.execute(c, """CREATE TABLE IF NOT EXISTS hmay_classes(
        id text PRIMARY KEY,
        name text NOT NULL UNIQUE,
        norm text NOT NULL UNIQUE,
        aliases text NOT NULL DEFAULT '[]',
        active integer NOT NULL DEFAULT 1,
        created_at text NOT NULL,
        updated_at text NOT NULL
    )""")
    _v36_classes_ready=True

def _v36_class_rows(app,c,active_only=False):
    _v36_classes_ensure(app,c)
    sql='SELECT id,name,norm,aliases,active,created_at,updated_at FROM hmay_classes'
    if active_only:
        sql+=' WHERE active=1'
    sql+=' ORDER BY lower(name)'
    rows=[]
    for raw in app.db.execute(c,sql).fetchall():
        row=dict(raw)
        try:
            aliases=_v36_json.loads(row.get('aliases') or '[]')
        except Exception:
            aliases=[]
        if not isinstance(aliases,list):
            aliases=[]
        row['aliases']=[F.text(x,160) for x in aliases if F.text(x,160)]
        rows.append(row)
    return rows

def _v36_class_lookup(app,c):
    lookup={}
    for row in _v36_class_rows(app,c,True):
        lookup[F.norm(row['name'])]=row['name']
        for alias in row['aliases']:
            lookup[F.norm(alias)]=row['name']
    return lookup

def _v36_validate_class_names(app,c,names,source_label):
    lookup=_v36_class_lookup(app,c)
    invalid=[]
    for value in names:
        raw=F.text(value,160)
        if not raw:
            invalid.append('(sem turma)')
        elif F.norm(raw) not in lookup:
            invalid.append(raw)
    invalid=sorted(set(invalid),key=F.norm)
    if invalid:
        shown=', '.join(invalid[:20])
        extra='' if len(invalid)<=20 else f' e mais {len(invalid)-20}'
        raise ValueError(
            f'{source_label}: turma(s) não cadastrada(s): {shown}{extra}. '
            'Cadastre a turma ou ajuste o nome/alias no Painel de bordo antes de importar.'
        )

def _v36_class_payload(app,c):
    rows=_v36_class_rows(app,c,False)
    lookup=_v36_class_lookup(app,c)
    detected=[]
    for raw in app.db.execute(c,'SELECT metadata FROM hmay_performance').fetchall():
        meta=_rx_json(raw['metadata'])
        name=F.text(meta.get('TURMA'),160) or '(sem turma)'
        detected.append(name)
    counts={}
    for name in detected:
        counts[name]=counts.get(name,0)+1
    unregistered=[
        {'name':name,'records':count}
        for name,count in sorted(counts.items(),key=lambda x:F.norm(x[0]))
        if name=='(sem turma)' or F.norm(name) not in lookup
    ]
    return {'classes':rows,'unregistered':unregistered}

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
    aliases=sorted({x for x in aliases if F.norm(x)!=F.norm(name)},key=F.norm)
    active=1 if data.get('active',True) else 0
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
        exists=app.db.execute(c,'SELECT id FROM hmay_classes WHERE id=?',(class_id,)).fetchone()
        if not exists:
            raise ValueError('Turma não encontrada.')
        app.db.execute(
            c,'UPDATE hmay_classes SET name=?,norm=?,aliases=?,active=?,updated_at=? WHERE id=?',
            (name,F.norm(name),_v36_json.dumps(aliases,ensure_ascii=False),active,stamp,class_id),
        )
    else:
        class_id='cls_'+_v36_uuid.uuid4().hex
        app.db.execute(
            c,'INSERT INTO hmay_classes(id,name,norm,aliases,active,created_at,updated_at) VALUES (?,?,?,?,?,?,?)',
            (class_id,name,F.norm(name),_v36_json.dumps(aliases,ensure_ascii=False),active,stamp,stamp),
        )
    _v36_dashboard_cache.clear()
    app.event(c,user,user['id'],'class_registry_update')
    return {'id':class_id,'name':name,'aliases':aliases,'active':bool(active)}

def _v36_metric_number(key):
    try:
        return int(str(key).split(':')[-1])
    except Exception:
        return None

def _v36_exam_area_maps(app,c):
    result={}
    for raw in app.db.execute(c,'SELECT id,items FROM hmay_exams').fetchall():
        items=_rx_json(raw['items'])
        qmap={}
        if isinstance(items,list):
            for item in items:
                if not isinstance(item,dict):
                    continue
                try:
                    number=int(item.get('number'))
                except Exception:
                    continue
                area=_mgmt_area_key(item.get('area'))
                if area:
                    qmap[number]=area
        result[raw['id']]=qmap
    return result

def _v36_data_stamp(app,c):
    perf=app.db.execute(c,"SELECT COUNT(*) AS n,COALESCE(MAX(updated_at),'') AS stamp FROM hmay_performance").fetchone()
    exams=app.db.execute(c,"SELECT COUNT(*) AS n,COALESCE(MAX(updated_at),'') AS stamp FROM hmay_exams").fetchone()
    _v36_classes_ensure(app,c)
    classes=app.db.execute(c,"SELECT COUNT(*) AS n,COALESCE(MAX(updated_at),'') AS stamp FROM hmay_classes").fetchone()
    return f"{perf['n']}:{perf['stamp']}|{exams['n']}:{exams['stamp']}|{classes['n']}:{classes['stamp']}"

_mgmt_dashboard_data_v35=_mgmt_dashboard_data

def _mgmt_dashboard_data(app,c,user,query):
    if user.get('role') not in ('master','coordenador'):
        raise ValueError('Painel gerencial exclusivo do Master e da coordenação.')
    selected={
        'year':F.text((query or {}).get('year'),4),
        'turma':F.text((query or {}).get('turma'),160),
        'activityKey':F.text((query or {}).get('activityKey'),250),
        'date':F.text((query or {}).get('date'),40),
    }
    stamp=_v36_data_stamp(app,c)
    cache_key=(stamp,selected['year'],selected['turma'],selected['activityKey'],selected['date'])
    cached=_v36_dashboard_cache.get(cache_key)
    if cached and _v36_time.time()-cached[0] < 180:
        return cached[1]

    class_rows=_v36_class_rows(app,c,True)
    class_lookup=_v36_class_lookup(app,c)
    active_students=app.db.execute(
        c,"SELECT COUNT(*) AS n FROM hmay_users WHERE role IN ('user','aluno') AND active=1"
    ).fetchone()['n']
    conditions=["u.role IN ('user','aluno')","u.active=1"]
    args=[]
    if selected['year']:
        conditions.append('p.applied_on LIKE ?');args.append(selected['year']+'%')
    if selected['activityKey']:
        conditions.append('p.activity_key=?');args.append(selected['activityKey'])
    if selected['date']:
        conditions.append('p.applied_on=?');args.append(selected['date'])
    raw_rows=app.db.execute(
        c,
        """SELECT p.id,p.user_id,p.activity_key,p.activity,p.applied_on,p.metrics,p.metadata
           FROM hmay_performance p JOIN hmay_users u ON u.id=p.user_id
           WHERE """+' AND '.join(conditions)+' ORDER BY p.applied_on,p.activity',
        tuple(args),
    ).fetchall()

    area_maps=_v36_exam_area_maps(app,c)
    participants=set();total_correct=0;total_valid=0
    tri_general=[];redactions=[]
    areas={key:{'correct':0,'valid':0,'tri':[]} for key in ('LC','CH','CN','MT')}
    simulations={};classes={};years=set();sim_options={};participations=0

    for raw in raw_rows:
        row=dict(raw);metadata=_rx_json(row.get('metadata'))
        raw_class=F.text(metadata.get('TURMA'),160) or 'Sem turma'
        canonical=class_lookup.get(F.norm(raw_class),raw_class)
        if selected['turma'] and canonical!=selected['turma']:
            continue
        date=F.text(row.get('applied_on'),40)
        if len(date)>=4:
            years.add(date[:4])
        sim_options[(row['activity_key'],date)]={'activityKey':row['activity_key'],'activity':row['activity'],'date':date}
        participants.add(row['user_id']);participations+=1

        metrics=_rx_json(row.get('metrics'))
        if not isinstance(metrics,dict):
            metrics={}
        qmap=area_maps.get(F.text(metadata.get('_exam_id'),160),{})
        row_correct=0;row_valid=0
        row_area={key:{'correct':0,'valid':0} for key in ('LC','CH','CN','MT')}
        for mkey,mval in metrics.items():
            if not isinstance(mval,dict):
                continue
            try:
                correct=max(0,int(mval.get('correct') or 0))
                valid=max(0,int(mval.get('total') or 0))
            except Exception:
                continue
            row_correct+=correct;row_valid+=valid
            number=_v36_metric_number(mkey)
            area=qmap.get(number)
            if not area and number:
                area='LC' if number<=45 else 'CH' if number<=90 else 'CN' if number<=135 else 'MT' if number<=180 else None
            if area in row_area:
                row_area[area]['correct']+=correct;row_area[area]['valid']+=valid
        total_correct+=row_correct;total_valid+=row_valid

        scores=_tri_scores_from_metadata(metadata)
        if scores.get('tri') is not None: tri_general.append(scores['tri'])
        if scores.get('redaction') is not None: redactions.append(scores['redaction'])

        skey=(row['activity_key'],date)
        sim=simulations.setdefault(skey,{'activityKey':row['activity_key'],'activity':row['activity'],'date':date,'participants':set(),'correct':0,'valid':0,'triGeneral':[],'lc':[],'ch':[],'cn':[],'mt':[],'redaction':[]})
        sim['participants'].add(row['user_id']);sim['correct']+=row_correct;sim['valid']+=row_valid
        cls=classes.setdefault(canonical,{'turma':canonical,'participants':set(),'correct':0,'valid':0,'triGeneral':[],'redaction':[]})
        cls['participants'].add(row['user_id']);cls['correct']+=row_correct;cls['valid']+=row_valid

        for area_key in ('LC','CH','CN','MT'):
            areas[area_key]['correct']+=row_area[area_key]['correct']
            areas[area_key]['valid']+=row_area[area_key]['valid']
        for key,value in (('triGeneral',scores.get('tri')),('lc',scores.get('lc')),('ch',scores.get('ch')),('cn',scores.get('cn')),('mt',scores.get('mt')),('redaction',scores.get('redaction'))):
            if value is not None: sim[key].append(value)
        if scores.get('tri') is not None: cls['triGeneral'].append(scores['tri'])
        if scores.get('redaction') is not None: cls['redaction'].append(scores['redaction'])
        for area_key,score_key in (('LC','lc'),('CH','ch'),('CN','cn'),('MT','mt')):
            value=scores.get(score_key)
            if value is not None: areas[area_key]['tri'].append(value)

    sim_rows=[]
    for sim in simulations.values():
        sim_rows.append({
            'activityKey':sim['activityKey'],'activity':sim['activity'],'date':sim['date'],
            'participants':len(sim['participants']),'correct':sim['correct'],'valid':sim['valid'],
            'accuracy':None if not sim['valid'] else round(100*sim['correct']/sim['valid'],2),
            'triGeneral':_mgmt_mean(sim['triGeneral']),'lc':_mgmt_mean(sim['lc']),'ch':_mgmt_mean(sim['ch']),
            'cn':_mgmt_mean(sim['cn']),'mt':_mgmt_mean(sim['mt']),'redaction':_mgmt_mean(sim['redaction']),
        })
    sim_rows.sort(key=lambda x:(x['date'],F.norm(x['activity'])),reverse=True)

    class_summary=[]
    for cls in classes.values():
        class_summary.append({
            'turma':cls['turma'],'participants':len(cls['participants']),'correct':cls['correct'],'valid':cls['valid'],
            'accuracy':None if not cls['valid'] else round(100*cls['correct']/cls['valid'],2),
            'triGeneral':_mgmt_mean(cls['triGeneral']),'redaction':_mgmt_mean(cls['redaction']),
        })
    class_summary.sort(key=lambda x:(-(x['participants'] or 0),F.norm(x['turma'])))

    area_rows=[]
    for key,label in (('LC','Linguagens'),('CH','Humanas'),('CN','Natureza'),('MT','Matemática')):
        bucket=areas[key]
        area_rows.append({
            'key':key,'name':label,'correct':bucket['correct'],'valid':bucket['valid'],
            'accuracy':None if not bucket['valid'] else round(100*bucket['correct']/bucket['valid'],2),
            'tri':_mgmt_mean(bucket['tri']),
        })
    area_rows.append({'key':'RED','name':'Redação','correct':0,'valid':0,'accuracy':None,'tri':_mgmt_mean(redactions)})

    exam_rows=app.db.execute(c,'SELECT title,applied_on FROM hmay_exams ORDER BY applied_on,title').fetchall()
    catalog={(F.norm(x['title']),F.text(x['applied_on'],40)) for x in exam_rows}
    all_years=sorted({F.text(x['applied_on'],40)[:4] for x in exam_rows if len(F.text(x['applied_on'],40))>=4} | years,reverse=True)
    options=sorted(sim_options.values(),key=lambda x:(x['date'],F.norm(x['activity'])),reverse=True)
    result={
        'filters':{'years':all_years,'turmas':[x['name'] for x in class_rows],'simulations':options,'selected':selected},
        'kpis':{
            'activeStudents':active_students,'participants':len(participants),'catalogSimulations':len(catalog),'maps':len(exam_rows),
            'simulationsWithResults':len(sim_rows),'participations':participations,'correct':total_correct,'valid':total_valid,
            'accuracy':None if not total_valid else round(100*total_correct/total_valid,2),
            'triGeneral':_mgmt_mean(tri_general),'redaction':_mgmt_mean(redactions),
        },
        'areas':area_rows,'simulations':sim_rows,'classes':class_summary,'scaleMax':1000,
    }
    _v36_dashboard_cache[cache_key]=(_v36_time.time(),result)
    if len(_v36_dashboard_cache)>12:
        for key in list(_v36_dashboard_cache.keys())[:-8]:
            _v36_dashboard_cache.pop(key,None)
    return result

_v36_original_tri_preview=_tri_preview

def _tri_preview(app,c,data):
    parsed,match,preview=_v36_original_tri_preview(app,c,data)
    _v36_validate_class_names(app,c,[row.get('group') for row in parsed.get('records',[])],'TRI e Redação')
    return parsed,match,preview

_v36_original_handle=handle

def handle(app,c,user,path,method,data,query,start,HTTPError):
    if path == '/api/model-data/classes':
        if user.get('role') not in ('master','coordenador'):
            raise HTTPError(403,'Cadastro de turmas exclusivo do Master e da coordenação.')
        if method=='GET':
            return app.reply(start,200,_v36_class_payload(app,c))
        if method=='POST':
            saved=_v36_save_class(app,c,user,data)
            return app.reply(start,200,{'saved':saved,**_v36_class_payload(app,c)})
        raise HTTPError(405,'Use GET ou POST para o cadastro de turmas.')

    if path in ('/api/model-data/preview','/api/model-data/confirm') and method=='POST' and user.get('role') in ('master','coordenador'):
        parsed=_parse(data,False)
        _v36_validate_class_names(app,c,[student.get('group') for student in parsed.get('students',[])],'DADOS DOS ALUNOS')

    return _v36_original_handle(app,c,user,path,method,data,query,start,HTTPError)
'''

TRI_MODEL=r'''
# === TRI MODEL WITHOUT BONUS V3.6 ===
def _qi_tri_template_workbook():
    headers = [
        'NOME', 'LOGIN (opcional)', 'NOME DO SIMULADO', 'DATA DE APLICAÇÃO', 'TURMA',
        'RANKING', 'NOTA TRI GERAL', 'TRI LINGUAGENS', 'TRI HUMANAS',
        'TRI NATUREZA', 'TRI MATEMÁTICA',
        'TEMA DA REDAÇÃO', 'C1', 'C2', 'C3', 'C4', 'C5', 'NOTA DA REDAÇÃO',
    ]
    rows = [['' for _ in headers] for _ in range(200)]
    help_headers = ['Campo', 'Orientação']
    help_rows = [
        ['NOME', 'Obrigatório. Deve corresponder ao nome usado no resultado já importado.'],
        ['LOGIN', 'Opcional. Serve apenas como apoio; o vínculo principal continua pelo nome.'],
        ['NOME DO SIMULADO', 'Informe o mesmo nome da avaliação já importada.'],
        ['DATA DE APLICAÇÃO', 'Use dd/mm/aaaa ou aaaa-mm-dd.'],
        ['TURMA', 'Use o nome oficial cadastrado no Painel de bordo ou um alias autorizado.'],
        ['RANKING', 'Posição do aluno no simulado, quando disponível.'],
        ['NOTA TRI GERAL', 'Nota oficial geral.'],
        ['TRI POR ÁREA', 'Linguagens, Humanas, Natureza e Matemática. Deixe vazio quando a área não foi aplicada.'],
        ['TEMA DA REDAÇÃO', 'Opcional. Texto do tema/proposta da redação.'],
        ['C1–C5', 'Cada competência deve estar entre 0 e 200.'],
        ['NOTA DA REDAÇÃO', 'De 0 a 1000. Se ficar vazia e C1–C5 estiverem completos, o sistema calcula a soma.'],
        ['REGRA DE ATUALIZAÇÃO', 'Campos vazios não apagam notas existentes. Respostas A–E, acertos, mapa de questões e cronograma são preservados.'],
        ['ARQUIVO', 'Use XLSX sem fórmulas, macros, proteção ou vínculos externos.'],
    ]
    return T.export(headers, rows, first_name='TRI e Redação', extra_sheets=[('Como preencher', help_headers, help_rows)])
'''

JS=r'''
// === MANAGEMENT REFINEMENT V3.6 ===
let classRegistryCache=null;
let classRegistryLoading=false;

managementSimulationChart=function(rows){
 const ordered=[...(rows||[])].sort((a,b)=>String(a.date||'').localeCompare(String(b.date||'')));
 if(!ordered.length)return '<div class="notice">Nenhum simulado com resultados nos filtros selecionados.</div>';
 const cols=ordered.map(x=>{
  const tri=Number(x.triGeneral),hasTri=Number.isFinite(tri),height=hasTri?Math.max(3,Math.min(100,tri/10)):0;
  return '<div class="management-score-col"><span class="management-score-value">'+(hasTri?managementFmt(tri,1):'—')+'</span><div class="management-score-track"><span style="height:'+height+'%"></span></div><strong>'+esc(x.activity||'Simulado')+'</strong><small>'+esc(x.date||'')+'</small><em>'+managementInt(x.participants)+' participantes · % acertos '+managementFmt(x.accuracy,1,'%')+'</em></div>';
 }).join('');
 return '<div class="management-score-chart"><div class="management-scale"><span>1000</span><span>750</span><span>500</span><span>250</span><span>0</span></div><div class="management-score-columns">'+cols+'</div></div><p class="micro">Nota TRI geral média em escala de 0 a 1000. O percentual de acertos aparece como informação complementar.</p>';
};

managementAreaHtml=function(rows){
 if(!(rows||[]).length)return '<div class="notice">Sem dados de área para os filtros selecionados.</div>';
 return '<div class="management-area-grid">'+rows.map(x=>{
  const tri=Number(x.tri),hasTri=Number.isFinite(tri),width=hasTri?Math.max(0,Math.min(100,tri/10)):0;
  const tct=x.accuracy===null||x.accuracy===undefined?'':('<span>% acertos '+managementFmt(x.accuracy,1,'%')+'</span>');
  return '<article><div class="management-area-title"><strong>'+esc(x.name)+'</strong><span>Nota média '+(hasTri?managementFmt(tri,1):'—')+' / 1000</span></div><div class="management-bar tri-scale"><span style="width:'+width+'%"></span></div><div class="management-area-meta">'+tct+'<span>Escala TRI 0–1000</span></div></article>';
 }).join('')+'</div>';
};

managementSimulationTable=function(rows){
 const body=(rows||[]).map(x=>'<tr><td><strong>'+esc(x.activity||'Simulado')+'</strong><br><small>'+esc(x.date||'')+'</small></td><td>'+managementInt(x.participants)+'</td><td>'+managementFmt(x.accuracy,1,'%')+'</td><td>'+managementFmt(x.triGeneral,1)+'</td><td>'+managementFmt(x.lc,1)+'</td><td>'+managementFmt(x.ch,1)+'</td><td>'+managementFmt(x.cn,1)+'</td><td>'+managementFmt(x.mt,1)+'</td><td>'+managementFmt(x.redaction,1)+'</td></tr>').join('');
 return body?'<div class="table-wrap"><table><thead><tr><th>Simulado</th><th>Participantes</th><th>% acertos</th><th>TRI geral</th><th>LC</th><th>CH</th><th>CN</th><th>MT</th><th>Redação</th></tr></thead><tbody>'+body+'</tbody></table></div>':'<div class="notice">Sem resultados para listar.</div>';
};

managementClassTable=function(rows){
 const body=(rows||[]).map(x=>'<tr><td><strong>'+esc(x.turma||'Sem turma')+'</strong></td><td>'+managementInt(x.participants)+'</td><td>'+managementFmt(x.accuracy,1,'%')+'</td><td>'+managementFmt(x.triGeneral,1)+'</td><td>'+managementFmt(x.redaction,1)+'</td></tr>').join('');
 return body?'<div class="table-wrap"><table><thead><tr><th>Turma</th><th>Participantes</th><th>% acertos</th><th>TRI geral</th><th>Redação</th></tr></thead><tbody>'+body+'</tbody></table></div>':'<div class="notice">Sem turmas para os filtros selecionados.</div>';
};

async function loadClassRegistry(force=false){
 if(!managementDashboardAllowed()||classRegistryLoading||(!force&&classRegistryCache))return;
 classRegistryLoading=true;
 try{classRegistryCache=await api('/api/model-data/classes');}
 catch(error){classRegistryCache={error:error?.message||'Não foi possível carregar o cadastro de turmas.'};}
 finally{classRegistryLoading=false;if(view==='home'&&typeof render==='function')render();}
}
function classRegistryPanel(){
 if(!classRegistryCache&&!classRegistryLoading)queueMicrotask(()=>loadClassRegistry());
 if(classRegistryLoading||!classRegistryCache)return '<section class="card"><h2>Cadastro de turmas</h2><p>Carregando…</p></section>';
 if(classRegistryCache.error)return '<section class="card"><h2>Cadastro de turmas</h2><div class="notice warning">'+esc(classRegistryCache.error)+'</div></section>';
 const rows=(classRegistryCache.classes||[]).map(x=>'<tr><td><input data-class-name="'+esc(x.id)+'" value="'+esc(x.name)+'"></td><td><input data-class-aliases="'+esc(x.id)+'" value="'+esc((x.aliases||[]).join('; '))+'" placeholder="Aliases separados por ;"></td><td><label class="check"><input type="checkbox" data-class-active="'+esc(x.id)+'"'+(x.active?' checked':'')+'> Ativa</label></td><td><button type="button" class="secondary" data-act="class-registry-save" data-class-id="'+esc(x.id)+'">Salvar</button></td></tr>').join('');
 const missing=classRegistryCache.unregistered||[];
 const missingHtml=missing.length?'<div class="notice warning"><strong>Nomes encontrados fora do cadastro:</strong><ul>'+missing.map(x=>'<li>'+esc(x.name)+' · '+managementInt(x.records)+' registro(s)</li>').join('')+'</ul></div>':'<div class="notice success">Todos os nomes já existentes estão cobertos por turma oficial ou alias.</div>';
 return '<section class="card class-registry-card"><h2>Cadastro de turmas</h2><p>O nome oficial e seus aliases são usados para validar novas importações. Um nome não cadastrado bloqueia a confirmação e é listado para correção.</p><div class="class-new-grid"><label>Nova turma<input id="class-new-name" placeholder="Ex.: Qi Med 01"></label><label>Aliases autorizados<input id="class-new-aliases" placeholder="Ex.: 01 Qi Med 01; MED 01"></label><button type="button" class="primary" data-act="class-registry-new">Cadastrar turma</button></div>'+missingHtml+'<div class="table-wrap"><table><thead><tr><th>Nome oficial</th><th>Aliases</th><th>Status</th><th></th></tr></thead><tbody>'+rows+'</tbody></table></div></section>';
}
const managementDashboardViewV36Base=managementDashboardView;
managementDashboardView=function(){return managementDashboardViewV36Base()+classRegistryPanel();};

acts['class-registry-new']=async()=>{
 const name=document.querySelector('#class-new-name')?.value||'',aliases=document.querySelector('#class-new-aliases')?.value||'';
 if(!name.trim())throw new Error('Informe o nome oficial da turma.');
 await api('/api/model-data/classes',{name,aliases,active:true});
 classRegistryCache=null;managementDashboardCache=null;await loadClassRegistry(true);toast('Turma cadastrada.');
};
acts['class-registry-save']=async el=>{
 const id=el?.dataset?.classId||'';
 const name=document.querySelector('[data-class-name="'+CSS.escape(id)+'"]')?.value||'';
 const aliases=document.querySelector('[data-class-aliases="'+CSS.escape(id)+'"]')?.value||'';
 const active=!!document.querySelector('[data-class-active="'+CSS.escape(id)+'"]')?.checked;
 await api('/api/model-data/classes',{id,name,aliases,active});
 classRegistryCache=null;managementDashboardCache=null;await loadClassRegistry(true);toast('Turma atualizada.');
};

function classImportErrorBox(message){
 return '<div class="notice danger"><strong>Turma não cadastrada.</strong><p>'+esc(message)+'</p><p>Abra Visão geral → Cadastro de turmas para cadastrar o nome oficial ou um alias antes de importar.</p></div>';
}
window.addEventListener('load',()=>{
 if(typeof acts!=='undefined'&&acts['result-import-preview']){
  const original=acts['result-import-preview'];
  acts['result-import-preview']=async()=>{try{return await original();}catch(error){const box=document.querySelector('#result-import-preview');if(box)box.innerHTML=classImportErrorBox(error?.message||'Nome de turma inválido.');throw error;}};
 }
 if(typeof acts!=='undefined'&&acts['tri-import-preview']){
  const original=acts['tri-import-preview'];
  acts['tri-import-preview']=async()=>{try{return await original();}catch(error){const box=document.querySelector('#tri-import-preview');if(box)box.innerHTML=classImportErrorBox(error?.message||'Nome de turma inválido.');throw error;}};
 }
});
'''

CSS=r'''
/* === MANAGEMENT REFINEMENT V3.6 === */
.management-score-chart{height:300px;display:grid;grid-template-columns:46px minmax(0,1fr);gap:.7rem;border-bottom:1px solid var(--line)}.management-scale{display:flex;flex-direction:column;justify-content:space-between;align-items:flex-end;padding:1.8rem 0 .9rem;color:var(--muted);font-size:.68rem}.management-score-columns{display:flex;align-items:flex-end;gap:1rem;overflow-x:auto;padding:1rem .4rem .4rem}.management-score-col{height:100%;min-width:125px;display:grid;grid-template-rows:auto 1fr auto auto auto;gap:.2rem;justify-items:center;text-align:center}.management-score-value{font-weight:800;color:#9f4351}.management-score-track{height:100%;width:32px;background:#f3e0e4;border-radius:8px 8px 3px 3px;display:flex;align-items:flex-end;overflow:hidden}.management-score-track span{width:100%;background:linear-gradient(180deg,#db8d99,#b65362);border-radius:7px 7px 2px 2px}.management-score-col strong{max-width:125px;line-height:1.1}.management-score-col small,.management-score-col em{font-size:.68rem;color:var(--muted);font-style:normal}.management-bar.tri-scale{height:12px}.class-registry-card{display:grid;gap:.9rem}.class-new-grid{display:grid;grid-template-columns:1fr 1.4fr auto;gap:.7rem;align-items:end}.class-registry-card input{width:100%}
@media(max-width:800px){.class-new-grid{grid-template-columns:1fr}.management-score-chart{grid-template-columns:38px minmax(0,1fr)}}
'''

def main():
    model=ROOT/"model_data.py"
    text=model.read_text(encoding="utf-8")
    if BACKEND_MARK not in text:
        text=text.rstrip()+"\n\n"+BACKEND.strip()+"\n"
    if TRI_MODEL_MARK not in text:
        text=text.rstrip()+"\n\n"+TRI_MODEL.strip()+"\n"
    model.write_text(text,encoding="utf-8")

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
    text=re.sub(r'/static/student_summary\.js\?v=[^"\']+','/static/student_summary.js?v=3.6.0',text)
    html.write_text(text,encoding="utf-8")

    print("MEUCRONOGRAMA_MANAGEMENT_REFINEMENT_READY: cached fast dashboard, TRI 0-1000, percent tables, class registry/validation and no visible bonus field installed.",flush=True)

if __name__=="__main__":
    main()
