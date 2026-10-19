document.getElementById('start').addEventListener('click', async () => {
  const status = document.getElementById('status');
  try {
    const [tab] = await chrome.tabs.query({active: true, currentWindow: true});
    if (!/^https:\/\/studio\.youtube\.com\/channel\/UC[A-Za-z0-9_-]{22}\/videos\//.test(tab?.url || '')) {
      throw new Error('请先打开已登录的YouTube Studio → 内容 → 视频列表，再点击扩展。');
    }
    await chrome.scripting.executeScript({target: {tabId: tab.id}, files: ['xlsx.js', 'content.js']});
    status.textContent = '已开始，请回到Studio查看右下角进度。扫描期间不要切换频道、筛选或翻页。';
  } catch (error) { status.textContent = error.message; }
});
