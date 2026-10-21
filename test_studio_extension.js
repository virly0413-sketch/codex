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
test('recognizes explicit monetization ineligibility without treating disabled monetization as a problem',()=>{
  for(const label of ['此视频不符合创收条件','不符合创收条件','此影片不符合營利資格','This video is not eligible for monetization','Ineligible for monetization','This video cannot be monetized','Monetization: Ineligible']){
    assert.equal(core.StudioCopyright.classify(label),'不符合创收条件（原因待核对）');
  }
  for(const label of ['符合创收条件','Eligible for monetization','Monetization off','Not monetized','Limited'])assert.equal(core.StudioCopyright.classify(label),undefined);
  assert.equal(core.StudioCopyright.classify('此视频不符合创收条件：已声明版权的内容'),'版权声明/版权问题');
});
function fixture(pages,{missingCell=false,failNext=false,start=0,rowMarkup=null,extraRow='',bridgeFailure=false}={}){
  const channel='UC_o03Jz0Ek8xYGE_oy3zapg';
  const dom=new JSDOM('<html><body><div id="rows"></div><button id="navigate-before">prev</button><button id="navigate-after">next</button></body></html>',{url:'https://studio.youtube.com/channel/'+channel+'/videos/upload',runScripts:'outside-only'});
  const w=dom.window;w.TextEncoder=TextEncoder;w.alert=()=>{};
  w.HTMLElement.prototype.getClientRects=function(){return [1];};
  const realTimeout=w.setTimeout.bind(w);w.setTimeout=(fn,ms)=>realTimeout(fn,0);
  if(failNext){let now=0;w.Date.now=()=>now+=10000;}
  let index=start;const messages=[];
  w.eval(source('model_reader.js'));
  w.chrome={runtime:{sendMessage:async m=>{if(m.type==='studioRows')return bridgeFailure?{error:'bridge unavailable'}:{rows:w.readStudioRowModels(m.token)};messages.push(m);return {id:1};}}};
  function render(){w.document.getElementById('rows').innerHTML=pages[index].map((r,i)=>rowMarkup?rowMarkup(r,i):`<ytcp-video-row><a href="/video/${r[0]}/edit" title="${r[1]}">${r[1]}</a>${missingCell?'':`<div id="restrictions">${r[2]}</div>`}<div id="visibility">${r[3]||'Private'}</div></ytcp-video-row>`).join('')+extraRow;Array.from(w.document.querySelectorAll('ytcp-video-row')).forEach((row,i)=>{if(pages[index][i]?.[5])row.data=pages[index][i][5];});w.document.getElementById('navigate-before').disabled=index===0;w.document.getElementById('navigate-after').disabled=index===pages.length-1;}
  w.document.getElementById('navigate-before').onclick=()=>{index--;render();};
  w.document.getElementById('navigate-after').onclick=()=>{if(!failNext){index++;render();}};render();
  w.eval(source('xlsx.js'));w.eval(source('content.js'));
  return {dom,w,messages,async done(){const end=Date.now()+5000;while(w.__studioCopyrightRunning){if(Date.now()>end)throw Error('test timed out');await new Promise(r=>setTimeout(r,5));}return w.document.getElementById('studio-copyright-progress').shadowRoot.textContent;}};
}
test('reads existing tab, returns to first page, paginates, exports copyright and blocked',async()=>{
  const f=fixture([[['copyright01','Copyright drama','Copyright'],['normal00001','Copyright in TITLE only','None']],[['blocked0001','Blocked drama','Copyright — Blocked'],['agerisk0001','Other','年龄限制']]],{start:1});
  try{assert.match(await f.done(),/列表读取结束：4 个未发布视频/);assert.equal(f.messages.length,1);assert.match(f.messages[0].filename,/\.xlsx$/);
    const bytes=Buffer.from(f.messages[0].url.split(',')[1],'base64');
    let at=0,main='';while(bytes.readUInt32LE(at)===0x04034b50){const size=bytes.readUInt32LE(at+18),n=bytes.readUInt16LE(at+26),extra=bytes.readUInt16LE(at+28),name=bytes.subarray(at+30,at+30+n).toString(),begin=at+30+n+extra;if(name==='xl/worksheets/sheet1.xml')main=bytes.subarray(begin,begin+size).toString();at=begin+size;}
    assert.match(main,/Copyright drama/);assert.match(main,/Blocked drama/);assert.doesNotMatch(main,/TITLE only|Other/);
    const out=process.env.STUDIO_TEST_XLSX;if(out)fs.writeFileSync(out,bytes);
  }finally{f.dom.window.close();}
});
test('missing restrictions column fails without exporting a misleading empty workbook',async()=>{
  const f=fixture([[['copyright01','A','Copyright']]],{missingCell:true});try{assert.match(await f.done(),/无法定位版权限制或通知列/);assert.equal(f.messages.length,0);}finally{f.dom.window.close();}
});
test('pagination timeout does not export a partial result',async()=>{
  const f=fixture([[['copyright01','A','Copyright']],[['blocked0001','B','Blocked']]],{failNext:true});try{assert.match(await f.done(),/翻页后列表未稳定/);assert.equal(f.messages.length,0);}finally{f.dom.window.close();}
});
test('xlsx writer encodes formula-like titles as text and preserves Unicode',()=>{
  const out=core.StudioCopyright.workbook([{name:'版权问题',rows:[['视频名称','视频链接'],['=HYPERLINK("x") 中文','https://www.youtube.com/watch?v=copyright01']]}]);
  assert.equal(out[0],0x50);assert.equal(out[1],0x4b);
  if(process.env.STUDIO_TEST_SAFE_XLSX)fs.writeFileSync(process.env.STUDIO_TEST_SAFE_XLSX,Buffer.from(out));
});

