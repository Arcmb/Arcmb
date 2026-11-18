"use strict";
// Explicit return from a managed account to the signed-in account.
function ownerReturnInstall(){
 const editing=[...document.querySelectorAll('.notice')].find(x=>/Você está editando a conta de/i.test(x.textContent||''));
 const old=document.querySelector('[data-owner-return-wrap]');
 if(!editing||!ME?.id||target===ME.id){if(old)old.remove();return;}
 if(editing.querySelector('[data-owner-return-wrap]'))return;
 const wrap=document.createElement('span');
 wrap.dataset.ownerReturnWrap='1';wrap.className='actions';wrap.style.display='inline-flex';wrap.style.marginLeft='.75rem';
 const control=document.createElement('button');control.type='button';control.className='secondary';
 control.dataset.act='return-owner';control.textContent='Voltar ao meu usuário';
 wrap.appendChild(control);editing.appendChild(wrap);
}

acts['return-owner']=async()=>{
 if(!ME?.id||target===ME.id)return;
 const open=acts['open-account'];
 if(typeof open==='function')await open({dataset:{id:ME.id}});
 else{target=ME.id;await load();view='home';render();}
};

document.addEventListener('DOMContentLoaded',ownerReturnInstall,{once:true});
window.addEventListener('load',ownerReturnInstall,{once:true});
new MutationObserver(ownerReturnInstall).observe(document.documentElement,{childList:true,subtree:true});
