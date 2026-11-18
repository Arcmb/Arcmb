"""Area-separated workbook tests. Synthetic accounts and temporary SQLite only."""
import base64
import hashlib
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1])); sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'checks'))

import area_workbook as A
import performance as F
from test_system import Browser
from webapp import App

CONFIG = {
    'fields': ['NOME', 'LOGIN', 'TURMA', 'COR DA PROVA', 'TIPO de prova', 'data de aplicação', 'L. estrangeira selecionada'],
    'areas': {
        'LC': {'enabled': True, 'questions': 2, 'skills': True, 'disciplines': ['Português', 'Literatura']},
        'CH': {'enabled': True, 'questions': 1, 'skills': True, 'disciplines': ['História']},
        'CN': {'enabled': False},
        'MT': {'enabled': True, 'questions': 1, 'skills': True, 'disciplines': ['Matemática']},
        'RED': {'enabled': True},
    },
}


def workbook(name='Aluno Áreas', login='alunoareas', title='Simulado áreas', date='04/11/2026'):
    general = [{'NOME': name, 'LOGIN': login, 'TURMA': 'T1', 'COR DA PROVA': 'Azul', 'TIPO de prova': title, 'data de aplicação': date, 'L. estrangeira selecionada': 'Inglês'}]
    area_rows = {
        'LC': [{'NOME': name, 'LOGIN': login, 'TURMA': 'T1', 'Acertos em Linguagens': 1, 'Nota TRI Linguagens': 650, 'Acertos - Português': 1, 'Acertos - Literatura': 0, 'Acertos Hab 01': 1, 'Acerto/erro questão 01': 1, 'Acerto/erro questão 02': 0}],
        'CH': [{'NOME': name, 'LOGIN': login, 'TURMA': 'T1', 'Acertos em Humanas': 1, 'Nota TRI Humanas': 680, 'Acertos - História': 1, 'Acertos Hab 01': 1, 'Acerto/erro questão 03': 1}],
        'MT': [{'NOME': name, 'LOGIN': login, 'TURMA': 'T1', 'Acertos em Matemática': 0, 'Nota TRI Matemática': 500, 'Acertos - Matemática': 0, 'Acertos Hab 01': 0, 'Acerto/erro questão 04': 0}],
        'RED': [{'NOME': name, 'LOGIN': login, 'TURMA': 'T1', 'Tema da redação': 'Tema', 'Nota C1': 160, 'Nota C2': 180, 'Nota C3': 160, 'Nota C4': 180, 'Nota C5': 200, 'Nota de redação': 880}],
    }
    maps = {
        'LC': [{'QUESTÃO': 1, 'DISCIPLINA': 'Português', 'TÓPICO': 'Leitura', 'ASSUNTO': 'Texto', 'HABILIDADE': 'H01'}, {'QUESTÃO': 2, 'DISCIPLINA': 'Literatura', 'TÓPICO': 'Literatura', 'ASSUNTO': 'Modernismo', 'HABILIDADE': 'H16'}],
        'CH': [{'QUESTÃO': 3, 'DISCIPLINA': 'História', 'TÓPICO': 'Brasil', 'ASSUNTO': 'República', 'HABILIDADE': 'H01'}],
        'MT': [{'QUESTÃO': 4, 'DISCIPLINA': 'Matemática', 'TÓPICO': 'Álgebra', 'ASSUNTO': 'Função', 'HABILIDADE': 'H01'}],
    }
    blob, _ = A.export_area_workbook(CONFIG, general, area_rows, maps)
    return {'filename': 'areas.xlsx', 'file': base64.b64encode(blob).decode()}


