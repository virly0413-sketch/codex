"""Create the Nov 16-20 Spanish schedule from the latest supplied resource XLSX."""
import csv
import datetime as dt
import hashlib
import json
import re
from pathlib import Path

from openpyxl import Workbook, load_workbook

ROOT = Path(__file__).resolve().parents[1]
RESOURCE = Path('/workspace/attachments/3d986933-f246-4639-b27d-c1da98129ba9/YouTube剧集资源表-杭州 (1).xlsx')
TRANSPOSED = Path('/workspace/attachments/b3305418-b642-4cc1-a374-38816345c1e4/排片表 - 转置结果.csv')
OUT = ROOT / 'schedules/spanish_20261116_20261120_two_daily'
CHANNEL = 'UCaQI24vmsim_8jDI0NuwbEg'
SHANGHAI = dt.timezone(dt.timedelta(hours=8))
CHOICES = [
    (16, 0, '2026 WW45'), (16, 5, '2026 WW34'),
    (17, 0, '2026 WW25'), (17, 5, '2026 WW02'),
    (18, 0, '2026 WW61'), (18, 5, '2026 WW54'),
    (19, 0, '2026 WW56'), (19, 5, '2026 WW17'),
    (20, 0, '2026 WW62'), (20, 5, '2026 WW73'),
]
ALIASES = {
    '2026 WW34': {'2609 KR51'},  # Same bathtub/ocean story, different catalog title.
}


def normalized(title):
    title = re.sub(r'AI[+＋]?\s*(?:真人|仿真人|实拍)', '', str(title), flags=re.I)
    return ''.join(re.findall(r'\w', title)).casefold()


def history():
    result = []
    paths = (list((ROOT / 'materials').glob('**/schedule.json')) +
             list((ROOT / 'schedules').glob('**/schedule.json')) +
             list((ROOT / 'data').glob('jobs*.json')))
    for path in paths:
        if path.resolve() == (OUT / 'schedule.json').resolve():
            continue
        try:
            jobs = json.loads(path.read_text(encoding='utf-8'))
        except (ValueError, OSError):
            continue
        if not isinstance(jobs, list):
            continue
        for job in jobs:
            if not isinstance(job, dict) or not job.get('title_zh'):
                continue
            codes = {str(c.get('drama_code', '')).strip() for c in job.get('candidates', [])}
            spanish = (job.get('language') == 'es' or '西语' in str(path) or 'jobs.es' in path.name)
            when = job.get('publish_local')
            try:
                when = dt.datetime.fromisoformat(when) if when else None
                if when and when.tzinfo is None:
                    when = when.replace(tzinfo=SHANGHAI)
            except ValueError:
                when = None
            result.append((normalized(job['title_zh']), codes, spanish, when, str(path)))
    # The user's transposed upload contains September/October channel slots absent
    # from the later material packages; Spanish entries must remain excluded.
    with TRANSPOSED.open(encoding='utf-8-sig', newline='') as stream:
        matrix = list(csv.reader(stream))
    for row in matrix[1:]:
        spanish = row[0].strip() in ('西班牙', '西语')
        for index, title in enumerate(row[1:], 1):
            if not title.strip() or index >= len(matrix[0]):
                continue
            try:
                date = dt.datetime.strptime(matrix[0][index].strip(), '%Y.%m.%d').date()
            except ValueError:
                continue
            when = dt.datetime.combine(date, dt.time(), SHANGHAI)
            result.append((normalized(title), set(), spanish, when, str(TRANSPOSED)))
    return result


