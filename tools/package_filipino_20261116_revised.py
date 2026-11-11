"""Build the Filipino Nov 16-20 material pack with available dubbed versions."""
import hashlib
import json
import re
import shutil
import datetime as dt
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED

from openpyxl import Workbook, load_workbook
from PIL import Image, ImageOps

from preview_filipino_20261116 import TITLES

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'materials/西语/assets_es_20261116_20261120_latest10_v1'
RESOURCE = Path('/workspace/attachments/3d986933-f246-4639-b27d-c1da98129ba9/YouTube剧集资源表-杭州 (1).xlsx')
OUT = ROOT / 'materials/菲律宾语/assets_tl_20261116_20261120_1200_1700_v2'
RELEASE = ROOT / 'releases/filipino_materials_20261116_20261120_1200_1700_v2.zip'
REPLACEMENTS = {
    1: (775, None, TITLES[1], '同剧情菲律宾语配音版本，原西语代码2026 WW34无菲律宾语标记'),
    3: (1155, 'exec-a9ef52d1-fa1a-494f-89c5-d609515795c3.png',
        '💍 Akala niya pulubi ang asawa; sa opisina, siya pala ang bagong bise direktor! 😱',
        '替换无菲律宾语配音的《被师父赶下山我被迫娶真千金》'),
    9: (1171, 'exec-b92b2acc-0854-4668-837c-ffe474258d22.png',
        '👻 Tatlong talo na ang kaharian; tinawag niya ang mga bayani mula sa ibang mundo! 🔥',
        '替换菲律宾语11月5日已排的《大明憨王爹我真想就藩》'),
}


def clean_title(value):
    match = re.search(r'《([^》]+)》', str(value))
    return match.group(1) if match else str(value).strip()