function zipEntry(message,name){
  const bytes=Buffer.from(message.url.split(',')[1],'base64');let at=0;
  while(bytes.readUInt32LE(at)===0x04034b50){const size=bytes.readUInt32LE(at+18),n=bytes.readUInt16LE(at+26),extra=bytes.readUInt16LE(at+28),filename=bytes.subarray(at+30,at+30+n).toString(),begin=at+30+n+extra;if(filename===name)return bytes.subarray(begin,begin+size).toString();at=begin+size;}throw Error('ZIP entry missing');
}
test('recognizes private scheduled and unlisted without confusing public',()=>{
  for(const label of ['Private','私享','私密'])assert.equal(core.StudioCopyright.visibility(label),'private');
  for(const label of ['Scheduled','定时发布'])assert.equal(core.StudioCopyright.visibility(label),'scheduled');
  for(const label of ['Unlisted','不公开列出'])assert.equal(core.StudioCopyright.visibility(label),'unlisted');
  for(const label of ['Public','公开'])assert.equal(core.StudioCopyright.visibility(label),'public');
  assert.equal(core.StudioCopyright.visibility(''), 'unknown');
});
test('includes all three unpublished types in default scan',async()=>{
  const f=fixture([[['copyright01','A','Copyright','Private'],['blocked0001','B','Blocked','Scheduled'],['unlisted001','C','Copyright','Unlisted']]]);
  try{assert.match(await f.done(),/列表读取结束：3/);const main=zipEntry(f.messages[0],'xl/worksheets/sheet1.xml');assert.match(main,/unlisted001/);}finally{f.dom.window.close();}
});
test('public list is refused before any next-page navigation',async()=>{
  const f=fixture([[['public00001','A','Copyright','Public']],[['copyright01','B','Copyright','Private']]]);
  try{assert.match(await f.done(),/不会遍历全部公开视频/);assert.equal(f.messages.length,0);assert.match(f.w.document.getElementById('rows').textContent,/Public/);}finally{f.dom.window.close();}
});
test('handles separate title text and standard YouTube watch link plus blank placeholder',async()=>{
  const f=fixture([[['copyright01','Separate title','Copyright']]],{rowMarkup:r=>`<ytcp-video-row><a id="video-thumbnail" href="https://www.youtube.com/watch?v=${r[0]}">1:20:00</a><span id="video-title">${r[1]}</span><div id="restrictions">${r[2]}</div><div id="visibility">私享</div></ytcp-video-row>`,extraRow:'<ytcp-video-row></ytcp-video-row>'});
  try{assert.match(await f.done(),/列表读取结束：1/);const main=zipEntry(f.messages[0],'xl/worksheets/sheet1.xml');assert.match(main,/Separate title/);assert.doesNotMatch(main,/1:20:00/);}finally{f.dom.window.close();}
});
test('thumbnail URL can supply missing video ID',async()=>{
  const f=fixture([[['copyright01','Thumbnail source','Copyright']]],{rowMarkup:r=>`<ytcp-video-row><img src="https://i.ytimg.com/vi/${r[0]}/hqdefault.jpg"><span id="video-title">${r[1]}</span><div id="restrictions">${r[2]}</div><div id="visibility">Private</div></ytcp-video-row>`});
  try{assert.match(await f.done(),/列表读取结束：1/);assert.match(zipEntry(f.messages[0],'xl/worksheets/sheet1.xml'),/Thumbnail source/);}finally{f.dom.window.close();}
});
test('missing title preserves link and explicitly marks name for review',async()=>{
  const f=fixture([[['copyright01','','Copyright']]]);
  try{assert.match(await f.done(),/列表读取结束：1/);assert.match(zipEntry(f.messages[0],'xl/worksheets/sheet1.xml'),/名称未读取/);assert.match(zipEntry(f.messages[0],'xl/worksheets/sheet4.xml'),/copyright01/);}finally{f.dom.window.close();}
});

