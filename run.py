"""Import ChatGPT-created assets -> exact approval -> scheduled YouTube upload. No generation API."""
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

from prepare import prepare, description_with_code

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
    token = ROOT / config['oauth_token']
    scopes = ['https://www.googleapis.com/auth/youtube.force-ssl']
    creds = Credentials.from_authorized_user_file(str(token), scopes) if token.exists() else None
    if creds and creds.expired and creds.refresh_token:
        creds.refresh(Request())
    if not creds or not creds.valid:
        flow = InstalledAppFlow.from_client_secrets_file(str(ROOT / config['oauth_client']), scopes)
        creds = flow.run_local_server(port=0)
    token.write_text(creds.to_json(), encoding='utf-8')
    token.chmod(0o600)
    youtube = build('youtube', 'v3', credentials=creds)
    channels = youtube.channels().list(part='id', mine=True).execute().get('items', [])
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






def review(config, args):
    j = job(config, args.job)
    directory = ROOT / config['work'] / args.job
    creative = load(directory / 'creative.json')
    video = Path(args.video).resolve()
    if not video.is_file():
        raise ValueError('Video file does not exist.')
    if not (1 <= args.title <= len(creative['titles']) and 1 <= args.cover <= creative['cover_count']):
        raise ValueError('Title or cover selection out of range.')
    chosen_code = args.code or creative.get('drama_code')
    candidates = [c for c in j['candidates'] if c['drama_code'] == chosen_code]
    if len(candidates) != 1:
        raise ValueError('Choose the exact resource version with --code; no code is guessed.')
    description = Path(args.description).read_bytes().decode('utf-8')
    cover = directory / f'cover_{args.cover}.jpg'
    from zoneinfo import ZoneInfo
    local = dt.datetime.fromisoformat(args.publish_local).replace(tzinfo=ZoneInfo('Asia/Shanghai')) if args.publish_local else dt.datetime.fromisoformat(j['publish_local']).astimezone(ZoneInfo('Asia/Shanghai'))
    if args.publish_local and dt.datetime.fromisoformat(args.publish_local).tzinfo is not None:
        raise ValueError('Use local clock time without offset, e.g. 2026-10-17T17:00:00')
    if local <= dt.datetime.now(dt.timezone.utc):
        raise ValueError('Past schedule: explicitly provide a future --publish-local and review it again.')
    package = dict(job_id=args.job, channel_id=config['channel_id'],
        title=creative['titles'][args.title - 1], video=str(video), video_sha256=digest(video),
        thumbnail=str(cover.resolve()), thumbnail_sha256=digest(cover),
        description_before=description,
        description_after=description_with_code(description, chosen_code),
        publish_local=local.isoformat(), publish_at=local.astimezone(dt.timezone.utc).isoformat().replace('+00:00', 'Z'),
        drama_code=chosen_code, demo=False)
    save(directory / 'review.json', package)
    print(json.dumps(package, ensure_ascii=False, indent=2))
    print('\nReview fingerprint:', fingerprint(package))
    print('Review files, synopsis accuracy, English audio, rights, restrictions and timing before approve.')




def approve(config, args):
    directory = ROOT / config['work'] / args.job
    package = load(directory / 'review.json')
    if package['demo']:
        raise ValueError('Demo packages cannot be approved or uploaded.')
    expected = fingerprint(package)
    if args.fingerprint != expected:
        raise ValueError('Fingerprint mismatch. Review the current package again.')
    save(directory / 'approval.json', dict(fingerprint=expected,
        approved_at=dt.datetime.now(dt.timezone.utc).isoformat(),
        rights_audio_restrictions_confirmed=True))
    print('Approved this exact package locally. Upload requires a separate upload command.')