def build():
    sheet = load_workbook(RESOURCE, read_only=False, data_only=True)['最新剧集']
    by_code = {}
    for number, row in enumerate(sheet.iter_rows(min_row=3, values_only=True), 3):
        code = str(row[1] or '').strip()
        if code in {choice[2] for choice in CHOICES}:
            by_code[code] = (number, row)
    previous = history()
    jobs, rows, audits = [], [], []
    for day, hour, code in CHOICES:
        number, row = by_code[code]
        raw, availability, category = str(row[0]), str(row[5] or ''), str(row[23] or '')
        title = re.sub(r'^《([^》]+)》.*$', r'\1', raw).strip()
        if '有' not in availability or '男频' not in category:
            raise ValueError('西语配音或男频属性不足：' + code)
        flags = ' '.join(str(row[i] or '') for i in (0, 2, 29, 30, 31, 32))
        if any(word in flags for word in ('禁播', '外采', '代运营')):
            raise ValueError('资源表限制：' + code)
        start = dt.datetime(2026, 11, day, hour, tzinfo=SHANGHAI)
        matching = [item for item in previous if item[0] == normalized(title) or
                    code in item[1] or item[1] & ALIASES.get(code, set())]
        if any(item[2] for item in matching):
            raise ValueError('与西语历史重复：' + title)
        dated = [(abs((start - item[3]).total_seconds()) / 3600, item) for item in matching if item[3]]
        closest = min(dated, key=lambda pair: pair[0]) if dated else None
        if closest and closest[0] < 168:
            raise ValueError('跨频道间隔不足7天：' + title)
        if any(normalized(title) == normalized(job['title_zh']) for job in jobs):
            raise ValueError('本次重复：' + title)
        job_id = hashlib.sha256(f'es|{start.isoformat()}|{code}|{title}'.encode()).hexdigest()[:16]
        job = {
            'job_id': job_id, 'title_zh': title, 'channel': '西语男频',
            'channel_id': CHANNEL, 'language': 'es', 'date': start.date().isoformat(),
            'slot': 1 if hour == 0 else 2, 'timezone': 'Asia/Shanghai',
            'publish_local': start.isoformat(),
            'publish_at': start.astimezone(dt.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),
            'candidates': [{'resource_xlsx_sheet': '最新剧集', 'resource_row': number,
                            'resource_title': raw, 'drama_code': code,
                            'audio_language': 'es', 'audio_availability': availability,
                            'category': category, 'minutes': str(row[26] or ''),
                            'episodes': str(row[27] or '')}],
            'description_mode': 'append_code_only_preserve_existing',
            'description_code_position': 'last_line',
            'blockers': ['youtube_oauth_not_connected', 'existing_video_selection_required'],
            'approved': False,
        }
        jobs.append(job)
        rows.append([start.date().isoformat(), '00:00' if hour == 0 else '05:00', title,
                     code, availability, number,
                     f'{closest[0]:.0f}' if closest else '未见同剧排期'])
        audits.append([title, code, ', '.join(sorted(ALIASES.get(code, []))),
                       f'{closest[0]:.0f}' if closest else '未见同剧排期',
                       closest[1][4] if closest else ''])
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / 'schedule.json').write_text(json.dumps(jobs, ensure_ascii=False, indent=2), encoding='utf-8')
    with (OUT / '西语排片表.csv').open('w', encoding='utf-8-sig', newline='') as stream:
        writer = csv.writer(stream)
        writer.writerow(['日期', '北京时间', '中文剧名', '剧集代码', '西语标记', '资源表行号', '最近同剧间隔(小时)'])
        writer.writerows(rows)
    book = Workbook()
    overview = book.active
    overview.title = '排片总览'
    overview.append(['日期', '00:00剧名', '00:00代码', '05:00剧名', '05:00代码'])
    for i in range(0, len(rows), 2):
        overview.append([rows[i][0], rows[i][2], rows[i][3], rows[i + 1][2], rows[i + 1][3]])
    details = book.create_sheet('10部明细')
    details.append(['日期', '北京时间', '中文剧名', '剧集代码', '西语标记', '资源表行号', '最近同剧间隔(小时)'])
    for row in rows:
        details.append(row)
    audit = book.create_sheet('跨频道间隔核对')
    audit.append(['中文剧名', '剧集代码', '同剧情异名版本代码', '最近间隔(小时)', '历史排期来源'])
    for row in audits:
        audit.append(row)
    for ws in book:
        ws.freeze_panes = 'A2'
        for column in ws.columns:
            letter = column[0].column_letter
            ws.column_dimensions[letter].width = min(65, max(16, max(len(str(cell.value or '')) for cell in column) + 2))
    book.save(OUT / '西语排片与间隔核对.xlsx')
    (OUT / 'README.md').write_text(
        '2026年11月16—20日，每天北京时间00:00、05:00，共10部。使用2026年11月9日上传的《YouTube剧集资源表-杭州 (1).xlsx》最新剧集表。'
        '合并此前上传的转置排片表及各语种已交付排片，排除西语历史同剧及资源表标注禁播、代运营、外采的剧；与已提供的各频道排期同剧至少间隔168小时。'
        '《别惹卖鱼的他海底有龙宫》与《我家浴缸通海底》按同剧情核对；最新剧《诡异擂台我请万界天骄诛神》与西语历史同剧情，未纳入。'
        '资源表更靠后的WW87、WW88、WW91、WW92、WW95在目标日期内与其他频道已排同剧不足168小时；WW90与西语旧排《末日之我的房车无限升级》同剧情，因此未选。'
        '本包只有排片，没有封面和西语标题，不能直接作为程序完整素材包导入；未修改YouTube或原排片。'
        '线上未提供的临时变更无法核验。\n', encoding='utf-8')
    print('Wrote', OUT, 'jobs', len(jobs))


if __name__ == '__main__':
    build()
