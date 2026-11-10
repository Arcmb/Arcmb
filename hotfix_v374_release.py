"""Hotfix v3.7.4: align student-report target query parsing with the rest of the app."""
from pathlib import Path
import re

ROOT=Path(__file__).resolve().parent
BACKEND_MARK="# === HOTFIX V3.7.4 ==="

BACKEND=r'''
# === HOTFIX V3.7.4 ===
def _reports_target(app,c,user,target_id):
    if user.get('role') in ('master','coordenador'):
        if isinstance(target_id,(list,tuple)):
            target_id=target_id[0] if target_id else ''
        target_id=F.text(target_id,160)
        if not target_id or target_id==user.get('id'):
            return None
        row=app.db.execute(
            c,
            'SELECT id,name,username,role,active FROM hmay_users WHERE id=?',
            (target_id,),
        ).fetchone()
        if not row:
            raise ValueError('Aluno não encontrado para consulta de relatórios.')
        account=dict(row)
        if user.get('role')=='master':
            if account.get('role') not in ('user','aluno') or not account.get('active'):
                raise ValueError('A conta selecionada não é um aluno ativo.')
            return account
        if account.get('role') in ('user','aluno') and account.get('active'):
            return account
        raise ValueError('Você não pode consultar os relatórios deste perfil.')

    if user.get('role') in ('user','aluno'):
        return user
    raise ValueError('Perfil sem acesso aos relatórios do aluno.')

_reports_handle_v374_base=handle

def handle(app,c,user,path,method,data,query,start,HTTPError):
    if path=='/api/model-data/student-reports':
        if method!='GET':
            raise HTTPError(405,'Use GET para consultar relatórios.')
        raw=query.get('userId',['']) if isinstance(query,dict) else ['']
        return app.reply(start,200,_reports_student_data(app,c,user,raw))
    return _reports_handle_v374_base(app,c,user,path,method,data,query,start,HTTPError)
'''

def main():
    model=ROOT/'model_data.py'
    text=model.read_text(encoding='utf-8')
    if BACKEND_MARK not in text:
        model.write_text(text.rstrip()+"\n\n"+BACKEND.strip()+"\n",encoding='utf-8')

    site=ROOT/'site_version_release.py'
    source=site.read_text(encoding='utf-8').replace('PUBLIC_VERSION="3.7.3"','PUBLIC_VERSION="3.7.4"')
    site.write_text(source,encoding='utf-8')

    vsite=ROOT/'verify_site_version.py'
    source=vsite.read_text(encoding='utf-8').replace('v3.7.3','v3.7.4')
    vsite.write_text(source,encoding='utf-8')

    print("MEUCRONOGRAMA_HOTFIX_374_READY: student report userId query now follows the app's list-based query parser.",flush=True)

if __name__=='__main__':
    main()
