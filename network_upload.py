"""Schedule-driven, read-only shared-folder discovery and private YouTube uploads."""
import os
import re
from pathlib import Path

from baidu_download import ALIASES, VIDEOS, file_language, sha256_file, atomic_json
from prepare import normalize
from networking import read_request


def title_key(value, codes=()):
    value = Path(value).stem if Path(value).suffix.lower() in VIDEOS else value
    for code in codes:
        if code:
            value = re.sub(r'^\s*' + re.escape(code) + r'[ _—\-：:]*', '', value)
    for aliases in ALIASES.values():
        for alias in aliases:
            value = value.replace(alias, '')
    value = re.sub(r'(1080[pP]|720[pP]|2160[pP]|4[Kk]|高清|完整版|全集)', '', value)
    return normalize(value)


def inventory(root, stop=None):
    root = Path(root).resolve()
    if not root.is_dir():
        raise ValueError('共享目录不可访问，请先在资源管理器打开并登录：' + str(root))
    files = []
    def failed(exc):
        raise OSError('部分共享目录无法读取，请选择权限完整的片源子目录。') from exc
    for folder, dirs, names in os.walk(root, onerror=failed, followlinks=False):
        if stop and stop.is_set(): raise InterruptedError('已停止扫描')
        dirs[:] = [d for d in dirs if not (Path(folder)/d).is_symlink()]
        for name in names:
            path = Path(folder)/name
            if path.suffix.lower() not in VIDEOS or path.is_symlink(): continue
            stat = path.stat()
            if not stat.st_size: continue
            parents = [root.name] + list(path.relative_to(root).parts[:-1])
            files.append(dict(path=str(path), name=name, parents=parents,
                              size=stat.st_size, mtime_ns=stat.st_mtime_ns))
    return files


def matches(task, files):
    key = normalize(task['title'])
    codes = [c['code'] for c in task.get('candidates', [])]
    return [f for f in files if file_language(f) == task['language'] and
            any(title_key(label, codes) == key for label in [f['name']] + f['parents'])]


def existing_uploads(youtube, channel_id):
    channels = read_request(youtube.channels().list(part='id,contentDetails', mine=True), '读取上传列表')['items']
    channel = next((c for c in channels if c['id'] == channel_id), None)
    if channel is None: raise ValueError('目标频道未在授权结果中返回。')
    playlist = channel['contentDetails']['relatedPlaylists']['uploads']
    found = {}; page = None
    while True:
        result = read_request(youtube.playlistItems().list(part='snippet,contentDetails', playlistId=playlist,
                              maxResults=50, pageToken=page), '检查已有视频')
        for item in result.get('items', []):
            video_id = item['contentDetails']['videoId']
            found.setdefault(normalize(item['snippet']['title']), []).append(video_id)
            lines = item['snippet'].get('description', '').splitlines()
            if lines and lines[-1].strip():
                found.setdefault('code:' + lines[-1].strip(), []).append(video_id)
        page = result.get('nextPageToken')
        if not page: return found


def upload_private(youtube, config, task, selected, state_path, stop=None, progress=lambda s: None):
    """No automatic mutation retries; uncertain uploads are blocked until reconciled."""
    from googleapiclient.http import MediaFileUpload
    import json
    path = Path(selected['path'])
    stat = path.stat()
    if (stat.st_size, stat.st_mtime_ns) != (selected['size'], selected['mtime_ns']):
        raise ValueError('片源已更改，请重新扫描。')
    if not task.get('code'): raise ValueError('请先明确选择剧集版本代码。')
    if len(task['title']) > 100: raise ValueError('原剧名超过YouTube标题长度限制。')
    state_path = Path(state_path)
    state = json.loads(state_path.read_text(encoding='utf-8')) if state_path.exists() else {}
    # Title identity prevents duplicate uploads on a different date or selected row.
    identity = config['channel_id'] + '|' + task['language'] + '|' + normalize(task['title'])
    if identity in state:
        record = state[identity]
        if record.get('video_id'): return record['video_id']
        raise ValueError('此前上传结果未确认。请先在YouTube Studio检查；不会自动重复上传。')
    progress('核验文件指纹（大文件可能需要一些时间）')
    file_hash = sha256_file(path)
    if stop and stop.is_set(): raise InterruptedError('已停止')
    if (path.stat().st_size, path.stat().st_mtime_ns) != (stat.st_size, stat.st_mtime_ns):
        raise ValueError('片源正在变化，请等待文件写入完成。')
    state[identity] = dict(status='uploading_or_unknown', path=str(path), sha256=file_hash)
    atomic_json(state_path, state)
    request = youtube.videos().insert(part='snippet,status', body={
        'snippet': {'title': task['title'], 'description': task['code'], 'categoryId': '24'},
        'status': {'privacyStatus': 'private', 'selfDeclaredMadeForKids': False}},
        media_body=MediaFileUpload(str(path), chunksize=8*1024*1024, resumable=True))
    response = None
    while response is None:
        if stop and stop.is_set():
            raise InterruptedError('已停止；请到Studio核对未完成上传，程序不会盲目重传。')
        status, response = request.next_chunk(num_retries=0)
        if status: progress(f'上传 {status.progress()*100:.0f}%')
    video_id = response.get('id')
    if not video_id: raise ValueError('未收到视频ID，请先检查Studio。')
    state[identity].update(status='uploaded_private', video_id=video_id)
    atomic_json(state_path, state)
    return video_id
