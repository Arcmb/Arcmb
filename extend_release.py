"""Apply the versioned, reviewable import/access extension after legacy extraction."""
from pathlib import Path
ROOT=Path(__file__).resolve().parent

def replace(text,old,new,count=1):
    if text.count(old)!=count:raise RuntimeError('Unexpected source; extension was not applied: '+old[:90])
    return text.replace(old,new)

def extend():
    path=ROOT/'webapp.py';s=path.read_text()
    s=replace(s,'import planner as P','import planner as P\nimport performance as PERF')
    s=replace(s,"                found=self.execute(c,'SELECT id FROM hmay_users WHERE username=?',(owner,)).fetchone()", "                PERF.schema(self,c)\n                found=self.execute(c,'SELECT id FROM hmay_users WHERE username=?',(owner,)).fetchone()")
    s=replace(s,"    def require_target(self,user,target):\n        if user['role']!='master' and target!=user['id']:raise HTTPError(403,'Você só pode acessar a própria conta.')", """    def require_target(self,user,target,c=None):
        if user['role']=='master' or target==user['id']:return
        if user['role']=='coordenador' and c is not None:
            row=self.db.execute(c,'SELECT role,active FROM hmay_users WHERE id=?',(target,)).fetchone()
            if row and row['role'] in ('user','aluno') and row['active']:return
        raise HTTPError(403,'Você não tem acesso a esta conta.')""")
    s=s.replace('self.require_target(user,target)','self.require_target(user,target,c)')
    s=replace(s,"'login.js':'application/javascript; charset=utf-8'", "'login.js':'application/javascript; charset=utf-8','performance.js':'application/javascript; charset=utf-8'")
    s=replace(s,"            if path=='/api/state' and method=='GET':", "            if path.startswith('/api/performance'):\n                return PERF.handle(self,c,user,path,method,data,query,start,HTTPError)\n            if path=='/api/state' and method=='GET':")
    s=replace(s,"            if path=='/api/accounts':\n                if user['role']!='master':raise HTTPError(403,'Área exclusiva do Master.')", """            if path=='/api/accounts':
                if user['role']=='coordenador' and method=='GET':
                    return self.reply(start,200,dict(accounts=PERF.allowed_accounts(self,c,user)))
                if user['role']!='master':raise HTTPError(403,'Área exclusiva do Master.')""")
    s=replace(s,"                target_id=data.get('id');password=data.get('password','')", "                target_id=data.get('id');password=data.get('password','')\n                role=data.get('role')\n                if role is not None and role not in ('master','coordenador','especial','aluno','user'):raise ValueError('Perfil de acesso inválido.')")
    s=replace(s,"                    active=bool(data.get('active',True))", "                    active=bool(data.get('active',True))\n                    role=role or old['role']\n                    if old['username']==self.owner and role!='master':raise ValueError('arcmb permanece Master.')")
    s=replace(s,"                    self.db.execute(c,'UPDATE hmay_users SET name=?,active=? WHERE id=?',(name,int(active),target_id))", "                    self.db.execute(c,'UPDATE hmay_users SET name=?,active=?,role=? WHERE id=?',(name,int(active),role,target_id))")
    s=replace(s,"                    if password or not active:self.db.execute(c,'DELETE FROM hmay_sessions WHERE user_id=?',(target_id,))", "                    if password or not active or role!=old['role']:self.db.execute(c,'DELETE FROM hmay_sessions WHERE user_id=?',(target_id,))")
    s=s.replace(">=200:raise ValueError('Limite de 200 contas nesta versão.')",">=10000:raise ValueError('Limite de 10.000 contas nesta versão.')")
    s=replace(s,"target_id=self.db.create_user(c,login,name,valid_password(password));", "target_id=self.db.create_user(c,login,name,valid_password(password),role or 'user');")
    path.write_text(s)

    path=ROOT/'static/app.html';s=path.read_text()
    s=replace(s,'<script src="/static/app.js" defer></script>','<script src="/static/app.js" defer></script><script src="/static/performance.js" defer></script>')
    s=s.replace('v2.0','v2.1')
    path.write_text(s)
    path=ROOT/'static/app.js';s=path.read_text()
    s=replace(s,"const days=['Segunda'", "const roleLabel=r=>({master:'Master',coordenador:'Coordenador',especial:'Especial',aluno:'Aluno',user:'Aluno'}[r]||r);\nconst manages=()=>['master','coordenador'].includes(ME?.role);\nconst days=['Segunda'")
    s=s.replace('HORÁRIO DA MAY','MEU CRONOGRAMA')
    s=replace(s,"['data','Dados e backup']", "['performance','Desempenho'],['data','Dados e backup']")
    s=replace(s,"ME?.role==='master'?[['accounts','Painel Master']]", "manages()?[['accounts',ME.role==='master'?'Painel Master':'Meus alunos']]")
    s=replace(s,"(ME.role==='master'?'Master':'Conta individual')", "roleLabel(ME.role)")
    s=replace(s,"!(ME.role==='master'&&target!==ME.id)", "!(manages()&&target!==ME.id)")
    s=replace(s,"accounts:accountsView}", "accounts:accountsView,performance:performanceView}")
    s=replace(s,"function accountsView(){return head('Painel Master'", "function accountsView(){if(ME.role==='coordenador')return coordinatorView();return head('Painel Master'")
    s=replace(s,"tag(a.role==='master'?'Master':'Individual')", "tag(roleLabel(a.role))")
    s=replace(s,"${check('Conta ativa','active',!!a.active)}</div>", "${a.username==='arcmb'?'<p>Perfil: Master permanente.</p>':select('Perfil de acesso','role',a.role==='user'?'aluno':a.role||'aluno',[['aluno','Aluno — somente a própria conta'],['coordenador','Coordenador — consulta e edição dos alunos'],['especial','Especial — titular e Master'],['master','Master — acesso completo']])}${check('Conta ativa','active',!!a.active)}</div>")
    s=replace(s,"async function refreshAccounts(){if(ME.role!=='master')return;", "async function refreshAccounts(){if(!manages())return;")
    s=replace(s,'O Master pode visualizar e editar sua rotina.', 'O Master pode visualizar e editar sua rotina. Coordenadores acessam somente contas de alunos; contas especiais são restritas ao titular e ao Master.')
    path.write_text(s)
    print('Meu Cronograma: dynamic discipline import and access roles prepared.')

if __name__=='__main__':extend()
