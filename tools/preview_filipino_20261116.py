"""Make a reviewable Filipino creative preview without claiming unavailable audio."""
import csv
import json
import shutil
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED

from openpyxl import Workbook

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'materials/西语/assets_es_20261116_20261120_latest10_v1'
OUT = ROOT / 'materials/菲律宾语/preview_tl_20261116_20261120_same_slots'
RELEASE = ROOT / 'releases/filipino_creative_preview_same_spanish_schedule_20261116_20261120.zip'
TITLES = [
    '🐒 Iniligtas niya ang unggoy at binigyan ng tatlong mahiwagang buhok—isa pa lang, nagkagulo na! 🔥',
    '🌊 Pinalayas siya ng pamilya; sa lumang bathtub niya, may palasyong puno ng ginto! 💰',
    '☄️ Itinulak siya ng asawa sa bangin—muling isinilang bilang meteor na lumulunok ng planeta! 🤯',
    '💍 Ayaw siyang pakasalan ng tagapagmana; nang iligtas niya ang lolo nito, nabunyag ang sabwatan! ⚡',
    '👁️ Bulag ang guro, pero ang unggoy na tinuruan niya ang kinatakutan ng mga diyos! 🐒',
    '🔫 Kasal pa lang sila nang lumiko ang bala—saka nalaman ng asawa kung sino talaga siya! 😱',
    '🫏 Naging asno ang mandirigma; sa araw ng hatol, bumalik siya para iligtas ang pamilya! 🔥',
    '⚔️ Kalalaya lang niya sa bilangguan, hinarang na niya ang kasal ng nobya—sino ba talaga siya? 🤯',
    "📺 Isang maling bombilya sa nayon ng dekada '80, patay ka! Siya lang ang nakaalam ng tuntunin 👻",
    '👑 Gusto lang niyang umalis; sa gitna ng tagtuyot, siya pala ang magliligtas sa kaharian! 🔥',
]
STATUS = ['菲律宾语配音已标有', '原代码无菲律宾语配音；同剧情2609 KR51标有',
          '菲律宾语配音已标有', '资源表未标菲律宾语配音',
          '菲律宾语配音已标有', '菲律宾语配音已标有',
          '菲律宾语配音已标有', '菲律宾语配音已标有',
          '菲律宾语配音已标有', '菲律宾语11月5日已排同剧']


def build():
    schedule = json.loads((SOURCE / 'schedule.json').read_text(encoding='utf-8'))
    manifest = json.loads((SOURCE / 'manifest.json').read_text(encoding='utf-8'))
    if len(schedule) != len(TITLES) or len(manifest['jobs']) != len(TITLES):
        raise ValueError('来源素材并非10部。')
    cover_dir = OUT / 'covers'
    cover_dir.mkdir(parents=True, exist_ok=True)
    rows = []
    for job, entry, title, status in zip(schedule, manifest['jobs'], TITLES, STATUS):
        if job['job_id'] != entry['job_id'] or len(title.encode('utf-16-le')) // 2 > 100:
            raise ValueError('排片与封面或标题不符。')
        source = SOURCE / entry['covers'][0]
        target = cover_dir / source.name
        shutil.copy2(source, target)
        rows.append([job['date'], '00:00' if job['slot'] == 1 else '05:00',
                     job['title_zh'], job['candidates'][0]['drama_code'],
                     title, 'covers/' + source.name, status])
    header = ['日期', '北京时间', '中文剧名', '原剧集代码', '菲律宾语标题', '封面文件', '发布核对']
    OUT.mkdir(parents=True, exist_ok=True)
    with (OUT / '菲律宾语封面标题预览.csv').open('w', encoding='utf-8-sig', newline='') as stream:
        writer = csv.writer(stream)
        writer.writerow(header)
        writer.writerows(rows)
    book = Workbook()
    sheet = book.active
    sheet.title = '10部预览'
    sheet.append(header)
    for row in rows:
        sheet.append(row)
    sheet.freeze_panes = 'A2'
    for column in sheet.columns:
        sheet.column_dimensions[column[0].column_letter].width = min(95, max(16, max(len(str(cell.value or '')) for cell in column) + 2))
    book.save(OUT / '菲律宾语封面标题预览.xlsx')
    (OUT / 'README.md').write_text(
        '这是沿用西语10部及11月16—20日00:00、05:00排期的菲律宾语封面标题预览，不是可发布素材包。'
        '封面无文字，沿用本轮全新生成的10张图；标题已改为菲律宾语。'
        '资源表显示原代码2026 WW34无菲律宾语配音，但同剧情2609 KR51有；2026 WW02未标菲律宾语配音；'
        '《大明憨王爹我真想就藩》已在菲律宾语11月5日排过。待确定是否换剧后再制作可导入程序的完整素材包。\n',
        encoding='utf-8')
    with ZipFile(RELEASE, 'w', ZIP_DEFLATED, compresslevel=6) as archive:
        for path in sorted(OUT.rglob('*')):
            if path.is_file():
                archive.write(path, OUT.name + '/' + str(path.relative_to(OUT)).replace('\\', '/'))
    print(RELEASE, RELEASE.stat().st_size)


if __name__ == '__main__':
    build()
