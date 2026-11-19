const list=await (await fetch('http://127.0.0.1:9222/json/list')).json();const page=list.find(x=>x.type==='page');
const ws=new WebSocket(page.webSocketDebuggerUrl);await new Promise(r=>ws.onopen=r);let id=0;const pend={};const errors=[];
ws.onmessage=m=>{const d=JSON.parse(m.data);if(d.id&&pend[d.id]){pend[d.id](d);delete pend[d.id];}if(d.method==='Runtime.exceptionThrown')errors.push((d.params.exceptionDetails.exception?.description||d.params.exceptionDetails.text||'').split('\n')[0]);};
const send=(method,params={})=>new Promise(r=>{const i=++id;pend[i]=r;ws.send(JSON.stringify({id:i,method,params}));});const sleep=ms=>new Promise(r=>setTimeout(r,ms));
const ev=async e=>{const r=await send('Runtime.evaluate',{expression:e,awaitPromise:true,returnByValue:true});return r.result.exceptionDetails?'ERR '+(r.result.exceptionDetails.exception?.description||'').split('\n')[0]:r.result.result.value;};
await send('Runtime.enable');await send('Network.enable');
let fails=0;const check=(label,cond,extra='')=>{console.log((cond?'OK  ':'FALHA ')+label+(extra?' → '+extra:''));if(!cond)fails++;};
async function login(u,p){await send('Network.clearBrowserCookies');await send('Page.navigate',{url:'http://127.0.0.1:8765/login'});await sleep(1500);await ev(`document.querySelector('[name=username]').value='${u}';document.querySelector('[name=password]').value='${p}';document.querySelector('form').submit()`);await sleep(3500);await ev(`document.querySelectorAll('dialog[open],.guide-overlay,.use-guide').forEach(x=>x.remove?.());1`);}
const nav=()=>ev(`[...document.querySelectorAll('#nav button')].map(b=>b.textContent.replace(/^\\d+/,'').trim()).join(' | ')`);
const search=async q=>{await ev(`{const i=document.querySelector('#account-search');i.focus();i.value=${JSON.stringify(q)};i.dispatchEvent(new Event('input',{bubbles:true}));}1`);await sleep(300);await ev(`document.querySelector('.account-search-result').dispatchEvent(new MouseEvent('mousedown',{bubbles:true}));1`);await sleep(2500);};
const shot=async n=>{const r=await send('Page.captureScreenshot',{format:'png'});(await import('fs')).writeFileSync('/tmp/qi-browser-'+n+'.png',Buffer.from(r.result.data,'base64'));};
const sel=async(q,v)=>{await ev(`(()=>{const s=document.querySelector(${JSON.stringify(q)});s.value=${JSON.stringify(v)};s.dispatchEvent(new Event('change',{bubbles:true}));return 1})()`);await sleep(800);};
await send('Page.enable');await ev(`window.confirm=()=>true;1`);
await login('arcmb','TEST_master_13579');await ev(`window.confirm=()=>true;1`);
const typeIn=async(name,value)=>ev(`(()=>{const i=document.querySelector('#modal-form [name=${name}]');i.value=${JSON.stringify(value)};i.dispatchEvent(new Event('input',{bubbles:true}));return 1})()`);
const tick=async name=>{await ev(`(()=>{const i=document.querySelector('#modal-form [name=${name}]');i.click();return 1})()`);await sleep(200);};
const state=()=>ev(`(()=>{const e=document.querySelector('#modal-form').elements;return {scores:[e.scores.checked,e.scores.disabled],answers:[e.answers.checked,e.answers.disabled],map:[e.map.checked,e.map.disabled],summary:document.querySelector('[data-exam-delete-text=summary]').innerText}})()`);
const openDelete=async title=>{await ev(`[...document.querySelectorAll('#exam-list .item')].find(x=>x.innerText.includes(${JSON.stringify(title)})).querySelector('[data-act="exam-delete"]').click();1`);await sleep(1500);};
const listText=()=>ev(`document.querySelector('#exam-list').innerText`);
const api=(url,body)=>ev(`fetch(${JSON.stringify(url)},{method:'POST',credentials:'same-origin',headers:{'Content-Type':'application/json','X-CSRF-Token':CSRF},body:JSON.stringify(${JSON.stringify(body)})}).then(async r=>({status:r.status,data:await r.json()}))`);

await ev(`[...document.querySelectorAll('#nav button')].find(b=>b.textContent.includes('Mapa de questões')).click();1`);await sleep(3000);
check('Botão Excluir… em cada caderno',await ev(`document.querySelectorAll('#exam-list [data-act="exam-delete"]').length`)>=2);
const before=(await api('/api/model-data/exam-delete-preview',{examId:'ex1'})).data;
console.log(JSON.stringify(before.scopes.caderno));
check('Prévia conta resultados e notas',before.scopes.caderno.results>40&&before.scopes.caderno.withScores===before.scopes.caderno.results);

