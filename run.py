"""Import ChatGPT-created assets -> exact approval -> updates to existing YouTube videos. No generation API."""
import argparse
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile
import time
import shutil
import zipfile
from contextlib import contextmanager

from prepare import prepare, description_with_code, normalize
from networking import timeout_seconds, requests_session, http_transport, read_request, diagnose

ROOT = Path(__file__).resolve().parent


@contextmanager
def upload_lock(directory):
    directory.mkdir(parents=True, exist_ok=True)
    lock = directory / 'upload.lock'
    try:
        fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError:
        raise ValueError('Upload lock exists. Stop concurrent jobs; after a crash verify Studio/state before removing it.')
    os.close(fd)
    try:
        yield
    finally:
        lock.unlink(missing_ok=True)


def load(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def save(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent)
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as stream:
            json.dump(value, stream, ensure_ascii=False, indent=2)
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def digest(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def fingerprint(package):
    return hashlib.sha256(json.dumps(package, sort_keys=True, ensure_ascii=False).encode()).hexdigest()




def verify_channel(config, channels):
    expected = config['channel_id']
    actual = '\n'.join(c.get('snippet', {}).get('title', '未返回名称') + ' | ' + c['id'] for c in channels)
    print('目标频道：', config.get('channel_name', ''), config.get('channel_handle', ''), '|', expected)
    print('本次授权返回的频道：\n' + (actual or '未返回可访问的频道'))
    if expected not in [c['id'] for c in channels]:
        raise ValueError('授权频道不匹配。目标：' + expected + '；实际：' + (actual or '无频道') +
            '。请点击“切换授权频道”，选择管理目标频道的正确账号/品牌频道；不会自动改目标频道。')


def auth(config, reauthorize=False, scopes=None):
    from google.oauth2.credentials import Credentials
    from google.auth.transport.requests import Request
    from google_auth_oauthlib.flow import InstalledAppFlow
    from googleapiclient.discovery import build
    from google_auth_httplib2 import AuthorizedHttp
    timeout = timeout_seconds(config)
    session = requests_session(config)
    token = ROOT / config['oauth_token']
    scopes = scopes or ['https://www.googleapis.com/auth/youtube.force-ssl']
    creds = Credentials.from_authorized_user_file(str(token), scopes) if token.exists() and not reauthorize else None
    if creds and creds.expired and creds.refresh_token:
        request = Request(session=session)
        def timed_request(*args, **kwargs):
            kwargs['timeout'] = kwargs.get('timeout') or timeout
            return request(*args, **kwargs)
        print('正在刷新 Google 授权…')
        try:
            creds.refresh(timed_request)
        except Exception as exc:
            raise RuntimeError('Google 授权刷新失败（' + type(exc).__name__ + '）。先检查代理和“诊断连接”；若令牌确已失效再重新授权。') from exc
    if not creds or not creds.valid:
        flow = InstalledAppFlow.from_client_secrets_file(str(ROOT / config['oauth_client']), scopes)
        flow.oauth2session.proxies.update(session.proxies)
        flow.oauth2session.trust_env = session.trust_env
        original_request = flow.oauth2session.request
        def bounded_request(*args, **kwargs):
            kwargs['timeout'] = kwargs.get('timeout') or timeout
            return original_request(*args, **kwargs)
        flow.oauth2session.request = bounded_request
        print('请在浏览器完成授权；回调地址 localhost 应直连。')
        creds = flow.run_local_server(port=0, timeout_seconds=180, prompt='consent select_account')
    youtube = build('youtube', 'v3', http=AuthorizedHttp(creds, http=http_transport(config)),
                    static_discovery=True, cache_discovery=False)
    print('正在核对 YouTube 频道…')
    channels = read_request(youtube.channels().list(part='id,snippet', mine=True), '核对频道').get('items', [])
    verify_channel(config, channels)
    # A failed channel switch must never overwrite a previously usable binding.
    token.write_text(creds.to_json(), encoding='utf-8')
    token.chmod(0o600)
    return youtube


def plan(config):
    now = dt.datetime.now(dt.timezone.utc)
    from zoneinfo import ZoneInfo
    if config.get('planning_source'):
        jobs = load(ROOT / config['planning_source'])
        for entry in jobs:
            entry['approved'] = False
            if entry.get('publish_at') and dt.datetime.fromisoformat(entry['publish_at'].replace('Z', '+00:00')) <= now:
                if 'past_publish_time_do_not_backfill_automatically' not in entry['blockers']:
                    entry['blockers'].append('past_publish_time_do_not_backfill_automatically')
    else:
        jobs = prepare(ROOT / config['schedule'], ROOT / config['resources'],
                       config.get('schedule_channel_name',config['channel_name']),
                       now.astimezone(ZoneInfo('Asia/Shanghai')).date(), now, language=config.get('language','en'))
    if config.get('start_date'):
        start_date = dt.date.fromisoformat(config['start_date']).isoformat()
        jobs = [j for j in jobs if j['date'] >= start_date]
    save(ROOT / config['work'] / 'queue.json', jobs)
    if not jobs: print('当前频道暂无排片；未沿用其他频道的任务。请先提供该频道排片与素材。')
    for j in jobs:
        if j['publish_at'] and dt.datetime.fromisoformat(j['publish_at'].replace('Z', '+00:00')) > now:
            print(j['job_id'], j['publish_local'], j['title_zh'],
                  ' | '.join(c['drama_code'] for c in j['candidates']))
    print('Saved queue.json. Nothing was uploaded.')


def job(config, job_id):
    matches = [j for j in load(ROOT / config['work'] / 'queue.json') if j['job_id'] == job_id]
    if len(matches) != 1:
        raise ValueError('Unknown job_id. Run plan first.')
    return matches[0]










def approve(config, args):
    directory = ROOT / config['work'] / args.job
    package = load(directory / 'review.json')
    if package.get('demo') or package.get('workflow') != 'existing_video_v2':
        raise ValueError('Only current existing-video reviews can be approved.')
    expected = fingerprint(package)
    if args.fingerprint != expected:
        raise ValueError('Fingerprint mismatch. Review the current package again.')
    save(directory / 'approval.json', dict(fingerprint=expected,
        approved_at=dt.datetime.now(dt.timezone.utc).isoformat(),
        rights_audio_restrictions_confirmed=True))
    print('Approved this exact package locally. Apply requires a separate command; no remote changes made.')




def import_pack(config, args):
    from PIL import Image, ImageOps
    pack = Path(args.pack).resolve()
    manifest = load(pack / 'manifest.json')
    if manifest.get('channel_id') and manifest['channel_id'] != config['channel_id']:
        raise ValueError('素材包属于其他频道，禁止导入。')
    if manifest.get('language') and config.get('language') and manifest['language'] != config['language']:
        raise ValueError('素材包语种与当前频道配置不符，禁止导入。')
    jobs = {j['job_id']: j for j in load(ROOT / config['work'] / 'queue.json')}
    count = 0
    for entry in manifest['jobs']:
        job_id = entry['job_id']
        if job_id not in jobs:
            raise ValueError('Asset job absent from schedule: ' + job_id)
        if len(entry['titles']) != 3 or any(not isinstance(t, str) or not t.strip() or len(t) > 100 for t in entry['titles']):
            raise ValueError('Expected three titles, each <=100 characters.')
        if entry['title_zh'] != jobs[job_id]['title_zh']:
            raise ValueError('Asset and schedule titles do not match.')
        if entry.get('drama_code') and entry['drama_code'] not in [c['drama_code'] for c in jobs[job_id]['candidates']]:
            raise ValueError('Asset code not present in resource candidates.')
        images = []
        for relative in entry['covers']:
            source = (pack / relative).resolve()
            if not source.is_relative_to(pack) or not source.is_file():
                raise ValueError('Invalid asset path.')
            expected = manifest.get('sha256', {}).get(relative)
            if not expected or digest(source) != expected:
                raise ValueError('Asset integrity mismatch: ' + relative)
            images.append(source)
        if not images:
            raise ValueError('Asset entry has no cover.')
        directory = ROOT / config['work'] / job_id
        creative = {**entry, 'cover_count': len(images), 'demo': False}
        if (directory / 'creative.json').exists():
            previous = load(directory / 'creative.json')
            if previous == creative:
                print('Already imported:', job_id)
                continue
            raise ValueError('Existing creative differs. Archive its job folder before importing a new version: ' + job_id)
        directory.mkdir(parents=True, exist_ok=True)
        for number, source in enumerate(images, 1):
            with Image.open(source) as im:
                target = directory / f'cover_{number}.jpg'
                preserve_resolution=manifest.get('preserve_thumbnail_resolution') is True
                if preserve_resolution:
                    expected_size=tuple(manifest.get('thumbnail_resolution',[3840,2160]))
                    if expected_size not in ((3840,2160),(1920,1080)):
                        raise ValueError('保留尺寸素材仅支持3840×2160或1920×1080。')
                    label='4K素材' if expected_size==(3840,2160) else '1080p素材'
                    if im.format!='JPEG' or im.size!=expected_size or source.stat().st_size>=2*1024*1024:
                        raise ValueError(label+'必须为'+str(expected_size[0])+'×'+str(expected_size[1])+' JPEG且小于2MB，不会静默缩小。')
                    shutil.copyfile(source,target)
                elif im.format == 'JPEG' and im.size == (1280, 720) and source.stat().st_size < 2 * 1024 * 1024:
                    shutil.copyfile(source, target)
                else:
                    image = ImageOps.pad(im.convert('RGB'), (1280, 720), color='black')
                    image.save(target, quality=92)
                if target.stat().st_size >= 2 * 1024 * 1024:
                    raise ValueError('Converted thumbnail too large.')
        save(directory / 'creative.json', creative)
        count += 1
    print('Imported', count, 'packages. No API Key required; no uploads or approvals performed.')


SNIPPET_FIELDS = ('title', 'description', 'categoryId', 'tags', 'defaultLanguage', 'defaultAudioLanguage')
STATUS_FIELDS = ('privacyStatus', 'publishAt', 'license', 'embeddable',
                 'publicStatsViewable', 'selfDeclaredMadeForKids', 'containsSyntheticMedia')


def remote_state(video):
    return {'id': video['id'], 'channel_id': video['snippet']['channelId'],
            'snippet': {k: video['snippet'][k] for k in SNIPPET_FIELDS if k in video['snippet']},
            'status': {k: video['status'][k] for k in STATUS_FIELDS if k in video['status']}}


def desired_state(package):
    return {'id':package['video_id'], 'channel_id':package['channel_id'],
        'snippet':dict(package['remote_before']['snippet'], title=package['title'], description=package['description_after']),
        'status':dict(package['remote_before']['status'], privacyStatus='private', publishAt=package['publish_at'])}


def state_differences(expected, actual):
    """Validate every requested/preserved field; tolerate only known semantic equivalences."""
    differences = []
    missing = object()
    for section in ('identity', 'snippet', 'status'):
        want = {k:expected[k] for k in ('id','channel_id')} if section == 'identity' else expected[section]
        got = actual if section == 'identity' else actual[section]
        for key, value in want.items():
            returned = got.get(key, missing)
            equal = returned is not missing and value == returned
            if returned is not missing and key == 'publishAt':
                try:
                    equal = dt.datetime.fromisoformat(value.replace('Z','+00:00')) == dt.datetime.fromisoformat(returned.replace('Z','+00:00'))
                except (TypeError, ValueError): equal = False
            elif key == 'tags':
                # Empty tags and an omitted tags field represent the same empty list.
                actual_tags = [] if returned is missing else returned
                equal = isinstance(value,list) and isinstance(actual_tags,list) and sorted(value) == sorted(actual_tags)
            elif returned is not missing and key in ('defaultLanguage','defaultAudioLanguage'):
                equal = str(value).casefold() == str(returned).casefold()
            if not equal:
                differences.append({'field':section+'.'+key, 'expected':value,
                                    'actual':returned if returned is not missing else None,
                                    'actual_missing':returned is missing})
    # Extra fields returned by the service were not requested changes. Record, don't treat them as failures.
    added = {s:{k:v for k,v in actual[s].items() if k not in expected[s]} for s in ('snippet','status')}
    return differences, added


def verify_result(youtube, config, package, directory, first_video=None, attempts=3):
    expected = desired_state(package)
    for attempt in range(attempts):
        actual_video = first_video if attempt == 0 and first_video is not None else get_video(youtube,config,package['video_id'])
        actual = remote_state(actual_video)
        differences, added = state_differences(expected, actual)
        report = dict(video_id=package['video_id'], fingerprint=fingerprint(package),
            checked_at=dt.datetime.now(dt.timezone.utc).isoformat(),
            metadata_and_schedule_confirmed=not differences,
            thumbnail_confirmation='Not verified by readback; visually confirm the actual thumbnail in Studio',
            differences=differences, server_added_fields=added, expected=expected, actual=actual)
        save(directory/'verification.json',report)
        if not differences:
            print('线上标题、说明及排期已核对一致；保留字段已核对。封面需在 Studio 目视确认。')
            return report
        print('线上核对第',attempt+1,'次，差异字段：',', '.join(d['field'] for d in differences))
        if attempt+1 < attempts:
            time.sleep(2*(attempt+1))
    for difference in differences:
        def brief(value):
            text=json.dumps(value,ensure_ascii=False)
            return text if len(text)<=160 else text[:160]+'…（完整内容仅保存在本机 verification.json）'
        print(difference['field'], '\n  审核值：',brief(difference['expected']), '\n  返回值：',brief(difference['actual']))
    raise ValueError('线上结果未确认，差异字段：'+', '.join(d['field'] for d in differences)+
        '。部分修改可能已生效；未重新写入。请在 Studio 核对，或点击“核对线上结果”。本机报告：'+str(directory/'verification.json'))


def verify_existing(config, args):
    directory = ROOT/config['work']/args.job
    package=load(directory/'review.json')
    if package.get('workflow') != 'existing_video_v2' or package['channel_id'] != config['channel_id']:
        raise ValueError('审核单不是当前频道的现有视频审核单。请重新生成。')
    verify_result(auth(config),config,package,directory)
    print('本次仅查询并保存核对报告，未修改 YouTube。')


def get_video(youtube, config, video_id):
    items = read_request(youtube.videos().list(part='snippet,status', id=video_id), '读取视频信息').get('items', [])
    if len(items) != 1 or items[0]['snippet']['channelId'] != config['channel_id']:
        raise ValueError('Video missing, inaccessible, or belongs to a different channel.')
    return items[0]


def scan(config, args=None):
    youtube = auth(config)
    print('正在读取频道上传列表…')
    channels = read_request(youtube.channels().list(part='contentDetails', id=config['channel_id']), '读取上传列表')['items']
    playlist = channels[0]['contentDetails']['relatedPlaylists']['uploads']
    ids, page = [], None
    while True:
        print('正在读取视频列表，第', len(ids)//50+1, '页…')
        response = read_request(youtube.playlistItems().list(part='contentDetails', playlistId=playlist,
            maxResults=50, pageToken=page), '读取视频列表')
        ids.extend(item['contentDetails']['videoId'] for item in response.get('items', []))
        page = response.get('nextPageToken')
        if not page: break
    videos = []
    ids = list(dict.fromkeys(ids))
    for offset in range(0, len(ids), 50):
        print('正在读取视频详情，第', offset//50+1, '批…')
        response = read_request(youtube.videos().list(part='snippet,status', id=','.join(ids[offset:offset+50])), '读取视频详情')
        videos.extend(v for v in response.get('items', []) if v['snippet']['channelId'] == config['channel_id'])
    save(ROOT / config['work'] / 'channel_videos.json', videos)
    for video in videos:
        print(video['id'], video['status']['privacyStatus'], video['snippet']['title'])
    print('Scanned', len(videos), 'existing channel videos. Read-only; nothing changed.')


def match_videos(title_zh, videos):
    key = normalize(title_zh)
    return [v for v in videos if key and key in normalize(v['snippet']['title'])]


def review(config, args):
    j = job(config, args.job)
    directory = ROOT / config['work'] / args.job
    creative = load(directory / 'creative.json')
    if not (1 <= args.title <= len(creative['titles']) and 1 <= args.cover <= creative['cover_count']):
        raise ValueError('Title or cover selection out of range.')
    chosen_code = args.code or creative.get('drama_code')
    if len([c for c in j['candidates'] if c['drama_code'] == chosen_code]) != 1:
        raise ValueError('Choose the exact resource version with --code.')
    video_id = args.video_id
    if not video_id:
        cache = ROOT / config['work'] / 'channel_videos.json'
        if not cache.exists(): raise ValueError('Run scan first, or provide --video-id.')
        matches = match_videos(j['title_zh'], load(cache))
        if len(matches) != 1:
            raise ValueError('Title match is missing or ambiguous. Select the exact --video-id after inspection.')
        video_id = matches[0]['id']
    youtube = auth(config)
    video = get_video(youtube, config, video_id)
    if video['status'].get('privacyStatus') != 'private':
        raise ValueError('Scheduling requires an existing private, never-published video. No privacy change made.')
    if video['status'].get('uploadStatus') in ('failed', 'rejected', 'deleted'):
        raise ValueError('Video processing failed or the video was rejected/deleted.')
    from zoneinfo import ZoneInfo
    if args.publish_local:
        local = dt.datetime.fromisoformat(args.publish_local)
        if local.tzinfo: raise ValueError('Provide Beijing local time without offset.')
        local = local.replace(tzinfo=ZoneInfo('Asia/Shanghai'))
    else:
        local = dt.datetime.fromisoformat(j['publish_local']).astimezone(ZoneInfo('Asia/Shanghai'))
    if local <= dt.datetime.now(dt.timezone.utc) + dt.timedelta(minutes=5):
        raise ValueError('Choose a future schedule at least 5 minutes ahead; no automatic rescheduling.')
    description = video['snippet'].get('description', '')
    cover = directory / f'cover_{args.cover}.jpg'
    after = description_with_code(description, chosen_code)
    if len(after) > 5000: raise ValueError('Description plus code exceeds YouTube limit.')
    package = dict(workflow='existing_video_v2', job_id=args.job, channel_id=config['channel_id'],
        video_id=video_id, video_url='https://www.youtube.com/watch?v=' + video_id,
        title_before=video['snippet']['title'], title=creative['titles'][args.title - 1],
        description_before=description, description_after=after,
        thumbnail=str(cover.resolve()), thumbnail_sha256=digest(cover),
        thumbnail_before=video['snippet'].get('thumbnails', {}),
        remote_before=remote_state(video), remote_etag=video.get('etag'),
        publish_local=local.isoformat(), publish_at=local.astimezone(dt.timezone.utc).isoformat().replace('+00:00', 'Z'),
        drama_code=chosen_code, demo=False)
    save(directory / 'review.json', package)
    print(json.dumps(package, ensure_ascii=False, indent=2))
    print('Review fingerprint:', fingerprint(package))
    print('Read-only review saved. Verify the exact video, title, cover, original description and schedule before approval.')


def apply_changes(config, args):
    from googleapiclient.http import MediaFileUpload
    directory = ROOT / config['work'] / args.job
    package, approval = load(directory / 'review.json'), load(directory / 'approval.json')
    if (package.get('workflow') != 'existing_video_v2' or
            approval['fingerprint'] != fingerprint(package) or package.get('demo')):
        raise ValueError('Missing/stale approval or legacy upload review. Generate and approve a new review.')
    if package['channel_id'] != config['channel_id'] or digest(package['thumbnail']) != package['thumbnail_sha256']:
        raise ValueError('Channel or thumbnail changed. Review and approve again.')
    if Path(package['thumbnail']).stat().st_size >= 2 * 1024 * 1024:
        raise ValueError('Thumbnail must be under 2 MB.')
    youtube = auth(config)
    current = get_video(youtube, config, package['video_id'])
    state_path = directory / 'apply_state.json'
    state = load(state_path) if state_path.exists() else {}
    if state and state.get('fingerprint') != fingerprint(package):
        raise ValueError('Another reviewed change has execution state. Inspect Studio and archive old state before continuing.')
    desired = desired_state(package)
    desired_snippet, desired_status = desired['snippet'], desired['status']
    if state.get('stage') in ('metadata_started', 'done'):
        verify_result(youtube,config,package,directory,first_video=current)
        save(state_path, dict(fingerprint=fingerprint(package), stage='done', video_id=package['video_id']))
        print('Approved changes already confirmed on existing video:', package['video_id'])
        return
    if remote_state(current) != package['remote_before']:
        raise ValueError('Video metadata changed since review. Fetch and approve a fresh review.')
    if state.get('stage') == 'thumbnail_started':
        raise ValueError('Prior thumbnail operation outcome uncertain. Inspect Studio and generate a fresh review.')
    if not state and current.get('etag') != package['remote_etag']:
        raise ValueError('Video changed since review (including thumbnail). Review again.')
    when = dt.datetime.fromisoformat(package['publish_at'].replace('Z', '+00:00'))
    if when <= dt.datetime.now(dt.timezone.utc) + dt.timedelta(minutes=5):
        raise ValueError('Publish time must be >5 minutes ahead. No automatic rescheduling.')
    if state.get('stage') != 'thumbnail_done':
        save(state_path, dict(fingerprint=fingerprint(package), stage='thumbnail_started'))
        youtube.thumbnails().set(videoId=package['video_id'], media_body=MediaFileUpload(package['thumbnail'])).execute()
        current = get_video(youtube, config, package['video_id'])
        if remote_state(current) != package['remote_before']:
            raise ValueError('Metadata changed while applying thumbnail. Stop and review; thumbnail may already be changed.')
        save(state_path, dict(fingerprint=fingerprint(package), stage='thumbnail_done', etag=current.get('etag')))
    else:
        if current.get('etag') != state.get('etag'):
            raise ValueError('Video changed after thumbnail step. Stop and review again.')
    if when <= dt.datetime.now(dt.timezone.utc) + dt.timedelta(minutes=2):
        raise ValueError('Too close to schedule. Thumbnail may be changed; re-review a new time.')
    save(state_path, dict(fingerprint=fingerprint(package), stage='metadata_started'))
    request = youtube.videos().update(part='snippet,status', body={
        'id': package['video_id'], 'snippet': desired_snippet, 'status': desired_status})
    if not current.get('etag'): raise ValueError('Missing remote version ETag; stop without metadata changes.')
    request.headers['If-Match'] = current['etag']
    request.execute()
    verify_result(youtube,config,package,directory)
    save(state_path, dict(fingerprint=fingerprint(package), stage='done', video_id=package['video_id']))
    print('Updated and scheduled existing video:', package['video_url'], package['publish_local'])


def apply_approved(config):
    for path in sorted((ROOT / config['work']).glob('*/approval.json')):
        with upload_lock(path.parent):
            apply_changes(config, argparse.Namespace(job=path.parent.name))


def publish(config, args):
    """One explicit publish action: fetch current data, bind the exact intent, then apply."""
    directory=ROOT/config['work']/args.job
    creative=load(directory/'creative.json')
    j=job(config,args.job)
    video_id=args.video_id
    if not video_id:
        cache=ROOT/config['work']/'channel_videos.json'
        if not cache.exists():raise ValueError('请先扫描频道并选择具体视频。')
        matches=match_videos(j['title_zh'],load(cache))
        if len(matches)!=1:raise ValueError('视频匹配不唯一，请先选择具体视频再发布。')
        video_id=matches[0]['id']
    from zoneinfo import ZoneInfo
    if args.publish_local:
        local=dt.datetime.fromisoformat(args.publish_local)
        if local.tzinfo:raise ValueError('请输入不带时区后缀的北京时间。')
        local=local.replace(tzinfo=ZoneInfo('Asia/Shanghai'))
    else:local=dt.datetime.fromisoformat(j['publish_local'])
    intent=dict(channel_id=config['channel_id'],video_id=video_id,
        title=creative['titles'][args.title-1],drama_code=args.code or creative.get('drama_code'),
        thumbnail_sha256=digest(directory/f'cover_{args.cover}.jpg'),
        publish_at=local.astimezone(dt.timezone.utc).isoformat().replace('+00:00','Z'))
    with upload_lock(directory):
        if (directory/'apply_state.json').exists():
            old=load(directory/'review.json')
            if any(old.get(k)!=v for k,v in intent.items()):
                raise ValueError('该任务已有另一组发布结果或未完成操作。请先核对线上结果，不能覆盖不确定状态。')
            apply_changes(config,argparse.Namespace(job=args.job))
            return
        review(config,args)
        package=load(directory/'review.json')
        if any(package.get(k)!=v for k,v in intent.items()):
            raise ValueError('发布过程中选择发生变化，已停止。请重新选择后点击发布。')
        save(directory/'approval.json',dict(fingerprint=fingerprint(package),
            approved_at=dt.datetime.now(dt.timezone.utc).isoformat(),authorization='explicit_publish_action'))
        print('正在执行本次点击发布的内容，不再要求单独批准。')
        apply_changes(config,argparse.Namespace(job=args.job))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', default=str(ROOT / 'config.json'))
    commands = parser.add_subparsers(dest='command', required=True)
    for name in ['plan', 'scan', 'diagnose', 'apply-approved']: commands.add_parser(name)
    authentication = commands.add_parser('auth')
    authentication.add_argument('--reauth', action='store_true', help='Choose the Google account and brand channel again')
    imp = commands.add_parser('import-pack'); imp.add_argument('--pack')
    rev = commands.add_parser('review')
    rev.add_argument('--job', required=True); rev.add_argument('--video-id')
    rev.add_argument('--title', type=int, default=1); rev.add_argument('--cover', type=int, default=1)
    rev.add_argument('--code'); rev.add_argument('--publish-local')
    app = commands.add_parser('approve'); app.add_argument('--job', required=True)
    app.add_argument('--fingerprint', required=True)
    app.add_argument('--confirm-rights-audio-restrictions', action='store_true', required=True)
    apply = commands.add_parser('apply'); apply.add_argument('--job', required=True)
    verify = commands.add_parser('verify'); verify.add_argument('--job', required=True)
    pub = commands.add_parser('publish')
    pub.add_argument('--job',required=True); pub.add_argument('--video-id')
    pub.add_argument('--title',type=int,default=1); pub.add_argument('--cover',type=int,default=1)
    pub.add_argument('--code'); pub.add_argument('--publish-local')
    args = parser.parse_args(); config = load(args.config)
    if args.command == 'plan': plan(config)
    elif args.command == 'auth': auth(config, reauthorize=args.reauth); print('Channel authentication verified.')
    elif args.command == 'diagnose': diagnose(config)
    elif args.command == 'scan': scan(config)
    elif args.command == 'import-pack':
        if not args.pack: args.pack=str(ROOT/config.get('assets_path','assets'))
        import_pack(config, args)
    elif args.command == 'review': review(config, args)
    elif args.command == 'approve': approve(config, args)
    elif args.command == 'verify': verify_existing(config,args)
    elif args.command == 'publish': publish(config,args)
    elif args.command == 'apply-approved': apply_approved(config)
    elif args.command == 'apply':
        with upload_lock(ROOT / config['work'] / args.job): apply_changes(config, args)


if __name__ == '__main__':
    try: main()
    except Exception as exc:
        print(f'Error: {type(exc).__name__}: {str(exc)[:350]}', file=sys.stderr)
        sys.exit(1)
