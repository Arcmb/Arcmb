"""Add academic-year cycles and year-over-year performance comparison."""
from pathlib import Path
import re

ROOT=Path(__file__).resolve().parent
STATIC=ROOT/'static'
MARK='# === MEU CRONOGRAMA: CICLOS DE ANO LETIVO V1 ==='
JS_MARK='// === MEU CRONOGRAMA: CICLOS DE ANO LETIVO V1 ==='
CSS_MARK='/* === CICLOS DE ANO LETIVO V2 === */'

PY_HELPERS=r'''
# === MEU CRONOGRAMA: CICLOS DE ANO LETIVO V1 ===
def academic_year_schema(app,c):
    app.db.execute(c,'CREATE TABLE IF NOT EXISTS hmay_academic_year (user_id TEXT PRIMARY KEY REFERENCES hmay_users(id), active_year INTEGER NOT NULL, updated_at TEXT NOT NULL)')
    app.db.execute(c,'CREATE TABLE IF NOT EXISTS hmay_academic_cycles (id TEXT PRIMARY KEY, user_id TEXT NOT NULL REFERENCES hmay_users(id), academic_year INTEGER NOT NULL, profile TEXT NOT NULL, opened_at TEXT NOT NULL, closed_at TEXT NOT NULL, UNIQUE(user_id,academic_year))')
    app.db.execute(c,'CREATE INDEX IF NOT EXISTS hmay_academic_cycles_user_year ON hmay_academic_cycles(user_id,academic_year)')

def _academic_year_target(app,c,user,target_id,HTTPError):
    if user.get('role') not in ('master','coordenador'):
        raise HTTPError(403,'A gestão de ano letivo é exclusiva do Master e da coordenação.')
    app.require_target(user,target_id,c)
    row=app.db.execute(c,'SELECT id,username,name,role,active FROM hmay_users WHERE id=?',(target_id,)).fetchone()
    if not row:raise HTTPError(404,'Aluno não encontrado.')
    target=dict(row)
    if target.get('role') not in ('user','aluno'):
        raise HTTPError(400,'Selecione uma conta de aluno.')
    return target

def _academic_year_active(app,c,target_id):
    academic_year_schema(app,c)
    row=app.db.execute(c,'SELECT active_year FROM hmay_academic_year WHERE user_id=?',(target_id,)).fetchone()
    return int(row['active_year']) if row else int(P.now().year)

def academic_year_status(app,c,user,target_id,HTTPError):
    target=_academic_year_target(app,c,user,target_id,HTTPError)
    active=_academic_year_active(app,c,target_id)
    rows=app.db.execute(c,'SELECT academic_year,opened_at,closed_at FROM hmay_academic_cycles WHERE user_id=? ORDER BY academic_year DESC',(target_id,)).fetchall()
    return {'student':{'id':target['id'],'name':target['name'],'username':target['username'],'active':bool(target['active'])},'activeYear':active,'archived':[dict(r) for r in rows],'nextYear':active+1}

def academic_year_open(app,c,user,target_id,new_year,HTTPError):
    import json
    target=_academic_year_target(app,c,user,target_id,HTTPError)
    current=_academic_year_active(app,c,target_id)
    try:new_year=int(new_year)
    except (TypeError,ValueError):raise ValueError('Ano letivo inválido.')
    if new_year!=current+1:raise ValueError('O próximo ano letivo deve ser '+str(current+1)+'.')
    if not 2020<=new_year<=2100:raise ValueError('Ano letivo fora do intervalo permitido.')
    state=app.db.execute(c,'SELECT profile,version FROM hmay_state WHERE user_id=?',(target_id,)).fetchone()
    if not state:raise HTTPError(404,'Perfil acadêmico não encontrado.')
    stamp=P.now().isoformat()
    existing=app.db.execute(c,'SELECT id FROM hmay_academic_cycles WHERE user_id=? AND academic_year=?',(target_id,current)).fetchone()
    if existing:raise HTTPError(409,'O ano '+str(current)+' já foi arquivado. Atualize a página antes de tentar novamente.')
    app.db.execute(c,'INSERT INTO hmay_academic_cycles(id,user_id,academic_year,profile,opened_at,closed_at) VALUES (?,?,?,?,?,?)',(P.uid(),target_id,current,state['profile'],str(current)+'-01-01T00:00:00',stamp))
    fresh=P.default_profile(target['name'],target_id)
    app.db.execute(c,'UPDATE hmay_state SET profile=?,version=version+1,updated_at=? WHERE user_id=?',(encode(fresh),stamp,target_id))
    app.db.execute(c,'INSERT INTO hmay_academic_year(user_id,active_year,updated_at) VALUES (?,?,?) ON CONFLICT(user_id) DO UPDATE SET active_year=excluded.active_year,updated_at=excluded.updated_at',(target_id,new_year,stamp))
    app.event(c,user,target_id,'academic_year_open_'+str(new_year))
    return academic_year_status(app,c,user,target_id,HTTPError)

def academic_year_comparison(app,c,user,target_id,HTTPError):
    target=_academic_year_target(app,c,user,target_id,HTTPError)
    active=_academic_year_active(app,c,target_id);previous=active-1
    import model_data as AY_MODEL
    data=AY_MODEL.student_summary(app,c,user,target)
    buckets={previous:{'year':previous,'simulations':0,'correct':0,'marked':0,'valid':0,'areas':{}},active:{'year':active,'simulations':0,'correct':0,'marked':0,'valid':0,'areas':{}}}
    for sim in data.get('simulations',[]):
        try:year=int(str(sim.get('date',''))[:4])
        except (TypeError,ValueError):continue
        if year not in buckets:continue
        b=buckets[year];b['simulations']+=1;b['correct']+=int(sim.get('correct') or 0);b['marked']+=int(sim.get('marked') or 0);b['valid']+=int(sim.get('valid') or 0)
        for area in sim.get('areas') or []:
            name=str(area.get('name') or 'Não informado')
            a=b['areas'].setdefault(name,{'name':name,'correct':0,'marked':0,'total':0})
            a['correct']+=int(area.get('correct') or 0);a['marked']+=int(area.get('marked') or 0);a['total']+=int(area.get('total') or 0)
    def finish(b):
        b['accuracy']=None if not b['marked'] else round(100*b['correct']/b['marked'],2)
        b['averageCorrect']=None if not b['simulations'] else round(b['correct']/b['simulations'],2)
        rows=[]
        for a in b.pop('areas').values():
            a['accuracy']=None if not a['marked'] else round(100*a['correct']/a['marked'],2);rows.append(a)
        b['areas']=sorted(rows,key=lambda x:x['name'])
        return b
    prev=finish(buckets[previous]);cur=finish(buckets[active])
    delta=None if prev['accuracy'] is None or cur['accuracy'] is None else round(cur['accuracy']-prev['accuracy'],2)
    names=sorted({x['name'] for x in prev['areas']}|{x['name'] for x in cur['areas']})
    pa={x['name']:x for x in prev['areas']};ca={x['name']:x for x in cur['areas']}
    area_compare=[]
    for name in names:
        p=pa.get(name,{});n=ca.get(name,{})
        pv=p.get('accuracy');nv=n.get('accuracy')
        area_compare.append({'name':name,'previous':pv,'current':nv,'delta':None if pv is None or nv is None else round(nv-pv,2)})
    return {'student':{'id':target['id'],'name':target['name']},'previous':prev,'current':cur,'delta':delta,'areas':area_compare,'notice':'A comparação usa os resultados registrados em cada ano. Conteúdos e revisões do ano anterior não entram no cronograma atual.'}
'''

