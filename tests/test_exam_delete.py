"""Exclusão de notas, respostas e gabarito de um simulado. SQLite temporário e dados sintéticos."""
from pathlib import Path
from tempfile import TemporaryDirectory
import json
import re
import sys
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[1])); sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'checks'))

import exam_metadata as maps
import model_data
import planner as P
import results_store as RS
from webapp import App
from verify_release import Client

PASSWORD = 'LocalFixture2026!'


def items(answer_first='A'):
    return [dict(number=n, area='LC' if n <= 2 else 'MT', language='', answer=answer_first if n == 1 else 'B',
                 discipline='Português' if n <= 2 else 'Matemática', topic='Leitura' if n <= 2 else 'Funções',
                 subject='Interpretação' if n <= 2 else 'Função afim', skill='H%02d' % n) for n in range(1, 5)]


def metrics(wrong):
    return {'questao:%03d' % n: {'name': 'Questão %02d' % n, 'correct': 0 if n in wrong else 1, 'total': 1}
            for n in range(1, 5)}


class ExamFixture(unittest.TestCase):
    """Dois simulados (um com duas cores), três alunos e revisões geradas pelos erros."""

    def setUp(self):
        folder = TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.app = App({'LOCAL_TEST': '1', 'LOCAL_DB': str(Path(folder.name) / 'fixture.sqlite3')})
        self.app.db.initialize(self.app.owner, PASSWORD)
        # Os testes rodam em SQLite, mas a produção usa Postgres, onde o app troca "?" por "%s".
        # Lá, um "%" solto no SQL (ex.: LIKE '%x%') quebra a consulta: falha aqui também.
        execute = self.app.db.execute

        def postgres_placeholders(conn, sql, args=()):
            if args:
                converted = sql.replace('?', '%s')
                stray = re.findall(r'%(?![s%])', converted)
                self.assertFalse(stray, 'SQL com "%" literal quebraria no Postgres: ' + sql)
            return execute(conn, sql, args)

        self.app.db.execute = postgres_placeholders
        with self.app.db.connection(write=True) as c:
            self.master = dict(c.execute("SELECT id,role FROM hmay_users WHERE role='master'").fetchone())
            self.app.db.create_user(c, 'coord.teste', 'Coordenação', PASSWORD, 'coordenador', False)
            self.students = [self.app.db.create_user(c, 'aluno%d' % i, 'Aluno %d' % i, PASSWORD, 'aluno', False)
                             for i in range(3)]
            self.exams = {}
            for title, date, color in (('Simulado 5', '2026-10-25', 'Azul'), ('Simulado 5', '2026-10-25', 'Amarela'),
                                       ('Simulado 6', '2026-11-08', 'Azul')):
                key = maps.identity_key(title, date, color)
                eid = 'md_' + key[:32]
                c.execute('INSERT INTO hmay_exams VALUES (?,?,?,?,?,?,?,?,?,?)',
                          (eid, key, self.master['id'], title, date, color, '', json.dumps(items()), 1, date))
                self.exams[(title, color)] = eid
            n = 0
            for i, uid in enumerate(self.students):
                for title, date, color in (('Simulado 5', '2026-10-25', 'Azul' if i < 2 else 'Amarela'),
                                           ('Simulado 6', '2026-11-08', 'Azul')):
                    md = {'COR DA PROVA': color, 'TURMA': 'T1', '_exam_id': self.exams[(title, color)],
                          '_tri_lc': 600 + i, '_tri_mt': 700, '_ranking': i + 1, '_redaction_c1': 160,
                          '_tri_imported_at': '2026-11-10T10:00:00'}
                    c.execute('INSERT INTO hmay_performance VALUES (?,?,?,?,?,?,?,?,?)',
                              ('r%d' % n, uid, model_data.F.norm(title), title, date, json.dumps(metrics({1, 3})),
                               json.dumps(md), 1, date))
                    n += 1
            for uid in self.students:
                model_data._er_sync_target(self.app, c, self.master, uid)
        self.client = Client(self.app, 'testserver')
        self.client.login('arcmb', PASSWORD)

    # ------------------------------------------------------------ apoio

    def preview(self, exam=('Simulado 5', 'Azul'), client=None):
        r = (client or self.client).request('/api/model-data/exam-delete-preview', {'examId': self.exams[exam]})
        self.assertEqual(r['status'], 200, r['data'])
        return r['data']

    def delete(self, exam=('Simulado 5', 'Azul'), whole=False, expected=None, confirmation='EXCLUIR', **marks):
        if expected is None:
            scope = self.preview(exam)['scopes']['simulado' if whole else 'caderno']
            expected = {k: scope[k] for k in ('exams', 'results', 'withScores')}
        body = dict(examId=self.exams[exam], whole=whole, expected=expected, confirmation=confirmation, **marks)
        return self.client.request('/api/model-data/exam-delete', body)

    def rows(self):
        with self.app.db.connection() as c:
            return {r['id']: dict(r, metadata=json.loads(r['metadata']), metrics=json.loads(r['metrics']))
                    for r in c.execute('SELECT * FROM hmay_performance').fetchall()}

    def profile(self, uid):
        with self.app.db.connection() as c:
            return json.loads(c.execute('SELECT profile FROM hmay_state WHERE user_id=?', (uid,)).fetchone()['profile'])

    def exam_errors(self, uid):
        out = []
        for content in self.profile(uid)['contents']:
            if content.get('sourceType') == 'exam_error':
                out += [(e['simulation'], e['date']) for e in content['examErrors']]
        return out


