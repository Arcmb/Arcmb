"""v3.12.0 — Cadastro de disciplinas oficiais. SQLite temporário."""
import json, sys, tempfile, unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from webapp import App  # noqa: E402
from verify_release import Client  # noqa: E402
import planner as P  # noqa: E402
import disciplines_catalog as D  # noqa: E402

HOST, PASS = 'testserver', 'TEST_account_1234'
ITEMS = [{'number': 1, 'area': 'LC', 'discipline': 'ESPANHOL', 'answer': 'A', 'language': 'Espanhol'},
         {'number': 2, 'area': 'LC', 'discipline': 'L. corporal', 'answer': 'B', 'language': ''},
         {'number': 3, 'area': 'LC', 'discipline': 'Linguagem Corporal', 'answer': 'C', 'language': ''},
         {'number': 4, 'area': 'CN', 'discipline': 'Astronomia', 'answer': 'D', 'language': ''},
         {'number': 5, 'area': 'MT', 'discipline': 'Matemática', 'answer': 'E', 'language': ''}]


class DisciplinesCatalogTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.app = App({'LOCAL_TEST': '1', 'LOCAL_DB': cls.tmp.name + '/db.sqlite3', 'SECRET_KEY': 'd' * 64, 'MASTER_PASSWORD': 'TEST_master_13579'})
        cls.app.db.initialize(cls.app.owner, 'TEST_master_13579')
        with cls.app.db.connection(write=True) as c:
            cls.app.db.create_user(c, 'coord', 'Coord', PASS, 'coordenador', False)
            uid = cls.app.db.create_user(c, 'ana', 'Ana', PASS, 'aluno', False)
            cls.app.db.execute(c, 'INSERT INTO hmay_exams(id,identity_key,owner_id,title,applied_on,color,area,items,version,updated_at) VALUES (?,?,?,?,?,?,?,?,?,?)',
                               ('ex1', 'k1', uid, 'Sim', P.today(), 'AZUL', 'GERAL', json.dumps(ITEMS), 1, P.now().isoformat()))
        cls.coord = Client(cls.app, HOST); cls.coord.login('coord', PASS)
        cls.student = Client(cls.app, HOST); cls.student.login('ana', PASS)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_1_found_and_pending(self):
        d = self.coord.request('/api/disciplines/catalog')['data']
        st = {f['name']: f for f in d['found']}
        self.assertEqual(st['ESPANHOL']['official'], 'Espanhol')
        self.assertEqual(st['L. corporal']['official'], 'Linguagem Corporal')
        self.assertFalse(st['Linguagem Corporal']['changes'])
        self.assertEqual(st['Astronomia']['official'], '')
        self.assertEqual(d['pending'], {'exams': 1, 'questions': 2, 'applied': False})

    def test_2_save_apply(self):
        d = self.coord.request('/api/disciplines/catalog')['data']
        cat = d['catalog']
        for x in cat['disciplines']:
            if x['name'] == 'Física':
                x['aliases'] = ['Astronomia']
        saved = self.coord.request('/api/disciplines/catalog', {'catalog': cat, 'version': d['version']})['data']
        self.assertEqual(saved['version'], d['version'] + 1)
        self.assertEqual(saved['pending']['questions'], 3)
        stale = self.coord.request('/api/disciplines/catalog', {'catalog': cat, 'version': d['version']})
        self.assertEqual(stale['status'], 400)
        r = self.coord.request('/api/disciplines/apply', {})['data']
        self.assertEqual((r['exams'], r['questions']), (1, 3))
        with self.app.db.connection() as c:
            row = self.app.db.execute(c, 'SELECT items,version FROM hmay_exams WHERE id=?', ('ex1',)).fetchone()
        names = [x['discipline'] for x in json.loads(row['items'])]
        self.assertEqual(names, ['Espanhol', 'Linguagem Corporal', 'Linguagem Corporal', 'Física', 'Matemática'])
        self.assertEqual(row['version'], 2)
        self.assertEqual(self.coord.request('/api/disciplines/catalog')['data']['pending']['questions'], 0)

    def test_3_import_conversion(self):
        items = [{'discipline': 'INGLÊS'}, {'discipline': '  l  corporal '}, {'discipline': 'Robótica'}]
        with self.app.db.connection(write=True) as c:
            n = D.canon_items(self.app, c, items)
        self.assertEqual(n, 2)
        self.assertEqual([x['discipline'] for x in items], ['Inglês', 'Linguagem Corporal', 'Robótica'])

    def test_4_permissions_and_validation(self):
        self.assertEqual(self.student.request('/api/disciplines/catalog')['status'], 403)
        bad = {'disciplines': [{'name': 'Artes', 'area': 'XX', 'aliases': []}]}
        self.assertEqual(self.coord.request('/api/disciplines/catalog', {'catalog': bad, 'version': 99})['status'], 400)
