"""In-process Chromium UI flows; no production data or network credentials."""
import sys,tempfile,json,re,base64
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1])); sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'checks'))
from webapp import App
from test_system import Browser
from playwright.sync_api import sync_playwright
import performance as F
R=Path(__file__).resolve().parents[1];tmp=tempfile.TemporaryDirectory();app=App({'LOCAL_TEST':'1','LOCAL_DB':tmp.name+'/db','SECRET_KEY':'u'*64,'MASTER_PASSWORD':'TEST_master_13579'})
client=Browser(app);assert client.login()['status']==303
with app.db.connection(write=True)as c:app.db.create_user(c,'aluno','Aluno Teste','TEST_student_123','aluno',False)
errors=[]
with sync_playwright()as pw:
 b=pw.chromium.launch(executable_path='/usr/bin/chromium',headless=True,args=['--no-sandbox']);page=b.new_page(viewport={'width':1280,'height':900},accept_downloads=True)
 page.set_default_timeout(8000)
 page.on('pageerror',lambda e:errors.append(str(e)));page.on('dialog',lambda d:d.accept())
 def bridge(url,opts):
  data=json.loads(opts['body'])if opts.get('body')else None;r=client.request(url,data);return dict(status=r['status'],headers=r['headers'],body=base64.b64encode(r['raw']).decode())
 page.expose_function('test_wsgi',bridge)
 html=(R/'static/app.html').read_text();html=re.sub(r'<script[^>]*>.*?</script>','',html);html=re.sub(r'<link[^>]*>','',html)
 page.set_content(html);page.add_style_tag(content=(R/'static/style.css').read_text());page.add_script_tag(content="window.fetch=async(url,opts={})=>{const r=await window.test_wsgi(url,opts);return new Response(Uint8Array.from(atob(r.body),c=>c.charCodeAt(0)),{status:r.status,headers:r.headers});};")
 page.add_script_tag(content='\n'.join((R/'static'/n).read_text()for n in ('app.js','performance.js','adaptive.js','selective.js')))
 page.locator('[data-view=mapping]').wait_for();page.locator('[data-view=mapping]').click();page.locator('#objective-form').wait_for()
 assert page.locator('#objective-form select').count()==20
 assert page.locator('.question-help').count()==20
 assert 'estuda por conta própria' in page.locator('[name=focus]').locator('..').inner_text()
 page.locator('[name=focus]').select_option('25');page.locator('#objective-form button[type=submit]').click();page.wait_for_function("!dirty && document.querySelector('#objective-form [name=focus]')?.value==='25'")
 page.locator('[name=focus]').scroll_into_view_if_needed();page.screenshot(path='/mnt/data/mc23_questionario.png')
 page.locator('[data-view=performance]').click();page.locator('[data-act=perf-template]').click();page.get_by_text('Disciplinas',exact=True).click();page.locator('[data-template-field="Acertos - Física"]').check()
 with page.expect_download()as dl:page.locator('[data-act=template-download]').click()
 path=dl.value.path();rows=F.load_matrix('x.xlsx',Path(path).read_bytes())[0];assert rows[0]==['NOME','TIPO de prova','data de aplicação','Acertos - Física'],rows[0]
 page.evaluate('closeModal(true)')
 file=dict(name='resultados.csv',mimeType='text/csv',buffer=b'NOME;TIPO;data;Acerto/erro questao 91;Acertos - Quimica\nAluno Teste;Prova A;28/10/2026;1;invalido')
 page.set_input_files('#performance-file',file);page.wait_for_function('perfDraft?.file')
 page.locator('[data-act=perf-preview]').click();page.locator('[data-map-perf="4"]').wait_for();page.locator('[data-map-perf="4"]').fill('');page.locator('[data-act=perf-preview]').last.click();page.locator('[data-act=perf-confirm]').wait_for();page.screenshot(path='/mnt/data/mc23_importacao.png')
 page.locator('[data-act=perf-confirm]').click();page.wait_for_function('perfDraft===null')
 with app.db.connection()as c:
  rs=app.db.execute(c,'SELECT metrics FROM hmay_performance').fetchall();assert len(rs)==1;assert 'questao:091'in json.loads(rs[0]['metrics'])
 page.locator('[data-view=exams]').click();page.locator('[data-act=exam-new]').click()
 page.locator('[name=exam-title]').fill('Prova A');page.locator('[name=exam-date]').fill('2026-10-28')
 page.set_input_files('#exam-file',dict(name='mapa.csv',mimeType='text/csv',buffer='Prova Azul;Disciplina;Assunto;Habilidade\n91;Química;Oxirredução;H24\n92;Química;Propriedades;H19'.encode()))
 page.wait_for_function('examDraft?.file');page.locator('[data-act=exam-inspect]').click();page.locator('[data-act=exam-preview]').wait_for();page.locator('[data-act=exam-preview]').click();page.locator('[data-act=exam-confirm]').wait_for();page.screenshot(path='/mnt/data/mc23_simulado.png')
 page.locator('[data-act=exam-confirm]').click();page.wait_for_function('examDraft===null')
 page.locator('[data-view=performance]').click();page.set_input_files('#performance-file',file);page.wait_for_function('perfDraft?.file');page.locator('[data-act=perf-preview]').click();page.locator('[data-map-perf="4"]').wait_for();page.locator('[data-map-perf="4"]').fill('')
 eid=client.request('/api/exams')['data']['exams'][0]['id'];page.locator('[name=perf-exam]').select_option(eid);page.locator('[data-act=perf-preview]').last.click();page.locator('[data-act=perf-confirm]').wait_for();page.locator('[data-act=perf-confirm]').click();page.wait_for_function('perfDraft===null')
 page.set_viewport_size({'width':390,'height':844});page.evaluate("view='mapping';render()")
 page.locator('#objective-form').wait_for();assert page.evaluate('document.documentElement.scrollWidth<=innerWidth+2');page.screenshot(path='/mnt/data/mc23_celular.png',full_page=True)
 assert not errors,errors;b.close()
tmp.cleanup();print('V23_UI_OK: 20 clarified questions/save, selected XLSX download, ignored invalid column, confirmation, exam map upload, linking and 390px layout; no JS errors. In-process WSGI, not a physical iPhone.')
