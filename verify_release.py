"""Server-side smoke test against the configured database, before Gunicorn.
Uses one disposable test account. Real accounts and planning are not modified.
Secrets, session tokens, connection strings and personal records are never logged.
"""
import hashlib
import io
import json
import os
import secrets
from http.cookies import SimpleCookie
from urllib.parse import urlencode
from webapp import App


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


class Client:
    def __init__(self, app, host):
        self.app, self.host, self.cookies, self.csrf = app, host, {}, ''

    def request(self, path, data=None, form=False, csrf=True):
        route, _, query = path.partition('?')
        raw = (urlencode(data) if form else json.dumps(data)).encode() if data is not None else b''
        env = {'REQUEST_METHOD': 'POST' if data is not None else 'GET',
               'PATH_INFO': route, 'QUERY_STRING': query, 'HTTP_HOST': self.host,
               'wsgi.input': io.BytesIO(raw), 'wsgi.url_scheme': 'https',
               'CONTENT_LENGTH': str(len(raw)), 'REMOTE_ADDR': '127.0.0.1',
               'CONTENT_TYPE': 'application/x-www-form-urlencoded' if form else 'application/json',
               'HTTP_COOKIE': '; '.join(k + '=' + v for k, v in self.cookies.items()),
               'HTTP_ORIGIN': 'https://' + self.host}
        if csrf:
            env['HTTP_X_CSRF_TOKEN'] = self.csrf
        result = {}

        def start(status, headers):
            result['status'] = int(status.split()[0])
            for key, value in headers:
                if key.lower() == 'set-cookie':
                    parsed = SimpleCookie(); parsed.load(value)
                    for name, cookie in parsed.items():
                        self.cookies[name] = cookie.value
        body = b''.join(self.app(env, start))
        try:
            result['data'] = json.loads(body)
        except (ValueError, UnicodeError):
            result['data'] = {}
        return result

    def login(self, login, password):
        require(self.request('/login')['status'] == 200, 'Login page unavailable.')
        result = self.request('/login', {'username': login, 'password': password,
                              'csrf': self.cookies.get('hmay_login', '')}, form=True)
        require(result['status'] == 303, 'Authentication check failed.')
        result = self.request('/api/me')
        require(result['status'] == 200, 'Authenticated account read failed.')
        self.csrf = result['data']['csrf']
        return result['data']['user']


def main():
    app = App()
    require(app.db.configured, 'DATABASE_URL is required.')
    require(len(app.secret) >= 32, 'SECRET_KEY is required.')
    host = os.getenv('RENDER_EXTERNAL_HOSTNAME') or sorted(app.hosts)[0]
    app.db.initialize(app.owner, app.env.get('MASTER_PASSWORD', ''), app.env.get('MAYRA_INITIAL_PASSWORD', ''))
    login, password = 'verificacao_' + secrets.token_hex(8), secrets.token_urlsafe(32)
    test_id = None
    try:
        with app.db.connection(write=True) as conn:
            owner = app.db.execute(conn, 'SELECT id,role,active FROM hmay_users WHERE username=?', (app.owner,)).fetchone()
            require(owner and owner['role'] == 'master' and owner['active'] == 1, 'Owner must remain Master.')
            test_id = app.db.create_user(conn, login, 'Verificação técnica temporária', password, must_change=False)
        client = Client(app, host)
        require(client.request('/api/state')['status'] == 401, 'Anonymous access must be blocked.')
        require(client.request('/readyz')['status'] == 200, 'Database readiness failed.')
        user = client.login(login, password)
        require(user['id'] == test_id and user['role'] == 'user', 'Individual role check failed.')
        state = client.request('/api/state')['data']
        marker = 'release-check-' + secrets.token_hex(8)
        payload = {'user': test_id, 'version': state['version'], 'op': 'diagnosis', 'data': {'goal': marker}}
        require(client.request('/api/action', payload, csrf=False)['status'] == 403, 'CSRF check failed.')
        saved = client.request('/api/action', payload)
        require(saved['status'] == 200 and saved['data']['profile']['answers']['goal'] == marker, 'Write check failed.')
        require(client.request('/api/action', payload)['status'] == 409, 'Concurrent-write protection failed.')
        require(client.request('/api/state?user=' + owner['id'])['status'] == 403, 'Account isolation failed.')
        require(client.request('/api/accounts')['status'] == 403, 'Master authorization failed.')
        require(client.request('/api/logout', {})['status'] == 200, 'Logout check failed.')
        second = Client(App(), host)
        second.login(login, password)
        reread = second.request('/api/state')
        require(reread['status'] == 200 and reread['data']['profile']['answers']['goal'] == marker, 'Committed data was not retained.')
        require(second.request('/api/logout', {})['status'] == 200, 'Second-session logout failed.')
    finally:
        if test_id:
            with app.db.connection(write=True) as conn:
                for table, column in (('hmay_sessions', 'user_id'), ('hmay_state', 'user_id'), ('hmay_users', 'id')):
                    if table == 'hmay_users':
                        app.db.execute(conn, 'DELETE FROM hmay_events WHERE actor_id=? OR target_id=?', (test_id, test_id))
                    app.db.execute(conn, f'DELETE FROM {table} WHERE {column}=?', (test_id,))
                key = 'user:' + hashlib.sha256(login.encode()).hexdigest()
                app.db.execute(conn, 'DELETE FROM hmay_attempts WHERE key=?', (key,))
    print('MEUCRONOGRAMA_RELEASE_CHECK_OK: login, persistence, isolation, CSRF, concurrency and cleanup passed.', flush=True)


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        print('MEUCRONOGRAMA_RELEASE_CHECK_FAILED: ' + type(exc).__name__ + '. Credentials omitted.', flush=True)
        raise SystemExit(1)