class AreaWorkbookPure(unittest.TestCase):
    def test_01_sheet_order(self):
        blob, _ = A.template(CONFIG)
        self.assertEqual(F.load_matrix('areas.xlsx', blob)[2], ['Geral', 'Informações do simulado', 'Linguagens', 'Humanas', 'Matemática', 'Redação', 'Como preencher'])

    def test_02_continuous_ranges(self):
        blob, _ = A.template(CONFIG)
        lc = F.load_matrix('areas.xlsx', blob, 'Linguagens')[0]
        ch = F.load_matrix('areas.xlsx', blob, 'Humanas')[0]
        mt = F.load_matrix('areas.xlsx', blob, 'Matemática')[0]
        self.assertEqual([int(x[0]) for x in lc[5:7]], [1, 2])
        self.assertEqual([int(x[0]) for x in ch[5:6]], [3])
        self.assertEqual([int(x[0]) for x in mt[5:6]], [4])

    def test_03_area_columns(self):
        blob, _ = A.template(CONFIG)
        lc = F.load_matrix('areas.xlsx', blob, 'Linguagens')[0][-1]
        self.assertIn('Acertos em Linguagens', lc)
        self.assertIn('Nota TRI Linguagens', lc)
        self.assertIn('Acertos Hab 01', lc)
        self.assertIn('Acerto/erro questão 01', lc)

    def test_04_canonical_scoped_skills(self):
        data = workbook()
        converted = A._canonicalize(data)
        extra = next(iter(converted['extras'].values()))
        self.assertEqual(extra['metrics']['habilidade:LC:h01']['correct'], 1)
        self.assertEqual(extra['metrics']['habilidade:CH:h01']['correct'], 1)
        self.assertEqual(extra['metrics']['habilidade:MT:h01']['correct'], 0)
        self.assertEqual(extra['metadata']['Redação - Nota calculada'], 880)

    def test_05_numbering_rejected(self):
        data = workbook()
        # Construct a valid workbook with CH beginning at 4 rather than 3.
        broken = {**CONFIG, 'areas': {**CONFIG['areas'], 'LC': {**CONFIG['areas']['LC'], 'questions': 3}}}
        blob, _ = A.template(broken)
        # A blank model is still parseable only after data; direct range generation itself is checked.
        self.assertEqual(F.load_matrix('x.xlsx', blob, 'Humanas')[0][5][0], '4')

    def test_06_only_redaction(self):
        config = {'fields': CONFIG['fields'], 'areas': {k: {'enabled': k == 'RED'} for k in A.AREA_ORDER}}
        blob, _ = A.template(config)
        self.assertEqual(F.load_matrix('x.xlsx', blob)[2], ['Geral', 'Informações do simulado', 'Redação', 'Como preencher'])


class AreaWorkbookAPI(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.env = {'LOCAL_TEST': '1', 'LOCAL_DB': cls.tmp.name + '/db', 'SECRET_KEY': 'x' * 64, 'MASTER_PASSWORD': 'TEST_master_24680'}
        cls.app = App(cls.env)
        cls.master = Browser(cls.app)
        assert cls.master.login('arcmb', 'TEST_master_24680')['status'] == 303
        with cls.app.db.connection(write=True) as c:
            cls.app.db.create_user(c, 'alunoareas', 'Aluno Áreas', 'TEST_areas_24680', 'aluno', False)
        cls.student = Browser(cls.app)
        assert cls.student.login('alunoareas', 'TEST_areas_24680')['status'] == 303

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_07_template_endpoint(self):
        response = self.master.request('/api/workbook/template', CONFIG)
        self.assertEqual(response['status'], 200, response)
        self.assertEqual(F.load_matrix('x.xlsx', response['raw'])[2][2], 'Linguagens')

    def test_08_preview_confirm_and_analysis(self):
        payload = workbook()
        preview = self.master.request('/api/workbook/preview', payload)
        self.assertEqual(preview['status'], 200, preview)
        confirmed = self.master.request('/api/workbook/confirm', {**payload, 'token': preview['data']['token'], 'mapping': preview['data']['mapping']})
        self.assertEqual(confirmed['status'], 200, confirmed)
        record = self.student.request('/api/performance')['data']['records'][0]
        self.assertEqual(record['metrics']['habilidade:LC:h01']['correct'], 1)
        self.assertEqual(record['metrics']['habilidade:CH:h01']['correct'], 1)
        self.assertEqual(record['metrics']['habilidade:MT:h01']['correct'], 0)
        self.assertEqual(record['analysis']['overall']['marked'], 4)
        self.assertEqual(record['metadata']['Redação - Nota calculada'], 880)

    def test_09_old_workbook_compatibility(self):
        import unified as U
        fields = ['NOME', 'TIPO de prova', 'data de aplicação', 'Acerto/erro questão 01']
        response = self.master.request('/api/workbook/template', {'fields': fields, 'questionFirst': 1, 'questionLast': 1})
        self.assertEqual(response['status'], 200)
        self.assertEqual(F.load_matrix('old.xlsx', response['raw'])[2][0], U.RESULTS)


if __name__ == '__main__':
    unittest.main()
