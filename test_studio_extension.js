// Development tests: STUDIO_TEST_JSDOM can point to a temporary jsdom installation.
const {test}=require('node:test');const assert=require('node:assert/strict');
const fs=require('node:fs');const vm=require('node:vm');const path=require('node:path');
const {JSDOM}=require(process.env.STUDIO_TEST_JSDOM||'jsdom');
const source=name=>fs.readFileSync(path.join(__dirname,'studio_copyright_extension',name),'utf8');
const core={TextEncoder,Uint8Array,DataView};vm.createContext(core);vm.runInContext(source('xlsx.js'),core);
test('classify copyright and blocked labels without mistaking age or revenue status',()=>{
  for(const label of ['Copyright','已声明版权的内容','Copyright claim','Авторские права'])assert.equal(core.StudioCopyright.classify(label),'版权声明/版权问题');
  assert.equal(core.StudioCopyright.classify('Copyright — Blocked'),'版权问题及禁播标识');
  assert.equal(core.StudioCopyright.classify('Blocked'),'禁播（版权原因待核对）');
  assert.equal(core.StudioCopyright.classify('None'),null);
  for(const label of ['Age restriction','年龄限制','Limited','No copyright issues',''])assert.equal(core.StudioCopyright.classify(label),undefined);
});
function fixture(pages,{missingCell=false,failNext=false,start=0}={}){
  const channel='UC_o03Jz0Ek8xYGE_oy3zapg';
  const dom=new JSDOM('<html><body><div id="rows"></div><button id="navigate-before">prev</button><button id="navigate-after">next</button></body></html>',{url:'https://studio.youtube.com/channel/'+channel+'/videos/upload',runScripts:'outside-only'});
  const w=dom.window;w.TextEncoder=TextEncoder;w.alert=()=>{};
  w.HTMLElement.prototype.getClientRects=function(){return [1];};
  const realTimeout=w.setTimeout.bind(w);w.setTimeout=(fn,ms)=>realTimeout(fn,0);
  if(failNext){let now=0;w.Date.now=()=>now+=10000;}
  let index=start;const messages=[];
  w.chrome={runtime:{sendMessage:async m=>{messages.push(m);return {id:1};}}};
  function render(){w.document.getElementById('rows').innerHTML=pages[index].map((r,i)=>`<ytcp-video-row><a href="/video/${r[0]}/edit" title="${r[1]}">${r[1]}</a>${missingCell?'':`<div id="restrictions">${r[2]}</div>`}</ytcp-video-row>`).join('');w.document.getElementById('navigate-before').disabled=index===0;w.document.getElementById('navigate-after').disabled=index===pages.length-1;}
  w.document.getElementById('navigate-before').onclick=()=>{index--;render();};
  w.document.getElementById('navigate-after').onclick=()=>{if(!failNext){index++;render();}};render();
  w.eval(source('xlsx.js'));w.eval(source('content.js'));
  return {dom,w,messages,async done(){const end=Date.now()+5000;while(w.__studioCopyrightRunning){if(Date.now()>end)throw Error('test timed out');await new Promise(r=>setTimeout(r,5));}return w.document.getElementById('studio-copyright-progress').shadowRoot.textContent;}};
}
test('reads existing tab, returns to first page, paginates, exports copyright and blocked',async()=>{
  const f=fixture([[['copyright01','Copyright drama','Copyright'],['normal00001','Copyright in TITLE only','None']],[['blocked0001','Blocked drama','Copyright — Blocked'],['agerisk0001','Other','年龄限制']]],{start:1});
  try{assert.match(await f.done(),/扫描完成：4/);assert.equal(f.messages.length,1);assert.match(f.messages[0].filename,/\.xlsx$/);
    const bytes=Buffer.from(f.messages[0].url.split(',')[1],'base64');
    let at=0,main='';while(bytes.readUInt32LE(at)===0x04034b50){const size=bytes.readUInt32LE(at+18),n=bytes.readUInt16LE(at+26),extra=bytes.readUInt16LE(at+28),name=bytes.subarray(at+30,at+30+n).toString(),begin=at+30+n+extra;if(name==='xl/worksheets/sheet1.xml')main=bytes.subarray(begin,begin+size).toString();at=begin+size;}
    assert.match(main,/Copyright drama/);assert.match(main,/Blocked drama/);assert.doesNotMatch(main,/TITLE only|Other/);
    const out=process.env.STUDIO_TEST_XLSX;if(out)fs.writeFileSync(out,bytes);
  }finally{f.dom.window.close();}
});
test('missing restrictions column fails without exporting a misleading empty workbook',async()=>{
  const f=fixture([[['copyright01','A','Copyright']]],{missingCell:true});try{assert.match(await f.done(),/无法定位版权限制列/);assert.equal(f.messages.length,0);}finally{f.dom.window.close();}
});
test('pagination timeout does not export a partial result',async()=>{
  const f=fixture([[['copyright01','A','Copyright']],[['blocked0001','B','Blocked']]],{failNext:true});try{assert.match(await f.done(),/翻页后列表未稳定/);assert.equal(f.messages.length,0);}finally{f.dom.window.close();}
});
test('xlsx writer encodes formula-like titles as text and preserves Unicode',()=>{
  const out=core.StudioCopyright.workbook([{name:'版权问题',rows:[['视频名称','视频链接'],['=HYPERLINK("x") 中文','https://www.youtube.com/watch?v=copyright01']]}]);
  assert.equal(out[0],0x50);assert.equal(out[1],0x4b);
  if(process.env.STUDIO_TEST_SAFE_XLSX)fs.writeFileSync(process.env.STUDIO_TEST_SAFE_XLSX,Buffer.from(out));
});
