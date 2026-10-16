/* Twemoji (CC-BY 4.0, https://github.com/jdecked/twemoji): emoji-ləri öz saytımızdan verilən SVG ilə əvəz edir, hər cihazda eyni görünür.
   Fayllar assets/twemoji/ qovluğundadır; siyahı aşağıdadır: burada olmayan simvol olduğu kimi qalır. */
(function(){
"use strict";
var BASE=new URL("twemoji/",document.currentScript.src).href, FBASE=new URL("fluent/",document.currentScript.src).href;
/* Fluent Emoji 3D (© Microsoft, MIT lisenziyası, https://github.com/microsoft/fluentui-emoji): daha canlı görünür, olan simvol üçün
   Twemoji əvəzinə assets/fluent/<kod>.webp (96 px) göstərilir; siyahısı FL-dədir. Fluent-də olmayan simvol Twemoji ilə qalır. */
var FL=new Set("1f32d 1f330 1f334 1f336 1f338 1f33a 1f33b 1f33d 1f33e 1f33f 1f344 1f345 1f346 1f347 1f348 1f349 1f34a 1f34b 1f34c 1f34d 1f34e 1f34f 1f350 1f351 1f352 1f353 1f354 1f355 1f356 1f357 1f35a 1f35c 1f35d 1f35e 1f35f 1f362 1f363 1f366 1f369 1f36a 1f36b 1f36c 1f36d 1f36e 1f36f 1f370 1f372 1f373 1f374 1f375 1f376 1f377 1f378 1f379 1f37a 1f37c 1f37d 1f37e 1f37f 1f382 1f389 1f3a8 1f3b2 1f3b9 1f3c6 1f3e0 1f419 1f41f 1f420 1f426 1f431 1f436 1f43e 1f456 1f45e 1f45f 1f476 1f484 1f485 1f487 1f4a1 1f4a7 1f4aa 1f4cb 1f4cf 1f4d3 1f4e6 1f50b 1f50c 1f50d 1f525 1f526 1f52a 1f534 1f56f 1f58d 1f5d1 1f681 1f697 1f6ac 1f6b0 1f6bd 1f6bf 1f6c1 1f6cf 1f6d2 1f7e1 1f7e3 1f7eb 1f916 1f943 1f944 1f950 1f951 1f952 1f953 1f954 1f955 1f956 1f957 1f958 1f95a 1f95b 1f95c 1f95d 1f95e 1f95f 1f963 1f964 1f965 1f966 1f967 1f968 1f969 1f96a 1f96b 1f96c 1f96d 1f96f 1f980 1f983 1f990 1f991 1f99f 1f9c0 1f9c1 1f9c2 1f9c3 1f9c4 1f9c5 1f9c7 1f9c8 1f9ca 1f9cb 1f9e2 1f9e3 1f9e4 1f9e5 1f9e6 1f9f0 1f9f1 1f9f3 1f9f4 1f9f5 1f9f8 1f9f9 1f9fa 1f9fb 1f9fc 1f9fd 1fa72 1fa74 1fa79 1fa86 1fa91 1fa92 1fa9d 1faa1 1faa3 1faa4 1faa5 1faae 1fab4 1fad0 1fad1 1fad2 1fad3 1fad6 1fad7 1fad8 1fad9 1fada 1fadb 1fae7 23f0 2615 2661 2665 2696 2699 26a0 26a1 26bd 2702 270f 2713 2744".split(" "));
var HAVE=new Set("1f32c 1f32d 1f330 1f334 1f336 1f338 1f33a 1f33b 1f33d 1f33e 1f33f 1f344 1f345 1f346 1f347 1f348 1f349 1f34a 1f34b 1f34c 1f34d 1f34e 1f34f 1f350 1f351 1f352 1f353 1f354 1f355 1f356 1f357 1f35a 1f35c 1f35d 1f35e 1f35f 1f362 1f363 1f366 1f369 1f36a 1f36b 1f36c 1f36d 1f36e 1f36f 1f370 1f372 1f373 1f374 1f375 1f376 1f377 1f378 1f379 1f37a 1f37c 1f37d 1f37e 1f37f 1f382 1f383 1f389 1f3a8 1f3b2 1f3b9 1f3c6 1f3e0 1f419 1f41f 1f420 1f426 1f431 1f436 1f43e 1f455 1f456 1f45e 1f45f 1f476 1f484 1f485 1f487 1f4a1 1f4a7 1f4aa 1f4cb 1f4cf 1f4d3 1f4e6 1f50b 1f50c 1f50d 1f525 1f526 1f52a 1f534 1f56f 1f58d 1f5d1 1f681 1f697 1f6ac 1f6b0 1f6bd 1f6bf 1f6c1 1f6cf 1f6d2 1f7e1 1f7e3 1f7eb 1f916 1f943 1f944 1f950 1f951 1f952 1f953 1f954 1f955 1f956 1f957 1f958 1f95a 1f95b 1f95c 1f95d 1f95e 1f95f 1f963 1f964 1f965 1f966 1f967 1f968 1f969 1f96a 1f96b 1f96c 1f96d 1f96f 1f980 1f983 1f990 1f991 1f99f 1f9c0 1f9c1 1f9c2 1f9c3 1f9c4 1f9c5 1f9c7 1f9c8 1f9ca 1f9cb 1f9e2 1f9e3 1f9e4 1f9e5 1f9e6 1f9f0 1f9f1 1f9f3 1f9f4 1f9f5 1f9f8 1f9f9 1f9fa 1f9fb 1f9fc 1f9fd 1fa72 1fa74 1fa79 1fa86 1fa91 1fa92 1fa9d 1faa1 1faa3 1faa4 1faa5 1faae 1fab4 1fad0 1fad1 1fad2 1fad3 1fad6 1fad7 1fad8 1fad9 1fada 1fadb 1fae7 23f0 2615 2661 2665 2696 2699 26a0 26a1 26bd 2702 270f 2713 2744".split(" "));
var RX=/\p{Extended_Pictographic}(?:\uFE0F|\u200D\p{Extended_Pictographic}\uFE0F?|[\u{1F3FB}-\u{1F3FF}])*/gu;
var SKIP={SCRIPT:1,STYLE:1,TEXTAREA:1,OPTION:1,TITLE:1,INPUT:1,NOSCRIPT:1};
function code(e){ var a=Array.from(e); if(e.indexOf("\u200D")<0) a=a.filter(function(c){return c!=="\uFE0F"}); return a.map(function(c){return c.codePointAt(0).toString(16)}).join("-"); }
function img(e,c){
  var i=document.createElement("img");
  i.className="emoji"; i.alt=e; i.draggable=false; i.src=FL.has(c)?FBASE+c+".webp":BASE+c+".svg";
  i.onerror=function(){ if(i.src.indexOf(FBASE)===0) i.src=BASE+c+".svg"; else i.replaceWith(document.createTextNode(e)); };
  return i;
}
function conv(t){
  var s=t.nodeValue, last=0, f=null, m;
  RX.lastIndex=0;
  while((m=RX.exec(s))){
    var c=code(m[0]); if(!HAVE.has(c)) continue;
    f=f||document.createDocumentFragment();
    if(m.index>last) f.appendChild(document.createTextNode(s.slice(last,m.index)));
    f.appendChild(img(m[0],c)); last=m.index+m[0].length;
  }
  if(f){ if(last<s.length) f.appendChild(document.createTextNode(s.slice(last))); t.replaceWith(f); }
}
function walk(root){
  if(root.nodeType===3){ if(!SKIP[root.parentNode&&root.parentNode.nodeName]) conv(root); return; }
  if(root.nodeType!==1||SKIP[root.nodeName]) return;
  var w=document.createTreeWalker(root,NodeFilter.SHOW_TEXT,{acceptNode:function(n){
    return SKIP[n.parentNode.nodeName]?NodeFilter.FILTER_REJECT:NodeFilter.FILTER_ACCEPT}}), list=[], n;
  while((n=w.nextNode())) list.push(n);
  list.forEach(conv);
}
var queue=[], busy=false;
function flush(){ busy=false; var q=queue; queue=[]; q.forEach(function(n){ if(n.isConnected) walk(n); }); }
new MutationObserver(function(ms){
  ms.forEach(function(m){
    if(m.type==="characterData") queue.push(m.target);
    else m.addedNodes.forEach(function(n){ if(n.nodeType===1||n.nodeType===3) queue.push(n); });
  });
  if(queue.length&&!busy){ busy=true; requestAnimationFrame(flush); }
}).observe(document.documentElement,{childList:true,subtree:true,characterData:true});
walk(document.body);
})();
