"use strict";
// === ESTILOS INLINE COMPATÍVEIS COM A POLÍTICA DE SEGURANÇA (v3.14.1) ===
// A política do site (style-src 'self') faz o navegador ignorar atributos style="" escritos no HTML,
// por isso barras de gráfico apareciam todas cheias. Este script reaplica esses estilos pela API do
// navegador (CSSOM), que a política permite, sem liberar estilos inline em geral.
(function(){
 const done=new WeakMap();
 function apply(el){
  if(!el||el.nodeType!==1||!el.hasAttribute('style'))return;
  const raw=el.getAttribute('style')||'';
  if(done.get(el)===raw)return;
  done.set(el,raw);
  raw.split(';').forEach(part=>{
   const i=part.indexOf(':');if(i<1)return;
   const prop=part.slice(0,i).trim(),value=part.slice(i+1).trim();
   if(!prop||!value||el.style.getPropertyValue(prop)!=='')return;
   const important=/!important\s*$/i.test(value);
   try{el.style.setProperty(prop,value.replace(/!important\s*$/i,'').trim(),important?'important':'');}catch(_){}
  });
 }
 function scan(root){
  if(!root||root.nodeType!==1)return;
  apply(root);
  root.querySelectorAll('[style]').forEach(apply);
 }
 window.qiApplyInlineStyles=scan;
 const observer=new MutationObserver(list=>{
  for(const m of list){
   if(m.type==='attributes')apply(m.target);
   else m.addedNodes.forEach(scan);
  }
 });
 function start(){scan(document.body);observer.observe(document.body,{childList:true,subtree:true,attributes:true,attributeFilter:['style']});}
 if(document.body)start();else document.addEventListener('DOMContentLoaded',start,{once:true});
})();
