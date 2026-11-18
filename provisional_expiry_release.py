"""v3.7.17: validade de 7 dias para senhas provisórias e renovação pela coordenação.

Aplica-se somente a senhas provisórias definidas a partir desta versão. Contas já
existentes sem prazo registrado continuam sem expiração.
"""
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parent
MARK = '# === PROVISIONAL EXPIRY V3.7.17 ==='


def patch(text, old, new, label):
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f'{label}: esperado 1 trecho, encontrado {count}.')
    return text.replace(old, new, 1)


def patch_webapp():
    path = ROOT / 'webapp.py'
    text = path.read_text(encoding='utf-8')
    if MARK in text:
        return
    text = patch(text, 'import model_data as MODEL_DATA\n',
                 'import model_data as MODEL_DATA\nimport provisional_access as PROVISIONAL  ' + MARK + '\n', 'import')
    text = patch(text, '                EXAMS.schema(self,c)\n',
                 '                EXAMS.schema(self,c)\n                PROVISIONAL.schema(self,c)\n', 'schema')
    text = patch(text, "'use_guide.js':'application/javascript; charset=utf-8',",
                 "'use_guide.js':'application/javascript; charset=utf-8','provisional_renewal.js':'application/javascript; charset=utf-8',",
                 'static allowlist')
    text = patch(text,
                 "                    if not user or not correct or not user['active']:\n",
                 "                    if user and correct and user['active'] and PROVISIONAL.expired(self,c,user):\n"
                 "                        error=PROVISIONAL.EXPIRED_MESSAGE\n"
                 "                    elif not user or not correct or not user['active']:\n",
                 'login expiry')
    text = patch(text,
                 "            if user['must_change'] and path not in ('/api/me','/api/password','/api/logout'):",
                 "            if path!='/api/logout' and PROVISIONAL.expired(self,c,user):raise HTTPError(403,PROVISIONAL.EXPIRED_MESSAGE)\n"
                 "            if user['must_change'] and path not in ('/api/me','/api/password','/api/logout'):",
                 'session expiry')
    text = patch(text,
                 "self.db.execute(c,'UPDATE hmay_users SET password=?,must_change=0 WHERE id=?',(password_hash(new),user['id']))",
                 "self.db.execute(c,'UPDATE hmay_users SET password=?,must_change=0 WHERE id=?',(password_hash(new),user['id']));PROVISIONAL.clear(self,c,user['id'])",
                 'password change')
    text = patch(text, "self.event(c,user,target_id,'account_created_by_coordinator')",
                 "self.event(c,user,target_id,'account_created_by_coordinator');PROVISIONAL.start(self,c,target_id,user['id'])",
                 'coordinator create')
    text = patch(text, "        app.event(c, user, target_id, 'account_created_bulk_results')\n",
                 "        app.event(c, user, target_id, 'account_created_bulk_results')\n"
                 "        PROVISIONAL.start(app, c, target_id, user.get('id'))\n",
                 'bulk create')
    text = patch(text,
                 "target_id=self.db.create_user(c,login,name,valid_password(password),role or 'user');self.event(c,user,target_id,'account_created')",
                 "target_id=self.db.create_user(c,login,name,valid_password(password),role or 'user');self.event(c,user,target_id,'account_created');PROVISIONAL.start_if_student(self,c,target_id,user['id'])",
                 'master create')
    text = patch(text,
                 "self.db.execute(c,'UPDATE hmay_users SET password=?,must_change=1 WHERE id=?',(password_hash(valid_password(password)),target_id))",
                 "self.db.execute(c,'UPDATE hmay_users SET password=?,must_change=1 WHERE id=?',(password_hash(valid_password(password)),target_id));PROVISIONAL.start_if_student(self,c,target_id,user['id'])",
                 'master reset')
    text = patch(text, "            if path.startswith('/api/adaptive'):\n",
                 "            if path.startswith('/api/provisional'):\n"
                 "                return PROVISIONAL.handle(self,c,user,path,method,data,query,start,HTTPError)\n"
                 "            if path.startswith('/api/adaptive'):\n",
                 'route')
    path.write_text(text, encoding='utf-8')


def patch_assets():
    shutil.copyfile(ROOT / 'release_assets' / 'provisional_renewal.js', ROOT / 'static' / 'provisional_renewal.js')
    html_path = ROOT / 'static' / 'app.html'
    html = html_path.read_text(encoding='utf-8')
    if '/static/provisional_renewal.js' not in html:
        html = patch(html, '<script src="/static/academic_year.js?v=1.1.0" defer></script>',
                     '<script src="/static/academic_year.js?v=1.1.0" defer></script>'
                     '<script src="/static/provisional_renewal.js?v=3.7.17" defer></script>',
                     'app.html script')
        html_path.write_text(html, encoding='utf-8')
    bulk_path = ROOT / 'static' / 'bulk_accounts_panel.js'
    bulk = bulk_path.read_text(encoding='utf-8')
    if 'Válida até' not in bulk:
        bulk = patch(bulk,
                     "[['Nome','Login','Senha provisória','Troca obrigatória no primeiro acesso'],...rows.map(x=>[x.name,x.username,bulkAccountsPassword,'SIM'])]",
                     "[['Nome','Login','Senha provisória','Troca obrigatória no primeiro acesso','Válida até'],...rows.map(x=>[x.name,x.username,bulkAccountsPassword,'SIM',new Date(Date.now()+7*864e5).toLocaleDateString('pt-BR')])]",
                     'bulk csv')
        bulk = patch(bulk, 'os nomes ausentes são cadastrados como <strong>Aluno</strong>.',
                     'os nomes ausentes são cadastrados como <strong>Aluno</strong>. A senha provisória vale <strong>7 dias</strong>.',
                     'bulk text')
        bulk_path.write_text(bulk, encoding='utf-8')


def main():
    patch_webapp()
    patch_assets()
    print('MEUCRONOGRAMA_V3717_PROVISIONAL_EXPIRY_READY: 7-day provisional passwords and coordinator renewal applied.', flush=True)


if __name__ == '__main__':
    main()
