"""Armazém compartilhado de resultados (results_store). SQLite temporário e dados sintéticos."""
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import results_store as RS
from webapp import App


def metrics(n=180, nulls=(), responses=False):
    out = {}
    for q in range(1, n + 1):
        key = 'questao:%03d' % q
        if q in nulls:
            out[key] = {'name': 'Questão %02d' % q, 'correct': None, 'total': None}
        else:
            out[key] = {'name': 'Questão %02d' % q, 'correct': q % 2, 'total': 1}
            if responses:
                out[key]['response'] = '' if q % 7 == 0 else 'ABCDE'[q % 5]
    return out


def without_names(data):
    return {k: {f: v for f, v in item.items() if f != 'name'} for k, item in data.items()}


class CompactFormatTest(unittest.TestCase):
    def roundtrip(self, data):
        row = {'id': 'p1', 'user_id': 'u1', 'activity_key': 'k', 'activity': 'A', 'applied_on': '2026-01-01',
               'metrics': json.dumps(data), 'metadata': '{"TURMA":"T1"}'}
        return RS.Record(row, {})

    def test_plain_answers_are_compacted_and_restored(self):
        data = metrics()
        rec = self.roundtrip(data)
        self.assertIsNone(rec._raw)
        self.assertEqual(len(rec._data), 3 * 180)
        self.assertEqual(rec.metrics(), without_names(data))

    def test_null_and_responses_are_kept(self):
        data = metrics(nulls=(77, 90), responses=True)
        rec = self.roundtrip(data)
        self.assertIsNone(rec._raw)
        self.assertEqual(rec.metrics(), without_names(data))
        self.assertIsNone(rec.metrics()['questao:077']['correct'])
        self.assertEqual(rec.metrics()['questao:007']['response'], '')

    def test_unusual_format_is_kept_as_is(self):
        data = metrics(5)
        data['extra'] = {'name': 'Bônus', 'correct': 3, 'total': 5, 'nota': 'x'}
        rec = self.roundtrip(data)
        self.assertEqual(rec.metrics(), data)

    def test_question_keys_are_shared_between_records(self):
        cache = {}
        row = {'id': 'p', 'metrics': json.dumps(metrics()), 'metadata': '{}'}
        a, b = RS.Record(row, cache), RS.Record(dict(row, id='q'), cache)
        self.assertIs(a._keys, b._keys)


class StoreRefreshTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        env = dict(os.environ, LOCAL_TEST='1', LOCAL_DB=str(Path(self.tmp.name) / 'store.sqlite3'),
                   SECRET_KEY='x' * 64, MASTER_PASSWORD='senha-local-123', ALLOWED_HOSTS='meucronograma.onrender.com')
        self.app = App(env)
        self.app.db.initialize(self.app.owner, env['MASTER_PASSWORD'], '')
        self.store = RS.Store()
        with self.app.db.connection(write=True) as c:
            self.app.db.execute(c, "INSERT INTO hmay_users VALUES ('u1','aluno1','Aluno','x','aluno',1,0,'t')", ())
            for i in range(RS.PAGE + 5):  # mais de um lote
                self.insert(c, 'p%04d' % i, 'k%d' % i, '2026-02-%02d' % (1 + i % 28), '2026-01-01T00:00:%02d' % (i % 60))

    def tearDown(self):
        self.tmp.cleanup()

    def insert(self, c, pid, key, date, stamp):
        self.app.db.execute(c, 'INSERT INTO hmay_performance VALUES (?,?,?,?,?,?,?,?,?)',
                            (pid, 'u1', key, 'Simulado ' + key, date, json.dumps(metrics(4)), '{"TURMA":"T1"}', 1, stamp))

    def records(self):
        with self.app.db.connection() as c:
            return self.store.records(self.app, c)

    def test_reads_every_page_sorted_by_date(self):
        recs = self.records()
        self.assertEqual(len(recs), RS.PAGE + 5)
        self.assertEqual([r.date for r in recs], sorted(r.date for r in recs))

    def test_same_data_reuses_the_copy(self):
        self.assertIs(self.records(), self.records())

    def test_insert_update_and_delete_refresh_the_copy(self):
        first = self.records()
        with self.app.db.connection(write=True) as c:
            self.insert(c, 'z9999', 'novo', '2026-03-01', '2026-11-19T10:00:00')
        second = self.records()
        self.assertIsNot(first, second)
        self.assertEqual(len(second), len(first) + 1)
        with self.app.db.connection(write=True) as c:
            self.app.db.execute(c, "UPDATE hmay_performance SET metadata='{\"TURMA\":\"T2\"}',updated_at='2026-11-19T11:00:00' WHERE id='p0000'", ())
        third = self.records()
        self.assertEqual(next(r for r in third if r.id == 'p0000').md['TURMA'], 'T2')
        with self.app.db.connection(write=True) as c:
            self.app.db.execute(c, "DELETE FROM hmay_performance WHERE id='z9999'", ())
        self.assertEqual(len(self.records()), len(first))

    def test_accuracy_uses_exam_area_map_and_default_ranges(self):
        rec = self.records()[0]
        acc = self.store.accuracy(rec, {})
        self.assertEqual(acc['ALL'], {'correct': 2, 'valid': 4})
        self.assertEqual(acc['LC'], {'correct': 2, 'valid': 4})
        maps = {'': {1: 'MT', 2: 'MT'}}
        acc = self.store.accuracy(rec, maps)
        self.assertEqual(acc['MT'], {'correct': 1, 'valid': 2})
        self.assertIs(self.store.accuracy(rec, maps), acc)


if __name__ == '__main__':
    unittest.main()


class SeparateDatabasesTest(unittest.TestCase):
    def test_copy_is_never_shared_between_databases(self):
        store = RS.Store()
        seen = []
        for name in ('a', 'b'):
            tmp = tempfile.TemporaryDirectory()
            self.addCleanup(tmp.cleanup)
            env = dict(os.environ, LOCAL_TEST='1', LOCAL_DB=str(Path(tmp.name) / 'db.sqlite3'),
                       SECRET_KEY='x' * 64, MASTER_PASSWORD='senha-local-123', ALLOWED_HOSTS='meucronograma.onrender.com')
            app = App(env)
            app.db.initialize(app.owner, env['MASTER_PASSWORD'], '')
            with app.db.connection(write=True) as c:
                app.db.execute(c, "INSERT INTO hmay_users VALUES ('u1','aluno1','Aluno','x','aluno',1,0,'t')", ())
                # Mesma contagem e mesma data de alteração nos dois bancos.
                app.db.execute(c, 'INSERT INTO hmay_performance VALUES (?,?,?,?,?,?,?,?,?)',
                               ('p1', 'u1', 'k', 'Simulado ' + name, '2026-01-01', '{}', '{}', 1, '2026-01-01T00:00:00'))
            with app.db.connection() as c:
                seen.append(store.records(app, c)[0].activity)
        self.assertEqual(seen, ['Simulado a', 'Simulado b'])
