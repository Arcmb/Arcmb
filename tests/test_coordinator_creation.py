"""Authorization and persistence regressions. Synthetic accounts; temporary SQLite."""
import json
import tempfile
import unittest
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1])); sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'checks'))
from webapp import App, password_ok
import planner as P
from test_system import Browser

ENDPOINT = '/api/coordinator/accounts'


class CoordinatorCreationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.app = App({'LOCAL_TEST': '1', 'LOCAL_DB': cls.tmp.name + '/db.sqlite3',
                       'SECRET_KEY': 'c' * 64, 'MASTER_PASSWORD': 'TEST_master_13579'})
        cls.master = Browser(cls.app)
        assert cls.master.login()['status'] == 303
        cls.clients = {}
        with cls.app.db.connection(write=True) as c:
            for role in ('coordenador', 'especial', 'aluno', 'user'):
                cls.app.db.create_user(c, 'test_' + role, 'Teste ' + role,
                                      'TEST_account_1234', role, False)
        for role in ('coordenador', 'especial', 'aluno', 'user'):
            b = Browser(cls.app)
            assert b.login('test_' + role, 'TEST_account_1234')['status'] == 303
            cls.clients[role] = b
        cls.coord = cls.clients['coordenador']

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def payload(self, **kwargs):
        data = {'name': 'Aluno de teste', 'username': 'new_' + P.uid()[:16],
                'password': 'TEST_temporary_1234', 'role': 'aluno'}
        data.update(kwargs)
        return data

    def create(self, **kwargs):
        data = self.payload(**kwargs)
        r = self.coord.request(ENDPOINT, data)
        self.assertEqual(r['status'], 200, r)
        return data, r['data']

    def row(self, uid):
        with self.app.db.connection() as c:
            return dict(self.app.db.execute(c, 'SELECT * FROM hmay_users WHERE id=?', (uid,)).fetchone())

    def test_01_create_student_and_default_state(self):
        data, r = self.create()
        row = self.row(r['id'])
        self.assertEqual(row['role'], 'aluno')
        self.assertEqual(row['active'], 1)
        self.assertEqual(row['must_change'], 1)
        state = self.coord.state(r['id'])
        self.assertEqual(state['status'], 200)
        self.assertEqual(state['data']['profile']['name'], data['name'])
        self.assertEqual(state['data']['version'], 1)

    def test_02_password_hashed_not_returned(self):
        data, r = self.create()
        stored = self.row(r['id'])['password']
        self.assertNotEqual(stored, data['password'])
        self.assertTrue(password_ok(data['password'], stored))
        self.assertNotIn(data['password'], json.dumps(r))
        self.assertNotIn(stored, json.dumps(r))

    def test_03_force_password_change_then_individual_access(self):
        data, r = self.create()
        b = Browser(self.app)
        self.assertEqual(b.login(data['username'], data['password'])['status'], 303)
        self.assertEqual(b.state()['status'], 428)
        changed = b.request('/api/password', {'current': data['password'],
                            'password': 'TEST_new_private_2345', 'confirm': 'TEST_new_private_2345'})
        self.assertEqual(changed['status'], 200)
        self.assertEqual(b.state()['status'], 200)
        self.assertEqual(b.state(self.master.user['id'])['status'], 403)
        self.assertEqual(b.request(ENDPOINT, self.payload())['status'], 403)

    def test_04_creator_audit(self):
        _, r = self.create()
        with self.app.db.connection() as c:
            events = self.app.db.execute(c, 'SELECT actor_id,kind FROM hmay_events WHERE target_id=?', (r['id'],)).fetchall()
        self.assertTrue(any(x['actor_id'] == self.coord.user['id'] and
                            x['kind'] == 'account_created_by_coordinator' for x in events))

    def test_05_visible_to_master_and_coordinator(self):
        _, r = self.create()
        for b in (self.master, self.coord):
            rows = b.request('/api/accounts')['data']['accounts']
            self.assertIn(r['id'], [x['id'] for x in rows])
        self.assertNotIn(self.clients['especial'].user['id'],
                         [x['id'] for x in self.coord.request('/api/accounts')['data']['accounts']])

    def test_06_no_role_escalation(self):
        for role in ('master', 'coordenador', 'especial', 'user', '', None, ['aluno']):
            with self.subTest(role=role):
                self.assertEqual(self.coord.request(ENDPOINT, self.payload(role=role))['status'], 403)

    def test_07_no_extra_control_fields(self):
        for field, value in [('id', self.master.user['id']), ('id', ''),
                             ('active', False), ('must_change', False), ('owner', True)]:
            with self.subTest(field=field):
                self.assertEqual(self.coord.request(ENDPOINT, self.payload(**{field: value}))['status'], 403)

    def test_08_default_role_aluno(self):
        data = self.payload()
        del data['role']
        r = self.coord.request(ENDPOINT, data)
        self.assertEqual(r['status'], 200)
        self.assertEqual(self.row(r['data']['id'])['role'], 'aluno')

    def test_09_existing_account_unchanged(self):
        who = self.clients['especial'].user['id']
        before = self.row(who)
        r = self.coord.request(ENDPOINT, self.payload(username='test_especial'))
        self.assertEqual(r['status'], 409)
        self.assertEqual(before, self.row(who))

    def test_10_duplicate_not_create_or_reset(self):
        data, created = self.create()
        before = self.row(created['id'])
        self.assertEqual(self.coord.request(ENDPOINT, {**data, 'password': 'TEST_replaced_123'})['status'], 409)
        self.assertEqual(before, self.row(created['id']))

    def test_11_legacy_admin_endpoint_still_forbidden(self):
        self.assertEqual(self.coord.request('/api/accounts', self.payload())['status'], 403)
        self.assertEqual(self.coord.request('/api/accounts', {'id': self.master.user['id'],
                         'role': 'aluno', 'username': 'arcmb', 'name': 'Changed'})['status'], 403)

    def test_12_special_and_student_forbidden(self):
        for role in ('especial', 'aluno', 'user'):
            self.assertEqual(self.clients[role].request(ENDPOINT, self.payload())['status'], 403)

    def test_13_anonymous_forbidden(self):
        self.assertEqual(Browser(self.app).request(ENDPOINT, self.payload())['status'], 401)

    def test_14_csrf_required(self):
        self.assertEqual(self.coord.request(ENDPOINT, self.payload(), csrf=False)['status'], 403)

    def test_15_cross_origin_rejected(self):
        self.assertEqual(self.coord.request(ENDPOINT, self.payload(), origin='https://other.example')['status'], 403)

    def test_16_invalid_name_password_login(self):
        for update in ({'name': ''}, {'name': 'x' * 151}, {'name': 123}, {'username': 'a'},
                       {'username': "evil' or 1=1"}, {'username': None}, {'password': '1234567'},
                       {'password': 'x' * 129}, {'password': None}):
            with self.subTest(update=list(update)):
                self.assertEqual(self.coord.request(ENDPOINT, self.payload(**update))['status'], 400)

    def test_17_master_retains_all_roles(self):
        for role in ('especial', 'coordenador', 'aluno', 'master'):
            data = self.payload(role=role)
            r = self.master.request('/api/accounts', data)
            self.assertEqual(r['status'], 200)
            self.assertEqual(self.row(r['data']['id'])['role'], role)

    def test_18_master_owner_protected(self):
        before = self.row(self.master.user['id'])
        self.assertEqual(self.coord.request(ENDPOINT, self.payload(username='arcmb'))['status'], 409)
        self.assertEqual(self.row(self.master.user['id']), before)

    def test_19_no_special_access_or_reset(self):
        uid = self.clients['especial'].user['id']
        for path in ('/api/state', '/api/performance', '/api/calendar', '/api/backup'):
            self.assertEqual(self.coord.request(path + '?user=' + uid)['status'], 403)
        self.assertEqual(self.coord.request('/api/accounts', {**self.payload(), 'id': uid})['status'], 403)
        self.assertEqual(self.coord.request('/api/backup?all=1')['status'], 403)

    def test_20_creation_is_atomic(self):
        data = self.payload()
        original = self.app.event
        def fail(c, user, target, kind):
            if kind == 'account_created_by_coordinator':
                raise RuntimeError('Synthetic failure')
            return original(c, user, target, kind)
        try:
            self.app.event = fail
            self.assertEqual(self.coord.request(ENDPOINT, data)['status'], 503)
        finally:
            self.app.event = original
        with self.app.db.connection() as c:
            self.assertIsNone(self.app.db.execute(c, 'SELECT id FROM hmay_users WHERE username=?', (data['username'],)).fetchone())

    def test_21_get_does_not_create(self):
        self.assertEqual(self.coord.request(ENDPOINT)['status'], 405)

    def test_22_coordinator_edits_new_student_routine(self):
        _, r = self.create()
        result = self.coord.action('diagnosis', {'goal': 'Organização ajustada pela coordenação'}, r['id'])
        self.assertEqual(result['status'], 200)
        self.assertEqual(self.master.state(r['id'])['data']['profile']['answers']['goal'],
                         'Organização ajustada pela coordenação')


if __name__ == '__main__':
    unittest.main()
