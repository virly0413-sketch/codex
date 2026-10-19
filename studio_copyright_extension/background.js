chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
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
