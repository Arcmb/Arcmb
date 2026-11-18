"""v3.7.17 — validade de 7 dias da senha provisória. Contas sintéticas; SQLite temporário.

Executar depois do build:  python -m unittest tests/test_provisional_expiry.py
"""
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from webapp import App, bulk_create_student_accounts  # noqa: E402
from verify_release import Client  # noqa: E402
import provisional_access as PA  # noqa: E402

HOST = 'testserver'
PASS = 'TEST_account_1234'
TEMP = 'TEST_provisoria_123'


def try_login(app, login, password):
    client = Client(app, HOST)
    client.request('/login')
    result = client.request('/login', {'username': login, 'password': password,
                                       'csrf': client.cookies.get('hmay_login', '')}, form=True)
    if result['status'] == 303:
        client.csrf = client.request('/api/me')['data'].get('csrf', '')
    return result['status'], client


class ProvisionalExpiryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.app = App({'LOCAL_TEST': '1', 'LOCAL_DB': cls.tmp.name + '/db.sqlite3',
                       'SECRET_KEY': 'c' * 64, 'MASTER_PASSWORD': 'TEST_master_13579'})
        cls.app.db.initialize(cls.app.owner, 'TEST_master_13579')
        with cls.app.db.connection(write=True) as c:
            for role in ('coordenador', 'especial', 'aluno'):
                cls.app.db.create_user(c, 'base_' + role, 'Base ' + role, PASS, role, False)
            cls.legacy_id = cls.app.db.create_user(c, 'legacy_aluno', 'Aluno legado', TEMP, 'aluno', True)
            cls.legacy2_id = cls.app.db.create_user(c, 'legacy_dois', 'Aluno legado dois', TEMP, 'aluno', True)
        cls.master = Client(cls.app, HOST); cls.master.login('arcmb', 'TEST_master_13579')
        cls.coord = Client(cls.app, HOST); cls.coord.login('base_coordenador', PASS)
        cls.student = Client(cls.app, HOST); cls.student.login('base_aluno', PASS)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def expire(self, user_id):
        with self.app.db.connection(write=True) as c:
            self.app.db.execute(c, 'UPDATE hmay_provisional SET expires_at=? WHERE user_id=?', (1, user_id))

    def create_by_coordinator(self, login):
        result = self.coord.request('/api/coordinator/accounts', {'username': login, 'name': 'Aluno ' + login,
                                                                  'password': TEMP, 'role': 'aluno'})
        self.assertEqual(result['status'], 200)
        return result['data']['id']

    def test_new_account_gets_seven_days(self):
        uid = self.create_by_coordinator('novo.prazo')
        with self.app.db.connection() as c:
            limit = PA.expires_at(self.app, c, uid)
        import time
        self.assertAlmostEqual(limit - time.time(), 7 * 86400, delta=60)
        self.assertEqual(try_login(self.app, 'novo.prazo', TEMP)[0], 303)

    def test_expired_password_blocks_login_and_session(self):
        uid = self.create_by_coordinator('novo.vencido')
        status, client = try_login(self.app, 'novo.vencido', TEMP)
        self.assertEqual(status, 303)
        self.expire(uid)
        self.assertEqual(try_login(self.app, 'novo.vencido', TEMP)[0], 401)
        self.assertEqual(client.request('/api/me')['status'], 403)
        self.assertEqual(client.request('/api/password', {'current': TEMP, 'password': 'TEST_nova_12345',
                                                          'confirm': 'TEST_nova_12345'})['status'], 403)

    def test_coordinator_renews_and_first_access_clears(self):
        uid = self.create_by_coordinator('novo.renovado')
        self.expire(uid)
        result = self.coord.request('/api/provisional/renew', {'username': 'novo.renovado', 'password': 'TEST_renovada_1'})
        self.assertEqual(result['status'], 200)
        status, client = try_login(self.app, 'novo.renovado', 'TEST_renovada_1')
        self.assertEqual(status, 303)
        self.assertEqual(client.request('/api/password', {'current': 'TEST_renovada_1', 'password': 'TEST_definitiva_1',
                                                          'confirm': 'TEST_definitiva_1'})['status'], 200)
        with self.app.db.connection() as c:
            self.assertIsNone(PA.expires_at(self.app, c, uid))
        renew = self.coord.request('/api/provisional/renew', {'username': 'novo.renovado', 'password': 'TEST_outra_123'})
        self.assertEqual(renew['status'], 409)

    def test_renewal_scope(self):
        self.assertEqual(self.student.request('/api/provisional/renew', {'username': 'legacy_aluno', 'password': 'TEST_x_123456'})['status'], 403)
        self.assertEqual(self.coord.request('/api/provisional/renew', {'username': 'base_especial', 'password': 'TEST_x_123456'})['status'], 404)
        self.assertEqual(self.coord.request('/api/provisional/renew', {'username': 'nao.existe', 'password': 'TEST_x_123456'})['status'], 404)
        self.assertEqual(self.coord.request('/api/provisional/renew', {'username': 'base_coordenador', 'password': 'TEST_x_123456'})['status'], 404)
        self.assertEqual(self.coord.request('/api/provisional/renew', {'username': 'legacy_aluno', 'password': 'TEST_x_123456'}, csrf=False)['status'], 403)

    def test_existing_accounts_without_deadline_do_not_expire(self):
        with self.app.db.connection() as c:
            self.assertIsNone(PA.expires_at(self.app, c, self.legacy2_id))
        self.assertEqual(try_login(self.app, 'legacy_dois', TEMP)[0], 303)

    def test_bulk_and_master_paths_start_deadline(self):
        with self.app.db.connection(write=True) as c:
            owner = dict(self.app.db.execute(c, 'SELECT * FROM hmay_users WHERE username=?', ('arcmb',)).fetchone())
            result = bulk_create_student_accounts(self.app, c, owner, [{'name': 'Lote Teste Prazo'}], TEMP)
            bulk_id = result['created'][0]['id']
            self.assertIsNotNone(PA.expires_at(self.app, c, bulk_id))
        created = self.master.request('/api/accounts', {'username': 'master.aluno', 'name': 'Aluno do Master',
                                                        'password': TEMP, 'role': 'aluno'})
        self.assertEqual(created['status'], 200)
        staff = self.master.request('/api/accounts', {'username': 'master.coord', 'name': 'Coord do Master',
                                                      'password': TEMP, 'role': 'coordenador'})
        with self.app.db.connection() as c:
            self.assertIsNotNone(PA.expires_at(self.app, c, created['data']['id']))
            self.assertIsNone(PA.expires_at(self.app, c, staff['data']['id']))
        reset = self.master.request('/api/accounts', {'id': self.legacy_id, 'username': 'legacy_aluno', 'name': 'Aluno legado',
                                                      'password': 'TEST_reset_1234', 'role': 'aluno', 'active': True})
        self.assertEqual(reset['status'], 200)
        with self.app.db.connection() as c:
            self.assertIsNotNone(PA.expires_at(self.app, c, self.legacy_id))


if __name__ == '__main__':
    unittest.main()
