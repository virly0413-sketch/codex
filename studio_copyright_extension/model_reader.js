/* Injected in Studio's MAIN world only to read the marked row's bound video identity.
   Does not read cookies, auth tokens, network responses or global account objects. */
function readStudioRowModels(token) {
  if (!/^sc_[a-f0-9]{16}$/.test(token)) return [];
  return Array.from(document.querySelectorAll('[data-studio-copyright-token="'+token+'"]')).map(row => {
    const ids=new Set(),titles=[];const seen=new Set();
    const get=(obj,key)=>{try{return obj?.[key];}catch{return undefined;}};
    function visit(obj,depth,videoContext=false){
      if(!obj||typeof obj!=='object'||seen.has(obj)||depth>5)return;seen.add(obj);
      for(const key of ['videoId','video_id','encryptedVideoId','externalVideoId']){
        const id=get(obj,key);if(typeof id==='string'&&/^[A-Za-z0-9_-]{11}$/.test(id))ids.add(id);
      }
      if(videoContext){const id=get(obj,'id');if(typeof id==='string'&&/^[A-Za-z0-9_-]{11}$/.test(id))ids.add(id);}
      for(const key of ['title','videoTitle']){
        const value=get(obj,key);
        if(typeof value==='string'&&value.trim())titles.push(value.trim());
        else if(value&&typeof get(value,'simpleText')==='string')titles.push(get(value,'simpleText'));
      }
      for(const key of ['video','videoData','videoEntity','videoDetails','data','__data','item','model','rowData','metadata','details']){
        visit(get(obj,key),depth+1,videoContext||key.startsWith('video'));
      }
    }
    // DOM properties on these row elements are the only page objects inspected.
    visit(row,0);
    for(const cell of row.querySelectorAll('ytcp-video-list-cell-video, #video-title'))visit(cell,0);
    return {key:row.getAttribute('data-studio-copyright-key'),text:(row.textContent||'').slice(0,1200),
      id:ids.size===1?[...ids][0]:null,title:titles[0]||'',conflictingIds:ids.size>1};
  });
}
