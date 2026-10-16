// index.html-dəki saf funksiyaları node-da yükləyir: const api=require('./site_harness.js')(indexHtmlPath)
// Getter-lər: səhifədə olmayan ad undefined qaytarır (köhnə/yeni index.html ilə işləyir).
// Yeni index.html-də expandQ/matchQ/alpha/jaccard/TR yoxdur: axtarış api.search(q) / api.qparse(q) / api.score(g,Q,gid) ilə;
// expandQ yoxdursa, qparse əsasında uyğunluq üçün sadə əvəz verilir (hər söz üçün alternativlər).
const fs=require('fs'),vm=require('vm');
module.exports=function(path){
  const html=fs.readFileSync(path,'utf8');
  const scripts=[...html.matchAll(/<script>([\s\S]*?)<\/script>/g)].map(m=>m[1]);
  const js=scripts[scripts.length-1];
  const mkEl=()=>{const t={classList:{toggle(){},add(){},remove(){},contains(){return false}},style:{},dataset:{},setAttribute(){},
    addEventListener(){},querySelectorAll:()=>[],querySelector:()=>mkEl(),scrollIntoView(){},blur(){}};return t;};
  const ctx={console,document:{addEventListener(){},getElementById:mkEl,querySelector:mkEl,querySelectorAll:()=>[]},
    localStorage:{getItem:()=>null,setItem(){}},addEventListener(){},fetch:async()=>({ok:false,status:0}),
    setTimeout:()=>0,clearTimeout(){},location:{hash:''},window:{scrollTo(){}},innerWidth:390,performance};
  vm.createContext(ctx);
  const names=['fold','kw','stem','expandQ','matchQ','hasAlt','tokens','alpha','jaccard','parseSize','attrs','fmtSize','compat','isKg','group','mk','SYN','TR',
    'GEN','GEN_NAME','EMOJI','search','qparse','score','qscore','catName','ICONS','iconOf','picOf','typeOf','tpIdx','metaOf'];
  vm.runInContext(js+`;globalThis.__api={${names.map(n=>`get ${n}(){try{return ${n}}catch(e){return undefined}}`).join(',')},
    setDB(d){DB=d;stores=DB.stores||[];GL=DB.groups;GM=Object.fromEntries(GL.map(g=>[g.id,g]));for(const k in GROUPS)delete GROUPS[k];},
    groups:(gid)=>groups(gid), GL:()=>GL, F:()=>F, apply:()=>{apply();return filtered;}, setCur:(c)=>{cur=c;}};`,ctx);
  const api=ctx.__api;
  if(!api.expandQ&&api.qparse) Object.defineProperty(api,'expandQ',{value:q=>api.qparse(q).w.map(w=>w.A.map(x=>x.a))});
  return api;
};
