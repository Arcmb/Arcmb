"""Structured routine, validation, permissions and schedule regressions."""
import copy
import tempfile
import unittest
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1])); sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'checks'))
import planner as P
from routine_entries import save_table
from webapp import App
from test_system import Browser


class RoutineTableTests(unittest.TestCase):
    def setUp(self):
        self.p=P.default_profile('Teste rotina')
        self.anchor=P.add(P.week(P.add(P.today(),7)),1)  # segunda-feira (a semana começa no domingo desde a v3.7.18)
        self.data=dict(settings=copy.deepcopy(self.p['settings']),availability=copy.deepcopy(self.p['availability']),
                       entries=[dict(start='08:00',end='12:00',title='Trabalho'),dict(start='12:00',end='13:00',title='Almoço')],
                       days=[0,1,2,3,4],recurrence='weekly',anchor=self.anchor)
    def test_01_batch_and_original_unchanged(self):
        result=save_table(self.p,self.data)
        self.assertEqual(len(result['fixed']),2);self.assertEqual(self.p['fixed'],[])
        self.assertEqual(result['fixed'][0]['days'],[0,1,2,3,4])
        self.assertEqual(result['fixed'][0]['title'],'Trabalho')
    def test_02_no_inferred_availability(self):
        result=save_table(self.p,self.data)
        self.assertTrue(all(a['status']=='unknown' for a in result['availability']))
        self.assertEqual(P.free(result,self.anchor),[])
    def test_03_free_windows_subtract_activities(self):
        self.data['availability'][0]=dict(day=0,status='available',ranges=[dict(start='08:00',end='18:00')])
        result=save_table(self.p,self.data);self.assertEqual(P.free(result,self.anchor),[[780,1080]])
    def test_04_blank_rows_ignored(self):
        self.data['entries'].append(dict(start='',end='',title=''))
        self.assertEqual(len(save_table(self.p,self.data)['fixed']),2)
    def test_05_partial_row_rejected_atomic(self):
        self.data['entries'].append(dict(start='15:00',end='',title='Aula'))
        with self.assertRaisesRegex(ValueError,'preencha'):save_table(self.p,self.data)
        self.assertEqual(self.p['fixed'],[])
    def test_06_invalid_and_reversed_times(self):
        for start,end in [('8:00','12:00'),('24:00','12:00'),('11:00','08:00'),('08:00','08:00')]:
            with self.subTest(start=start,end=end):
                self.data['entries']=[dict(start=start,end=end,title='Teste')]
                with self.assertRaises(ValueError):save_table(self.p,self.data)
    def test_07_days_required(self):
        for days in ([],[True],[7],[0,0],'segunda'):
            self.data['days']=days
            with self.assertRaises(ValueError):save_table(self.p,self.data)
    def test_08_once_uses_date_not_weekdays(self):
        self.data.update(recurrence='once',days=[])
        result=save_table(self.p,self.data);self.assertEqual(result['fixed'][0]['days'],[0])
        self.assertTrue(P.occurs(result['fixed'][0],self.anchor));self.assertFalse(P.occurs(result['fixed'][0],P.add(self.anchor,7)))
    def test_09_independent_fortnightly(self):
        self.data['recurrence']='biweekly';r=save_table(self.p,self.data);f=r['fixed'][0]
        self.assertTrue(P.occurs(f,self.anchor));self.assertFalse(P.occurs(f,P.add(self.anchor,7)));self.assertTrue(P.occurs(f,P.add(self.anchor,14)))
    def test_10_exact_duplicate_not_duplicated(self):
        r=save_table(self.p,self.data);rr=save_table(r,self.data)
        self.assertEqual(len(rr['fixed']),2);self.assertEqual([x['id'] for x in rr['fixed']],[x['id'] for x in r['fixed']])
    def test_11_settings_only_without_entries(self):
        self.data.update(entries=[],days=[],anchor='')
        self.data['settings']['weeklyGoal']=450
        self.assertEqual(save_table(self.p,self.data)['settings']['weeklyGoal'],450)
    def test_12_missing_free_range_or_overlap_rejected(self):
        self.data['availability'][0]['status']='available'
        with self.assertRaisesRegex(ValueError,'horário livre'):save_table(self.p,self.data)
        self.data['availability'][0]['ranges']=[dict(start='13:00',end='15:00'),dict(start='14:00',end='16:00')]
        with self.assertRaisesRegex(ValueError,'sobrepostos'):save_table(self.p,self.data)
    def test_13_future_study_schedule_preserved(self):
        sid=P.uid();self.p['subjects']=[dict(id=sid,name='Matemática',action='Exercícios',kind='study',active=True,weeklyMin=120,difficulty=3,importance=3,examDate='')]
        self.p['sessions']=[dict(id=P.uid(),subjectId=sid,contentId='',title='Estudar',date=self.anchor,start=540,end=570,kind='study',status='planned',locked=True)]
        self.p['planMeta']={'dirty':False};r=save_table(self.p,self.data)
        self.assertEqual(r['sessions'],self.p['sessions']);self.assertTrue(r['planMeta']['dirty'])
    def test_14_unknown_keys_and_too_many_rows(self):
        self.data['role']='master'
        with self.assertRaises(ValueError):save_table(self.p,self.data)
        del self.data['role'];self.data['entries']*=26
        with self.assertRaises(ValueError):save_table(self.p,self.data)
    def test_15_saved_sleep_and_preexisting_overnight_kept(self):
        self.p['fixed']=[dict(id=P.uid(),start='22:00',end='02:00',title='Plantão',category='Trabalho',days=[5],recurrence='weekly',anchor=self.anchor,until='',before=0,after=0)]
        r=save_table(self.p,self.data)
        self.assertEqual(r['fixed'][0],self.p['fixed'][0]);self.assertEqual({k:v for k,v in r['settings'].items() if k!='reviewStartDate'},self.p['settings'])
    def test_16_bad_title_date_and_recurrence(self):
        for k,v in [('anchor','2026-99-00'),('recurrence','monthly')]:
            d=copy.deepcopy(self.data);d[k]=v
            with self.assertRaises(ValueError):save_table(self.p,d)
        self.data['entries'][0]['title']='x'*251
        with self.assertRaises(ValueError):save_table(self.p,self.data)


class RoutineTableWebTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp=tempfile.TemporaryDirectory();cls.app=App({'LOCAL_TEST':'1','LOCAL_DB':cls.temp.name+'/db','SECRET_KEY':'r'*64,'MASTER_PASSWORD':'TEST_master_13579'})
        cls.master=Browser(cls.app);assert cls.master.login()['status']==303
        cls.clients={}
        with cls.app.db.connection(write=True) as c:
            for role in ('coordenador','aluno','especial'):
                cls.app.db.create_user(c,'routine_'+role,role,'TEST_routine_1234',role,False)
        for role in ('coordenador','aluno','especial'):
            b=Browser(cls.app);assert b.login('routine_'+role,'TEST_routine_1234')['status']==303;cls.clients[role]=b
    @classmethod
    def tearDownClass(cls):cls.temp.cleanup()
    def payload(self,client,target=None):
        p=client.state(target)['data']['profile']
        return dict(settings=p['settings'],availability=p['availability'],entries=[dict(start='08:00',end='09:00',title='Atividade '+P.uid())],days=[0],recurrence='weekly',anchor=P.today())
    def test_17_student_own_and_persisted(self):
        b=self.clients['aluno'];d=self.payload(b);r=b.action('routine_table',d)
        self.assertEqual(r['status'],200,r)
        other=Browser(self.app);other.login('routine_aluno','TEST_routine_1234')
        self.assertIn(d['entries'][0]['title'],[x['title'] for x in other.state()['data']['profile']['fixed']])
    def test_18_coordinator_student_and_audit(self):
        b=self.clients['coordenador'];uid=self.clients['aluno'].user['id'];r=b.action('routine_table',self.payload(b,uid),uid)
        self.assertEqual(r['status'],200,r)
        h=b.request('/api/adaptive?user='+uid)['data']['history'];self.assertEqual(h[0]['kind'],'routine_table')
    def test_19_master_special_allowed(self):
        uid=self.clients['especial'].user['id'];r=self.master.action('routine_table',self.payload(self.master,uid),uid)
        self.assertEqual(r['status'],200,r)
    def test_20_other_account_and_special_denied(self):
        for b,target in [(self.clients['aluno'],self.master.user['id']),(self.clients['coordenador'],self.clients['especial'].user['id'])]:
            r=b.request('/api/action',dict(user=target,version=1,op='routine_table',data=self.payload(b)))
            self.assertEqual(r['status'],403,r)
    def test_21_csrf_and_concurrency(self):
        b=self.clients['aluno'];state=b.state()['data'];data=dict(user=b.user['id'],version=state['version'],op='routine_table',data=self.payload(b))
        self.assertEqual(b.request('/api/action',data,csrf=False)['status'],403)
        self.assertEqual(b.request('/api/action',data)['status'],200)
        self.assertEqual(b.request('/api/action',data)['status'],409)
    def test_22_atomic_invalid_does_not_update(self):
        b=self.clients['aluno'];before=b.state()['data'];d=self.payload(b);d['entries'].append(dict(start='',end='12:00',title='Erro'))
        self.assertEqual(b.action('routine_table',d)['status'],400)
        self.assertEqual(b.state()['data']['version'],before['version'])

if __name__=='__main__':unittest.main()
