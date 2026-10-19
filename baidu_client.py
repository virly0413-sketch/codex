"""Official-client handoff and verified routing from a dedicated download inbox."""
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import time

from baidu_browser import ClientHandoffNotStarted, DownloadUnavailable, validate_video
from baidu_download import atomic_json, share_identity


def client_executable():
    candidates=[]
    for variable in ('APPDATA','LOCALAPPDATA','ProgramFiles','ProgramFiles(x86)'):
        value=os.environ.get(variable)
        if value:
            for tail in ('baidu/BaiduNetdisk/BaiduNetdisk.exe','BaiduNetdisk/BaiduNetdisk.exe'):
                candidates.append(Path(value)/tail)
    return str(next((p for p in candidates if p.is_file()),''))


def launch_client(path):
    path=Path(path)
    if os.name!='nt':raise ValueError('本机百度客户端模式需要Windows。')
    if not path.is_file() or path.name.lower()!='baidunetdisk.exe':
        raise ValueError('请选择已安装的百度网盘BaiduNetdisk.exe。')
    subprocess.Popen([str(path)])


def matching_name(name, expected):
    if Path(name).suffix.lower()!=Path(expected).suffix.lower():return False
    a=Path(name).stem.casefold();b=Path(expected).stem.casefold()
    return a==b or bool(re.fullmatch(re.escape(b)+r'\s*[（(]\d+[）)]',a))


def fingerprint(path):
    st=path.stat();return [st.st_size,st.st_mtime_ns]


def candidates(inbox, expected):
    for path in Path(inbox).rglob('*'):
        if path.is_file() and matching_name(path.name,expected):
            yield path


def cloud_md5(path):
    digest=hashlib.md5()
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda:stream.read(4*1024*1024),b''):digest.update(chunk)
    return digest.hexdigest()


class ClientDownloads:
    def __init__(self,browser,inbox,work,cancelled=lambda:False,log=print,
                 timeout_seconds=7200,stable_seconds=4,poll_seconds=1):
        self.browser=browser;self.inbox=Path(inbox).resolve();self.work=Path(work)
        self.cancelled=cancelled;self.log=log;self.timeout=timeout_seconds
        self.stable=stable_seconds;self.poll=poll_seconds
        self.pending_path=self.work/'client_pending.json'
        self.pending=json.loads(self.pending_path.read_text(encoding='utf-8')) if self.pending_path.exists() else {}
        self.inbox.mkdir(parents=True,exist_ok=True)

    def inventory(self,share):return self.browser.inventory(share)

    def _find_complete(self,item,pending,stability,bad):
        valid=[]
        md5=str(item.get('md5','')).lower()
        has_md5=bool(re.fullmatch('[a-f0-9]{32}',md5))
        if item['size']<=0 and not has_md5:
            raise ValueError('客户端下载缺少可核对大小/校验值，无法判断完整性。')
        for path in candidates(self.inbox,item['name']):
            try:
                fp=fingerprint(path);key=str(path.resolve())
                if pending['baseline'].get(key)==fp:continue
                if item['size']>0 and fp[0]!=item['size']:continue
                # The client keeps partial files under temporary suffixes; do not take them.
                if any(Path(str(path)+s).exists() for s in ('.baiduyun.downloading','.downloading','.aria2','.tmp','.baidupart')):
                    continue
                now=time.monotonic()
                if key not in stability or stability[key][0]!=fp:stability[key]=(fp,now)
                if now-stability[key][1]<self.stable:continue
                if bad.get(key)==fp:continue
                validate_video(path,item['name'],item['size'])
                if has_md5 and cloud_md5(path)!=md5:
                    bad[key]=fp;continue
                valid.append(path)
            except (OSError,ValueError):continue
        if len(valid)>1:
            raise ValueError('中转目录出现多个同名匹配，请先处理重复项；未随意归档。')
        return valid[0] if valid else None

    def download(self,share,item,target):
        target=Path(target)
        if target.exists():raise ValueError('目标同名文件未经完成校验，未覆盖。')
        if self.inbox==target.parent.resolve() or self.inbox in target.resolve().parents or target.parent.resolve() in self.inbox.parents:
            raise ValueError('中转目录必须与各语种保存目录分开，且不能相互包含。')
        identity=hashlib.sha256((share_identity(share)+'|'+item['id']+'|'+str(target.resolve())).encode()).hexdigest()
        if identity not in self.pending:
            baseline={str(p.resolve()):fingerprint(p) for p in candidates(self.inbox,item['name'])}
            self.pending[identity]=dict(baseline=baseline,started_at=time.time(),name=item['name'],target=str(target))
            atomic_json(self.pending_path,self.pending)
            try:self.browser.queue_client(share,item,self.inbox)
            except ClientHandoffNotStarted:
                del self.pending[identity];atomic_json(self.pending_path,self.pending)
                raise
        else:
            self.log('恢复等待已有客户端任务，不重复发送：'+item['name'])
        pending=self.pending[identity];started=time.monotonic();last_log=started-20
        stability={};bad={}
        while time.monotonic()-started<self.timeout:
            if self.cancelled():raise InterruptedError('已停止等待；客户端可继续下载，未完成任务记录已保留。')
            source=self._find_complete(item,pending,stability,bad)
            if source:
                target.parent.mkdir(parents=True,exist_ok=True)
                temp=target.with_suffix(target.suffix+'.baidupart')
                try:
                    shutil.copyfile(source,temp)
                    validate_video(temp,item['name'],item['size'])
                    md5=str(item.get('md5','')).lower()
                    if re.fullmatch('[a-f0-9]{32}',md5) and cloud_md5(temp)!=md5:
                        raise ValueError('归档后校验不一致，保留中转文件，未标为成功。')
                    if target.exists():raise ValueError('目标文件刚被其他任务占用，未覆盖。')
                    temp.replace(target)
                    # Only the freshly matched, verified inbox file is removed.
                    try:source.unlink()
                    except OSError:self.log('已完成归档；客户端仍占用中转副本，暂未删除副本。')
                finally:temp.unlink(missing_ok=True)
                del self.pending[identity];atomic_json(self.pending_path,self.pending)
                return
            if time.monotonic()-last_log>=15:
                self.log('等待百度客户端完成：'+item['name']+'；请确认客户端已登录、任务已开始且下载位置为中转目录。')
                last_log=time.monotonic()
            time.sleep(self.poll)
        raise DownloadUnavailable('等待客户端文件超时。任务保留；请检查客户端任务和中转目录，下次可继续等待而不重复发送。')
