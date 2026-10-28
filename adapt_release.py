"""Apply the objective-mapping extension after the import/access extension."""
from pathlib import Path
ROOT=Path(__file__).resolve().parent

def change(s,old,new):
    if s.count(old)!=1:raise RuntimeError('Unexpected source while applying objective mapping: '+old[:80])
    return s.replace(old,new)

def adapt():
    path=ROOT/'webapp.py';s=path.read_text(encoding='utf-8')
    s=change(s,'import performance as PERF','import performance as PERF\nimport adaptive as ADAPT')
    s=change(s,'                PERF.schema(self,c)','                PERF.schema(self,c)\n                ADAPT.schema(self,c)')
    s=change(s,"'performance.js':'application/javascript; charset=utf-8'","'performance.js':'application/javascript; charset=utf-8','adaptive.js':'application/javascript; charset=utf-8'")
    s=change(s,"            if path.startswith('/api/performance'):","            if path.startswith('/api/adaptive'):\n                return ADAPT.handle(self,c,user,path,method,data,query,start,HTTPError)\n            if path.startswith('/api/performance'):")
    s=change(s,"                p=P.action(json.loads(row['profile']),str(data.get('op','')),data.get('data',{}))", "                p=ADAPT.apply_action(self,c,user,target,json.loads(row['profile']),str(data.get('op','')),data.get('data',{}))")
    path.write_text(s,encoding='utf-8')
    path=ROOT/'planner.py';s=path.read_text(encoding='utf-8')
    s=change(s,'def generate(p,week_start,current=None):','def generate(p,week_start,current=None,mode="reorganize",bonuses=None):')
    old="    p['sessions']=[x for x in p['sessions'] if not(start<=x['date']<=end and x['status']=='planned' and not x.get('locked') and (x['date']>td or x['date']==td and x['start']>=mins))]"
    s=change(s,old,"    if mode not in ('fill','reorganize'):raise ValueError('Modo inválido.')\n    bonuses=bonuses or {}\n    if mode=='reorganize':\n    "+old)
    old="                    score=energy-8*day_used[d]/max(caps[d],1)-repetitions*4-delay*(20 if task.get('due') else .35)-t/10000"
    new=old+"\n                    slot_period='manha' if t<720 else 'tarde' if t<1080 else 'noite'\n                    score+=max(-3,min(3,float(bonuses.get(slot_period,0))))"
    s=change(s,old,new);path.write_text(s,encoding='utf-8')
    path=ROOT/'static/app.html';s=path.read_text(encoding='utf-8')
    s=change(s,'<script src="/static/performance.js" defer></script>','<script src="/static/performance.js" defer></script><script src="/static/adaptive.js" defer></script>')
    s=s.replace('v2.1','v2.2');path.write_text(s,encoding='utf-8')
    path=ROOT/'static/app.js';s=path.read_text(encoding='utf-8')
    s=change(s,"['diagnosis','Meu diagnóstico']","['mapping','Mapeamento objetivo'],['diagnosis','Observações pessoais']")
    s=change(s,'performance:performanceView};','performance:performanceView,mapping:mappingView};')
    # Keep the old free-text record without pretending to interpret it.
    s=s.replace("head('Meu diagnóstico'","head('Observações pessoais'")
    s=s.replace('Preencha o diagnóstico e confirme seus horários.','Preencha o mapeamento objetivo e confirme seus horários.')
    path.write_text(s,encoding='utf-8')
    path=ROOT/'verify_release.py';s=path.read_text(encoding='utf-8')
    if 'DELETE FROM hmay_adjustments WHERE actor_id' not in s:
        s=change(s,"            with app.db.connection(write=True) as conn:\n                for table, column", "            with app.db.connection(write=True) as conn:\n                app.db.execute(conn, 'DELETE FROM hmay_adjustments WHERE actor_id=? OR target_id=?', (test_id, test_id))\n                for table, column")
        path.write_text(s,encoding='utf-8')
    print('Meu Cronograma 2.2: objective mapping, preview confirmation and bounded adaptation prepared.')

if __name__=='__main__':adapt()
