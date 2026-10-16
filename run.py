"""Import ChatGPT-created assets -> exact approval -> updates to existing YouTube videos. No generation API."""
import argparse
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile
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




def auth(config):
    from google.oauth2.credentials import Credentials
    from google.auth.transport.requests import Request
    from google_auth_oauthlib.flow import InstalledAppFlow
    from googleapiclient.discovery import build
    from google_auth_httplib2 import AuthorizedHttp
    timeout = timeout_seconds(config)
    session = requests_session(config)
    token = ROOT / config['oauth_token']
    scopes = ['https://www.googleapis.com/auth/youtube.force-ssl']
    creds = Credentials.from_authorized_user_file(str(token), scopes) if token.exists() else None
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
        print('请在浏览器完成授权；回调地址 localhost 应直连。')
        creds = flow.run_local_server(port=0, timeout_seconds=180, timeout=timeout)
    token.write_text(creds.to_json(), encoding='utf-8')
    token.chmod(0o600)
    youtube = build('youtube', 'v3', http=AuthorizedHttp(creds, http=http_transport(config)),
                    static_discovery=True, cache_discovery=False)
    print('正在核对 YouTube 频道…')
    channels = read_request(youtube.channels().list(part='id', mine=True), '核对频道').get('items', [])
    if config['channel_id'] not in [c['id'] for c in channels]:
        raise ValueError('OAuth account/channel does not match configured channel_id.')
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
                       config['channel_name'], now.astimezone(ZoneInfo('Asia/Shanghai')).date(), now)
    if config.get('start_date'):
        start_date = dt.date.fromisoformat(config['start_date']).isoformat()
        jobs = [j for j in jobs if j['date'] >= start_date]
    save(ROOT / config['work'] / 'queue.json', jobs)
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
                if im.format == 'JPEG' and im.size == (1280, 720) and source.stat().st_size < 2 * 1024 * 1024:
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
    desired_snippet = dict(package['remote_before']['snippet'], title=package['title'], description=package['description_after'])
    desired_status = dict(package['remote_before']['status'], privacyStatus='private', publishAt=package['publish_at'])
    desired = {'id':package['video_id'], 'channel_id':config['channel_id'], 'snippet':desired_snippet, 'status':desired_status}
    if state.get('stage') in ('metadata_started', 'done'):
        if remote_state(current) == desired:
            save(state_path, dict(fingerprint=fingerprint(package), stage='done', video_id=package['video_id']))
            print('Approved changes already confirmed on existing video:', package['video_id'])
            return
        raise ValueError('Previous result differs or is uncertain. Inspect Studio and generate a fresh review; no changes made.')
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
    actual = get_video(youtube, config, package['video_id'])
    # Compare timestamps as instants; YouTube may normalize the timezone representation.
    actual_state = remote_state(actual)
    actual_time = actual_state['status'].get('publishAt')
    if actual_time and dt.datetime.fromisoformat(actual_time.replace('Z', '+00:00')) == when:
        actual_state['status']['publishAt'] = package['publish_at']
    if actual_state != desired:
        raise ValueError('YouTube result differs from approved changes. Check Studio; do not blindly retry.')
    save(state_path, dict(fingerprint=fingerprint(package), stage='done', video_id=package['video_id']))
    print('Updated and scheduled existing video:', package['video_url'], package['publish_local'])


def apply_approved(config):
    for path in sorted((ROOT / config['work']).glob('*/approval.json')):
        with upload_lock(path.parent):
            apply_changes(config, argparse.Namespace(job=path.parent.name))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', default=str(ROOT / 'config.json'))
    commands = parser.add_subparsers(dest='command', required=True)
    for name in ['plan', 'auth', 'scan', 'diagnose', 'apply-approved']: commands.add_parser(name)
    imp = commands.add_parser('import-pack'); imp.add_argument('--pack', default=str(ROOT / 'assets'))
    rev = commands.add_parser('review')
    rev.add_argument('--job', required=True); rev.add_argument('--video-id')
    rev.add_argument('--title', type=int, default=1); rev.add_argument('--cover', type=int, default=1)
    rev.add_argument('--code'); rev.add_argument('--publish-local')
    app = commands.add_parser('approve'); app.add_argument('--job', required=True)
    app.add_argument('--fingerprint', required=True)
    app.add_argument('--confirm-rights-audio-restrictions', action='store_true', required=True)
    apply = commands.add_parser('apply'); apply.add_argument('--job', required=True)
    args = parser.parse_args(); config = load(args.config)
    if args.command == 'plan': plan(config)
    elif args.command == 'auth': auth(config); print('Channel authentication verified.')
    elif args.command == 'diagnose': diagnose(config)
    elif args.command == 'scan': scan(config)
    elif args.command == 'import-pack': import_pack(config, args)
    elif args.command == 'review': review(config, args)
    elif args.command == 'approve': approve(config, args)
    elif args.command == 'apply-approved': apply_approved(config)
    elif args.command == 'apply':
        with upload_lock(ROOT / config['work'] / args.job): apply_changes(config, args)


if __name__ == '__main__':
    try: main()
    except Exception as exc:
        print(f'Error: {type(exc).__name__}: {str(exc)[:350]}', file=sys.stderr)
        sys.exit(1)
