"""v3.10.0 — Relatórios da escola. Dados sintéticos com resultado conhecido; SQLite temporário."""
import json, sys, tempfile, unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1])); sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'checks'))
from webapp import App, encode  # noqa: E402
from verify_release import Client  # noqa: E402
import planner as P  # noqa: E402

HOST, PASS = 'testserver', 'TEST_account_1234'
ITEMS = [{'number': n, 'area': 'MT' if n <= 5 else 'CN', 'discipline': 'Matemática' if n <= 5 else 'Química',
          'subject': 'Funções' if n <= 5 else 'Estequiometria', 'skill': f'H{n:02d}', 'answer': 'A', 'language': ''} for n in range(1, 11)]


def add_result(app, c, uid, turma, date, key, correct_upto, general, comps, wrong_letter='C'):
    md = {'_exam_id': 'ex1', 'TURMA': turma, 'COR DA PROVA': 'AZUL', '_tri_general': general, '_tri_lc': general, '_tri_ch': general,
          '_tri_cn': general, '_tri_mt': general, '_tri_redaction': sum(comps), **{f'_redaction_c{i+1}': v for i, v in enumerate(comps)}}
    m = {f'questao:{n:03d}': {'correct': int(n <= correct_upto), 'total': 1, 'response': 'A' if n <= correct_upto else wrong_letter} for n in range(1, 11)}
    app.db.execute(c, 'INSERT INTO hmay_performance(id,user_id,activity_key,activity,applied_on,metrics,metadata,version,updated_at) VALUES (?,?,?,?,?,?,?,?,?)',
                   (P.uid(), uid, key, key.upper(), date, json.dumps(m), json.dumps(md), 1, P.now().isoformat()))


class SchoolReportsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.app = App({'LOCAL_TEST': '1', 'LOCAL_DB': cls.tmp.name + '/db.sqlite3', 'SECRET_KEY': 'c' * 64, 'MASTER_PASSWORD': 'TEST_master_13579'})
        cls.app.db.initialize(cls.app.owner, 'TEST_master_13579')
        d1, d2 = P.add(P.today(), -40), P.add(P.today(), -10)
        with cls.app.db.connection(write=True) as c:
            cls.app.db.create_user(c, 'coord', 'Coord', PASS, 'coordenador', False)
            cls.a = cls.app.db.create_user(c, 'ana', 'Ana', PASS, 'aluno', False)      # turma A, cai 50 pontos
            cls.b = cls.app.db.create_user(c, 'bia', 'Bia', PASS, 'aluno', False)      # turma B, faltou ao 2º
            cls.e = cls.app.db.create_user(c, 'esp', 'Especial', PASS, 'especial', False)
            for i in range(4):
                cls.app.db.create_user(c, f'x{i}', f'Extra {i}', PASS, 'aluno', True)
            cls.app.db.execute(c, 'INSERT INTO hmay_exams(id,identity_key,owner_id,title,applied_on,color,area,items,version,updated_at) VALUES (?,?,?,?,?,?,?,?,?,?)',
                               ('ex1', 'k1', cls.a, 'Sim', d1, 'AZUL', 'GERAL', json.dumps(ITEMS), 1, P.now().isoformat()))
            add_result(cls.app, c, cls.a, 'Turma A', d1, 'sim1', 8, 720.0, [160, 160, 120, 160, 120])
            add_result(cls.app, c, cls.a, 'Turma A', d2, 'sim2', 6, 670.0, [160, 160, 120, 160, 120])
            add_result(cls.app, c, cls.b, 'Turma B', d1, 'sim1', 4, 600.0, [120, 120, 80, 120, 160], 'D')
            add_result(cls.app, c, cls.e, 'Turma A', d1, 'sim1', 10, 800.0, [200] * 5)
            for i in range(4):
                uid = cls.app.db.execute(c, 'SELECT id FROM hmay_users WHERE username=?', (f'x{i}',)).fetchone()['id']
                add_result(cls.app, c, uid, 'Turma A', d2, 'sim2', 5, 650.0, [160] * 5)
        cls.coord = Client(cls.app, HOST); cls.coord.login('coord', PASS)
        cls.master = Client(cls.app, HOST); cls.master.login('arcmb', 'TEST_master_13579')
        cls.student = Client(cls.app, HOST); cls.student.login('ana', PASS)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_student_blocked(self):
        self.assertEqual(self.student.request('/api/school-reports/attention')['status'], 403)

    def test_attention_flags(self):
        d = self.coord.request('/api/school-reports/attention')['data']
        by = {s['name']: {f['kind'] for f in s['flags']} for s in d['students']}
        self.assertIn('queda', by['Ana'])
        self.assertIn('falta', by['Bia'])
        self.assertIn('acesso', by['Extra 0'])
        self.assertNotIn('Especial', by)

    def test_questions(self):
        d = self.coord.request('/api/school-reports/questions?sim=sim1@@' + P.add(P.today(), -40))['data']
        q = {x['number']: x for x in d['questions']}
        self.assertEqual(q[1]['accuracy'], 100.0)        # Ana e Bia acertaram (Especial fora para coordenação)
        self.assertEqual(q[5]['accuracy'], 50.0)         # só Ana
        self.assertEqual(q[9]['accuracy'], 0.0)
        self.assertEqual(q[9]['turmas']['Turma A'], 0.0)
        self.assertEqual(q[9]['distractor']['letter'], 'C')
        self.assertEqual(q[5]['distractor']['letter'], 'D')
        self.assertEqual(q[5]['subject'], 'Funções')

    def test_master_includes_especial(self):
        d = self.master.request('/api/school-reports/questions?sim=sim1@@' + P.add(P.today(), -40))['data']
        q = {x['number']: x for x in d['questions']}
        self.assertEqual(q[9]['accuracy'], 33.3)

    def test_topics(self):
        d = self.coord.request('/api/school-reports/topics')['data']
        rows = {r['subject']: r for r in d['rows']}
        # Funções (q1-5): Ana 5+5, Bia 4, extras 4x5 = 34/35; Estequiometria (q6-10): Ana 3+1, Bia 0, extras 0 = 4/35
        self.assertEqual(rows['Funções']['accuracy'], round(100 * 34 / 35, 1))
        self.assertEqual(rows['Estequiometria']['accuracy'], round(100 * 4 / 35, 1))
        self.assertEqual(d['rows'][0]['subject'], 'Estequiometria')
        self.assertEqual(rows['Estequiometria']['turmas']['Turma B'], 0.0)

    def test_disciplines_priorities(self):
        d = self.coord.request('/api/school-reports/disciplines')['data']
        by = {x['discipline']: x for x in d['disciplines']}
        q = by['Química']
        est = q['subjects'][0]
        # Estequiometria: 31 erros em 35 respostas, 5 questões → prioridade alta; todos os 6 alunos com dificuldade
        self.assertEqual((est['label'], est['error'], est['questions'], est['priority']), ('Estequiometria', round(100 * 31 / 35, 1), 5, 'alta'))
        self.assertEqual((est['struggling'], est['students']), (6, 6))
        self.assertEqual(q['high'], 1)
        self.assertEqual(by['Matemática']['subjects'][0]['priority'], 'baixa')
        # habilidades: 7 respostas cada → poucos dados
        self.assertTrue(all(s['priority'] == 'dados' and s['answers'] == 7 for s in q['skills']))
        self.assertIn('H06', [s['label'] for s in q['skills']])
        only_b = self.coord.request('/api/school-reports/disciplines?turma=Turma+B')['data']
        qb = {x['discipline']: x for x in only_b['disciplines']}['Química']
        self.assertEqual((qb['answers'], qb['error'], qb['subjects'][0]['priority']), (5, 100.0, 'dados'))

    def test_most_missed(self):
        d = self.coord.request('/api/school-reports/most-missed')['data']
        top = d['rows'][0]
        self.assertEqual(top['subject'], 'Estequiometria')
        self.assertTrue(top['everywhere'])
        self.assertEqual((top['above'], top['withData']), (2, 2))
        self.assertEqual(top['turmas']['Turma A'], round(100 * 26 / 30, 1))
        fun = {r['subject']: r for r in d['rows']}['Funções']
        self.assertEqual(fun['above'], 0)
        self.assertEqual(self.student.request('/api/school-reports/most-missed')['status'], 403)

    def test_redaction(self):
        d = self.coord.request('/api/school-reports/redaction')['data']
        by = {r['turma']: r for r in d['rows']}
        self.assertEqual(by['Turma B']['weakest'], 'C3')
        self.assertEqual(by['Turma B']['competencies'], [120.0, 120.0, 80.0, 120.0, 160.0])
        self.assertEqual(by['Todas as turmas']['essays'], 7)

    def test_profiles(self):
        d = self.coord.request('/api/school-reports/profiles')['data']
        total = sum(r['students'] for r in d['rows'])
        self.assertEqual(total, 7)  # 6 alunos + a conta 'mayra' criada pela inicialização local
        by = {r['turma']: r for r in d['rows']}
        self.assertEqual(by['Turma B']['base'], 1)


if __name__ == '__main__':
    unittest.main()
