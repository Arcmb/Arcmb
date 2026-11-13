"""Run after building the site: python -m unittest discover -s tests -p test_exam_metadata.py."""
from pathlib import Path
from tempfile import TemporaryDirectory
import base64
import json
import unittest

import exam_metadata as maps
import model_data
from webapp import App, HTTPError
from verify_release import Client


class MapMetadataTests(unittest.TestCase):
    def setUp(self):
        folder=TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.app=App({'LOCAL_TEST':'1','LOCAL_DB':str(Path(folder.name)/'fixture.sqlite3')})
        self.app.db.initialize(self.app.owner,'LocalFixture2026!')
        with self.app.db.connection(write=True) as c:
            self.user=dict(c.execute("SELECT id,role FROM hmay_users WHERE role='master'").fetchone())
            self.old_date='2026-06-07'
            self.date='2026-06-14'
            self.old_key=maps.identity_key('Simulado',self.old_date,'Azul')
            self.eid='md_'+self.old_key[:32]
            self.items=[dict(number=1,area='LC',language='',answer='A',discipline='Português',
                             topic='',subject='',skill='')]
            c.execute('INSERT INTO hmay_exams VALUES (?,?,?,?,?,?,?,?,?,?)',
                      (self.eid,self.old_key,self.user['id'],'Simulado',self.date,'Azul','',
                       json.dumps(self.items),1,self.date))
            student=self.app.db.create_user(c,'aluno.fixture','Aluno',None,'aluno')
            self.grades={'COR DA PROVA':'Azul','_exam_id':self.eid,'_tri_lc':610,'_tri_redaction':960}
            c.execute('INSERT INTO hmay_performance VALUES (?,?,?,?,?,?,?,?,?)',
                      ('r',student,'simulado','Simulado',self.date,'{}',json.dumps(self.grades),1,self.date))

    def test_coordinator_edits_and_complements_another_users_map(self):
        password = 'LocalCoordinator2026!'
        login = 'coordenacao.teste'
        with self.app.db.connection(write=True) as c:
            self.app.db.create_user(c, login, 'Coordenação', password, 'coordenador', False)
            self.app.db.create_user(c, 'estudante.teste', 'Estudante', password, 'aluno', False)
        staff = Client(self.app, 'testserver')
        staff.login(login, password)
        for path in ('/api/model-data/exam-edit-list', '/api/exams'):
            response = staff.request(path)
            self.assertEqual(response['status'], 200)
            self.assertTrue(response['data']['exams'][0]['canEdit'])
        change = dict(examId=self.eid, version=1, title='Simulado revisado', date=self.date,
                      color='Verde', area='CN')
        saved = staff.request('/api/model-data/exam-metadata-update', change)
        self.assertEqual(saved['status'], 200, saved['data'])
        self.assertEqual(saved['data']['updatedResults'], 1)

        csv = 'QUESTÃO;DISCIPLINA;ÁREA;GABARITO\n2;Química;CN;B\n'
        upload = dict(change, filename='complemento.csv', file=base64.b64encode(csv.encode()).decode())
        preview = staff.request('/api/exams/preview', upload)
        self.assertEqual(preview['status'], 200, preview['data'])
        commit = staff.request('/api/exams/confirm', dict(upload, token=preview['data']['token']))
        self.assertEqual(commit['status'], 200, commit['data'])
        with self.app.db.connection() as c:
            row = c.execute('SELECT owner_id,title,color,items FROM hmay_exams WHERE id=?',(self.eid,)).fetchone()
            self.assertEqual((row['owner_id'],row['title'],row['color']), (self.user['id'],change['title'],'Verde'))
            self.assertEqual([item['number'] for item in json.loads(row['items'])], [1,2])
        student = Client(self.app, 'testserver')
        student.login('estudante.teste', password)
        for path, body in (('/api/exams',None),('/api/model-data/exam-edit-list',None),
                           ('/api/exams/preview',upload),('/api/exams/confirm',upload),
                           ('/api/model-data/exam-metadata-update',change)):
            self.assertEqual(student.request(path,body)['status'], 403)

    def test_old_date_lookup_and_reuse(self):
        with self.app.db.connection(write=True) as c:
            spec={'title':'Simulado','color':'Azul','date':self.date,'items':self.items}
            exam,old,_,_=model_data._exam_prepare(self.app,c,self.user,spec,False)
            self.assertEqual(exam['id'],self.eid)
            self.assertEqual(old['id'],self.eid)
            spec['date']=self.old_date
            exam,old,_,_=model_data._exam_prepare(self.app,c,self.user,spec,False)
            self.assertIsNone(old)
            self.assertNotEqual(exam['id'],self.eid)
            maps.release_obsolete_key(self.app,c,self.old_key)
            row=c.execute('SELECT identity_key FROM hmay_exams WHERE id=?',(self.eid,)).fetchone()
            self.assertEqual(row[0],maps.identity_key('Simulado',self.date,'Azul'))

    def test_edit_preserves_results_and_individual_areas(self):
        data=dict(examId=self.eid,version=1,title='Simulado corrigido',date=self.old_date,color='Verde',area='CN')
        with self.app.db.connection(write=True) as c:
            saved=maps.update(self.app,c,self.user,data,HTTPError)
            self.assertEqual(saved['updatedResults'],1)
        with self.app.db.connection() as c:
            exam=c.execute('SELECT * FROM hmay_exams WHERE id=?',(self.eid,)).fetchone()
            result=c.execute("SELECT * FROM hmay_performance WHERE id='r'").fetchone()
            self.assertEqual((exam['area'],json.loads(exam['items'])),('CN',self.items))
            self.assertEqual((result['activity'],result['applied_on']),(data['title'],data['date']))
            self.assertEqual(json.loads(result['metadata']),{**self.grades,'COR DA PROVA':'Verde'})
        with self.assertRaises(HTTPError), self.app.db.connection(write=True) as c:
            maps.update(self.app,c,self.user,data,HTTPError)


if __name__=='__main__':
    unittest.main()