test('draft rows without anchors use only the marked row-bound video model',async()=>{
  const f=fixture([[['copyright01','Draft with claim','可能存在收入限制','草稿',null,{video:{videoId:'copyright01',title:'Draft with claim'},unrelatedSecret:'not-exported'}]]],{rowMarkup:r=>`<ytcp-video-row><span id="video-title">${r[1]}</span><div id="notifications">${r[2]}</div><div id="visibility">${r[3]}</div><button>编辑草稿</button></ytcp-video-row>`});
  try{assert.match(await f.done(),/列表读取结束：1/);const main=zipEntry(f.messages[0],'xl/worksheets/sheet1.xml');assert.match(main,/Draft with claim/);assert.match(main,/watch\?v=copyright01/);assert.match(zipEntry(f.messages[0],'xl/worksheets/sheet2.xml'),/可能存在收入限制（通知，原因待核对）/);assert.doesNotMatch(Buffer.from(f.messages[0].url.split(',')[1],'base64').toString(),/not-exported/);}finally{f.dom.window.close();}
});
test('draft with no extractable ID preserves its name and marks the missing link',async()=>{
  const f=fixture([[['copyright01','No ID draft','可能存在收入限制','草稿']]],{bridgeFailure:true,rowMarkup:r=>`<ytcp-video-row><span id="video-title">${r[1]}</span><div id="notifications">${r[2]}</div><div id="visibility">草稿</div><button>编辑草稿</button></ytcp-video-row>`});
  try{assert.match(await f.done(),/链接待核对 1/);const main=zipEntry(f.messages[0],'xl/worksheets/sheet1.xml');assert.match(main,/No ID draft/);assert.doesNotMatch(main,/watch\?v=/);assert.match(zipEntry(f.messages[0],'xl/worksheets/sheet5.xml'),/未伪造视频链接/);}finally{f.dom.window.close();}
});
test('draft model IDs stay attached to the correct row across pagination',async()=>{
  const pages=[[['copyright01','First draft','Copyright','草稿',null,{videoId:'copyright01'}]],[['blocked0001','Second draft','Blocked','草稿',null,{videoId:'blocked0001'}]]];
  const f=fixture(pages,{rowMarkup:r=>`<ytcp-video-row><span id="video-title">${r[1]}</span><div id="notifications">${r[2]}</div><div id="visibility">草稿</div></ytcp-video-row>`});
  try{assert.match(await f.done(),/列表读取结束：2/);const main=zipEntry(f.messages[0],'xl/worksheets/sheet1.xml');assert.match(main,/copyright01/);assert.match(main,/blocked0001/);}finally{f.dom.window.close();}
});
test('model reader never walks unrelated global account or token objects',()=>{
  const d=new JSDOM('<ytcp-video-row data-studio-copyright-token="sc_0000000000000000" data-studio-copyright-key="0"></ytcp-video-row>',{runScripts:'outside-only'});
  try{const row=d.window.document.querySelector('ytcp-video-row');row.__data={videoData:{videoId:'copyright01',title:'Draft title'},session:{videoId:'wrong000001',token:'private-token'}};d.window.eval(source('model_reader.js'));const result=d.window.readStudioRowModels('sc_0000000000000000');assert.equal(result[0].id,'copyright01');assert.doesNotMatch(JSON.stringify(result),/private-token|wrong000001/);}finally{d.window.close();}
});
test('notice and restrictions columns are both considered',async()=>{
  const f=fixture([[['copyright01','Draft notice','可能存在收入限制','草稿',null,{videoId:'copyright01'}]]],{rowMarkup:r=>`<ytcp-video-row><span id="video-title">${r[1]}</span><div id="restrictions">—</div><div id="notification-container">${r[2]}</div><div id="visibility">草稿</div></ytcp-video-row>`});
  try{await f.done();assert.match(zipEntry(f.messages[0],'xl/worksheets/sheet1.xml'),/Draft notice/);}finally{f.dom.window.close();}
});

