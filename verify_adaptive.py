"""Disposable-account deployment check for objective mapping and preview/apply."""
import hashlib
import secrets
import os
from verify_release import Client,require
from webapp import App
import planner as P


def main():
    app=App();app.db.initialize(app.owner,app.env.get('MASTER_PASSWORD',''),app.env.get('MAYRA_INITIAL_PASSWORD',''))
    host=os.getenv('RENDER_EXTERNAL_HOSTNAME') or sorted(app.hosts)[0]
    login='map_check_'+secrets.token_hex(8);password=secrets.token_urlsafe(32);test_id=None
    try:
        with app.db.connection(write=True)as c:test_id=app.db.create_user(c,login,'Verificação técnica temporária',password,'aluno',False)
        client=Client(app,host);client.login(login,password)
        def state():return client.request('/api/state')['data']
        def action(op,data):
            r=client.request('/api/action',{'user':test_id,'version':state()['version'],'op':op,'data':data});require(r['status']==200,'Mapping action check failed.');return r['data']
        initial=state();result=action('objective',{'answers':{'focus':'25','energy':'manha','stability':'stable'}})
        require(result['profile']['settings']==initial['profile']['settings'],'Questionnaire must not silently change settings.')
        result=client.request('/api/adaptive');require(result['status']==200 and len(result['data']['questions'])==20,'Objective questions unavailable.')
        action('objective_settings',{'keys':['sessionMax','preferred']})
        require(state()['profile']['settings']['preferred']=='manha','Approved settings not saved.')
        require(client.request('/api/adaptive/consent',{'user':test_id,'version':state()['version'],'enabled':True})['status']==200,'Own consent failed.')
        require(client.request('/api/adaptive/consent',{'user':test_id,'version':state()['version'],'enabled':False})['status']==200,'Revocation failed.')
        baseline=state();preview=client.request('/api/adaptive/preview',{'user':test_id,'version':baseline['version'],'week':P.add(P.today(),7),'mode':'fill'})
        require(preview['status']==200,'Preview unavailable.');require(state()['version']==baseline['version'],'Preview altered planning state.')
        applied=client.request('/api/adaptive/confirm',{'user':test_id,'version':baseline['version'],'token':preview['data']['token']})
        require(applied['status']==200,'Proposal confirmation failed.')
        require(client.request('/api/adaptive')['data']['history'],'Adjustment history missing.')
        with app.db.connection()as c:owner=app.db.execute(c,'SELECT id FROM hmay_users WHERE username=?',(app.owner,)).fetchone()['id']
        require(client.request('/api/adaptive?user='+owner)['status']==403,'Objective endpoint isolation failed.')
        second=Client(App(),host);second.login(login,password)
        require(second.request('/api/adaptive')['data']['answers']['focus']=='25','Objective answers not retained in another session.')
    finally:
        if test_id:
            with app.db.connection(write=True)as c:
                for table,column in [('hmay_proposals','target_id'),('hmay_adjustments','target_id'),('hmay_adaptive_consent','user_id'),('hmay_adaptive_observations','user_id'),('hmay_sessions','user_id'),('hmay_state','user_id')]:
                    app.db.execute(c,f'DELETE FROM {table} WHERE {column}=?',(test_id,))
                app.db.execute(c,'DELETE FROM hmay_events WHERE actor_id=? OR target_id=?',(test_id,test_id))
                app.db.execute(c,'DELETE FROM hmay_users WHERE id=?',(test_id,))
                app.db.execute(c,'DELETE FROM hmay_attempts WHERE key=?',('user:'+hashlib.sha256(login.encode()).hexdigest(),))
    print('MEUCRONOGRAMA_MAPPING_CHECK_OK: 20 questions, explicit settings, consent/revocation, preview/confirm, history, isolation and persistence passed.',flush=True)

if __name__=='__main__':
    try:main()
    except Exception as exc:
        print('MEUCRONOGRAMA_MAPPING_CHECK_FAILED: '+type(exc).__name__+'. Credentials omitted.',flush=True)
        raise SystemExit(1)