PY_ROUTE=r'''            if path=='/api/academic-year':
                if method!='GET':raise HTTPError(405,'Use consulta GET.')
                target_id=query.get('user',[user['id']])[0]
                return self.reply(start,200,academic_year_status(self,c,user,target_id,HTTPError))
            if path=='/api/academic-year/open':
                if method!='POST':raise HTTPError(405,'Use POST para abrir o novo ano.')
                target_id=str(data.get('user') or '')
                result=academic_year_open(self,c,user,target_id,data.get('year'),HTTPError)
                return self.reply(start,200,result)
            if path=='/api/academic-year/comparison':
                if method!='GET':raise HTTPError(405,'Use consulta GET.')
                target_id=query.get('user',[user['id']])[0]
                return self.reply(start,200,academic_year_comparison(self,c,user,target_id,HTTPError))
'''

JS=r'''"use strict";
// === MEU CRONOGRAMA: CICLOS DE ANO LETIVO V2 ===
(function(){
 let statusCache=new Map(),comparisonCache=new Map(),loadingStatus=new Set(),loadingComparison=new Set();
 const canManage=()=>typeof manages==='function'&&manages();
 const id=()=>String(typeof target!=='undefined'&&target?target:'');
 const own=()=>String(typeof ME!=='undefined'&&ME?.id?ME.id:'');
 const pct=v=>v===null||v===undefined?'—':Number(v).toLocaleString('pt-BR',{minimumFractionDigits:1,maximumFractionDigits:1})+'%';
 const studentSelected=()=>canManage()&&id()&&id()!==own();

 async function loadStatus(force=false){
  const key=id();if(!studentSelected())return;
  if((!force&&statusCache.has(key))||loadingStatus.has(key))return;
  loadingStatus.add(key);
  try{statusCache.set(key,await api('/api/academic-year?user='+encodeURIComponent(key)));}
  catch(e){statusCache.set(key,{error:e.message||'Não foi possível carregar o ano letivo.'});}
  finally{loadingStatus.delete(key);if(view==='accounts'||view==='coordinator')render();}
 }
 async function loadComparison(force=false){
  const key=id();if(!studentSelected())return;
  if((!force&&comparisonCache.has(key))||loadingComparison.has(key))return;
  loadingComparison.add(key);
  try{comparisonCache.set(key,await api('/api/academic-year/comparison?user='+encodeURIComponent(key)));}
  catch(e){comparisonCache.set(key,{error:e.message||'Não foi possível comparar os anos.'});}
  finally{loadingComparison.delete(key);if(view==='performance')render();}
 }
 function yearPanel(){
  if(!canManage())return '';
  if(!studentSelected())return '<section class="card academic-year-card"><p class="eyebrow">ANO LETIVO</p><h2>Escolha um aluno</h2><p>Use a caixa <strong>Pesquisar aluno</strong> no topo. Depois de selecionar o nome, o controle do ano letivo aparecerá aqui.</p></section>';
  const key=id();
  if(!statusCache.has(key)&&!loadingStatus.has(key))queueMicrotask(()=>loadStatus());
  const d=statusCache.get(key);
  if(!d)return '<section class="card academic-year-card"><h2>Ano letivo</h2><p>Carregando situação do perfil…</p></section>';
  if(d.error)return '<section class="card academic-year-card"><h2>Ano letivo</h2><div class="notice warning">'+esc(d.error)+'</div>'+button('Tentar novamente','academic-year-refresh','secondary')+'</section>';
  const archived=(d.archived||[]).map(x=>'<span class="academic-year-pill">'+x.academic_year+' arquivado</span>').join('');
  const options='<option value="'+d.activeYear+'">'+d.activeYear+' — ativo</option><option value="'+d.nextYear+'">'+d.nextYear+' — iniciar novo ciclo</option>';
  return '<section class="card academic-year-card"><div class="page-head"><div><p class="eyebrow">ANO LETIVO</p><h2>Ano letivo de '+esc(d.student.name)+'</h2><p>Escolha qual ciclo ficará ativo para este aluno.</p></div>'+button('Atualizar','academic-year-refresh','secondary')+'</div>'+
   '<div class="academic-year-control"><label>Ano letivo ativo<select id="academic-year-select">'+options+'</select></label>'+button('Ativar ano selecionado','academic-year-activate','primary')+'</div>'+
   '<div class="stats"><div class="stat"><strong>'+d.activeYear+'</strong><span>ano ativo agora</span></div><div class="stat"><strong>'+(d.archived||[]).length+'</strong><span>ano(s) arquivado(s)</span></div></div>'+
   '<div class="notice"><strong>Se você ativar '+d.nextYear+':</strong><p>O planejamento, os conteúdos, as revisões e os registros de execução de '+d.activeYear+' serão arquivados. '+d.nextYear+' começa limpo. Os resultados dos simulados de '+d.activeYear+' continuam guardados para comparar a evolução.</p></div>'+
   '<div class="academic-year-archive">'+(archived||'<span class="micro">Nenhum ano arquivado ainda.</span>')+'</div></section>';
 }
 function comparePanel(){
  if(!studentSelected())return '';
  const key=id();
  if(!comparisonCache.has(key)&&!loadingComparison.has(key))queueMicrotask(()=>loadComparison());
  const d=comparisonCache.get(key);if(!d)return '<section class="card academic-year-compare"><h2>Evolução anual</h2><p>Carregando comparação…</p></section>';
  if(d.error)return '<section class="card academic-year-compare"><h2>Evolução anual</h2><div class="notice warning">'+esc(d.error)+'</div></section>';
  const p=d.previous||{},c=d.current||{},delta=d.delta;
  const deltaText=delta===null?'—':(delta>0?'+':'')+Number(delta).toLocaleString('pt-BR',{minimumFractionDigits:1,maximumFractionDigits:1})+' p.p.';
  const rows=(d.areas||[]).map(x=>'<tr><td>'+esc(x.name)+'</td><td>'+pct(x.previous)+'</td><td>'+pct(x.current)+'</td><td>'+(x.delta===null?'—':(x.delta>0?'+':'')+Number(x.delta).toLocaleString('pt-BR',{minimumFractionDigits:1,maximumFractionDigits:1})+' p.p.')+'</td></tr>').join('');
  return '<section class="card academic-year-compare"><div class="page-head"><div><p class="eyebrow">COMPARAÇÃO</p><h2>Evolução '+p.year+' → '+c.year+'</h2><p>'+esc(d.notice||'')+'</p></div>'+button('Atualizar comparação','academic-year-compare-refresh','secondary')+'</div><div class="academic-year-compare-grid"><div><span>'+p.year+'</span><strong>'+pct(p.accuracy)+'</strong><small>'+(p.simulations||0)+' simulado(s) · média '+(p.averageCorrect??'—')+' acertos</small></div><div class="academic-year-delta"><span>Evolução</span><strong>'+deltaText+'</strong><small>diferença no aproveitamento acumulado</small></div><div><span>'+c.year+'</span><strong>'+pct(c.accuracy)+'</strong><small>'+(c.simulations||0)+' simulado(s) · média '+(c.averageCorrect??'—')+' acertos</small></div></div>'+(rows?'<h3>Comparação por área</h3><div class="table-wrap"><table><thead><tr><th>Área</th><th>'+p.year+'</th><th>'+c.year+'</th><th>Variação</th></tr></thead><tbody>'+rows+'</tbody></table></div>':'<div class="notice">Ainda não há resultados suficientes nos dois anos para comparar por área.</div>')+'</section>';
 }
 if(typeof accountsView==='function'){const base=accountsView;accountsView=function(){return yearPanel()+base();};}
 if(typeof coordinatorView==='function'){const base=coordinatorView;coordinatorView=function(){return yearPanel()+base();};}
 if(typeof performanceView==='function'){const base=performanceView;performanceView=function(){return base()+comparePanel();};}
 acts['academic-year-refresh']=async()=>{statusCache.delete(id());await loadStatus(true);};
 acts['academic-year-compare-refresh']=async()=>{comparisonCache.delete(id());await loadComparison(true);};
 acts['academic-year-activate']=async()=>{
  const d=statusCache.get(id());if(!d)throw new Error('Atualize a situação do ano letivo.');
  const selected=Number(document.getElementById('academic-year-select')?.value||d.activeYear);
  if(selected===Number(d.activeYear)){toast(String(d.activeYear)+' já é o ano letivo ativo.');return;}
  if(selected!==Number(d.nextYear))throw new Error('Só é possível manter o ano atual ou abrir o próximo ciclo.');
  const msg='Ativar '+selected+' para '+d.student.name+'?\n\nO planejamento, os conteúdos e as revisões de '+d.activeYear+' serão arquivados. '+selected+' começará limpo. Os resultados de '+d.activeYear+' continuarão disponíveis para comparação.';
  if(!confirm(msg))return;
  await api('/api/academic-year/open',{user:id(),year:selected});
  statusCache.delete(id());comparisonCache.delete(id());toast('Ano '+selected+' ativado. O ciclo anterior foi arquivado.');location.reload();
 };
})();
'''
CSS=r'''
/* === CICLOS DE ANO LETIVO V1 === */
.academic-year-card,.academic-year-compare{margin-bottom:1rem}.academic-year-control{display:flex;align-items:end;gap:.75rem;flex-wrap:wrap;margin:1rem 0}.academic-year-control label{min-width:240px;display:grid;gap:.35rem}.academic-year-control select{width:100%}.academic-year-archive{display:flex;gap:.45rem;flex-wrap:wrap;margin-top:.7rem}.academic-year-pill{padding:.35rem .6rem;border-radius:999px;background:#fae9ec;color:#78323e;font-size:.8rem;font-weight:700}.academic-year-compare-grid{display:grid;grid-template-columns:1fr .85fr 1fr;gap:.75rem;margin:1rem 0}.academic-year-compare-grid>div{border:1px solid var(--line);border-radius:15px;padding:1rem;background:#fff;display:grid;gap:.25rem;text-align:center}.academic-year-compare-grid span{font-size:.78rem;color:var(--muted);font-weight:700}.academic-year-compare-grid strong{font-size:1.55rem}.academic-year-compare-grid small{color:var(--muted)}.academic-year-delta{background:#fdf0f2!important}
@media(max-width:700px){.academic-year-compare-grid{grid-template-columns:1fr}.academic-year-control{display:grid}.academic-year-control label{min-width:0}.academic-year-control .primary{width:100%}}
'''

