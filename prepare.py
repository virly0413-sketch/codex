"""Offline, read-only CSV importer. Does not upload or modify a channel."""
import argparse
import csv
import datetime as dt
import hashlib
import json
import re
from pathlib import Path
from zoneinfo import ZoneInfo


def description_with_code(body, code):
    code = code.strip()
    if not code or '\n' in code or '\r' in code:
        raise ValueError('A single-line drama code is required')
    if body.splitlines() and body.splitlines()[-1] == code:
        return body
    separator = '' if not body or body.endswith('\n') else '\n'
    return body + separator + code


def normalize(name):
    match = re.search(r'《([^》]+)》', name)
    if match:
        name = match.group(1)
    return re.sub(r'[^\w]', '', name).casefold()


def read(path):
    with Path(path).open(encoding='utf-8-sig', newline='') as stream:
        return list(csv.reader(stream))


def prepare(schedule, resources, channel, today, now=None, language='en'):
    now = now or dt.datetime.now(ZoneInfo('Asia/Shanghai'))
    table, catalog = read(schedule), read(resources)
    channel_rows = [row for row in table[1:] if row and row[0].strip() == channel]
    if len(channel_rows) != 1:
        raise ValueError('Expected exactly one channel row')
    index = {}
    language_header = {'en':'英语','ru':'俄语'}.get(language)
    if not language_header or language_header not in catalog[1]:
        raise ValueError('Unsupported or missing audio language column')
    audio_column = catalog[1].index(language_header)
    for line, row in enumerate(catalog[2:], 3):
        if not row or not row[0].strip():
            continue
        row = row + [''] * max(0, 30 - len(row))
        entry = dict(resource_csv_line=line, resource_title=row[0], drama_code=row[1],
                     english_availability=row[4], category=row[22], minutes=row[25],
                     episodes=row[26], synopsis=row[27], tags=row[28],
                     audio_language=language, audio_availability=row[audio_column])
        index.setdefault(normalize(row[0]), []).append(entry)
    queue = []
    for date, cell in zip(table[0][1:], channel_rows[0][1:]):
        if not date.strip() or not cell.strip():
            continue
        day = dt.datetime.strptime(date.strip(), '%Y.%m.%d').date()
        for slot, title in enumerate(cell.split('/'), 1):
            title = title.strip()
            if not title:
                continue
            matches = index.get(normalize(title), [])
            publish_time = {1: dt.time(17), 2: dt.time(21)}.get(slot)
            publish_local = dt.datetime.combine(day, publish_time, ZoneInfo('Asia/Shanghai')) if publish_time else None
            blockers = ['source_video_missing',
                        'rights_and_color_coded_restrictions_unverified',
                        'human_approval_required', 'youtube_oauth_not_connected']
            if day < today:
                blockers.append('past_date_do_not_backfill_automatically')
            if publish_local is None:
                blockers.append('slot_time_missing')
            elif publish_local <= now:
                blockers.append('past_publish_time_do_not_backfill_automatically')
            if len(matches) != 1:
                blockers.append('version_selection_required' if matches else 'resource_match_missing')
            elif not matches[0]['audio_availability'].strip():
                blockers.append(language+'_audio_availability_unverified')
            elif not matches[0]['drama_code'].strip():
                blockers.append('drama_code_missing')
            key = f'{channel}|{day}|{slot}|{title}'
            queue.append(dict(job_id=hashlib.sha256(key.encode()).hexdigest()[:16],
                              channel=channel, date=day.isoformat(), slot=slot,
                              timezone='Asia/Shanghai',
                              publish_local=publish_local.isoformat() if publish_local else None,
                              publish_at=publish_local.astimezone(dt.timezone.utc).isoformat().replace('+00:00', 'Z') if publish_local else None,
                              description_code_position='last_line',
                              description_mode='append_code_only_preserve_existing',
                              title_zh=title, status='needs_review',
                              candidates=matches, blockers=blockers,
                              approved=False, title_en=None, thumbnail=None))
    return queue


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--schedule', required=True)
    parser.add_argument('--resources', required=True)
    parser.add_argument('--channel', default='Supreme Hero Flicks')
    parser.add_argument('--today', required=True, type=dt.date.fromisoformat)
    parser.add_argument('--out', required=True)
    parser.add_argument('--language', choices=['en','ru'], default='en')
    args = parser.parse_args()
    queue = prepare(args.schedule, args.resources, args.channel, args.today, language=args.language)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    (out / 'queue.json').write_text(json.dumps(queue, ensure_ascii=False, indent=2), encoding='utf-8')
    with (out / 'review.csv').open('w', encoding='utf-8-sig', newline='') as stream:
        writer = csv.writer(stream)
        writer.writerow(['任务ID', '日期', '时区', '当日序号', '剧名', '候选剧名代码', '匹配数量', '待解决事项', '北京时间', 'UTC发布时间'])
        for job in queue:
            writer.writerow([job['job_id'], job['date'], job['timezone'], job['slot'], job['title_zh'],
                             ' | '.join(c['drama_code'] for c in job['candidates']),
                             len(job['candidates']), ' | '.join(job['blockers']), job['publish_local'], job['publish_at']])
    print(json.dumps(dict(jobs=len(queue), upcoming=sum(j['date'] >= args.today.isoformat() for j in queue),
                         no_match=sum(not j['candidates'] for j in queue),
                         ambiguous=sum(len(j['candidates']) > 1 for j in queue)), ensure_ascii=False))


if __name__ == '__main__':
    main()
