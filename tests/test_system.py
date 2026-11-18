"""Cliente de teste usado pelos testes antigos (v2.3 a v2.4.1). Simula um navegador sobre a aplicação WSGI."""
from verify_release import Client


class Browser(Client):
    def __init__(self, app, host='testserver'):
        super().__init__(app, host)
        self.user = None

    def request(self, path, data=None, form=False, csrf=True, origin=None):
        """Igual ao Client, mas devolve também o corpo bruto ('raw') e aceita outra origem (teste de CSRF)."""
        captured = {}
        original_app = self.app

        def app(env, start):
            if origin is not None:
                env['HTTP_ORIGIN'] = origin
            body = b''.join(original_app(env, start))
            captured['raw'] = body
            return [body]

        self.app = app
        try:
            result = super().request(path, data, form, csrf)
        finally:
            self.app = original_app
        result['raw'] = captured.get('raw', b'')
        return result

    def login(self, username=None, password='TEST_master_13579'):
        username = username or self.app.owner
        self.request('/login')
        result = self.request('/login', {'username': username, 'password': password,
                                         'csrf': self.cookies.get('hmay_login', '')}, form=True)
        if result['status'] == 303:
            me = self.request('/api/me')
            if me['status'] == 200:
                self.csrf = me['data']['csrf']
                self.user = me['data']['user']
        return result

    def state(self, target=None):
        return self.request('/api/state' + ('?user=' + str(target) if target else ''))

    def action(self, op, data, target=None):
        current = self.state(target)
        version = current['data'].get('version', 1) if current['status'] == 200 else 1
        return self.request('/api/action', dict(user=target or self.user['id'], version=version, op=op, data=data))
