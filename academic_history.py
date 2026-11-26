"""Vínculos de leitura para o desempenho do ciclo anterior."""
def schema(app,c):
    app.db.execute(c,'''CREATE TABLE IF NOT EXISTS hmay_history_links (
        target_id TEXT NOT NULL REFERENCES hmay_users(id), year INTEGER NOT NULL,
        source_id TEXT NOT NULL REFERENCES hmay_users(id), result_id TEXT NOT NULL,
        PRIMARY KEY(target_id,year,source_id,result_id))''')

def candidates(app,c,name,year):
    rows=app.db.execute(c,'''SELECT u.id,u.name,u.username,u.role,
        (SELECT COUNT(*) FROM hmay_performance p WHERE p.user_id=u.id
         AND p.applied_on LIKE ?) AS results
        FROM hmay_users u LEFT JOIN hmay_academic_year y ON y.user_id=u.id
        WHERE u.name=? AND u.role IN ('user','aluno','deleted') AND
        (COALESCE(y.active_year,CAST(substr(u.created_at,1,4) AS INTEGER))=?
        OR EXISTS(SELECT 1 FROM hmay_academic_cycles cy WHERE cy.user_id=u.id AND cy.academic_year=?)
        OR EXISTS(SELECT 1 FROM hmay_performance p WHERE p.user_id=u.id AND p.applied_on LIKE ?))
        ORDER BY u.username''',(f'{year}-%',name,year,year,f'{year}-%')).fetchall()
    return [{'id':r['id'],'name':r['name'],'reference':r['id'][:8] if r['role']=='deleted' else r['username'],
             'results':r['results']} for r in rows]

def search(app,c,term,year,target):
    term=term.strip()
    if not term:return []
    pattern='%'+term.lower().replace('!','!!').replace('%','!%').replace('_','!_')+'%'
    rows=app.db.execute(c,'''SELECT p.id,p.activity,p.applied_on,u.name,u.id AS source_id,u.username,u.role
        FROM hmay_performance p JOIN hmay_users u ON u.id=p.user_id
        WHERE p.applied_on LIKE ? AND u.id<>? AND u.role IN ('user','aluno','deleted') AND
        (lower(u.name) LIKE ? ESCAPE '!' OR lower(p.activity) LIKE ? ESCAPE '!' OR lower(u.username) LIKE ? ESCAPE '!')
        ORDER BY p.applied_on DESC,u.name,p.activity,p.id LIMIT 51''',(f'{year}-%',target,pattern,pattern,pattern)).fetchall()
    return [{'id':r['id'],'name':r['name'],'date':r['applied_on'],'activity':r['activity'],
             'reference':r['source_id'][:8] if r['role']=='deleted' else r['username']} for r in rows]

def link(app,c,user,target,year,source,result=''):
    if source==target:raise ValueError('Este resultado já pertence ao aluno.')
    schema(app,c)
    changed=app.db.execute(c,'''INSERT INTO hmay_history_links(target_id,year,source_id,result_id)
        VALUES (?,?,?,?) ON CONFLICT DO NOTHING''',(target,year,source,result)).rowcount
    if changed:app.event(c,user,target,'history_link_'+str(year)+'_'+source+'_'+result)

def link_on_creation(app,c,user,target,name,data,active):
    source=data.get('historySource')
    if not source:return
    year=active-1
    if data.get('historyYear')!=year or source not in {r['id'] for r in candidates(app,c,name,year)}:
        raise ValueError('O cadastro ou o ano letivo mudou. Confira o vínculo novamente.')
    link(app,c,user,target,year,source)

def linked_results(app,c,target,year):
    rows=app.db.execute(c,'''SELECT p.activity,p.applied_on,u.name FROM hmay_performance p
        JOIN hmay_users u ON u.id=p.user_id WHERE p.applied_on LIKE ? AND EXISTS
        (SELECT 1 FROM hmay_history_links h WHERE h.target_id=? AND h.year=?
         AND h.source_id=p.user_id AND (h.result_id='' OR h.result_id=p.id))
        ORDER BY p.applied_on,p.activity,p.id''',(str(year)+'-%',target,year)).fetchall()
    return [dict(row) for row in rows]
