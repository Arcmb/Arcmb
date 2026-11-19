"""Correção de divergências das importações na interface (v3.17.0): respostas + gabarito,
notas TRI e mapa avulso. Planilhas XLSX reais, pedidos HTTP com login e SQLite temporário."""
from pathlib import Path
from tempfile import TemporaryDirectory
import base64
import json
import os
import sys
import unittest
from unittest import mock
sys.path.insert(0, str(Path(__file__).resolve().parents[1])); sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'checks'))

import import_fixes as IF
import model_data as M
import templates_v23 as T
from webapp import App
from verify_release import Client

PASSWORD = 'LocalFixture2026!'
SH = ['NOME', 'LOGIN', 'TURMA', 'NOME DO SIMULADO', 'DATA DE APLICAÇÃO', 'COR DA PROVA', 'L. ESTRANGEIRA', 6, 7, 8]
MH = ['NOME DO SIMULADO', 'DATA DE APLICAÇÃO', 'COR DA PROVA', 'QUESTÃO', 'ÁREA', 'DISCIPLINA', 'TÓPICO', 'ASSUNTO',
      'HABILIDADE', 'LÍNGUA ESTRANGEIRA', 'GABARITO']
TH = ['NOME', 'NOME DO SIMULADO', 'DATA DE APLICAÇÃO', 'TURMA', 'RANKING', 'NOTA TRI GERAL', 'TRI LINGUAGENS', 'TRI HUMANAS',
      'TRI NATUREZA', 'TRI MATEMÁTICA', 'C1', 'C2', 'C3', 'C4', 'C5', 'NOTA DA REDAÇÃO']


def b64(blob):
    return base64.b64encode(blob if isinstance(blob, (bytes, bytearray)) else blob[0]).decode()


def results_file(students, exam):
    blob, _ = T.export(SH, students, first_name=M.STUDENTS_SHEET, extra_sheets=[(M.EXAM_SHEET, MH, exam)])
    return {'filename': 'resultados.xlsx', 'file': b64(blob)}


GOOD_EXAM = [['Simulado X', '04/11/2026', 'AZUL', 6, 'LC', 'Português', 'T', 'A', 'H01', '', 'A'],
             ['Simulado X', '04/11/2026', 'AZUL', 7, 'MT', 'Matemática', 'T', 'A', 'H02', '', 'B'],
             ['Simulado X', '04/11/2026', 'AZUL', 8, 'MT', 'Matemática', 'T', 'A', 'H03', '', 'C']]


