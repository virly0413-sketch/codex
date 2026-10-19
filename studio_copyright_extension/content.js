/* Runs only after an explicit extension click in an already logged-in Studio tab. */
(() => {
  if(globalThis.__studioCopyrightRunning){alert('版权扫描已在此标签页运行，请查看右下角进度。');return;}
  const match=location.pathname.match(/^\/channel\/(UC[A-Za-z0-9_-]{22})\/videos\/([^/]+)/);
  if(!match)throw new Error('请打开Studio内容视频列表');
  const channel=match[1],originalPath=location.pathname;
  globalThis.__studioCopyrightRunning=true;
  document.getElementById('studio-copyright-progress')?.remove();
  const host=document.createElement('div');host.id='studio-copyright-progress';document.documentElement.append(host);
  const shadow=host.attachShadow({mode:'open'});
  const panel=document.createElement('div');panel.style.cssText='position:fixed;right:18px;bottom:18px;z-index:2147483647;background:#fff;color:#111;padding:16px;width:360px;box-shadow:0 2px 20px #555;border-radius:8px;font:14px/1.6 system-ui;white-space:pre-wrap';shadow.append(panel);
  const text=document.createElement('div');panel.append(text);
  const button=document.createElement('button');button.textContent='停止扫描';button.style.cssText='margin-top:8px;padding:6px 18px';panel.append(button);
  let stopped=false;button.onclick=()=>{stopped=true;};
  const pause=ms=>new Promise(resolve=>setTimeout(resolve,ms));
  const visible=el=>Boolean(el.getClientRects().length);
  const cellText=el=>el ? [el.innerText ?? el.textContent,el.getAttribute('aria-label'),el.getAttribute('title'),
    ...Array.from(el.querySelectorAll('[aria-label],[title]')).flatMap(n=>[n.getAttribute('aria-label'),n.getAttribute('title')])]
    .filter(Boolean).map(s=>s.trim()).filter(Boolean).filter((s,i,a)=>a.indexOf(s)===i).join(' | ') : '';
  const chips=()=>Array.from(document.querySelectorAll('ytcp-filter-chip')).filter(visible).map(n=>(n.innerText ?? n.textContent).trim()).join('; ');
  const originalFilters=chips();
  const verify=()=>{
    if(stopped)throw new Error('已停止；未导出未完成的名单。');
    if(location.pathname!==originalPath||chips()!==originalFilters)throw new Error('频道、列表或筛选条件已改变，请重新扫描。');
  };
  function rows(){
    return Array.from(document.querySelectorAll('ytcp-video-row')).filter(visible);
  }
  function rowInfo(row){
    const anchors=Array.from(row.querySelectorAll('a[href*="/video/"]'));
    let id='',title='';
    for(const a of anchors){const m=(a.getAttribute('href')||'').match(/\/video\/([A-Za-z0-9_-]{11})(?:\/|$)/);if(!m)continue;id=m[1];title=(a.getAttribute('title')||a.innerText||a.textContent||'').trim();if(title)break;}
    if(!id||!title)throw new Error('有视频行无法识别名称或链接，请等待列表加载完成再重试。');
    return {id,title,row};
  }
  const ids=()=>rows().map(r=>rowInfo(r).id).join(',');
  function nav(id){
    const elements=Array.from(document.querySelectorAll('#'+id)).filter(visible);
    if(elements.length!==1)throw new Error('无法识别Studio翻页控件，未能确认名单完整。');
    return elements[0];
  }
  const disabled=el=>el.disabled===true||el.hasAttribute('disabled')||el.getAttribute('aria-disabled')==='true';
  async function changePage(button){
    const before=ids();button.click();const deadline=Date.now()+40000;let last='',stable=0;
    while(Date.now()<deadline){
      await pause(300);verify();let current='';try{current=ids();}catch{continue;}
      if(current&&current!==before){stable=current===last?stable+1:0;last=current;if(stable>=3)return;}
    }
    throw new Error('翻页后列表未稳定，未导出未完成的名单。');
  }
  function restrictionCell(row){
    const explicit=row.querySelector('#restrictions, #restrictions-cell, ytcp-video-restrictions');
    if(explicit)return explicit;
    // Layout fallback uses the actual Restrictions header position, never the video title.
    const headers=Array.from(document.querySelectorAll('ytcp-video-section [role="columnheader"], ytcp-table-header [role="columnheader"]')).filter(visible);
    const index=headers.findIndex(h=>/^(限制|Restrictions|Ограничения|Restricciones|제한사항)$/i.test((h.innerText ?? h.textContent).trim()));
    const cells=Array.from(row.querySelectorAll('[role="cell"], [role="gridcell"]'));
    return index>=0?cells[index]:null;
  }
  function toBase64(bytes){let value='';for(let i=0;i<bytes.length;i+=16384)value+=String.fromCharCode(...bytes.subarray(i,i+16384));return btoa(value);}
  async function run(){
    try{
      text.textContent='正在确认列表并回到第一页…\n只读取限制文字、翻页，不修改视频。';
      if(!rows().length)throw new Error('当前列表没有可读取视频，请等待加载完成；空频道/空筛选请在Studio人工确认。');
      for(let i=0;!disabled(nav('navigate-before'));i++){
        if(i>=10000)throw new Error('回到第一页超过安全上限');
        await changePage(nav('navigate-before'));
      }
      const found=[],unknown=[],seen=new Set(),pageSignatures=new Set();let checked=0,pages=0;
      while(true){
        verify();const current=rows().map(rowInfo),signature=current.map(r=>r.id).join(',');
        if(!signature||pageSignatures.has(signature))throw new Error('列表为空或重复，无法确认扫描完成。');
        pageSignatures.add(signature);pages++;
        for(const {id,title,row} of current){
          if(seen.has(id))continue;seen.add(id);checked++;
          const cell=restrictionCell(row);
          if(!cell)throw new Error('无法定位版权限制列。请确认当前是内容列表；页面结构可能已改变。');
          const restriction=cellText(cell),category=StudioCopyright.classify(restriction);
          const info={title,id,url:'https://www.youtube.com/watch?v='+id,restriction,category};
          if(category)found.push(info);
          else if(category===undefined)unknown.push(info);
        }
        if(ids()!==signature)throw new Error('读取过程中列表发生变化，请重新扫描。');
        text.textContent=`已检查 ${checked} 个视频，${pages} 页\n版权/禁播标识 ${found.length} 个；其他或未识别限制 ${unknown.length} 个\n扫描期间不要手动翻页或修改筛选。`;
        const next=nav('navigate-after');if(disabled(next))break;
        if(pages>=10000)throw new Error('超过分页安全上限，未导出。');
        await changePage(next);
      }
      verify();
      const unique=Array.from(new Map(found.map(r=>[r.id,r])).values());
      const now=new Date(),stamp=now.toISOString().replace(/[-:]/g,'').slice(0,15).replace('T','_');
      const sheets=[
        {name:'版权及禁播视频',rows:[['视频名称','视频链接'],...unique.map(r=>[r.title,r.url])]},
        {name:'版权限制详情',rows:[['视频名称','视频链接','分类','Studio限制原文'],...found.map(r=>[r.title,r.url,r.category,r.restriction])]},
        {name:'其他或未识别限制',rows:[['视频名称','视频链接','Studio限制原文'],...unknown.map(r=>[r.title,r.url,r.restriction||'空白/未加载，必须人工核对'])]},
        {name:'检测范围',rows:[['项目','结果'],['来源','当前已登录的Studio可见列表；未读取Cookie或发送到外部服务器'],['频道ID',channel],['页面地址',location.href],['筛选条件',originalFilters||'未识别到筛选标签（以页面实际条件为准）'],['检查数量',String(checked)],['检查页数',String(pages)],['导出时间',now.toISOString()],['范围','仅当前列表标签和筛选结果；需要检查Shorts/直播时分别打开对应列表扫描。'],['版权与收益','版权声明不一定影响收益。仅记录列表版权/禁播文字；是否分成、具体权利人和地区以版权详情为准。'],['识别边界','页面结构或语言变化可能无法识别。请核对其他或未识别限制表；零版权记录不保证没有版权问题。']]}
      ];
      const bytes=StudioCopyright.workbook(sheets);
      const response=await chrome.runtime.sendMessage({type:'copyrightExcel',filename:'Studio_copyright_'+channel+'_'+stamp+'.xlsx',url:'data:application/vnd.openxmlformats-officedocument.spreadsheetml.sheet;base64,'+toBase64(bytes)});
      if(response?.error)throw new Error('保存Excel失败：'+response.error);
      text.textContent=`扫描完成：${checked} 个视频\n登记版权/禁播 ${unique.length} 个；其他或未识别限制 ${unknown.length} 个。\n已发起Excel下载，请完成保存并在Chrome下载列表确认。`;
    }catch(error){text.textContent='扫描未完成：'+error.message+'\n请修复后再次点击扩展。不会把部分扫描当作完整名单。';}
    finally{globalThis.__studioCopyrightRunning=false;button.textContent='关闭提示';button.onclick=()=>host.remove();}
  }
  void run();
})();
