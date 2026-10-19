"""Download through Baidu's signed-in website; no bypass of client/captcha restrictions."""
from pathlib import Path, PurePosixPath
import re
from urllib.parse import parse_qs, urlencode, urlsplit, urlunsplit, quote

from baidu_download import VIDEOS


class DownloadUnavailable(ValueError):
    pass


class ClientHandoffNotStarted(ValueError):
    pass


def private_error(exc):
    text = re.sub(r'https?://\S+', '[网址已隐藏]', str(exc))
    return re.sub(r'(?i)(pwd|password|bdstoken|access_token|bduss)=\S+', r'\1=[已隐藏]', text)[:350]


def listing(payload):
    if not isinstance(payload, dict) or payload.get('errno', payload.get('error_code', 0)) != 0:
        raise ValueError('百度网页未允许读取该目录，请在浏览器核对登录、提取码或分享有效性。')
    items = payload.get('list')
    if items is None and isinstance(payload.get('data'), dict):
        items = payload['data'].get('list')
    if not isinstance(items, list):
        raise ValueError('百度目录响应格式不受支持，未将未知响应当作空目录。')
    result = []
    for item in items:
        if 'fs_id' not in item or 'server_filename' not in item:
            raise ValueError('百度文件记录缺少必要字段。')
        result.append(dict(id=str(item['fs_id']), name=item['server_filename'],
            path=item.get('path', ''), isdir=bool(int(item.get('isdir', 0))),
            size=int(item.get('size', 0)), md5=item.get('md5', '')))
    return result


def validate_video(path, suggested_name, expected_size):
    path = Path(path)
    if Path(suggested_name).suffix.lower() not in VIDEOS:
        raise ValueError('网页返回的不是视频文件，可能是压缩包或客户端提示，未标为成功。')
    actual = path.stat().st_size
    if actual <= 0 or (expected_size > 0 and actual != expected_size):
        raise ValueError('下载文件大小与网盘记录不符，未标为成功。')
    with path.open('rb') as f:
        prefix = f.read(512).lstrip().lower()
    if prefix.startswith((b'<!doctype', b'<html', b'{"errno', b'{"error', b'<script')):
        raise ValueError('下载得到网页/错误内容，未标为视频。')