class ImportFixesTests(unittest.TestCase):
    def setUp(self):
        folder = TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        # A assinatura do pacote de notas TRI lê SECRET_KEY do ambiente.
        patcher = mock.patch.dict(os.environ, {'SECRET_KEY': os.environ.get('SECRET_KEY') or 'k' * 64})
        patcher.start(); self.addCleanup(patcher.stop)
        self.app = App({'LOCAL_TEST': '1', 'LOCAL_DB': str(Path(folder.name) / 'fixture.sqlite3')})
        self.app.db.initialize(self.app.owner, PASSWORD)
        with self.app.db.connection(write=True) as c:
            for login, name in (('ana', 'Ana Souza'), ('bia', 'Bia Lima'), ('caio', 'Caio Rocha')):
                self.app.db.create_user(c, login, name, PASSWORD, 'aluno', False)
            M._v36_classes_ensure(self.app, c)
            c.execute("INSERT INTO hmay_classes(id,name,norm,aliases,active,created_at,updated_at) VALUES ('t1','T1','t1','[]',1,'x','x')")
        self.client = Client(self.app, 'testserver')
        self.client.login('arcmb', PASSWORD)

    def post(self, path, body):
        return self.client.request(path, body)

    # ------------------------------------------------------------ respostas + gabarito

    def broken_results(self):
        students = [['Ana Souza', 'ana', 'T1', 'Simulado X', '04/11/2026', 'AZUL', '', 'A', 'B', 'C'],
                    ['Bia Lima', 'bia', 'turma um', 'Simulado  Y', '04/11/2026', 'AZUL', '', 'A', 'B', 'D'],
                    ['Caio Rocha', 'caio', 'turma um', 'Simulado X', '04/11/2026', 'VERDE', 'Francês', 'A', 'A', 'C'],
                    ['Ana Souza', 'ana', 'T1', 'Simulado X', '04/11/2026', 'AZUL', '', 'A', 'B', 'C']]
        exam = [list(r) for r in GOOD_EXAM]
        exam[1][4] = 'XX'        # área inválida
        exam[2][5] = ''          # disciplina vazia
        return results_file(students, exam)

    def test_results_lists_every_issue_with_location_and_options(self):
        r = self.post('/api/model-data/inspect', self.broken_results())
        self.assertEqual(r['status'], 400)
        issues = r['data']['issues']
        found = {(i['sheet'], i['line'], i['header']): i for i in issues}
        self.assertEqual(r['data']['total'], len(issues))
        self.assertEqual(found[(M.EXAM_SHEET, 3, 'ÁREA')]['options'], ['LC', 'CH', 'CN', 'MT'])
        self.assertEqual(found[(M.EXAM_SHEET, 4, 'DISCIPLINA')]['value'], '')
        self.assertEqual(found[(M.STUDENTS_SHEET, 4, 'COR DA PROVA')]['options'], ['AZUL'])
        self.assertIn('repetido', found[(M.STUDENTS_SHEET, 5, 'NOME')]['message'])
        self.assertEqual(found[(M.STUDENTS_SHEET, 3, 'NOME DO SIMULADO')]['suggest'], 'Simulado X')
        self.assertNotIn('suggest', found[(M.STUDENTS_SHEET, 4, 'COR DA PROVA')])
        self.assertIn('ÁREA', r['data']['error'] + ''.join(i['header'] for i in issues))

    def fixed_results(self):
        data = self.broken_results()
        data['fixes'] = [
            {'sheet': M.EXAM_SHEET, 'line': 3, 'col': 4, 'value': 'MT'},
            {'sheet': M.EXAM_SHEET, 'line': 4, 'col': 5, 'value': 'Matemática'},
            {'sheet': M.STUDENTS_SHEET, 'line': 3, 'col': 3, 'value': 'Simulado X'},
            {'sheet': M.STUDENTS_SHEET, 'line': 4, 'col': 5, 'value': 'AZUL'},
            {'sheet': M.STUDENTS_SHEET, 'line': 4, 'col': 6, 'value': ''},
            {'sheet': M.STUDENTS_SHEET, 'line': 5, 'skip': True},
        ]
        return data

    def test_class_name_is_replaced_in_every_row(self):
        data = self.fixed_results()
        r = self.post('/api/model-data/preview', {**data, 'date': '2026-11-04'})
        self.assertEqual(r['status'], 400, r['data'])
        replace = [i for i in r['data']['issues'] if i['kind'] == 'replace']
        self.assertEqual(len(replace), 1)
        self.assertEqual(replace[0]['value'], 'turma um')
        self.assertEqual(replace[0]['options'], ['T1'])
        self.assertIn('2 aluno(s)', replace[0]['message'])
        data['fixes'].append({'sheet': M.STUDENTS_SHEET, 'col': replace[0]['col'], 'from': 'turma um', 'to': 'T1'})
        r = self.post('/api/model-data/preview', {**data, 'date': '2026-11-04'})
        self.assertEqual(r['status'], 200, r['data'])
        self.assertEqual(r['data']['summary']['rows'], 3)
        self.assertEqual(r['data']['summary']['linked'], 3)
        self.last = (data, r['data'])

    def test_confirm_uses_the_same_fixes(self):
        self.test_class_name_is_replaced_in_every_row()
        data, preview = self.last
        body = {**data, 'date': '2026-11-04', 'token': preview['token'], 'mapping': preview['mapping']}
        without = {k: v for k, v in body.items() if k != 'fixes'}
        self.assertNotEqual(self.post('/api/model-data/confirm', without)['status'], 200)
        r = self.post('/api/model-data/confirm', body)
        self.assertEqual(r['status'], 200, r['data'])
        with self.app.db.connection() as c:
            rows = {x['user_id']: json.loads(x['metadata']) for x in c.execute('SELECT user_id,metadata FROM hmay_performance').fetchall()}
            items = json.loads(c.execute('SELECT items FROM hmay_exams').fetchone()['items'])
        self.assertEqual(len(rows), 3)
        self.assertEqual({md['TURMA'] for md in rows.values()}, {'T1'})
        self.assertEqual({i['number']: i['area'] for i in items}[7], 'MT')

    # ------------------------------------------------------------ notas TRI

    def tri_file(self, rows):
        blob = T.export(TH, rows, first_name='TRI e Redação')
        return {'filename': 'tri.xlsx', 'file': b64(blob), 'activityKey': M.F.norm('Simulado X'), 'date': '2026-11-04'}

    def test_tri_values_class_and_unmatched_names(self):
        self.test_confirm_uses_the_same_fixes()
        rows = [['Ana Souza', 'Simulado X', '04/11/2026', 'T1', 1, 700, 650, 640, 630, 620, 250, 160, 160, 160, 160, 800],
                ['Bia Lim', 'Simulado X', '04/11/2026', 'T1', 2, 690, 640, 630, 620, 610, 160, 160, 160, 160, 160, 900],
                ['Caio Rocha', 'Simulado X', '04/11/2026', 'Turma Zeta', 3, 680, 630, 620, 610, 600, 120, 120, 120, 120, 120, 600]]
        data = self.tri_file(rows)
        r = self.post('/api/model-data/tri-preview', data)
        self.assertEqual(r['status'], 400, r['data'])
        issues = r['data']['issues']
        by = {(i['line'], i['header']): i for i in issues if i['line']}
        self.assertIn('C1 deve estar entre 0 e 200', by[(2, 'C1')]['message'])
        self.assertEqual(by[(3, 'NOTA DA REDAÇÃO')]['options'], ['800'])
        self.assertEqual(by[(3, 'NOTA DA REDAÇÃO')]['suggest'], '800')       # palpite: a soma C1–C5
        self.assertNotIn('suggest', by[(2, 'C1')])
        zeta = [i for i in issues if i['kind'] == 'replace'][0]
        self.assertEqual((zeta['value'], zeta['options']), ('Turma Zeta', ['T1']))
        data['fixes'] = [{'sheet': 'TRI e Redação', 'line': 2, 'col': by[(2, 'C1')]['col'], 'value': '160'},
                         {'sheet': 'TRI e Redação', 'line': 3, 'col': by[(3, 'NOTA DA REDAÇÃO')]['col'], 'value': '800'},
                         {'sheet': 'TRI e Redação', 'col': zeta['col'], 'from': 'Turma Zeta', 'to': 'T1'}]
        r = self.post('/api/model-data/tri-preview', data)
        self.assertEqual(r['status'], 200, r['data'])
        self.assertEqual((r['data']['matched'], r['data']['unmatched']), (2, 1))
        name_issue = r['data']['issues'][0]
        self.assertEqual((name_issue['line'], name_issue['value']), (3, 'Bia Lim'))
        self.assertEqual(name_issue['options'][0], 'Bia Lima')        # o nome mais parecido vem primeiro
        data['fixes'].append({'sheet': 'TRI e Redação', 'line': 3, 'col': name_issue['col'], 'value': 'Bia Lima'})
        r = self.post('/api/model-data/tri-preview', data)
        self.assertEqual(r['status'], 200, r['data'])
        self.assertEqual((r['data']['matched'], r['data']['unmatched'], r['data']['issues']), (3, 0, []))
        done = self.post('/api/model-data/tri-confirm', {'importToken': r['data']['importToken']})
        self.assertEqual(done['status'], 200, done['data'])
        with self.app.db.connection() as c:
            scores = {x['activity'] + x['user_id']: json.loads(x['metadata']).get('_redaction_c1')
                      for x in c.execute('SELECT activity,user_id,metadata FROM hmay_performance').fetchall()}
        self.assertEqual(sorted(scores.values()), [120, 160, 160])

    # ------------------------------------------------------------ mapa avulso

    def test_standalone_map(self):
        headers = ['QUESTÃO', 'ÁREA', 'DISCIPLINA', 'TÓPICO', 'ASSUNTO', 'HABILIDADE', 'LÍNGUA ESTRANGEIRA', 'GABARITO']
        rows = [[1, 'LC', 'Português', '', '', 'H01', '', 'A'],
                [2, 'ZZ', 'Português', '', '', '', '', 'B'],
                [2, 'LC', 'Português', '', '', '', '', 'B'],
                [3, 'MT', 'Matemática', '', '', '', '', 'Q']]
        blob = T.export(headers, rows)
        data = {'filename': 'mapa.xlsx', 'file': b64(blob), 'title': 'Mapa Avulso', 'date': '2026-11-10', 'color': 'AZUL', 'area': ''}
        r = self.post('/api/exams/preview', data)
        self.assertEqual(r['status'], 400, r['data'])
        by = {(i['line'], i['header']): i for i in r['data']['issues']}
        self.assertEqual(set(by), {(3, 'ÁREA'), (5, 'GABARITO')})
        self.assertEqual(by[(5, 'GABARITO')]['options'], ['A', 'B', 'C', 'D', 'E', 'ANULADA', ''])
        sheet = by[(3, 'ÁREA')]['sheet']
        data['fixes'] = [{'sheet': sheet, 'line': 3, 'skip': True},
                         {'sheet': sheet, 'line': 5, 'col': by[(5, 'GABARITO')]['col'], 'value': 'C'}]
        r = self.post('/api/exams/preview', data)
        self.assertEqual(r['status'], 200, r['data'])
        done = self.post('/api/exams/confirm', {**data, 'token': r['data']['token']})
        self.assertEqual(done['status'], 200, done['data'])
        with self.app.db.connection() as c:
            items = json.loads(c.execute("SELECT items FROM hmay_exams WHERE title='Mapa Avulso'").fetchone()['items'])
        self.assertEqual([(i['number'], i['answer']) for i in items], [(1, 'A'), (2, 'B'), (3, 'C')])

    # ------------------------------------------------------------ regras gerais

    def test_fix_format_is_validated(self):
        for bad in ('x', [{'sheet': 'a'}], [{'sheet': 'a', 'line': 0, 'col': 1, 'value': 'x'}], [{'sheet': 'a', 'line': 2, 'col': -1}]):
            r = self.post('/api/model-data/inspect', {**self.broken_results(), 'fixes': bad})
            self.assertEqual(r['status'], 400)
            self.assertNotIn('issues', r['data'])

    def test_apply_helpers(self):
        rows = [['NOME', 'TURMA'], ['Ana', 'turma um'], ['Bia', 'Turma  UM'], ['Caio', 'T2']]
        fixed = IF.apply(rows, 'A', [{'sheet': 'A', 'col': 1, 'from': 'turma um', 'to': 'T1'},
                                     {'sheet': 'A', 'line': 4, 'skip': True},
                                     {'sheet': 'B', 'line': 2, 'col': 0, 'value': 'x'},
                                     {'sheet': 'A', 'line': 2, 'col': 3, 'value': 'novo'}])
        self.assertEqual(fixed, [['NOME', 'TURMA'], ['Ana', 'T1', None, 'novo'], ['Bia', 'T1'], [None, None]])
        self.assertEqual(rows[1], ['Ana', 'turma um'])     # a leitura original não é alterada
        self.assertEqual(IF.digest([]), '')
        self.assertNotEqual(IF.digest([{'sheet': 'A', 'line': 2, 'skip': True}]), '')


if __name__ == '__main__':
    unittest.main()
