"""Chromium UI exercise using real in-process WSGI with temporary test accounts."""
import sys,tempfile,json,re,base64
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1])); sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'checks'))
from webapp import App
from test_system import Browser
import planner as P
from playwright.sync_api import sync_playwright
R=Path(__file__).resolve().parents[1];checks=[];errors=[]
with tempfile.TemporaryDirectory() as tmp:
 app=App({'LOCAL_TEST':'1','LOCAL_DB':tmp+'/db','SECRET_KEY':'t'*64,'MASTER_PASSWORD':'TEST_master_13579'})
 master=Browser(app);assert master.login()['status']==303
 with app.db.connection(write=True)as c:
  app.db.create_user(c,'routine_ui','Aluno de demonstração','TEST_routine_1234','aluno',False)
  app.db.create_user(c,'routine_coord_ui','Coordenação de demonstração','TEST_routine_1234','coordenador',False)
 client=Browser(app);assert client.login('routine_ui','TEST_routine_1234')['status']==303
 with sync_playwright()as pw:
  browser=pw.chromium.launch(executable_path='/usr/bin/chromium',headless=True,args=['--no-sandbox'])
  page=browser.new_page(viewport={'width':1366,'height':900},locale='pt-BR');page.set_default_timeout(10000)
  page.on('pageerror',lambda e:errors.append(str(e)));page.on('dialog',lambda d:d.accept())
  def bridge(url,opts):
   r=client.request(url,json.loads(opts['body'])if opts.get('body')else None)
   return dict(status=r['status'],headers=r['headers'],body=base64.b64encode(r['raw']).decode())
  page.expose_function('test_wsgi',bridge)
  raw=(R/'static/app.html').read_text();scripts=re.findall(r'<script src="/static/([^"?]+)(?:\?[^\"]*)?" defer></script>',raw)
  html=re.sub(r'<script[^>]*>.*?</script>','',raw);html=re.sub(r'<link[^>]*>','',html)
  page.set_content(html);page.add_style_tag(content=(R/'static/style.css').read_text())
  page.add_script_tag(content="window.fetch=async(url,opts={})=>{const r=await window.test_wsgi(url,opts);return new Response(Uint8Array.from(atob(r.body),c=>c.charCodeAt(0)),{status:r.status,headers:r.headers});};")
  page.add_script_tag(content='\n'.join((R/'static'/n).read_text()for n in scripts))
  page.locator('[data-view=routine]').wait_for();page.locator('[data-view=routine]').click()
  assert page.locator('#routine-table-form').count()==1;checks.append('structured-routine-form')
  assert page.get_by_role('columnheader',name='Horário de início').count();checks.append('three-explicit-columns')
  assert client.state()['data']['profile']['fixed']==[];checks.append('no-example-autosave')
  page.locator('[data-entry-start]').fill('08:00');page.locator('[data-entry-end]').fill('12:00');page.locator('[data-entry-title]').fill('Trabalho')
  page.locator('[data-act=routine-add-entry]').click()
  row=page.locator('[data-routine-entry]').nth(1);row.locator('[data-entry-start]').fill('12:00');row.locator('[data-entry-end]').fill('13:00');row.locator('[data-entry-title]').fill('Almoço')
  page.locator('[data-act=routine-weekdays]').click();checks.append('multiple-activity-rows-and-days')
  page.locator('[name=routineAnchor]').fill(P.week(P.add(P.today(),7)))
  page.locator('[name=freeStatus0]').select_option('available')
  page.locator('[name=freeStart0]').fill('13:00');page.locator('[name=freeEnd0]').fill('18:00');checks.append('separate-start-end-free-time')
  page.locator('[data-free-day="0"] [data-act=routine-add-range]').click()
  page.locator('[name=freeStart0]').nth(1).fill('19:00');page.locator('[name=freeEnd0]').nth(1).fill('20:00');checks.append('multiple-free-periods')
  assert client.state()['data']['profile']['fixed']==[];checks.append('editing-not-saved-before-confirmation')
  page.locator('#routine-table-form button[type=submit]').click()
  page.wait_for_function("P.fixed.length===2 && !saving")
  after=client.state()['data']['profile'];assert len(after['fixed'])==2 and len(after['availability'][0]['ranges'])==2;checks.append('atomic-save-activities-and-availability')
  assert page.locator('.routine-saved-table').get_by_text('Trabalho',exact=True).count()==1;checks.append('saved-activities-in-table')
  other=Browser(app);other.login('routine_ui','TEST_routine_1234');assert other.state()['data']['profile']['fixed']==after['fixed'];checks.append('new-session-persistence')
  page.locator('[data-entry-start]').fill('17:00');page.locator('[data-entry-end]').fill('16:00');page.locator('[data-entry-title]').fill('Atividade inválida');page.locator('[name=routineDay0]').check()
  page.locator('#routine-table-form button[type=submit]').click();page.wait_for_function("document.querySelector('#routine-table-error').textContent.includes('término')")
  assert len(client.state()['data']['profile']['fixed'])==2;checks.append('invalid-time-inline-error-and-no-partial-save')
  page.locator('[data-act=routine-remove-entry]').click()
  page.locator('#routine-table-form button[type=submit]').click();page.wait_for_function("!saving && !dirty")
  page.locator('.routine-saved-table tr').filter(has_text='Trabalho').locator('[data-act=edit-fixed]').click()
  assert page.locator('#modal-form [name=start]').input_value()=='08:00';page.locator('#close-dialog').click();checks.append('existing-detailed-edit-preserved')
  page.locator('[data-entry-start]').fill('08:00');page.locator('[data-entry-end]').fill('12:00');page.locator('[data-entry-title]').fill('Trabalho')
  page.locator('#routine-table-form > section').first.evaluate('(el)=>window.scrollTo(0,scrollY+el.getBoundingClientRect().top-100)')
  page.locator('#routine-table-form > section').first.screenshot(path='/mnt/data/MEU_CRONOGRAMA_V241_ROTINA_HORARIOS.png')
  page.set_viewport_size({'width':390,'height':844})
  assert page.evaluate('document.documentElement.scrollWidth<=innerWidth+2');checks.append('mobile-390px-no-page-overflow')
  page.locator('#routine-table-form > section').first.evaluate('(el)=>window.scrollTo(0,scrollY+el.getBoundingClientRect().top-100)')
  page.locator('#routine-table-form > section').first.screenshot(path='/mnt/data/MEU_CRONOGRAMA_V241_ROTINA_CELULAR.png')
  # Coordinator uses the same screen for an authorized student's routine.
  uid=client.user['id'];coord=Browser(app);coord.login('routine_coord_ui','TEST_routine_1234')
  d={'settings':after['settings'],'availability':after['availability'],'entries':[{'start':'20:00','end':'20:30','title':'Organizar materiais'}],'days':[1],'recurrence':'weekly','anchor':P.today()}
  assert coord.action('routine_table',d,uid)['status']==200;checks.append('coordinator-can-save-student-routine')
  assert not errors,errors;checks.append('no-js-errors')
  browser.close()
print('ROUTINE_UI_OK: '+str(len(checks))+' checks; '+', '.join(checks)+'. Chromium + real WSGI, not physical iPhone.')
