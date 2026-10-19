/* Runs only after an explicit extension click in an already logged-in Studio tab. */
(() => {
  if(globalThis.__studioCopyrightRunning){alert('版权扫描已在此标签页运行，请查看右下角进度。');return;}
  const match=location.pathname.match(/^\/channel\/(UC[A-Za-z0-9_-]{22})\/videos\/([^/]+)/);
  if(!match)throw new Error('请打开Studio内容视频列表');
  const channel=match[1],originalPath=location.pathname;
  const includeUnlisted=globalThis.StudioCopyrightOptions?.includeUnlisted!==false;
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
    return Array.from(document.querySelectorAll('ytcp-video-row')).filter(visible).filter(row=>
      !row.hidden && row.getAttribute('aria-hidden')!=='true' && !row.matches('[loading], [aria-busy="true"], [is-ghost], [is-placeholder], .skeleton, .placeholder') &&
      Boolean(row.textContent.trim()||row.querySelector('[href], [data-video-id], [video-id], img')));
  }
  function rowInfo(row){
    const candidates=[];
    for(const node of [row,...row.querySelectorAll('[data-video-id], [video-id]')]){
      const id=node.getAttribute('data-video-id')||node.getAttribute('video-id');
      if(/^[A-Za-z0-9_-]{11}$/.test(id||''))candidates.push(id);
    }
    const anchors=Array.from(row.querySelectorAll('[href]'));
    for(const a of anchors){
      const href=a.getAttribute('href')||'';
      try{
        const url=new URL(href,location.origin);
        if(!['studio.youtube.com','www.youtube.com','youtube.com','youtu.be'].includes(url.hostname))continue;
        const id=url.pathname.match(/\/(?:video|shorts|live)\/([A-Za-z0-9_-]{11})(?:\/|$)/)?.[1] ||
          (url.pathname==='/watch'?url.searchParams.get('v'):null) ||
          (url.hostname==='youtu.be'?url.pathname.slice(1):null);
        if(/^[A-Za-z0-9_-]{11}$/.test(id||''))candidates.push(id);
      }catch{}
    }
    for(const image of row.querySelectorAll('img[src]')){
      const id=(image.getAttribute('src')||'').match(/^https:\/\/(?:i|img)\.ytimg\.com\/(?:vi|vi_webp)\/([A-Za-z0-9_-]{11})\//)?.[1];
      if(id)candidates.push(id);
    }
    const unique=[...new Set(candidates)];
    if(unique.length!==1)throw new Error('视频ID尚未加载或链接无法识别');
    const titleNodes=[...row.querySelectorAll('#video-title, .video-title, [data-video-title], #title'),...anchors.filter(a=>!/thumbnail/i.test(a.id)&&/\/video\/|watch\?/.test(a.getAttribute('href')||''))];
    let title='';
    for(const node of titleNodes){
      title=(node.getAttribute('data-video-title')||node.getAttribute('title')||node.innerText||node.textContent||'').trim();
      if(title&&!/^\d{1,3}:\d{2}(?::\d{2})?$/.test(title))break;
      title='';
    }
    // A known ID is retained even if Studio puts the title in an unsupported element.
    return {id:unique[0],title:title||'名称未读取（视频ID：'+unique[0]+'）',missingTitle:!title,row};
  }
  function visibilityCell(row){
    return row.querySelector('#visibility, #visibility-cell, #privacy, ytcp-video-visibility') || columnCell(row,/^(公开范围|可见性|Visibility|Видимость|Доступ|Visibilidad|공개 상태)$/i);
  }
  async function readyRows(){
    let lastError;
    for(let attempt=0;attempt<20;attempt++){
      verify();
      try{
        const current=rows().map(rowInfo);
        if(!current.length)throw new Error('当前列表没有加载出视频行');
        if(current.some(r=>!cellText(visibilityCell(r.row))))throw new Error('尚未读取到公开范围列');
        if(current.some(r=>r.missingTitle)&&attempt<4){await pause(500);continue;}
        return current;
      }catch(error){lastError=error;await pause(500);}
    }
    throw new Error('等待列表加载后仍无法读取：'+lastError.message+'。请确认已筛选私享/定时视频，刷新Studio页面后重试。');
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
  function columnCell(row,pattern){
    const headers=Array.from(document.querySelectorAll('ytcp-video-section [role="columnheader"], ytcp-table-header [role="columnheader"]')).filter(visible);
    const index=headers.findIndex(h=>pattern.test((h.innerText ?? h.textContent).trim()));
    const cells=Array.from(row.querySelectorAll('[role="cell"], [role="gridcell"]'));
    return index>=0?cells[index]:null;
  }
  function restrictionCell(row){
    return row.querySelector('#restrictions, #restrictions-cell, ytcp-video-restrictions') || columnCell(row,/^(限制|Restrictions|Ограничения|Restricciones|제한사항)$/i);
  }
  function validateUnpublished(current){
    for(const info of current){
      const label=cellText(visibilityCell(info.row));
      const kind=StudioCopyright.visibility(label);
      if(kind==='private'||kind==='scheduled'||(includeUnlisted&&kind==='unlisted'))continue;
      if(kind==='unknown')throw new Error('无法确认视频公开范围：'+info.title+'。请检查公开范围列及页面语言，程序不会猜测未发布状态。');
      throw new Error('当前列表包含'+(kind==='unlisted'?'不公开列出':'已公开')+'视频。请先在Studio“公开范围”筛选中只选择私享/定时发布'+(includeUnlisted?'/不公开列出':'')+'，然后重新扫描；程序不会遍历全部公开视频。');
    }
  }
  function toBase64(bytes){let value='';for(let i=0;i<bytes.length;i+=16384)value+=String.fromCharCode(...bytes.subarray(i,i+16384));return btoa(value);}
  async function run(){
    try{
      text.textContent='正在确认未发布视频列表…\n请先在Studio公开范围筛选中选择私享、定时发布、不公开列出。';
      const initial=await readyRows();
      validateUnpublished(initial);
      for(let i=0;!disabled(nav('navigate-before'));i++){
        if(i>=10000)throw new Error('回到第一页超过安全上限');
        await changePage(nav('navigate-before'));
      }
      const found=[],unknown=[],missingNames=[],seen=new Set(),pageSignatures=new Set();let checked=0,pages=0;
      while(true){
        verify();const current=await readyRows(),signature=current.map(r=>r.id).join(',');
        validateUnpublished(current);
        if(!signature||pageSignatures.has(signature))throw new Error('列表为空或重复，无法确认扫描完成。');
        pageSignatures.add(signature);pages++;
        for(const {id,title,row,missingTitle} of current){
          if(seen.has(id))continue;seen.add(id);checked++;
          const cell=restrictionCell(row);
          if(!cell)throw new Error('无法定位版权限制列。请确认当前是内容列表；页面结构可能已改变。');
          const restriction=cellText(cell),category=StudioCopyright.classify(restriction);
          const info={title,id,visibility:cellText(visibilityCell(row)),url:'https://www.youtube.com/watch?v='+id,restriction,category};
          if(missingTitle)missingNames.push(info);
          if(category)found.push(info);
          else if(category===undefined)unknown.push(info);
        }
        if(ids()!==signature)throw new Error('读取过程中列表发生变化，请重新扫描。');
        text.textContent=`已检查 ${checked} 个未发布视频，${pages} 页\n版权/禁播标识 ${found.length} 个；其他或未识别限制 ${unknown.length} 个\n扫描期间不要手动翻页或修改筛选。`;
        const next=nav('navigate-after');if(disabled(next))break;
        if(pages>=10000)throw new Error('超过分页安全上限，未导出。');
        await changePage(next);
      }
      verify();
      const unique=Array.from(new Map(found.map(r=>[r.id,r])).values());
      const now=new Date(),stamp=now.toISOString().replace(/[-:]/g,'').slice(0,15).replace('T','_');
      const sheets=[
        {name:'版权及禁播视频',rows:[['视频名称','视频链接'],...unique.map(r=>[r.title,r.url])]},
        {name:'版权限制详情',rows:[['视频名称','视频链接','分类','Studio限制原文','公开范围'],...found.map(r=>[r.title,r.url,r.category,r.restriction,r.visibility])]},
        {name:'其他或未识别限制',rows:[['视频名称','视频链接','Studio限制原文'],...unknown.map(r=>[r.title,r.url,r.restriction||'空白/未加载，必须人工核对'])]},
        {name:'名称待核对',rows:[['视频名称','视频链接','公开范围'],...missingNames.map(r=>[r.title,r.url,r.visibility])]},
        {name:'检测范围',rows:[['项目','结果'],['来源','当前已登录的Studio可见列表；未读取Cookie或发送到外部服务器'],['频道ID',channel],['页面地址',location.href],['筛选条件',originalFilters||'未识别到筛选标签（以页面实际条件为准）'],['未发布口径',includeUnlisted?'私享、定时发布、不公开列出':'私享、定时发布（不含不公开列出）'],['名称待核对',String(missingNames.length)],['检查数量',String(checked)],['检查页数',String(pages)],['导出时间',now.toISOString()],['范围','仅当前列表标签和筛选结果；需要检查Shorts/直播时分别打开对应列表扫描。'],['版权与收益','版权声明不一定影响收益。仅记录列表版权/禁播文字；是否分成、具体权利人和地区以版权详情为准。'],['识别边界','页面结构或语言变化可能无法识别。请核对其他或未识别限制表；零版权记录不保证没有版权问题。']]}
      ];
      const bytes=StudioCopyright.workbook(sheets);
      const response=await chrome.runtime.sendMessage({type:'copyrightExcel',filename:'Studio_copyright_'+channel+'_'+stamp+'.xlsx',url:'data:application/vnd.openxmlformats-officedocument.spreadsheetml.sheet;base64,'+toBase64(bytes)});
      if(response?.error)throw new Error('保存Excel失败：'+response.error);
      text.textContent=`扫描完成：${checked} 个未发布视频\n登记版权/禁播 ${unique.length} 个；其他或未识别限制 ${unknown.length} 个；名称待核对 ${missingNames.length} 个。\n已发起Excel下载，请完成保存并在Chrome下载列表确认。`;
    }catch(error){text.textContent='扫描未完成：'+error.message+'\n请修复后再次点击扩展。不会把部分扫描当作完整名单。';}
    finally{globalThis.__studioCopyrightRunning=false;button.textContent='关闭提示';button.onclick=()=>host.remove();}
  }
  void run();
})();
