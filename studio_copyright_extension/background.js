importScripts('model_reader.js');
chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (message?.type === 'studioRows') {
    if (!/^https:\/\/studio\.youtube\.com\/channel\//.test(sender.url || '') ||
        !sender.tab?.id || !/^sc_[a-f0-9]{16}$/.test(message.token || '')) {
      sendResponse({error:'页面行读取请求无效'});return;
    }
    chrome.scripting.executeScript({target:{tabId:sender.tab.id,frameIds:[sender.frameId || 0]},
      world:'MAIN',func:readStudioRowModels,args:[message.token]}, results=>{
      sendResponse(chrome.runtime.lastError?{error:chrome.runtime.lastError.message}:{rows:results?.[0]?.result || []});
    });
    return true;
  }
  if (message?.type !== 'copyrightExcel') return;
  if (!/^https:\/\/studio\.youtube\.com\//.test(sender.url || '') ||
      !/^data:application\/vnd\.openxmlformats-officedocument\.spreadsheetml\.sheet;base64,[A-Za-z0-9+/=]+$/.test(message.url || '') ||
      !/^Studio_copyright_UC[A-Za-z0-9_-]{22}_\d{8}_\d{6}\.xlsx$/.test(message.filename || '')) {
    sendResponse({error: '导出请求格式无效'}); return;
  }
  chrome.downloads.download({url: message.url, filename: message.filename, saveAs: true}, id => {
    sendResponse(chrome.runtime.lastError ? {error: chrome.runtime.lastError.message} : {id});
  });
  return true;
});
