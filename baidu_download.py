"""Local multi-language download planning. Private share links stay on the user's PC."""
import csv
import datetime as dt
import hashlib
import json
from pathlib import Path
import re
from urllib.parse import parse_qs, urlsplit, urlunsplit

from prepare import normalize

LANGUAGES = {'俄语': ['俄语男频'], '英语': ['Supreme Hero Flicks'],
             '西语': ['男频西班牙'], '菲律宾语': ['男频菲律宾'], '韩语': ['무협역전숏드']}
ALIASES = {'俄语': ('俄语', '俄文'), '英语': ('英语', '英文'),
           '西语': ('西语', '西班牙语', '西班牙'), '菲律宾语': ('菲律宾语', '菲语'), '韩语': ('韩语', '韩文')}
VIDEOS = {'.mp4', '.mkv', '.mov', '.avi', '.flv', '.m4v', '.webm', '.ts'}


def read_csv(path):
    with Path(path).open(encoding='utf-8-sig', newline='') as f:
        return list(csv.reader(f))


def share_link(text):
    urls = re.findall(r'https?://pan\.baidu\.com/(?:s/|share/init\?)[^\s<>"“”]+', text)
    urls = list(dict.fromkeys(x.rstrip('。，,；;）)') for x in urls))
    if len(urls) != 1:
        return None
    url = urls[0]
    parts = urlsplit(url)
    query = parse_qs(parts.query)
    if parts.path == '/share/init' and not query.get('surl'):
        return None
    password = query.get('pwd', [''])[0]
    if not password:
        match = re.search(r'(?:提取码|访问码|密码)\s*[:：]?\s*([A-Za-z0-9]{4})\b', text)
        password = match.group(1) if match else ''
    if password and not re.fullmatch(r'[A-Za-z0-9]{4}', password):
        return None
    # Retain query fields (e.g. surl), but never write links to public reports.
    return {'url': urlunsplit(('https', parts.netloc, parts.path, parts.query, '')), 'password': password}


def share_identity(share):
    parts = urlsplit(share['url'])
    key = parts.path
    if parts.path == '/share/init':
        key += '?' + parse_qs(parts.query).get('surl', [''])[0]
    return key


def suffix_language(name, is_file=True):
    stem = Path(name).stem if is_file else name
    stem = re.sub(r'(?:[ _.-]*(?:1080[pP]|720[pP]|2160[pP]|4[Kk]|高清|完整版))+$', '', stem)
    stem = stem.rstrip(' _-—.()（）[]【】')
    choices = []
    for language, aliases in ALIASES.items():
        for alias in aliases:
            if stem.endswith(alias) and not stem.endswith('非' + alias):
                prefix = stem[:-len(alias)].rstrip(' _-—.()（）[]【】、,，+')
                # A combined label such as 英语俄语 is not a single-language guarantee.
                if any(prefix.endswith(a) for values in ALIASES.values() for a in values):
                    return None
                choices.append(language)
    return choices[0] if len(set(choices)) == 1 else None


def file_language(item):
    own = suffix_language(item['name'])
    if own:
        return own
    # A contradictory or explicitly multi-language filename cannot inherit a folder label.
    stem = Path(item['name']).stem
    if any(a in stem for values in ALIASES.values() for a in values):
        return None
    for parent in reversed(item.get('parents', [])):
        language = suffix_language(parent, is_file=False)
        if language:
            return language
        if any(a in parent for values in ALIASES.values() for a in values):
            return None
    return None


def select_files(items, language):
    return [x for x in items if not x.get('isdir') and
            Path(x['name']).suffix.lower() in VIDEOS and file_language(x) == language]


def row_language(label):
    explicit = [language for language, aliases in ALIASES.items() if any(a in label for a in aliases)]
    if len(explicit) == 1:
        return explicit[0]
    if not explicit:
        known = [language for language, labels in LANGUAGES.items() if label.strip() in labels]
        if len(known) == 1:
            return known[0]
    return None


def schedule_rows(path):
    table = read_csv(path)
    if not table or len(table[0]) < 2:
        raise ValueError('排片表需第一列为频道/语种，第一行为日期。')
    return [dict(row=i, label=r[0].strip(), language=row_language(r[0]),
                 populated=sum(bool(c.strip()) for c in r[1:]))
            for i,r in enumerate(table[1:],2) if r and r[0].strip() and any(c.strip() for c in r[1:])]


def date_columns(table, infer_blank=False):
    dates=[];last=None;seen=set()
    for column,value in enumerate(table[0][1:],2):
        value=value.strip();inferred=False
        if value:
            match=re.fullmatch(r'(\d{4})[./年-](\d{1,2})[./月-](\d{1,2})(?:日)?(?:\s*(?:周|星期)[一二三四五六日天])?',value)
            if not match:raise ValueError(f'第{column}列日期无法识别：{value}；请使用完整年月日。')
            last=dt.date(*map(int,match.groups()))
            date=last
        elif infer_blank and last:
            last+=dt.timedelta(days=1);date=last;inferred=True
        else:
            date=None
        if date in seen:raise ValueError('日期表头重复：'+date.isoformat()+'，请先核对原表。')
        if date:seen.add(date)
        dates.append((date.isoformat() if date else None,inferred,column))
    return dates