// 1) Só as notas
await openDelete('4º Simulado');
check('Modal aberto',await ev(`document.querySelector('#dialog-title').textContent`)==='Excluir dados do simulado');
check('Sem escolha de alcance com uma cor só',await ev(`!document.querySelector('#modal-form [name=scope]')`));
let st=await state();
check('Respostas com contagem',/\d+ resultados de \d+ alunos/.test(await ev(`document.querySelector('[data-exam-delete-text=answers]').innerText`)));
check('Nada marcado de início',!st.scores[0]&&!st.answers[0]&&!st.map[0],JSON.stringify(st));
await tick('scores');st=await state();
check('Resumo das notas',/as notas de \d+ resultados/.test(st.summary),st.summary);
await shot('excluir-notas');
await typeIn('confirmation','errado');
await ev(`document.querySelector('#modal-form button[type=submit]').click();1`);await sleep(800);
check('Confirmação errada bloqueia',await ev(`!!document.querySelector('#dialog[open]')`));
await typeIn('confirmation','EXCLUIR');
await ev(`document.querySelector('#modal-form button[type=submit]').click();1`);await sleep(2500);
check('Modal fechou',await ev(`!document.querySelector('#dialog[open]')`));
check('Aviso de conclusão',/notas retiradas de \d+ resultados/.test(await ev(`document.querySelector('#toast').textContent`)),await ev(`document.querySelector('#toast').textContent`));
let after=(await api('/api/model-data/exam-delete-preview',{examId:'ex1'})).data;
check('Notas sumiram e respostas ficaram',after.scopes.caderno.withScores===0&&after.scopes.caderno.results===before.scopes.caderno.results,JSON.stringify(after.scopes.caderno));

// 2) Gabarito exige as respostas
await openDelete('4º Simulado');
await tick('map');st=await state();
check('Marcar gabarito marca respostas',st.map[0]&&st.answers[0],JSON.stringify(st));
check('Notas já não existem: caixa desabilitada',st.scores[1],JSON.stringify(st));
check('Resumo fala de resultados e gabarito',/resultados com respostas.*gabarito de 1 caderno/.test(st.summary),st.summary);
await shot('excluir-tudo');
await typeIn('confirmation','excluir');
await ev(`document.querySelector('#modal-form button[type=submit]').click();1`);await sleep(3000);
check('Caderno saiu da lista',!/4º Simulado/.test(await listText()));
check('Aviso de resultados e gabarito',/resultados excluídos.*gabarito excluído/.test(await ev(`document.querySelector('#toast').textContent`)),await ev(`document.querySelector('#toast').textContent`));
check('Caderno não existe mais',(await api('/api/model-data/exam-delete-preview',{examId:'ex1'})).status===404);

// 3) Gabarito sem respostas sai sozinho
await openDelete('5º Simulado');st=await state();
check('Sem respostas: caixa de respostas desabilitada',st.answers[1],JSON.stringify(st));
const radios=await ev(`[...document.querySelectorAll('#modal-form input[name=scope]')].map(r=>{const b=r.getBoundingClientRect(),l=r.closest('label').getBoundingClientRect();return [Math.round(b.width),Math.round(b.left-l.left)]})`);
check('Alcance com duas opções de tamanho normal, alinhadas à esquerda',radios.length===2&&radios.every(([w,x])=>w<=24&&x<=4),JSON.stringify(radios));
check('Alcance começa em "Só o caderno"',await ev(`document.querySelector('#modal-form input[name=scope]:checked').value`)==='caderno');
await ev(`document.querySelector('#modal-form input[name=scope][value=simulado]').click();1`);await sleep(300);
check('Simulado inteiro: 2 cadernos',/2 cadernos \(AMARELA, AZUL\)/.test(await ev(`document.querySelector('[data-exam-delete-text=map]').innerText`)),await ev(`document.querySelector('[data-exam-delete-text=map]').innerText`));
await shot('excluir-alcance');
await tick('map');await typeIn('confirmation','EXCLUIR');
await ev(`document.querySelector('#modal-form button[type=submit]').click();1`);await sleep(2500);
check('5º Simulado saiu da lista',!/5º Simulado/.test(await listText()));

// 4) Painel da gestão acompanha
await ev(`[...document.querySelectorAll('#nav button')].find(b=>b.textContent.includes('Visão geral')).click();1`);await sleep(4000);
const dash=(await ev(`fetch('/api/model-data/management-dashboard',{credentials:'same-origin'}).then(r=>r.json())`));
check('Painel sem o 4º Simulado',!dash.simulations.some(s=>s.activity==='4º Simulado'),JSON.stringify(dash.simulations.map(s=>s.activity)));

await login('al1','TEST_aluno_1234');
check('Aluno não pode excluir',(await api('/api/model-data/exam-delete-preview',{examId:'ex2'})).status===403);
const jsErrors=[...new Set(errors)];console.log('Falhas:',fails,'Erros JS:',jsErrors);process.exit(fails||jsErrors.length?1:0);