class BaiduBrowser:
    def __init__(self, profile, pause, cancelled, log=print, channel='msedge'):
        self.profile, self.pause, self.cancelled, self.log, self.channel = Path(profile), pause, cancelled, log, channel
        self.playwright = self.context = self.page = None
        self.template = self.share = None

    def __enter__(self):
        from playwright.sync_api import sync_playwright
        self.profile.mkdir(parents=True, exist_ok=True)
        self.playwright = sync_playwright().start()
        try:
            kwargs = dict(user_data_dir=str(self.profile), headless=False, accept_downloads=True,
                          viewport={'width':1280, 'height':850})
            if self.channel != 'chromium': kwargs['channel'] = self.channel
            self.context = self.playwright.chromium.launch_persistent_context(**kwargs)
            self.page = self.context.pages[0] if self.context.pages else self.context.new_page()
            self.page.on('response', self._observe)
            return self
        except Exception:
            self.playwright.stop()
            raise RuntimeError('无法启动下载专用浏览器。Windows请选择已安装的Edge或Chrome；也可按说明安装Chromium。') from None

    def __exit__(self, *_):
        try:
            if self.context: self.context.close()
        finally:
            if self.playwright: self.playwright.stop()

    def _observe(self, response):
        parts = urlsplit(response.url)
        if parts.hostname != 'pan.baidu.com' or parts.path not in ('/share/list', '/share/wxlist'):
            return
        try:
            listing(response.json())
            self.template = response.url
        except Exception:
            pass

    def login(self):
        self.page.goto('https://pan.baidu.com/', wait_until='domcontentloaded', timeout=45000)
        self.pause('请在浏览器完成百度网盘登录，然后点击程序里的“已处理，继续”。')

    def open_share(self, share):
        self.template = None
        self.share = share
        self.page.goto(share['url'], wait_until='domcontentloaded', timeout=45000)
        self.page.wait_for_timeout(1200)
        fields = self.page.locator('input#accessCode, .pickpw input[type="text"], input[placeholder*="提取码"]')
        for field in fields.all():
            if field.is_visible() and share.get('password'):
                field.fill(share['password'])
                button = self.page.get_by_text(re.compile(r'^(提取文件|提取|访问文件|提交)$')).filter(visible=True)
                if button.count() == 1: button.click()
                else: field.press('Enter')
                self.page.wait_for_timeout(1500)
                break
        for attempt in range(2):
            if self.template:
                return
            data = self.page.evaluate('''() => {
                const y=window.yunData; const get=k=>{try{return y?.[k] || y?.get?.(k);}catch{return null;}};
                return {shareid:get('SHARE_ID')||get('shareid'), uk:get('SHARE_UK')||get('uk')};
            }''')
            if data.get('shareid') and data.get('uk'):
                self.template = 'https://pan.baidu.com/share/list?' + urlencode(dict(
                    shareid=str(data['shareid']), uk=str(data['uk']), web=1, order='name', desc=0, num=100, page=1, root=1))
                return
            if attempt == 0:
                self.pause('网页尚未返回目录。请在浏览器完成登录/验证码/提取码，并打开分享里的一个文件夹，再点击“已处理，继续”。')
                self.page.wait_for_timeout(1000)
        raise ValueError('无法取得分享目录；可能分享失效、无权限或页面结构变化，未下载未知内容。')

    def _list_dir(self, path, root=False):
        parts = urlsplit(self.template)
        params = {k: v[-1] for k, v in parse_qs(parts.query).items()}
        params.update(dir=path, root='1' if root else '0', num='100')
        all_items, seen, signatures = [], set(), set()
        for number in range(1, 1001):
            if self.cancelled(): raise InterruptedError('已停止。')
            params['page'] = str(number)
            response = self.page.request.get(urlunsplit((parts.scheme, parts.netloc, parts.path,
                urlencode(params), '')), timeout=30000)
            if not response.ok:
                raise ValueError('百度目录请求失败，HTTP ' + str(response.status))
            payload = response.json()
            items = listing(payload)
            signature = tuple(x['id'] for x in items)
            if signature and signature in signatures:
                raise ValueError('目录分页返回重复页，扫描不完整，已停止。')
            signatures.add(signature)
            for item in items:
                if item['id'] not in seen:
                    seen.add(item['id']); all_items.append(item)
            more = payload.get('has_more', payload.get('hasmore'))
            if more is False or more == 0:
                return all_items
            if not items:
                return all_items
        raise ValueError('目录超过分页安全上限，未将部分扫描作为完整结果。')

    def inventory(self, share):
        self.open_share(share)
        files, seen = [], set()
        pending = [('/', [], True)]
        while pending:
            path, parents, root = pending.pop()
            if path in seen: continue
            seen.add(path)
            if len(seen) > 1000 or len(parents) > 12:
                raise ValueError('分享目录过深或过多，请改用更具体的剧集分享链接。')
            for item in self._list_dir(path, root):
                item['parents'] = parents
                item['path'] = item['path'] or str(PurePosixPath(path) / item['name'])
                if item['isdir']:
                    pending.append((item['path'], parents + [item['name']], False))
                else:
                    files.append(item)
            if len(files) > 100000:
                raise ValueError('分享文件数过多，请使用更具体的剧集目录。')
        self.log(f'目录读取完成：{len(files)}个文件；只按明确语种标记筛选视频。')
        return files

    def _file_row(self, item):
        if re.fullmatch(r'\d+', item['id']):
            for selector in (f'[data-id="{item["id"]}"]', f'[data-fsid="{item["id"]}"]'):
                rows = self.page.locator(selector).filter(visible=True)
                if rows.count() == 1:
                    return rows
        labels = self.page.get_by_text(item['name'], exact=True).filter(visible=True)
        if labels.count() != 1:
            raise ValueError('无法唯一定位文件行，未点击可能错误的文件。')
        row = labels.locator('xpath=ancestor::*[self::tr or self::dd or @role="row" or '
            'contains(@class,"body-row")][1]')
        if row.count() != 1:
            raise ValueError('无法识别该版本的百度文件行，需要适配页面。')
        return row

    def _download_control(self, share, item):
        if self.cancelled(): raise InterruptedError('已停止。')
        # Fresh navigation clears previous selection. Never invoke a bulk selection.
        parent = str(PurePosixPath(item['path']).parent)
        parts = urlsplit(share['url'])
        url = urlunsplit((parts.scheme, parts.netloc, parts.path, parts.query,
            '/list/path=' + quote(parent, safe='') + '&parentPath=' + quote(str(PurePosixPath(parent).parent), safe='')))
        self.page.goto(url, wait_until='domcontentloaded', timeout=45000)
        # A same-directory SPA navigation may retain another file's checkbox.
        # Force a document reload, then require an explicit single-file selection below.
        self.page.reload(wait_until='domcontentloaded', timeout=45000)
        self.page.wait_for_timeout(1500)
        row = self._file_row(item)
        row.hover()
        direct = row.locator('a[title="下载"],button[title="下载"], [data-type="download"]').filter(visible=True)
        if direct.count() == 1:
            button = direct
        else:
            box = row.locator('input[type="checkbox"], [role="checkbox"], .icon-check').filter(visible=True)
            if box.count() != 1:
                raise ValueError('无法可靠选择唯一文件，未执行批量下载。')
            box.click()
            body = self.page.locator('body').inner_text()
            count = re.search(r'已选(?:中|择)?\s*(\d+)\s*(?:个|项)', body)
            if not count or count.group(1) != '1':
                raise ValueError('网页未确认只选中1个文件，已停止以防混下其他语种。')
            button = self.page.get_by_role('link', name='下载', exact=True).filter(visible=True)
            if button.count() != 1:
                button = self.page.get_by_role('button', name='下载', exact=True).filter(visible=True)
            if button.count() != 1:
                raise ValueError('无法唯一定位官方下载按钮。')
        return button

    def queue_client(self, share, item, inbox):
        """Ask Baidu's own page to launch the registered official client for one file."""
        try:
            button = self._download_control(share, item)
        except Exception as exc:
            raise ClientHandoffNotStarted(private_error(exc)) from None
        downloads=[]
        capture=lambda download:downloads.append(download)
        self.page.on('download',capture)
        try:
            button.click()
            self.page.wait_for_timeout(1800)
            if downloads:
                # Some files are delivered directly by the official website instead.
                download=downloads[0]
                if Path(download.suggested_filename).suffix.lower() not in VIDEOS:
                    download.cancel()
                    raise DownloadUnavailable('百度提供了非视频文件，未接收。请在网页选择客户端下载。')
                if Path(item['name']).name!=item['name'] or '\\' in item['name']:
                    download.cancel();raise ValueError('网盘文件名含路径分隔符。')
                destination=Path(inbox)/item['name']
                if destination.exists():
                    download.cancel();raise ValueError('中转目录已有同名文件，未覆盖。')
                temp=destination.with_suffix(destination.suffix+'.baidupart')
                try:
                    download.save_as(temp)
                    validate_video(temp,download.suggested_filename,item['size'])
                    temp.replace(destination)
                finally:temp.unlink(missing_ok=True)
                return
            protocols=self.page.locator('a[href^="baidunetdisk://"], a[href^="baiduyunguanjia://"]').filter(visible=True)
            if protocols.count()==1:
                href=protocols.get_attribute('href')
                import os
                if os.name!='nt':raise ValueError('客户端下载模式仅在Windows启用。')
                if not href or not href.startswith(('baidunetdisk://','baiduyunguanjia://')):
                    raise ValueError('未找到受支持的百度客户端协议。')
                os.startfile(href)
            else:
                action=self.page.get_by_text(re.compile(r'^(使用客户端下载|启动客户端|打开百度网盘|打开客户端|使用百度网盘下载|立即启动)$')).filter(visible=True)
                if action.count()==1:action.click()
            self.log('已请求官方下载；如出现浏览器“打开百度网盘”提示，请允许并在客户端确认任务。')
        finally:
            self.page.remove_listener('download',capture)

    def download(self, share, item, target):
        button=self._download_control(share,item)
        target = Path(target)
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.exists():
            raise ValueError('同名文件未通过已下载校验，未覆盖现有文件；请另选目录或先手动处理。')
        temporary = target.with_suffix(target.suffix + '.baidupart')
        try:
            with self.page.expect_download(timeout=45000) as event:
                button.click()
            download = event.value
            if Path(download.suggested_filename).suffix.lower() not in VIDEOS:
                download.cancel()
                raise ValueError('网页返回压缩包或非视频，已取消，未标为成功。')
            download.save_as(temporary)
            if download.failure():
                raise ValueError('浏览器报告下载失败，未标为成功。')
            validate_video(temporary, download.suggested_filename, item['size'])
            temporary.replace(target)
        except Exception as exc:
            temporary.unlink(missing_ok=True)
            if 'Timeout' in type(exc).__name__:
                raise DownloadUnavailable('网页未提供浏览器下载：可能要求客户端、登录或验证码；请在网页处理后重试。') from None
            raise