def build_tasks(schedule, resources, languages=None, start=None, end=None, *,
                row_selections=None, days=None, infer_blank=False):
    table,catalog=read_csv(schedule),read_csv(resources)
    if not table or len(catalog)<2:raise ValueError('排片表或资源表缺少表头。')
    if days is not None:
        if not start:raise ValueError('选择天数时必须指定开始日期。')
        if isinstance(days,bool) or not isinstance(days,int) or not 1<=days<=366:
            raise ValueError('天数须为1—366的整数。')
        end=(dt.date.fromisoformat(start)+dt.timedelta(days=days-1)).isoformat()
    dates=date_columns(table,infer_blank)
    if days is not None and start not in {d[0] for d in dates}:
        raise ValueError('开始日期在表头中不存在；不会从相邻列猜测。请核对日期，或明确开启空白日期顺延。')
    if row_selections is None:
        row_selections=[]
        for language in languages or []:
            matches=[r for r in schedule_rows(schedule) if r['language']==language]
            if len(matches)!=1:raise ValueError(language+'对应多行或没有对应行，请明确选择排片行。')
            row_selections.append(dict(row=matches[0]['row'],language=language))
    if not row_selections:raise ValueError('请至少明确选择一行排片。')
    index={}
    for row in catalog[2:]:
        if len(row)<=1 or not row[0].strip():continue
        entry=dict(title=row[0],code=row[1].strip(),share=share_link(row[29]) if len(row)>29 else None)
        index.setdefault(normalize(row[0]),[]).append(entry)
    schedule_hash=sha256_file(schedule);resource_hash=sha256_file(resources)
    tasks=[];seen_rows=set()
    for selection in row_selections:
        number=selection['row'];language=selection['language']
        if number in seen_rows:raise ValueError('同一排片行不能重复选择。')
        seen_rows.add(number)
        if not isinstance(number,int) or number<2 or number>len(table):raise ValueError('所选排片行已不存在，请重新读取。')
        if language not in LANGUAGES:raise ValueError('所选行需要明确设置支持的语种。')
        row=table[number-1]
        if not row:raise ValueError('所选排片行为空。')
        detected=row_language(row[0])
        if detected and detected!=language:raise ValueError('所选行标注语种与指定语种不一致：'+row[0])
        if any(c.strip() for c in row[len(table[0]):]):raise ValueError('所选行存在超出日期表头的剧名，请先补齐日期列。')
        for date,inferred,column in dates:
            cell=row[column-1] if column<=len(row) else ''
            if not date or not cell.strip() or (start and date<start) or (end and date>end):continue
            for slot,title in enumerate(cell.split('/'),1):
                title=title.strip()
                if not title:continue
                matches=index.get(normalize(title),[])
                selected=matches[0] if len(matches)==1 else None
                key=f'{language}|{number}|{date}|{slot}|{title}'
                from openpyxl.utils import get_column_letter
                task=dict(id=hashlib.sha256(key.encode()).hexdigest()[:16],language=language,date=date,
                    title=title,inferred_date=inferred,candidates=matches,
                    code=selected['code'] if selected else '',share=selected['share'] if selected else None,
                    source_row=number,source_row_label=row[0],source_column=column,
                    source_cell=get_column_letter(column)+str(number),slot=slot,
                    schedule_sha256=schedule_hash,resource_sha256=resource_hash)
                task['status']=ready_status(task);tasks.append(task)
    return sorted(tasks,key=lambda t:(t['date'],t['source_row'],t['source_column'],t['slot']))


def ready_status(task):
    if not task.get('code'):
        return '待选择版本代码' if task.get('candidates') else '资源表未匹配'
    if not task.get('share'):
        return '缺少有效百度链接，可手动补充'
    return '待扫描'


def destination(task, item, folder):
    def safe(value):
        value = re.sub(r'[<>:"/\\|?*\x00-\x1f]', '_', value).rstrip(' .')
        return value[:64] or '未命名'
    suffix = Path(item['name']).suffix.lower()
    identity = hashlib.sha256((share_identity(task['share']) + '|' + str(item['id']) +
        '|' + task['language']).encode()).hexdigest()[:10]
    name = f"{task['date']}_{safe(task['title'])}_{safe(task['code'])}_{safe(Path(item['name']).stem)[:54]}_{identity}{suffix}"
    return Path(folder) / name


def atomic_json(path, value):
    from run import save
    save(path, value)


def verified_existing(path, record):
    path = Path(path)
    if not record or not path.is_file() or path.stat().st_size != record.get('bytes'):
        return False
    return sha256_file(path) == record.get('sha256')


def sha256_file(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for chunk in iter(lambda: f.read(4 * 1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()
