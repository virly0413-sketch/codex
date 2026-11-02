"""Export the requested local schedule without resource inputs or credentials."""
import csv
import datetime as dt
import json
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED
from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

ROOT = Path(__file__).resolve().parents[1]
FOLDER = ROOT / 'schedules/russian_20261107_20261120_two_daily'
EXCEL = FOLDER / 'russian_schedule_20261107_20261120.xlsx'
OUTPUT = ROOT / 'releases/russian_schedule_20261107_20261120_two_daily.zip'


def build():
    data = json.loads((FOLDER / 'schedule.json').read_text())
    rows = data['rows']
    expected = [(f'2026-11-{day:02}', time) for day in range(7, 21) for time in ('17:00', '22:00')]
    assert [(r['日期'], r['北京时间']) for r in rows] == expected
    assert len({r['剧名'] for r in rows}) == 28
    assert len({r['剧集代码'] for r in rows}) == 28
    assert all(r['俄语配音'] in ('有', '有/新') for r in rows)
    assert sum(r['安排'] == '保留已有' for r in rows) == 4
    for r in rows:
        local = dt.datetime.fromisoformat(r['publish_local'])
        utc = dt.datetime.fromisoformat(r['publish_at'].replace('Z', '+00:00'))
        assert local == utc and local.utcoffset() == dt.timedelta(hours=8)
        gap = r['跨频道最小间隔/小时']
        assert gap == '无同剧记录' or gap >= 168
    overview = []
    for a, b in zip(rows[::2], rows[1::2]):
        overview.append({'日期': a['日期'], '星期': a['星期'], '17:00剧名': a['剧名'],
                         '17:00代码': a['剧集代码'], '17:00安排': a['安排'],
                         '22:00剧名': b['剧名'], '22:00代码': b['剧集代码'], '22:00安排': b['安排']})
    book = Workbook()
    book.remove(book.active)
    notes = [{'项目': '频道', '内容': data['channel_id']},
             {'项目': '时区与范围', '内容': '2026年11月7—20日，每天北京时间17:00、22:00，共28部。'},
             {'项目': '新增与保留', '内容': '最新上传表11月7—10日17:00已有4部保持不动，其余24部新增。'},
             {'项目': '片源', '内容': '最新资源表工作簿，俄语明确标有/有新、男频、2026年起。WW代码仅表明2026年，原表未填日期时不推断具体月份。'},
             {'项目': '排除', '内容': '按最新工作簿文字标记排除外采、代运营、禁播；合并已识别同剧情异名。'},
             {'项目': '去重', '内容': '俄语所有已知上传排片及旧程序方案保守去重；保留本次范围内原定4部。'},
             {'项目': '跨频道', '内容': '使用其他频道最新已交付排期，已知同剧至少间隔168小时；本批最小169小时。'},
             {'项目': '边界', '内容': '本次仅输出排片，未登录或修改YouTube；筛查不代表实时版权许可或线上实际状态。'}]
    excluded = [
        {'未采用剧名': '九龙苏醒踏山河', '同剧情已排剧名': '九龙归位震八方', '原因': '俄语历史已排，同剧情异名排除'},
        {'未采用剧名': '被师父赶下山我被迫娶真千金', '同剧情已排剧名': '我靠医术横扫江都', '原因': '俄语历史已排，同剧情异名排除'}]
    sheets = [('排片总览', overview), ('28部明细', rows), ('跨频道间隔核对', data['spacing_audit']),
              ('同剧情排除说明', excluded), ('安排规则', notes)]
    for label, table in sheets:
        sheet = book.create_sheet(label)
        keys = list(table[0])
        sheet.append(keys)
        for row in table:
            sheet.append([row.get(k, '') for k in keys])
        sheet.freeze_panes = 'C2' if len(keys) > 3 else 'A2'
        sheet.auto_filter.ref = sheet.dimensions
        sheet.sheet_view.zoomScale = 85
        for col, cell in enumerate(sheet[1], 1):
            cell.font = Font(bold=True, color='FFFFFF')
            cell.fill = PatternFill('solid', fgColor='075985')
            key = keys[col-1]
            width = 44 if '剧名' in key or key in ('内容', '原因') else 21
            if '记录' in key or '筛查' in key or '去重' in key:
                width = 58
            sheet.column_dimensions[get_column_letter(col)].width = width
        for row in sheet.iter_rows(min_row=2):
            sheet.row_dimensions[row[0].row].height = 52
            for cell in row:
                if isinstance(cell.value, str):
                    cell.data_type = 's'
                cell.alignment = Alignment(wrap_text=True, vertical='center')
                if cell.value == '保留已有':
                    cell.fill = PatternFill('solid', fgColor='DBEAFE')
                elif cell.value == '新增':
                    cell.fill = PatternFill('solid', fgColor='DCFCE7')
    book.save(EXCEL)
    for filename, table in [('schedule_overview.csv', overview), ('schedule_details.csv', rows)]:
        with (FOLDER / filename).open('w', encoding='utf-8-sig', newline='') as stream:
            writer = csv.DictWriter(stream, fieldnames=list(table[0]), lineterminator='\n')
            writer.writeheader()
            writer.writerows(table)
    with ZipFile(OUTPUT, 'w', ZIP_DEFLATED) as archive:
        for path in sorted(FOLDER.iterdir()):
            if path.is_file():
                archive.write(path, Path(FOLDER.name) / path.name)
    print(EXCEL.relative_to(ROOT), EXCEL.stat().st_size, 'bytes')
    print(OUTPUT.relative_to(ROOT), OUTPUT.stat().st_size, 'bytes')


if __name__ == '__main__':
    build()