def upload(config, args):
    from googleapiclient.http import MediaFileUpload
    directory = ROOT / config['work'] / args.job
    package = load(directory / 'review.json')
    approval = load(directory / 'approval.json')
    if package['demo'] or approval['fingerprint'] != fingerprint(package):
        raise ValueError('Missing or stale approval.')
    if package['channel_id'] != config['channel_id']:
        raise ValueError('Channel changed; regenerate review and approval.')
    for field in ['video', 'thumbnail']:
        if digest(package[field]) != package[field + '_sha256']:
            raise ValueError('Approved asset changed: ' + field)
    when = dt.datetime.fromisoformat(package['publish_at'].replace('Z', '+00:00'))
    if when <= dt.datetime.now(dt.timezone.utc) + dt.timedelta(minutes=15):
        raise ValueError('Publish time must be >15 minutes ahead. No automatic rescheduling.')
    youtube = auth(config)
    state_path = directory / 'upload_state.json'
    state = load(state_path) if state_path.exists() else {}
    if state.get('fingerprint') and state['fingerprint'] != fingerprint(package):
        raise ValueError('An upload exists for another package. Resolve it manually; do not duplicate.')
    if state.get('inserting') and not state.get('video_id'):
        raise ValueError('Prior upload outcome uncertain. Check YouTube Studio; do not blindly retry.')
    if state.get('scheduled'):
        actual = youtube.videos().list(part='status', id=state['video_id']).execute()['items'][0]['status']
        print('Already scheduled by this program; no new changes made:', state['video_id'], actual)
        return
    if not state.get('video_id'):
        save(state_path, dict(inserting=True, fingerprint=fingerprint(package)))
        request = youtube.videos().insert(part='snippet,status', body={
            'snippet': {'title': package['title'], 'description': package['description_after'],
                        'categoryId': '24', 'defaultLanguage': 'en'},
            'status': {'privacyStatus': 'private', 'selfDeclaredMadeForKids': False}},
            media_body=MediaFileUpload(package['video'], resumable=True))
        response = None
        while response is None:
            _, response = request.next_chunk()
        state = dict(video_id=response['id'], fingerprint=fingerprint(package))
        save(state_path, state)
    video_id = state['video_id']
    current = youtube.videos().list(part='snippet,status', id=video_id).execute()['items'][0]
    if current['snippet']['channelId'] != config['channel_id']:
        raise ValueError('Uploaded video belongs to another channel.')
    if (current['snippet']['title'] != package['title'] or
            current['snippet']['description'] != package['description_after']):
        raise ValueError('Remote metadata changed. Stop and review in Studio.')
    if Path(package['thumbnail']).stat().st_size >= 2 * 1024 * 1024:
        raise ValueError('Thumbnail exceeds 2 MB. Replace and reapprove before retrying.')
    youtube.thumbnails().set(videoId=video_id,
        media_body=MediaFileUpload(package['thumbnail'])).execute()
    if when <= dt.datetime.now(dt.timezone.utc) + dt.timedelta(minutes=5):
        raise ValueError('Upload took too long. Video remains private; review a new schedule.')
    youtube.videos().update(part='status', body={'id': video_id, 'status': {
        'privacyStatus': 'private', 'publishAt': package['publish_at'],
        'selfDeclaredMadeForKids': False}}).execute()
    actual = youtube.videos().list(part='status', id=video_id).execute()['items'][0]['status']
    if actual.get('privacyStatus') != 'private' or not actual.get('publishAt'):
        raise ValueError('Schedule not confirmed. Check Studio; do not claim scheduled.')
    actual_when = dt.datetime.fromisoformat(actual['publishAt'].replace('Z', '+00:00'))
    if actual_when != when:
        raise ValueError('Remote publication time differs; check Studio.')
    state.update(scheduled=True, status=actual)
    save(state_path, state)
    print('YouTube confirmed schedule:', video_id, package['publish_local'])


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


def upload_approved(config):
    count = 0
    work = ROOT / config['work']
    for path in sorted(work.glob('*/approval.json')):
        args = argparse.Namespace(job=path.parent.name)
        try:
            with upload_lock(path.parent):
                upload(config, args)
            count += 1
        except Exception as exc:
            print('Stopped:', args.job, type(exc).__name__, str(exc)[:200])
            raise ValueError('Batch stopped. Review the failed job before continuing.')
    print('Processed approved jobs:', count)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', default=str(ROOT / 'config.json'))
    commands = parser.add_subparsers(dest='command', required=True)
    commands.add_parser('plan')
    commands.add_parser('auth')
    imp = commands.add_parser('import-pack')
    imp.add_argument('--pack', default=str(ROOT / 'assets'))
    rev = commands.add_parser('review')
    rev.add_argument('--job', required=True)
    rev.add_argument('--video', required=True)
    rev.add_argument('--description', required=True)
    rev.add_argument('--title', type=int, default=1)
    rev.add_argument('--cover', type=int, default=1)
    rev.add_argument('--code', help='Required for ambiguous versions')
    rev.add_argument('--publish-local', help='Explicit new Beijing clock time if original date expired')
    app = commands.add_parser('approve')
    app.add_argument('--job', required=True)
    app.add_argument('--fingerprint', required=True)
    app.add_argument('--confirm-rights-audio-restrictions', action='store_true', required=True)
    up = commands.add_parser('upload')
    up.add_argument('--job', required=True)
    commands.add_parser('upload-approved')
    args = parser.parse_args()
    config = load(args.config)
    if args.command == 'plan': plan(config)
    elif args.command == 'auth': auth(config); print('Channel authentication verified.')
    elif args.command == 'import-pack': import_pack(config, args)
    elif args.command == 'review': review(config, args)
    elif args.command == 'approve': approve(config, args)
    elif args.command == 'upload-approved': upload_approved(config)
    elif args.command == 'upload':
        with upload_lock(ROOT / config['work'] / args.job):
            upload(config, args)


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        print(f'Error: {type(exc).__name__}: {str(exc)[:350]}', file=sys.stderr)
        sys.exit(1)




