"""v3.13.0 — Banco de itens do ENEM (TRI). SQLite temporário."""
import base64, sys, tempfile, unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1])); sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'checks'))
from webapp import App  # noqa: E402
from verify_release import Client  # noqa: E402
import enem_items as E  # noqa: E402
import templates_v23 as T  # noqa: E402

PASS = 'TEST_account_1234'
ROWS = [
    [2023, '', 'MATEMÁTICA', 'Geometria', 'Áreas e volumes', 'h08', 2.6, 1.5, 0.15],      # 650 → Média; alta
    [2023, 'MT', 'Matemática', 'Geometria', 'Áreas e volumes', 'H08', 0.031, 820, 0.12],  # já na escala ENEM → Muito difícil; alta
    [2022, 'MT', 'Matemática', 'Álgebra', 'Porcentagem', 'H15', 1.2, 0.4, 0.22],         # 540 → Fácil; baixa
    [2022, 'CN', 'Química', 'Estequiometria', 'Cálculo estequiométrico', 'H24', 2.0, 2.3, 0.25],  # 730 → Difícil; média
    [2022, '', 'Astronomia', '', 'Estrelas', '', 2.0, 1.0, 0.2],                          # sem área e sem cadastro → erro
    [2022, 'MT', 'Matemática', '', 'Funções', 'H20', 'x', 1, 0.2],                        # parâmetro inválido → erro
]


def payload(rows, mode=None, ignore=False):
    blob, _ = T.export(E.HEADERS, rows, first_name='Itens ENEM')
    p = {'filename': 'itens.xlsx', 'file': base64.b64encode(blob).decode()}
    if mode:
        p.update(mode=mode, ignoreErrors=ignore)
    return p


class EnemItemsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.app = App({'LOCAL_TEST': '1', 'LOCAL_DB': cls.tmp.name + '/db.sqlite3', 'SECRET_KEY': 'e' * 64, 'MASTER_PASSWORD': 'TEST_master_13579'})
        cls.app.db.initialize(cls.app.owner, 'TEST_master_13579')
        with cls.app.db.connection(write=True) as c:
            cls.app.db.create_user(c, 'coord', 'Coord', PASS, 'coordenador', False)
            cls.app.db.create_user(c, 'ana', 'Ana', PASS, 'aluno', False)
        cls.coord = Client(cls.app, 'testserver'); cls.coord.login('coord', PASS)
        cls.student = Client(cls.app, 'testserver'); cls.student.login('ana', PASS)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_0_rules(self):
        self.assertEqual(E.scale(2.6, 1.5), (2.6, 650.0))
        self.assertEqual(E.scale(0.031, 820), (3.1, 820))
        self.assertEqual([E.difficulty(x) for x in (599, 600, 700, 800)], ['Fácil', 'Média', 'Difícil', 'Muito difícil'])
        self.assertEqual([E.complexity(2.5, 0.2), E.complexity(1.4, 0.1), E.complexity(3, 0.3), E.complexity(2, 0.2)], ['Alta', 'Baixa', 'Baixa', 'Média'])

    def test_1_template(self):
        r = self.coord.request('/api/enem-items/template', {})
        self.assertEqual(r['status'], 200)

    def test_2_preview_and_import(self):
        p = self.coord.request('/api/enem-items/preview', payload(ROWS))['data']
        self.assertEqual((p['valid'], p['errorCount']), (4, 2))
        self.assertEqual(p['difficulty'], {'Fácil': 1, 'Média': 1, 'Difícil': 1, 'Muito difícil': 1})
        self.assertEqual(p['complexity'], {'Baixa': 1, 'Média': 1, 'Alta': 2})
        self.assertEqual(p['sample'][0]['discipline'], 'Matemática')
        self.assertEqual(p['sample'][0]['skill'], 'H08')
        blocked = self.coord.request('/api/enem-items/confirm', payload(ROWS, 'add'))
        self.assertEqual(blocked['status'], 400)
        r = self.coord.request('/api/enem-items/confirm', payload(ROWS, 'add', True))['data']
        self.assertEqual((r['added'], r['skipped'], r['ignored']), (4, 0, 2))
        again = self.coord.request('/api/enem-items/confirm', payload(ROWS, 'add', True))['data']
        self.assertEqual((again['added'], again['skipped']), (0, 4))

    def test_3_summary(self):
        d = self.coord.request('/api/enem-items/summary?level=subject')['data']
        top = d['rows'][0]
        self.assertEqual((top['label'], top['items'], top['share'], top['meanB'], top['level']), ('Áreas e volumes', 2, round(200 / 3, 1), 735.0, 'Difícil'))
        self.assertEqual(top['highComplexity'], 100.0)
        disc = self.coord.request('/api/enem-items/summary?level=discipline')['data']['rows']
        self.assertEqual([(r['label'], r['items']) for r in disc], [('Matemática', 3), ('Química', 1)])
        y = self.coord.request('/api/enem-items/summary?level=skill&year=2022&area=MT')['data']
        self.assertEqual([(r['label'], r['items']) for r in y['rows']], [('H15', 1)])
        self.assertEqual(d['years'], [2022, 2023])

    def test_4_replace_and_permissions(self):
        r = self.coord.request('/api/enem-items/confirm', payload(ROWS[2:4], 'replace'))['data']
        self.assertEqual(r['added'], 2)
        self.assertEqual(self.coord.request('/api/enem-items/summary')['data']['all'], 2)
        self.assertEqual(self.student.request('/api/enem-items/summary')['status'], 403)
        self.assertEqual(self.student.request('/api/enem-items/template', {})['status'], 403)
