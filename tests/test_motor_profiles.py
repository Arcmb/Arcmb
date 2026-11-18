"""v3.9.0 — perfis de foco pelas rotas HTTP. Contas sintéticas; SQLite temporário.
Executar depois do build:  python -m unittest tests/test_motor_profiles.py
"""
import json, sys, tempfile, unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from webapp import App, encode  # noqa: E402
from verify_release import Client  # noqa: E402
import planner as P  # noqa: E402

HOST, PASS = 'testserver', 'TEST_account_1234'


def perf(app, c, uid, n, general, correct):
    for i in range(n):
        md = {'_exam_id': 'x', '_tri_general': general, '_tri_lc': general, '_tri_ch': general, '_tri_cn': general, '_tri_mt': general}
        metrics = {f'questao:{q:03d}': {'correct': int(q <= correct), 'total': 1} for q in range(1, 101)}
        app.db.execute(c, 'INSERT INTO hmay_performance(id,user_id,activity_key,activity,applied_on,metrics,metadata,version,updated_at) VALUES (?,?,?,?,?,?,?,?,?)',
                       (P.uid(), uid, f'sim{i}', f'Simulado {i}', P.add(P.today(), -10 * (i + 1)), json.dumps(metrics), json.dumps(md), 1, P.now().isoformat()))


class MotorProfilesTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.app = App({'LOCAL_TEST': '1', 'LOCAL_DB': cls.tmp.name + '/db.sqlite3', 'SECRET_KEY': 'c' * 64, 'MASTER_PASSWORD': 'TEST_master_13579'})
        cls.app.db.initialize(cls.app.owner, 'TEST_master_13579')
        with cls.app.db.connection(write=True) as c:
            cls.app.db.create_user(c, 'coord', 'Coord', PASS, 'coordenador', False)
            cls.high = cls.app.db.create_user(c, 'alto', 'Aluno Alto', PASS, 'aluno', False)
            cls.low = cls.app.db.create_user(c, 'base', 'Aluno Base', PASS, 'aluno', False)
            cls.esp = cls.app.db.create_user(c, 'esp', 'Especial', PASS, 'especial', False)
            perf(cls.app, c, cls.high, 3, 790.0, 85)
            perf(cls.app, c, cls.low, 2, 590.0, 45)
            p = json.loads(cls.app.db.execute(c, 'SELECT profile FROM hmay_state WHERE user_id=?', (cls.high,)).fetchone()['profile'])
            p['availability'] = [dict(day=i, status='available', ranges=[dict(start='19:00', end='21:00')]) for i in range(7)]
            p['subjects'] = [dict(id='s1', name='Química', kind='study', action='Estudar', weeklyMin=90, difficulty=3, importance=3, priority=2, priorityManual=True, examDate='', active=True)]
            P.validate(p)
            cls.app.db.execute(c, 'UPDATE hmay_state SET profile=? WHERE user_id=?', (encode(p), cls.high))
        cls.master = Client(cls.app, HOST); cls.master.login('arcmb', 'TEST_master_13579')
        cls.coord = Client(cls.app, HOST); cls.coord.login('coord', PASS)
        cls.student = Client(cls.app, HOST); cls.student.login('alto', PASS)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_student_sees_focus_without_score_band(self):
        r = self.student.request('/api/motor/profile')
        self.assertEqual(r['status'], 200)
        self.assertEqual(r['data']['current'], 'precisao')
        self.assertNotIn('signals', r['data'])
        self.assertNotIn('760', json.dumps(r['data']))

    def test_manager_sees_signals_and_low_student_is_base(self):
        r = self.coord.request('/api/motor/profile?user=' + self.low)
        self.assertEqual(r['data']['current'], 'base')
        self.assertTrue(r['data']['provisional'] is False)
        self.assertIn('signals', r['data'])

    def test_manual_choice_and_back_to_auto(self):
        r = self.student.request('/api/motor/profile', {'user': self.high, 'mode': 'manual', 'key': 'intensiva'})
        self.assertEqual((r['data']['mode'], r['data']['current']), ('manual', 'intensiva'))
        r = self.student.request('/api/motor/profile', {'user': self.high, 'mode': 'auto'})
        self.assertEqual((r['data']['mode'], r['data']['current']), ('auto', 'precisao'))

    def test_permissions(self):
        self.assertEqual(self.student.request('/api/motor/config')['status'], 403)
        self.assertEqual(self.student.request('/api/motor/profile?user=' + self.low)['status'], 403)
        self.assertEqual(self.coord.request('/api/motor/profile?user=' + self.esp)['status'], 403)
        self.assertEqual(self.master.request('/api/motor/profile?user=' + self.esp)['status'], 200)

    def test_config_and_overview(self):
        cfg = self.coord.request('/api/motor/config')['data']['config']
        cfg['thresholds']['high'] = 800
        r = self.coord.request('/api/motor/config', {'config': cfg})
        self.assertEqual(r['status'], 200)
        ov = self.coord.request('/api/motor/overview')['data']
        by = {x['key']: x for x in ov['rows']}
        self.assertEqual(by['pratica']['suggested'], 1)
        self.assertEqual(by['base']['suggested'], 1)
        cfg['thresholds']['high'] = 760
        self.coord.request('/api/motor/config', {'config': cfg})
        bad = dict(cfg, thresholds=dict(cfg['thresholds'], base=800, high=700))
        self.assertEqual(self.coord.request('/api/motor/config', {'config': bad})['status'], 400)

    def test_preview_applies_profile(self):
        self.student.request('/api/motor/profile', {'user': self.high, 'mode': 'auto'})
        state = self.student.request('/api/state')['data']
        r = self.student.request('/api/adaptive/preview', {'user': self.high, 'version': state['version'], 'mode': 'fill', 'week': P.add(P.today(), 7)})
        self.assertEqual(r['status'], 200, r['data'])
        with self.app.db.connection() as c:
            row = self.app.db.execute(c, 'SELECT profile FROM hmay_proposals WHERE target_id=?', (self.high,)).fetchone()
        prof = json.loads(row['profile'])
        self.assertEqual(prof['settings']['motorProfile']['key'], 'precisao')
        self.assertEqual(prof['settings']['intervals'], [7, 30, 60])


if __name__ == '__main__':
    unittest.main()