class ExamDeleteTests(ExamFixture):

    def test_preview_counts_each_scope(self):
        data = self.preview()
        self.assertEqual(data['colors'], ['Amarela', 'Azul'])
        self.assertEqual(data['scopes']['caderno'], dict(exams=1, results=2, students=2, withScores=2, colors=['Azul']))
        self.assertEqual(data['scopes']['simulado'], dict(exams=2, results=3, students=3, withScores=3, colors=['Amarela', 'Azul']))

    def test_scores_only_keeps_answers_and_other_exams(self):
        before = self.rows()
        r = self.delete(scores=True)
        self.assertEqual(r['status'], 200, r['data'])
        self.assertEqual(r['data']['clearedScores'], 2)
        after = self.rows()
        self.assertEqual(set(after), set(before))
        for rid, row in after.items():
            mine = row['metadata']['_exam_id'] == self.exams[('Simulado 5', 'Azul')]
            self.assertEqual(any(k.startswith(('_tri_', '_redaction_')) or k == '_ranking' for k in row['metadata']), not mine)
            self.assertEqual(row['metrics'], before[rid]['metrics'])
            self.assertEqual(row['metadata']['TURMA'], 'T1')
        # Revisões vêm das respostas: continuam.
        self.assertIn(('Simulado 5', '2026-10-25'), self.exam_errors(self.students[0]))

    def test_whole_answers_delete_results_scores_and_generated_reviews(self):
        uid = self.students[0]
        self.assertIn(('Simulado 5', '2026-10-25'), self.exam_errors(uid))
        r = self.delete(whole=True, answers=True)
        self.assertEqual(r['status'], 200, r['data'])
        self.assertEqual(r['data']['deletedResults'], 3)
        self.assertEqual(r['data']['reviews']['students'], 3)
        rows = self.rows()
        self.assertEqual({row['activity'] for row in rows.values()}, {'Simulado 6'})
        for student in self.students:
            errors = self.exam_errors(student)
            self.assertNotIn(('Simulado 5', '2026-10-25'), errors)
            self.assertIn(('Simulado 6', '2026-11-08'), errors)
            P.validate(self.profile(student))
        # Gabaritos continuam: só as respostas foram marcadas.
        with self.app.db.connection() as c:
            self.assertEqual(c.execute('SELECT COUNT(*) AS n FROM hmay_exams').fetchone()['n'], 3)

    def test_review_without_errors_is_removed_or_paused_when_it_has_history(self):
        # Só o Simulado 6 fica com erros; os conteúdos do Simulado 5 somem ou são pausados.
        first = self.delete(exam=('Simulado 6', 'Azul'), whole=True, answers=True)
        self.assertEqual(first['status'], 200, first['data'])
        self.assertTrue(all(sim == 'Simulado 5' for sim, _ in self.exam_errors(self.students[0])))
        with_history, without = self.students[0], self.students[1]
        profile = self.profile(with_history)
        content = next(x for x in profile['contents'] if x.get('sourceType') == 'exam_error')
        profile['studyLogs'].append(dict(id='log1', contentId=content['id'], date='2026-11-01', minutes=20))
        profile['sessions'].append(dict(id='s-future', date='2099-01-01', start=600, end=620, kind='review',
                                        subjectId=content['subjectId'], contentId=content['id'], title='Revisão',
                                        status='planned', locked=False, reason=''))
        with self.app.db.connection(write=True) as c:
            c.execute('UPDATE hmay_state SET profile=? WHERE user_id=?', (json.dumps(profile), with_history))
        r = self.delete(whole=True, answers=True)
        self.assertEqual(r['status'], 200, r['data'])
        kept = [x for x in self.profile(with_history)['contents'] if x.get('id') == content['id']]
        self.assertEqual(len(kept), 1)
        self.assertTrue(kept[0]['paused'])
        self.assertEqual(kept[0]['examErrors'], [])
        self.assertFalse(any(s['id'] == 's-future' for s in self.profile(with_history)['sessions']))
        self.assertFalse([x for x in self.profile(without)['contents'] if x.get('sourceType') == 'exam_error'])
        for student in self.students:
            P.validate(self.profile(student))

    def test_map_needs_answers_when_results_are_linked(self):
        r = self.delete(map=True)
        self.assertEqual(r['status'], 409)
        self.assertEqual(len(self.rows()), 6)
        r = self.delete(map=True, answers=True)
        self.assertEqual(r['status'], 200, r['data'])
        self.assertEqual(r['data']['deletedExams'], 1)
        with self.app.db.connection() as c:
            ids = {x['id'] for x in c.execute('SELECT id FROM hmay_exams').fetchall()}
        self.assertNotIn(self.exams[('Simulado 5', 'Azul')], ids)
        self.assertIn(self.exams[('Simulado 5', 'Amarela')], ids)
        # Caderno sem respostas: o gabarito pode sair sozinho.
        r = self.delete(exam=('Simulado 5', 'Amarela'), map=True, answers=True)
        self.assertEqual(r['status'], 200, r['data'])
        key = maps.identity_key('Simulado 7', '2026-12-01', 'Azul')
        with self.app.db.connection(write=True) as c:
            c.execute('INSERT INTO hmay_exams VALUES (?,?,?,?,?,?,?,?,?,?)',
                      ('md_vazio', key, self.master['id'], 'Simulado 7', '2026-12-01', 'Azul', '', '[]', 1, 'x'))
        self.exams[('Simulado 7', 'Azul')] = 'md_vazio'
        r = self.delete(exam=('Simulado 7', 'Azul'), map=True)
        self.assertEqual(r['status'], 200, r['data'])

    def test_guards(self):
        self.assertEqual(self.delete(scores=True, confirmation='sim')['status'], 400)
        self.assertEqual(self.delete()['status'], 400)
        stale = dict(exams=1, results=1, withScores=1)
        self.assertEqual(self.delete(scores=True, expected=stale)['status'], 409)
        self.assertEqual(len([r for r in self.rows().values() if '_tri_lc' in r['metadata']]), 6)
        student = Client(self.app, 'testserver')
        student.login('aluno0', PASSWORD)
        body = dict(examId=self.exams[('Simulado 5', 'Azul')], scores=True, confirmation='EXCLUIR')
        self.assertEqual(student.request('/api/model-data/exam-delete-preview', body)['status'], 403)
        self.assertEqual(student.request('/api/model-data/exam-delete', body)['status'], 403)
        coord = Client(self.app, 'testserver')
        coord.login('coord.teste', PASSWORD)
        self.assertEqual(self.preview(client=coord)['scopes']['caderno']['results'], 2)

    def test_dashboards_see_the_deletion(self):
        with self.app.db.connection() as c:
            self.assertEqual(len(RS.STORE.records(self.app, c)), 6)
        self.assertEqual(self.delete(whole=True, answers=True)['status'], 200)
        with self.app.db.connection() as c:
            self.assertEqual(len(RS.STORE.records(self.app, c)), 3)


if __name__ == '__main__':
    unittest.main()
