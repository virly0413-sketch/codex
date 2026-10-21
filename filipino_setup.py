"""One-time local Filipino channel binding; no network calls or OAuth credentials."""
import re
from pathlib import Path
import run


PROFILE = 'profiles/filipino.json'
ASSETS = 'materials/菲律宾语/assets_tl_20261026_ready'


def valid_channel(value):
    return isinstance(value, str) and re.fullmatch(r'UC[A-Za-z0-9_-]{22}', value) is not None


def bind_channel(channel_id):
    channel_id = channel_id.strip()
    if not valid_channel(channel_id):
        raise ValueError('请输入完整的UC开头频道ID（共24位），不要填写频道名称或@标识名。')
    path = run.ROOT / PROFILE
    previous = run.load(path) if path.exists() else {}
    # Same channel retains the user's proxy/OAuth preferences and dedicated folder settings.
    config = previous if previous.get('channel_id') == channel_id else {}
    config = dict(config, channel_id=channel_id, channel_name='菲律宾语男频', language='tl',
        work='local_work_tl_20261026/' + channel_id,
        planning_source='data/jobs.tl.20261026.json', assets_path=ASSETS,
        thumbnail_text_mode='none')
    config.setdefault('oauth_client', 'client_secret.json')
    config.setdefault('oauth_token', 'token.tl.' + channel_id + '.json')
    config.setdefault('proxy_url', 'http://127.0.0.1:7897')
    config.setdefault('http_timeout_seconds', 30)
    run.save(path, config)
    return path


def ensure_profile(parent):
    path = run.ROOT / PROFILE
    if path.exists():
        config = run.load(path)
        if config.get('language') == 'tl' and valid_channel(config.get('channel_id')):
            return path
    from tkinter import simpledialog, messagebox
    while True:
        value = simpledialog.askstring('首次设置菲律宾语频道',
            '请输入菲律宾语频道UC开头的频道ID（24位）。\n仅保存到本机配置，之后还需YouTube官方授权校验。', parent=parent)
        if value is None:
            return None
        try:
            return bind_channel(value)
        except ValueError as exc:
            messagebox.showerror('频道ID格式不正确', str(exc), parent=parent)