def main():
    web=ROOT/'webapp.py';text=web.read_text(encoding='utf-8')
    if MARK not in text:
        if '\nclass App:\n' not in text:raise RuntimeError('Classe App não encontrada.')
        text=text.replace('\nclass App:\n','\n'+PY_HELPERS+'\n\nclass App:\n',1)
        anchor="            if path=='/api/coordinator/accounts':\n"
        if anchor not in text:raise RuntimeError('Rota de contas da coordenação não encontrada.')
        text=text.replace(anchor,PY_ROUTE+anchor,1)
    mapping="'academic_year.js':'application/javascript; charset=utf-8'"
    anchor="'use_guide.js':'application/javascript; charset=utf-8'"
    if mapping not in text:
        if anchor not in text:
            entries=list(re.finditer(r"'[^'\n]+\.js'\s*:\s*'application/javascript; charset=utf-8'",text))
            if not entries:raise RuntimeError('Lista de assets JS não encontrada.')
            pos=entries[-1].end();text=text[:pos]+','+mapping+text[pos:]
        else:text=text.replace(anchor,anchor+','+mapping,1)
    web.write_text(text,encoding='utf-8')
    (STATIC/'academic_year.js').write_text(JS,encoding='utf-8')
    css_path=STATIC/'style.css';css=css_path.read_text(encoding='utf-8')
    if CSS_MARK not in css:css=css.rstrip()+'\n\n'+CSS.strip()+'\n'
    css_path.write_text(css,encoding='utf-8')
    html_path=STATIC/'app.html';html=html_path.read_text(encoding='utf-8')
    if '/static/academic_year.js' not in html:html=html.replace('</body>','<script src="/static/academic_year.js?v=1.1.0" defer></script>\n</body>',1)\n    else:html=re.sub(r'/static/academic_year\\.js\\?v=[^"\\']+','/static/academic_year.js?v=1.1.0',html)\n    html=re.sub(r'/static/style\\.css\\?v=[^"\\']+','/static/style.css?v=5.5.0',html)
    html_path.write_text(html,encoding='utf-8')
    print('MEUCRONOGRAMA_ACADEMIC_YEAR_READY: explicit active-year control, annual reset and year-over-year comparison installed.',flush=True)

if __name__=='__main__':main()