def build():
    spanish = json.loads((SOURCE / 'schedule.json').read_text(encoding='utf-8'))
    source_manifest = json.loads((SOURCE / 'manifest.json').read_text(encoding='utf-8'))
    resource = load_workbook(RESOURCE, data_only=True, read_only=False)['最新剧集']
    old = json.loads((ROOT / 'materials/菲律宾语/assets_tl_20261105_character_conflict_v5/schedule.json').read_text(encoding='utf-8'))
    previous_titles = {job['title_zh'] for job in old}
    previous_codes = {c['drama_code'] for job in old for c in job['candidates']}
    if len(spanish) != len(TITLES) or len(spanish) != len(source_manifest['jobs']):
        raise ValueError('来源排片或封面不是10部。')
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / 'covers').mkdir(exist_ok=True)
    jobs, entries, hashes, table = [], [], {}, []
    for index, (source_job, source_entry) in enumerate(zip(spanish, source_manifest['jobs'])):
        if source_job['job_id'] != source_entry['job_id']:
            raise ValueError('西语排片与封面不匹配。')
        row_number, generated, title, note = REPLACEMENTS.get(
            index, (source_job['candidates'][0]['resource_row'], None, TITLES[index], '沿用无文字写实封面'))
        row = [cell.value for cell in resource[row_number]]
        name = clean_title(row[0])
        code = str(row[1]).strip()
        availability = str(row[18] or '').strip()
        if '有' not in availability or '男频' not in str(row[23] or ''):
            raise ValueError('资源表未确认菲律宾语配音或男频：' + name)
        if any(flag in str(row[0]) + str(row[2]) + str(row[29]) for flag in ('禁播', '代运营', '外采')):
            raise ValueError('资源表标记不允许排片：' + name)
        if name in previous_titles or code in previous_codes:
            raise ValueError('与菲律宾语已有排片重复：' + name)
        if len(title.encode('utf-16-le')) // 2 > 100:
            raise ValueError('标题超过100字符：' + name)
        hour = 12 if source_job['slot'] == 1 else 17
        local = dt.datetime.fromisoformat(source_job['date']).replace(
            hour=hour, tzinfo=dt.timezone(dt.timedelta(hours=8)))
        when = local.isoformat()
        utc = local.astimezone(dt.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
        job_id = hashlib.sha256(f'tl|{when}|{code}|{name}'.encode()).hexdigest()[:16]
        job = {
            'job_id': job_id, 'title_zh': name, 'channel': '菲律宾语男频',
            'language': 'tl', 'date': source_job['date'], 'slot': source_job['slot'],
            'timezone': 'Asia/Shanghai', 'publish_local': when,
            'publish_at': utc,
            'candidates': [{
                'resource_xlsx_sheet': '最新剧集', 'resource_row': row_number,
                'resource_title': str(row[0]), 'drama_code': code,
                'category': '男频', 'audio_language': 'tl',
                'audio_availability': availability,
                'minutes': str(row[26] or ''), 'episodes': str(row[27] or ''),
            }],
            'description_code_position': 'last_line',
            'description_mode': 'append_code_only_preserve_existing',
            'blockers': ['youtube_oauth_not_connected', 'existing_video_selection_required'],
            'approved': False,
        }
        relative = f"covers/{job['date']}_{'1200' if job['slot'] == 1 else '1700'}_{name}.jpg"
        target = OUT / relative
        if generated:
            source = Path('/workspace/generated_images') / generated
            if not source.is_file():
                raise FileNotFoundError(source)
            with Image.open(source) as image:
                image = ImageOps.fit(image.convert('RGB'), (1920, 1080), Image.Resampling.LANCZOS)
                image.save(target, 'JPEG', quality=90, optimize=True, subsampling=0)
        else:
            shutil.copy2(SOURCE / source_entry['covers'][0], target)
        with Image.open(target) as image:
            if image.format != 'JPEG' or image.size != (1920, 1080):
                raise ValueError('封面格式错误：' + relative)
        if target.stat().st_size >= 2 * 1024 * 1024:
            raise ValueError('封面超过2MB：' + relative)
        hashes[relative] = hashlib.sha256(target.read_bytes()).hexdigest()
        entry = {
            'job_id': job_id, 'title_zh': name, 'date': job['date'],
            'language': 'tl', 'drama_code': code, 'titles': [title],
            'recommended_title': 1, 'covers': [relative],
            'publish_local': when, 'thumbnail_text_mode': 'none',
            'thumbnail_resolution': [1920, 1080], 'creative_note': note,
        }
        jobs.append(job)
        entries.append(entry)
        table.append([job['date'], '12:00' if job['slot'] == 1 else '17:00',
                      name, code, title, relative, note, row_number])
    if len(jobs) != 10 or len({j['title_zh'] for j in jobs}) != 10:
        raise ValueError('菲律宾语新排片不是10部互异剧。')
    manifest = {
        'version': 2, 'language': 'tl', 'channel': '菲律宾语男频',
        'channel_id': None, 'titles_per_job': 1,
        'preserve_thumbnail_resolution': True, 'thumbnail_resolution': [1920, 1080],
        'scope': '2026年11月16—20日，每天北京时间12:00、17:00，共10部。',
        'cover_style': '复用8张无文字写实封面，按替换剧剧情全新生成2张封面。',
        'jobs': entries, 'sha256': hashes,
    }
    (OUT / 'manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding='utf-8')
    (OUT / 'schedule.json').write_text(json.dumps(jobs, ensure_ascii=False, indent=2), encoding='utf-8')
    book = Workbook()
    sheet = book.active
    sheet.title = '排片封面标题对应表'
    sheet.append(['日期', '北京时间', '中文剧名', '剧集代码', '菲律宾语标题', '封面文件', '更换说明', '资源表行号'])
    for row in table:
        sheet.append(row)
    sheet.freeze_panes = 'A2'
    for column in sheet.columns:
        sheet.column_dimensions[column[0].column_letter].width = min(100, max(14, max(len(str(cell.value or '')) for cell in column) + 2))
    book.save(OUT / '菲律宾语排片封面标题对应表.xlsx')
    (OUT / 'README.md').write_text(
        '菲律宾语11月16—20日完整素材包，每天北京时间12:00、17:00，共10部；剧目顺序沿用已确认版本。'
        '《别惹卖鱼的他海底有龙宫》改为同剧情、有菲律宾语音轨的《我家浴缸通海底》（2609 KR51）；'
        '《被师父赶下山我被迫娶真千金》换为《豪婿归来锋芒毕露》（2026 WW92）；'
        '重复的《大明憨王爹我真想就藩》换为《诡异擂台我请万界天骄诛神》（2026 WW93）。'
        '全部10部在最新资源表均标有菲律宾语音轨；本包未绑定菲律宾语频道ID，使用时按原程序首次配置真实ID。'
        '解压后在六频道程序选择菲律宾语，将素材文件夹设为本文件夹，再点击“切换频道并加载素材”。'
        '本包未修改YouTube线上排片或视频。\n', encoding='utf-8')
    RELEASE.parent.mkdir(parents=True, exist_ok=True)
    with ZipFile(RELEASE, 'w', ZIP_DEFLATED, compresslevel=6) as archive:
        for path in sorted(OUT.rglob('*')):
            if path.is_file():
                archive.write(path, OUT.name + '/' + str(path.relative_to(OUT)).replace('\\', '/'))
    print(RELEASE, RELEASE.stat().st_size)


if __name__ == '__main__':
    build()
