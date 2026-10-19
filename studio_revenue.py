"""Read visible Studio content rows, without changing videos or monetization."""
import re
import time
from pathlib import Path
from urllib.parse import urlsplit

LIMITATION = '收益状态来自本次Studio页面可见标识，不是Data API；未识别、未加载及未显示的状态必须人工核对。'


def revenue_status(text):
    text = re.sub(r'\s+', ' ', text).strip()
    low = text.casefold()
    if not text: return '收益待核对', 'Studio未显示可识别的收益状态'
    if any(x in low for x in ('limited', '受限', '有限', 'огранич', 'limitad')):
        return '收入限制', text
    if any(x in low for x in ('ineligible', 'not eligible', '不符合', '无法创收', '不能创收', 'недоступ', 'no apto')):
        return '无法创收', text
    if any(x in low for x in ('sharing', '分成', '共享收益', 'делит')):
        return '收益分成', text
    if any(x in low for x in ('checking', 'under review', '检查中', '审核中', 'провер')):
        return '收益审核中', text
    if low in ('off', '关闭', '已关闭', 'выкл.', 'desactivada', 'desactivado') or 'monetization off' in low or '创收功能已关闭' in low:
        return '收益关闭（需核对）', text
    if low in ('on', '开启', '已开启', 'вкл.', 'activada', 'activado') or low in ('monetization on', '创收功能已开启'):
        return None, text
    return '收益待核对', text


def scan_studio(channel_id, profile, browser='auto', progress=print, executable=''):
    from playwright.sync_api import sync_playwright
    if not re.fullmatch(r'UC[A-Za-z0-9_-]{22}',channel_id): raise ValueError('Studio频道ID格式错误')
    result=[];seen=set();pages=set()
    with sync_playwright() as p:
        from monitor_browser import launch_studio_browser
        context=launch_studio_browser(p.chromium,profile,browser,executable,progress)
        try:
            page=context.pages[0] if context.pages else context.new_page()
            page.goto('https://studio.youtube.com/channel/'+channel_id+'/videos/upload',wait_until='domcontentloaded',timeout=60000)
            progress('请在打开的浏览器中登录目标频道；等待内容列表显示（最多3分钟）。')
            page.locator('ytcp-video-row').first.wait_for(state='visible',timeout=180000)
            for _ in range(10000):
                current=re.search(r'/channel/([^/]+)',urlsplit(page.url).path)
                if not current or current.group(1)!=channel_id: raise ValueError('Studio当前频道与目标频道不一致，未导出收益扫描结果。')
                rows=page.locator('ytcp-video-row');count=rows.count()
                if not count: raise ValueError('Studio列表未加载，不能视为无收益限制。')
                page_ids=[]
                for i in range(count):
                    row=rows.nth(i)
                    anchors=row.locator('a[href*="/video/"]')
                    video_id=None;title=''
                    for j in range(anchors.count()):
                        anchor=anchors.nth(j);match=re.search(r'/video/([A-Za-z0-9_-]{11})(?:/|$)',anchor.get_attribute('href') or '')
                        if match:
                            video_id=match.group(1)
                            title=(anchor.get_attribute('title') or anchor.inner_text()).strip()
                            if title: break
                    if not video_id: raise ValueError('有Studio视频行无法读取视频ID，扫描不完整。')
                    page_ids.append(video_id)
                    if video_id in seen:continue
                    seen.add(video_id)
                    hosts=row.locator('ytcp-video-monetization, #monetization, #monetization-cell')
                    texts=[]
                    for j in range(hosts.count()):
                        host=hosts.nth(j)
                        texts.append(host.inner_text())
                        labels=host.locator('[aria-label], [title]')
                        for k in range(labels.count()):
                            node=labels.nth(k)
                            texts.extend([node.get_attribute('aria-label') or '',node.get_attribute('title') or ''])
                        texts.extend([host.get_attribute('aria-label') or '',host.get_attribute('title') or ''])
                    text=' '.join(dict.fromkeys(t.strip() for t in texts if t.strip()))
                    category,reason=revenue_status(text)
                    if category:
                        result.append({'视频名称':title or video_id,'视频链接':'https://www.youtube.com/watch?v='+video_id,
                                       '分类':category,'限制详情':reason,'来源':'Studio收益列'})
                signature=tuple(page_ids)
                if signature in pages:raise ValueError('Studio分页重复，未能确认扫描完整。')
                pages.add(signature);progress('Studio已检查 '+str(len(seen))+' 个视频')
                next_button=page.locator('ytcp-table-pagination #navigate-after')
                if next_button.count()!=1:raise ValueError('无法识别Studio下一页控件，不能确认扫描完整。')
                if next_button.is_disabled() or next_button.get_attribute('disabled') is not None or next_button.get_attribute('aria-disabled')=='true':
                    return dict(rows=result,checked=len(seen),limitation=LIMITATION)
                next_button.click()
                # Wait for actual row identity change, not just a fixed delay.
                deadline=time.monotonic()+30
                while time.monotonic()<deadline:
                    hrefs=page.locator('ytcp-video-row a[href*="/video/"]').evaluate_all('(nodes)=>nodes.map(n=>n.getAttribute("href"))')
                    new_ids=list(dict.fromkeys(m.group(1) for href in hrefs if (m:=re.search(r'/video/([A-Za-z0-9_-]{11})(?:/|$)',href or ''))))
                    if new_ids and tuple(new_ids)!=signature:break
                    page.wait_for_timeout(250)
                else:raise ValueError('Studio翻页超时，未完成收益扫描。')
            raise ValueError('Studio分页超过安全上限，扫描未完成。')
        finally:context.close()
