"""Install one complete material ZIP for the selected channel, with offline validation."""
import re
import shutil
import stat
import tempfile
from pathlib import Path, PurePosixPath
from zipfile import ZipFile, BadZipFile

import run
from material_library import load_materials, material_key, set_material_folder

MAX_FILES = 500
MAX_UNCOMPRESSED = 300 * 1024 * 1024
MAX_MEMBER = 50 * 1024 * 1024


def _members(archive):
    entries = archive.infolist()
    if not entries or len(entries) > MAX_FILES:
        raise ValueError('素材ZIP为空或文件数量超过500个。')
    total = 0
    seen = set()
    for info in entries:
        name = info.filename.replace('\\', '/')
        path = PurePosixPath(name)
        if (not name or name.startswith('/') or re.match(r'^[A-Za-z]:', name)
                or any(part in ('', '.', '..') for part in name.rstrip('/').split('/'))):
            raise ValueError('素材ZIP包含无效路径。')
        if name in seen:
            raise ValueError('素材ZIP包含重名文件。')
        seen.add(name)
        mode = (info.external_attr >> 16) & 0o170000
        if mode not in (0, stat.S_IFREG, stat.S_IFDIR):
            raise ValueError('素材ZIP不能包含链接或特殊文件。')
        if info.file_size > MAX_MEMBER:
            raise ValueError('素材ZIP含超过50MB的单个文件。')
        total += info.file_size
    if total > MAX_UNCOMPRESSED:
        raise ValueError('素材ZIP解压后超过300MB。')
    manifests = [info.filename.replace('\\', '/') for info in entries
                 if info.filename.replace('\\', '/').endswith('/manifest.json') or info.filename == 'manifest.json']
    if len(manifests) != 1:
        raise ValueError('整包必须有且只有一个manifest.json。')
    prefix = manifests[0].removesuffix('manifest.json')
    selected = [info for info in entries if info.filename.replace('\\', '/').startswith(prefix)]
    return selected, prefix


def install_material_zip(config, zip_path):
    """Validate before changing channel folder settings; no YouTube/network calls."""
    source = Path(zip_path).resolve()
    if not source.is_file() or source.suffix.lower() != '.zip':
        raise ValueError('请选择完整的排片封面标题ZIP文件。')
    key = material_key(config)
    if key not in ('en', 'en2', 'es', 'ko', 'ru', 'tl'):
        raise ValueError('请选择六个已配置频道之一。')
    parent = run.ROOT / 'local_material_bundles' / key
    parent.mkdir(parents=True, exist_ok=True)
    archive_hash = run.digest(source)
    final = parent / archive_hash[:20]
    if final.is_dir():
        loaded = load_materials(config, folder=final)
        set_material_folder(key, final)
        return loaded
    with tempfile.TemporaryDirectory(prefix='new-', dir=parent) as temp:
        stage = Path(temp)
        try:
            with ZipFile(source) as archive:
                entries, prefix = _members(archive)
                if archive.testzip() is not None:
                    raise ValueError('素材ZIP损坏，请重新下载。')
                for info in entries:
                    target = stage / info.filename.replace('\\', '/').removeprefix(prefix)
                    if info.is_dir():
                        target.mkdir(parents=True, exist_ok=True)
                    else:
                        target.parent.mkdir(parents=True, exist_ok=True)
                        with archive.open(info) as reader, target.open('wb') as writer:
                            shutil.copyfileobj(reader, writer)
        except BadZipFile as exc:
            raise ValueError('素材ZIP格式无效或损坏。') from exc
        # This also checks the exact channel, language, dates, codes, titles and image hashes.
        load_materials(config, folder=stage)
        stage.rename(final)
    loaded = load_materials(config, folder=final)
    set_material_folder(key, final)
    return loaded
