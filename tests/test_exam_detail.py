"""Consulta de um caderno: gabarito, notas e respostas vinculadas. SQLite temporário."""
from pathlib import Path
import json
import sys
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parent))

import test_exam_delete as base
from verify_release import Client


class ExamDetailTests(base.ExamFixture):
    def detail(self, exam=('Simulado 5', 'Azul'), client=None):
        return (client or self.client).request('/api/model-data/exam-detail?examId=' + self.exams[exam])

    def test_detail_lists_answer_key_scores_and_answers(self):
        r = self.detail()
        self.assertEqual(r['status'], 200, r['data'])
        d = r['data']
        self.assertEqual((d['exam']['title'], d['exam']['color'], d['exam']['questions']), ('Simulado 5', 'Azul', 4))
        self.assertEqual([it['number'] for it in d['items']], [1, 2, 3, 4])
        self.assertEqual(d['items'][0]['answer'], 'A')
        self.assertEqual(d['summary']['results'], 2)
        self.assertEqual(d['summary']['withScores'], 2)
        first = d['students'][0]
        self.assertEqual(first['name'], 'Aluno 0')
        self.assertEqual((first['correct'], first['valid']), (2, 4))
        self.assertEqual(first['wrong'], [1, 3])
        self.assertEqual(first['areas']['LC'], {'correct': 1, 'valid': 2})
        self.assertEqual(first['areas']['MT'], {'correct': 1, 'valid': 2})
        self.assertEqual(first['scores']['lc'], 600)
        self.assertEqual(first['ranking'], 1)
        self.assertEqual(first['competencies'][0], 160)
        self.assertEqual(first['turma'], 'T1')

    def test_detail_without_scores_and_blank_questions(self):
        self.assertEqual(self.delete(scores=True)['status'], 200)
        with self.app.db.connection(write=True) as c:
            row = c.execute("SELECT id,metrics FROM hmay_performance WHERE id='r0'").fetchone()
            m = json.loads(row['metrics']); m['questao:004'] = {'correct': None, 'total': None}
            c.execute('UPDATE hmay_performance SET metrics=? WHERE id=?', (json.dumps(m), 'r0'))
        d = self.detail()['data']
        self.assertEqual(d['summary']['withScores'], 0)
        s = next(x for x in d['students'] if x['resultId'] == 'r0')
        self.assertFalse(s['hasScores'])
        self.assertEqual(s['blank'], [4])
        self.assertEqual((s['correct'], s['valid']), (1, 3))

    def test_detail_guards(self):
        self.assertEqual(self.client.request('/api/model-data/exam-detail?examId=nao-existe')['status'], 404)
        student = Client(self.app, 'testserver'); student.login('aluno0', base.PASSWORD)
        self.assertEqual(self.detail(client=student)['status'], 403)
        coord = Client(self.app, 'testserver'); coord.login('coord.teste', base.PASSWORD)
        self.assertEqual(self.detail(client=coord)['status'], 200)


if __name__ == '__main__':
    unittest.main()
