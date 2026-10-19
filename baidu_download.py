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
           '西语': ('西语', '西班牙语'), '菲律宾语': ('菲律宾语', '菲语'), '韩语': ('韩语', '韩文')}
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


def build_tasks(schedule, resources, languages, start=None, end=None):
    table, catalog = read_csv(schedule), read_csv(resources)
    if not table or len(catalog) < 2:
        raise ValueError('排片表或资源表缺少表头。')
    index = {}
    for row in catalog[2:]:
        if len(row) <= 1 or not row[0].strip():
            continue
        entry = {'title': row[0], 'code': row[1].strip(),
                 'share': share_link(row[29]) if len(row) > 29 else None}
        index.setdefault(normalize(row[0]), []).append(entry)
    dates, last = [], None
    for value in table[0][1:]:
        if value.strip():
            last = dt.datetime.strptime(value.strip(), '%Y.%m.%d').date()
            inferred = False
        elif last:
            last += dt.timedelta(days=1)
            inferred = True
        else:
            inferred = False
        dates.append((last.isoformat() if last else None, inferred))
    tasks = []
    for language in languages:
        if language not in LANGUAGES:
            raise ValueError('不支持该语种：' + language)
        channels = [r for r in table[1:] if r and r[0].strip() in LANGUAGES[language]]
        if len(channels) != 1:
            raise ValueError(language + '未找到唯一频道行，请核对排片表行名。')
        for (date, inferred), cell in zip(dates, channels[0][1:]):
            if not date or not cell.strip() or (start and date < start) or (end and date > end):
                continue
            for slot, title in enumerate(cell.split('/'), 1):
                title = title.strip()
                if not title:
                    continue
                candidates = index.get(normalize(title), [])
                key = f'{language}|{date}|{slot}|{title}'
                selected = candidates[0] if len(candidates) == 1 else None
                task = dict(id=hashlib.sha256(key.encode()).hexdigest()[:16], language=language,
                    date=date, title=title, inferred_date=inferred, candidates=candidates,
                    code=selected['code'] if selected else '', share=selected['share'] if selected else None)
                task['status'] = ready_status(task)
                tasks.append(task)
    return sorted(tasks, key=lambda t: (t['date'], t['language'], t['id']))


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
