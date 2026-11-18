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
const HIDDEN=['Mapeamento objetivo','Observações pessoais','Rotina e horários','Disciplinas e metas','Conteúdos estudados','Quadro semanal','Revisões','Verificações'];
const none=n=>HIDDEN.every(h=>!n.split(' | ').includes(h));const all=n=>HIDDEN.every(h=>n.split(' | ').includes(h));
for(const [u,p] of [['arcmb','TEST_master_13579'],['laise','TEST_coord_1234']]){
 await login(u,p);let n=await nav();
 check(u+': abas do aluno ocultas',none(n),n);
 check(u+': numeração sequencial',await ev(`[...document.querySelectorAll('#nav .nav-number')].every((x,i)=>x.textContent===String(i+1).padStart(2,'0'))`));
 await ev(`view='calendar';render();1`);await sleep(800);
 check(u+': acesso direto volta à Visão geral',await ev('view')==='home');
 await search('Ana');await sleep(3000);n=await nav();
 check(u+': aluno aberto mostra as abas',all(n),n);
 await ev(`[...document.querySelectorAll('#nav button')].find(b=>b.textContent.includes('Quadro semanal')).click();1`);await sleep(2000);
 check(u+': abre Quadro semanal do aluno',await ev('view')==='calendar');
 await ev(`document.querySelector('[data-act="student-view-return"]').click();1`);await sleep(3000);n=await nav();
 check(u+': voltar ao meu usuário',(await ev('target===ME.id'))&&none(n)&&await ev('view')==='home',n);
}
await login('ana.souza','TEST_aluno_1234');const n2=await nav();
check('Aluno vê todas as abas',all(n2),n2);
const jsErrors=[...new Set(errors)];console.log('Falhas:',fails,'Erros JS:',jsErrors);process.exit(fails||jsErrors.length?1:0);
