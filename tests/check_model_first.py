"""Local UI + backend integration for the model-first flow; no real user data."""
import sys,tempfile,json,re,base64
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from webapp import App
from test_system import Browser
from playwright.sync_api import sync_playwright
import performance as F
import templates_v23 as T
R=Path(__file__).resolve().parents[1]
results=[];errors=[];tmp=tempfile.TemporaryDirectory()
app=App({'LOCAL_TEST':'1','LOCAL_DB':tmp.name+'/db','SECRET_KEY':'z'*64,'MASTER_PASSWORD':'TEST_master_13579'})
client=Browser(app);assert client.login()['status']==303
with app.db.connection(write=True)as c:
 app.db.create_user(c,'aluno','Aluno Teste','TEST_student_123','aluno',False)
 app.db.create_user(c,'coordenador','Coord Teste','TEST_student_123','coordenador',False)
def ok(name,condition=True):
 assert condition,name;results.append(name)
with sync_playwright()as pw:
 b=pw.chromium.launch(executable_path='/usr/bin/chromium',headless=True,args=['--no-sandbox'])
 page=b.new_page(viewport={'width':1380,'height':1000},accept_downloads=True);page.set_default_timeout(10000)
 page.on('pageerror',lambda e:errors.append(str(e)));page.on('dialog',lambda d:d.accept())
 def bridge(url,opts):
  data=json.loads(opts['body'])if opts.get('body')else None
  r=client.request(url,data);return dict(status=r['status'],headers=r['headers'],body=base64.b64encode(r['raw']).decode())
 page.expose_function('test_wsgi',bridge)
 html=(R/'static/app.html').read_text();html=re.sub(r'<script[^>]*>.*?</script>','',html);html=re.sub(r'<link[^>]*>','',html)
 page.set_content(html);page.add_style_tag(content=(R/'static/style.css').read_text())
 page.add_script_tag(content="window.fetch=async(url,opts={})=>{const r=await window.test_wsgi(url,opts);return new Response(Uint8Array.from(atob(r.body),c=>c.charCodeAt(0)),{status:r.status,headers:r.headers});};")
 page.add_script_tag(content='\n'.join((R/'static'/n).read_text()for n in ('app.js','performance.js','adaptive.js','selective.js','import_wizard.js')))
 page.locator('[data-view="result-model"]').wait_for();page.locator('[data-view="result-model"]').click()
 page.locator('[data-model-field="NOME"]').wait_for();ok('Modelo disponível antes de carregar qualquer arquivo',page.locator('input[type=file]:visible').count()==0)
 ok('Lista completa com 244 caixas de marcação',page.locator('[data-model-field]').count()==244)
 ok('Somente 3 obrigatórias inicialmente',page.locator('[data-model-field]:checked').count()==3)
 ok('Identificadores obrigatórios protegidos',page.locator('[data-model-field="NOME"]').is_disabled())
 for field in ['TURMA','Nota TRI','Acertos - Física','Acertos Hab 05','Acerto/erro questão 01','Acerto/erro questão 90']:
  page.locator('[data-model-field="'+field+'"]').check()
 ok('Contagem dos campos selecionados',page.locator('#model-count').inner_text()=='9 colunas selecionadas')
 page.locator('[name=model-discipline]').fill('Robótica');page.locator('[data-act=model-add]').click()
 ok('Disciplina nova incluída e marcada',page.locator('[data-model-field="Acertos - Robótica"]').is_checked())
 expected=page.evaluate('selectedModelFields()')
 with page.expect_download()as dl:page.locator('[data-act=model-download]').click()
 payload=Path(dl.value.path()).read_bytes();headers=F.load_matrix('modelo.xlsx',payload)[0][0]
 ok('XLSX contém apenas os campos marcados na ordem exibida',headers==expected)
 ok('XLSX não inclui campos desmarcados','Ranking'not in headers and 'Acertos - Química'not in headers)
 page.locator('[name=model-format]').select_option('csv')
 with page.expect_download()as dl:page.locator('[data-act=model-download]').click()
 csv=Path(dl.value.path()).read_bytes();ok('CSV corresponde à mesma seleção e inclui BOM',csv.startswith(b'\xef\xbb\xbf')and F.load_matrix('modelo.csv',csv)[0][0]==expected)
 page.evaluate('window.scrollTo(0,0)');page.screenshot(path='/mnt/data/MEU_CRONOGRAMA_SELECAO_CAMPOS.png')
 page.locator('[data-act=model-all][data-value="0"]').click()
 ok('Desmarcar opcionais preserva obrigatórios',page.locator('[data-model-field]:checked').count()==3)
 page.locator('[name=model-first]').fill('91');page.locator('[name=model-last]').fill('135');page.locator('[data-act=model-range]').click()
 ok('Intervalo 91 a 135 marca somente 45 questões',page.locator('[data-model-group="Questões"]:checked').count()==45 and not page.locator('[data-model-field="Acerto/erro questão 90"]').is_checked())
 page.locator('[data-act=model-group][data-group="Questões"][data-value="0"]').click()
 page.locator('[data-model-field="Acertos - Física"]').check()
 # Reimport a generated, filled template without manually remapping columns.
 row=['Aluno Teste','Prova A','28/10/2026',4]
 filled=T.export(['NOME','TIPO de prova','data de aplicação','Acertos - Física'],[row])[0]
 page.locator('[data-act=model-to-results]').click();page.locator('#performance-file').wait_for()
 ok('Geração de modelo vem antes do envio',page.locator('.model-entry h2').inner_text().startswith('1. Escolha'))
 page.set_input_files('#performance-file',dict(name='preenchido.xlsx',mimeType=T.MIME,buffer=filled));page.wait_for_function('perfDraft?.file')
 page.locator('[data-act=perf-preview]').first.click();page.locator('[data-map-perf="0"]').wait_for(state='attached')
 ok('Correspondência manual é opcional e fechada no modelo padrão',page.locator('.model-advanced').get_attribute('open')is None)
 page.locator('[data-act=perf-preview]').last.click();page.locator('[data-act=perf-confirm]').wait_for();page.locator('[data-act=perf-confirm]').click();page.wait_for_function('perfDraft===null')
 with app.db.connection()as c:
  r=app.db.execute(c,'SELECT metrics FROM hmay_performance').fetchall()
 ok('Modelo preenchido importado e salvo sem remapeamento manual',len(r)==1 and json.loads(r[0]['metrics'])['fisica']['correct']==4)
 page.locator('[data-view=exams]').click();page.locator('[data-act=exam-new]').click()
 page.set_input_files('#exam-file',dict(name='resultados.csv',mimeType='text/csv',buffer=b'nome;turma;simulado;data;nota_enem\nAluno Teste;A;Prova A;28/10/2026;700'))
 page.wait_for_function('examDraft?.file');page.locator('[data-act=exam-inspect]').click();page.get_by_text('Este arquivo parece conter resultados de alunos, não um mapa de questões.').wait_for()
 ok('Arquivo de resultados no mapa recebe orientação, não associação Nome/Questão',page.locator('[data-map-exam]').count()==0 and page.locator('[data-act=exam-preview]').count()==0)
 page.locator('#exam-inspection [data-act=perf-template]').click();page.locator('[data-model-field="NOME"]').wait_for()
 ok('Atalho do mapa leva à seleção de campos',page.locator('h1').inner_text()=='Modelo de resultados')
 page.set_viewport_size({'width':390,'height':844});page.evaluate('window.scrollTo(0,0)')
 ok('Tela de 390 px sem rolagem horizontal',page.evaluate('document.documentElement.scrollWidth<=innerWidth+2'))
 ok('Resumo e botão visíveis no celular',page.locator('.model-summary').is_visible() and page.locator('[data-act=model-download]').is_visible() and page.locator('.model-summary').evaluate("el=>getComputedStyle(el).transform==='none' && getComputedStyle(el).color==='rgb(39, 38, 61)'"))
 page.screenshot(path='/mnt/data/MEU_CRONOGRAMA_SELECAO_CELULAR.png')
 # Role checks: model creation remains staff-only.
 client=Browser(app);assert client.login('coordenador','TEST_student_123')['status']==303
 ok('Coordenador pode gerar o modelo',client.request('/api/performance/template-selected',{'fields':['NOME','TIPO de prova','data de aplicação','Acertos - Física'],'format':'xlsx'})['status']==200)
 client=Browser(app);assert client.login('aluno','TEST_student_123')['status']==303
 ok('Aluno não gera modelos em lote',client.request('/api/performance/template-selected',{'fields':['NOME','TIPO de prova','data de aplicação'],'format':'xlsx'})['status']==403)
 ok('Nenhum erro JavaScript',not errors)
 b.close()
tmp.cleanup()
print('\n'.join('OK — '+x for x in results));print('MODEL_FIRST_UI_OK:',len(results),'verificações; Chromium + WSGI local; não iPhone físico.')
