"""Chromium interface + real WSGI application, synthetic SQLite accounts."""
import sys, tempfile, json, re, base64
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1])); sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'checks'))
from webapp import App
from test_system import Browser
from playwright.sync_api import sync_playwright
R=Path(__file__).resolve().parents[1]
checks=[];errors=[]
with tempfile.TemporaryDirectory() as tmp:
 app=App({'LOCAL_TEST':'1','LOCAL_DB':tmp+'/db','SECRET_KEY':'b'*64,'MASTER_PASSWORD':'TEST_master_13579'})
 master=Browser(app);assert master.login()['status']==303
 with app.db.connection(write=True) as c:
  app.db.create_user(c,'coord_ui','Coordenação Teste','TEST_coord_1234','coordenador',False)
  app.db.create_user(c,'special_ui','Conta especial de teste','TEST_special_1234','especial',False)
 client=Browser(app);assert client.login('coord_ui','TEST_coord_1234')['status']==303
 with sync_playwright() as pw:
  browser=pw.chromium.launch(executable_path='/usr/bin/chromium',headless=True,args=['--no-sandbox'])
  page=browser.new_page(viewport={'width':1366,'height':900});page.set_default_timeout(8000)
  page.on('pageerror',lambda e:errors.append(str(e)));page.on('dialog',lambda d:d.accept())
  def bridge(url,opts):
   data=json.loads(opts['body']) if opts.get('body') else None
   r=client.request(url,data)
   return dict(status=r['status'],headers=r['headers'],body=base64.b64encode(r['raw']).decode())
  page.expose_function('test_wsgi',bridge)
  html=(R/'static/app.html').read_text();html=re.sub(r'<script[^>]*>.*?</script>','',html);html=re.sub(r'<link[^>]*>','',html)
  page.set_content(html);page.add_style_tag(content=(R/'static/style.css').read_text())
  page.add_script_tag(content="window.fetch=async(url,opts={})=>{const r=await window.test_wsgi(url,opts);return new Response(Uint8Array.from(atob(r.body),c=>c.charCodeAt(0)),{status:r.status,headers:r.headers});};")
  page.add_script_tag(content='\n'.join((R/'static'/n).read_text() for n in ('app.js','performance.js','adaptive.js','selective.js','import_wizard.js','coordinator_accounts.js')))
  page.locator('[data-view=accounts]').wait_for();page.locator('[data-view=accounts]').click()
  page.get_by_role('button',name='Cadastrar aluno',exact=True).wait_for();checks.append('coordinator-create-button')
  assert 'Conta especial de teste' not in page.locator('#main').inner_text();checks.append('special-account-hidden')
  assert page.locator('[data-act=edit-account]').count()==0;checks.append('no-access-administration')
  page.locator('[data-act=coordinator-new-student]').click()
  assert page.locator('#modal-form [name=role]').count()==0;assert 'Perfil fixo: Aluno' in page.locator('#dialog-body').inner_text();checks.append('fixed-student-role')
  page.locator('#modal-form [name=name]').fill('Aluno criado pela coordenação')
  page.locator('#modal-form [name=username]').fill('aluno_ui')
  page.locator('#modal-form [name=password]').fill('TEST_provisoria_1234')
  page.locator('#modal-form button[type=submit]').click();page.wait_for_function("!document.querySelector('#dialog').open")
  page.locator('#main .item').filter(has_text='Aluno criado pela coordenação').wait_for();checks.append('creation-persisted-and-list-refreshed')
  entries=master.request('/api/accounts')['data']['accounts'];student=next(x for x in entries if x['username']=='aluno_ui')
  assert student['role']=='aluno' and student['must_change']==1;checks.append('server-role-and-temporary-password')
  assert page.locator('#dialog-body [name=password]').count()==0;checks.append('password-not-retained-in-form')
  page.locator('[data-act=coordinator-new-student]').click()
  page.locator('#modal-form [name=name]').fill('Tentativa duplicada');page.locator('#modal-form [name=username]').fill('aluno_ui');page.locator('#modal-form [name=password]').fill('TEST_other_1234')
  page.locator('#modal-form button[type=submit]').click();page.wait_for_function("document.querySelector('#modal-error').textContent.includes('já está em uso')");checks.append('duplicate-inline-error')
  page.locator('#close-dialog').click()
  page.locator('#main .item').filter(has_text='Aluno criado pela coordenação').locator('[data-act=open-account]').click()
  page.wait_for_function("document.querySelector('#master-note').textContent.includes('Aluno criado pela coordenação')");checks.append('open-created-student-planning')
  page.locator('[data-view=accounts]').click();page.set_viewport_size({'width':390,'height':844});page.locator('[data-act=coordinator-new-student]').click()
  assert page.evaluate('document.documentElement.scrollWidth <= innerWidth+2');checks.append('mobile-390px-no-overflow')
  page.screenshot(path='/mnt/data/MEU_CRONOGRAMA_V241_CADASTRAR_ALUNO.png',full_page=True)
  page.locator('#close-dialog').click()
  page.set_viewport_size({'width':1366,'height':900});page.evaluate('window.scrollTo(0,0)')
  page.screenshot(path='/mnt/data/MEU_CRONOGRAMA_V241_MEUS_ALUNOS.png',full_page=True)
  # Same browser boot for Master confirms the existing account management stays.
  page.close();client=master
  page=browser.new_page();page.on('pageerror',lambda e:errors.append(str(e)));page.expose_function('test_wsgi',bridge)
  page.set_content(html);page.add_style_tag(content=(R/'static/style.css').read_text())
  page.add_script_tag(content="window.fetch=async(url,opts={})=>{const r=await window.test_wsgi(url,opts);return new Response(Uint8Array.from(atob(r.body),c=>c.charCodeAt(0)),{status:r.status,headers:r.headers});};")
  page.add_script_tag(content='\n'.join((R/'static'/n).read_text() for n in ('app.js','performance.js','adaptive.js','selective.js','import_wizard.js','coordinator_accounts.js')))
  page.locator('[data-view=accounts]').wait_for();page.locator('[data-view=accounts]').click();page.locator('[data-act=new-account]').click()
  assert page.locator('#modal-form [name=role]').count()==1;assert page.locator('#modal-form [name=role] option').count()==4;checks.append('master-all-roles-preserved')
  assert not errors,errors;checks.append('no-js-errors')
  browser.close()
print('COORDINATOR_UI_OK: '+str(len(checks))+' checks; '+', '.join(checks)+'. Real WSGI; not physical iPhone.')
