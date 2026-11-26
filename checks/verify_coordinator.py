"""Startup check with disposable accounts only. No existing passwords/data are edited."""
import hashlib
import os
import secrets
import planner as P
from webapp import App
from verify_release import Client, require


def main():
    app = App()
    app.db.initialize(app.owner, app.env.get('MASTER_PASSWORD', ''), app.env.get('MAYRA_INITIAL_PASSWORD', ''))
    host = os.getenv('RENDER_EXTERNAL_HOSTNAME') or sorted(app.hosts)[0]
    prefix = 'cc_' + secrets.token_hex(8)
    password = secrets.token_urlsafe(24)
    ids, logins = [], []
    try:
        with app.db.connection(write=True) as c:
            for suffix, role in (('_c', 'coordenador'), ('_s', 'especial')):
                login = prefix + suffix
                ids.append(app.db.create_user(c, login, 'Verificação técnica temporária', password, role, False))
                logins.append(login)
        coord = Client(app, host)
        coord.login(logins[0], password)
        payload = dict(username=prefix + '_a', name='Verificação técnica temporária', password=password, role='aluno')
        require(coord.request('/api/coordinator/accounts', {**payload, 'role': 'master'})['status'] == 403, 'Role escalation must be denied.')
        require(coord.request('/api/coordinator/accounts', payload, csrf=False)['status'] == 403, 'CSRF must be required.')
        result = coord.request('/api/coordinator/accounts', payload)
        require(result['status'] == 200, 'Coordinator creation failed.')
        student_id = result['data']['id']
        ids.append(student_id)
        logins.append(payload['username'])
        require(coord.request('/api/coordinator/accounts', payload)['status'] == 409, 'Duplicate must not overwrite.')
        require(coord.request('/api/accounts', {**payload, 'id': student_id})['status'] == 403, 'Access administration must remain restricted.')
        require(coord.request('/api/state?user=' + ids[1])['status'] == 403, 'Special account must remain isolated.')
        rows = coord.request('/api/accounts')['data']['accounts']
        require(student_id in [r['id'] for r in rows] and ids[1] not in [r['id'] for r in rows], 'Coordinator listing scope failed.')
        student = Client(App(), host)
        who = student.login(payload['username'], password)
        require(who['role'] == 'aluno' and who['must_change'] == 1, 'New account must be Aluno with mandatory password change.')
        require(student.request('/api/state')['status'] == 428, 'Temporary password must block planning until changed.')
        new_password = secrets.token_urlsafe(24)
        require(student.request('/api/password', dict(current=password, password=new_password, confirm=new_password))['status'] == 200, 'First password change failed.')
        require(student.request('/api/state')['status'] == 200, 'Student planning unavailable.')
        require(student.request('/api/coordinator/accounts', payload)['status'] == 403, 'Student must not create accounts.')
        state = student.request('/api/state')['data']
        routine = dict(settings=state['profile']['settings'], availability=state['profile']['availability'],
                       entries=[dict(start='08:00', end='10:00', title='Atividade técnica temporária')],
                       days=[0, 1, 2, 3, 4], recurrence='weekly', anchor=P.today())
        request = dict(user=student_id, version=state['version'], op='routine_table', data=routine)
        require(coord.request('/api/action', request)['status'] == 200, 'Coordinator routine table save failed.')
        reread = student.request('/api/state')['data']
        require(len(reread['profile']['fixed']) == 1 and reread['profile']['fixed'][0]['start'] == '08:00', 'Activity times were not retained.')
        require(all(x['status'] == 'unknown' for x in reread['profile']['availability']), 'Unspecified time must not become available.')
        require(coord.request('/api/action', request)['status'] == 409, 'Routine concurrency check failed.')
        require(coord.request('/api/action', {**request, 'user': ids[1]})['status'] == 403, 'Routine special-account isolation failed.')
        with app.db.connection() as c:
            event = app.db.execute(c, 'SELECT kind FROM hmay_events WHERE actor_id=? AND target_id=? AND kind=?',
                                   (ids[0], student_id, 'account_created_by_coordinator')).fetchone()
            require(event is not None, 'Creation must be audited.')
    finally:
        if ids:
            with app.db.connection(write=True) as c:
                for uid in reversed(ids):
                    for table, column in (('hmay_proposals', 'target_id'), ('hmay_adaptive_consent', 'user_id'),
                                          ('hmay_adaptive_observations', 'user_id'), ('hmay_sessions', 'user_id'),
                                          ('hmay_academic_year', 'user_id'), ('hmay_state', 'user_id')):
                        app.db.execute(c, f'DELETE FROM {table} WHERE {column}=?', (uid,))
                    app.db.execute(c, 'DELETE FROM hmay_adjustments WHERE actor_id=? OR target_id=?', (uid, uid))
                    app.db.execute(c, 'DELETE FROM hmay_events WHERE actor_id=? OR target_id=?', (uid, uid))
                    app.db.execute(c, 'DELETE FROM hmay_users WHERE id=?', (uid,))
                for login in logins:
                    app.db.execute(c, 'DELETE FROM hmay_attempts WHERE key=?', ('user:' + hashlib.sha256(login.encode()).hexdigest(),))
    print('MEUCRONOGRAMA_V241_CHECK_OK: coordinator student creation, mandatory password change, role restrictions, duplicate protection, audit, structured routine, persistence and cleanup passed.', flush=True)


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        print('MEUCRONOGRAMA_V241_CHECK_FAILED: ' + type(exc).__name__ + '. Credentials omitted.', flush=True)
        raise SystemExit(1)