test('background bridge injects only into the sender Studio frame and returns sanitized row data',()=>{
  const d=new JSDOM('<ytcp-video-row data-studio-copyright-token="sc_0000000000000000" data-studio-copyright-key="0"><span>A draft</span></ytcp-video-row>',{runScripts:'outside-only'});
  try{
    d.window.document.querySelector('ytcp-video-row').data={videoId:'copyright01',title:'A draft'};
    let listener,injected;
    const sandbox={chrome:{runtime:{onMessage:{addListener(fn){listener=fn;}}},scripting:{executeScript(options,callback){injected=options;const fn=d.window.eval('('+options.func.toString()+')');callback([{result:fn(...options.args)}]);}}}};
    vm.createContext(sandbox);sandbox.importScripts=name=>vm.runInContext(source(name),sandbox);vm.runInContext(source('background.js'),sandbox);
    let response;
    const keepAlive=listener({type:'studioRows',token:'sc_0000000000000000'},{url:'https://studio.youtube.com/channel/UC_o03Jz0Ek8xYGE_oy3zapg/videos/upload',tab:{id:7},frameId:0},r=>response=r);
    assert.equal(keepAlive,true);assert.equal(injected.world,'MAIN');assert.equal(injected.target.tabId,7);assert.equal(injected.target.frameIds[0],0);assert.equal(response.rows[0].id,'copyright01');
  }finally{d.window.close();}
});
test('background bridge rejects non-Studio senders',()=>{
  let listener,calls=0,response;
  const sandbox={chrome:{runtime:{onMessage:{addListener(fn){listener=fn;}}},scripting:{executeScript(){calls++;}}}};
  vm.createContext(sandbox);sandbox.importScripts=name=>vm.runInContext(source(name),sandbox);vm.runInContext(source('background.js'),sandbox);
  listener({type:'studioRows',token:'sc_0000000000000000'},{url:'https://example.com',tab:{id:1}},r=>response=r);
  assert.equal(calls,0);assert.match(response.error,/无效/);
});

test('ineligible monetization notification is exported with name link and original status',async()=>{
  const f=fixture([[['income00001','Unpublished income issue','此视频不符合创收条件','Private']]]);
  try{assert.match(await f.done(),/列表读取结束：1/);const main=zipEntry(f.messages[0],'xl/worksheets/sheet1.xml');assert.match(main,/Unpublished income issue/);assert.match(main,/watch\?v=income00001/);const details=zipEntry(f.messages[0],'xl/worksheets/sheet2.xml');assert.match(details,/不符合创收条件（原因待核对）/);assert.match(details,/此视频不符合创收条件/);}finally{f.dom.window.close();}
});
test('monetization icon tooltip is read even with no restrictions, while normal settings and title-only matches are ignored',async()=>{
  const f=fixture([[['income00001','Income issue','此视频不符合创收条件','Private'],['normal00001','此视频不符合创收条件 in title only','Eligible for monetization','Unlisted'],['normal00002','Disabled by owner','Monetization off','Scheduled']]],{rowMarkup:r=>`<ytcp-video-row><a href="/video/${r[0]}/edit">${r[1]}</a><div id="restrictions">None</div><div id="monetization"><span aria-label="${r[2]}"></span></div><div id="visibility">${r[3]}</div></ytcp-video-row>`});
  try{assert.match(await f.done(),/列表读取结束：3/);const main=zipEntry(f.messages[0],'xl/worksheets/sheet1.xml');assert.match(main,/income00001/);assert.doesNotMatch(main,/normal00001|normal00002|title only|Disabled by owner/);assert.doesNotMatch(zipEntry(f.messages[0],'xl/worksheets/sheet3.xml'),/normal00001|normal00002/);}finally{f.dom.window.close();}
});
test('monetization column can be located by header when its cell has no stable id',async()=>{
  const f=fixture([[['income00001','Header fallback','This video is not eligible for monetization','Private']]],{rowMarkup:r=>`<ytcp-video-row><div role="cell"><a href="/video/${r[0]}/edit">${r[1]}</a></div><div role="cell"><span title="${r[2]}"></span></div><div role="cell" id="visibility">${r[3]}</div></ytcp-video-row>`,extraRow:'<ytcp-video-section><div role="columnheader">视频</div><div role="columnheader">创收</div><div role="columnheader">公开范围</div></ytcp-video-section>'});
  try{assert.match(await f.done(),/列表读取结束：1/);assert.match(zipEntry(f.messages[0],'xl/worksheets/sheet1.xml'),/Header fallback/);}finally{f.dom.window.close();}
});
