"""Ship the prior desktop style with six current, complete material folders."""
import json
import subprocess
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED

ROOT = Path(__file__).resolve().parent
OUT = ROOT / 'releases/six_channel_publisher_legacy_style_complete_20261110.zip'
PART_ONE = ROOT / 'releases/six_channel_publisher_legacy_style_part1_20261110.zip'
PART_TWO = ROOT / 'releases/six_channel_publisher_legacy_style_part2_20261110.zip'
PREFIX = 'youtube_publisher/'
PACKS = {
    'english': 'materials/英语/assets_en_20261115_20261125_story_v1',
    'english2': 'materials/英语2/assets_en2_20261116_1800_original14_v3',
    'spanish': 'materials/西语/assets_es_20261106_fusion_titles_v6',
    'korean': 'materials/韩语/assets_ko_20261110_fresh_v3',
    'russian': 'materials/俄语/assets_ru_20261107_two_daily28',
    'filipino': 'materials/菲律宾语/assets_tl_20261105_character_conflict_v5',
}
CODE = ['run.py', 'prepare.py', 'networking.py', 'material_library.py',
        'publisher_profiles.py', 'publisher_start.py', 'requirements.txt',
        'six_channel_legacy_start.py']
GUIDE = '''六频道旧版界面整合程序（北京时间）

本包沿用原来的发布界面和Windows启动方式，内含六个语种现有排片、封面和标题。请先完整解压，再双击 youtube_publisher 文件夹里的 start_windows.bat。首次运行需要Python 3.10及网络安装依赖。

首次启动会提示绑定菲律宾语频道真实的UC开头ID；可以取消，先使用其他五频道，下次启动仍可绑定。程序不会猜测菲律宾语ID。

顶部“选择目标频道及内置素材”可切换英语1、英语2、西语、韩语、俄语、菲律宾语。每个频道有独立素材文件夹。以后把新的完整素材包解压到单独文件夹（含manifest.json、schedule.json、covers），先选频道，再点“设置所选频道素材文件夹”选择新包所在文件夹，点“切换频道并加载素材”。切回旧版时，用同一按钮选旧素材文件夹再加载。不要把新旧两个manifest.json放在同一个选中的文件夹下。

程序仍按旧方式扫描和匹配频道内已上传的私密视频，再修改标题、封面和定时公开；不会上传视频文件。频道授权与本机token按频道保存。复制到原来正常使用的程序目录时，保留原来的.venv、client_secret.json、token*.json和local_work*目录，不要删除它们。

六频道素材数：英语1 22；英语2 14；西语 19；韩语 22；俄语 28；菲律宾语 22。
'''


def build():
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with ZipFile(OUT, 'w', ZIP_DEFLATED, compresslevel=6, allowZip64=True) as archive:
        for name in CODE:
            archive.write(ROOT / name, PREFIX + name)
        # Preserve the exact interface from the last working multi-channel release.
        desktop = subprocess.run(['git', 'show', '36f631b:desktop.py'], cwd=ROOT,
                                 check=True, capture_output=True).stdout
        archive.writestr(PREFIX + 'desktop.py', desktop)
        filipino = (ROOT / 'filipino_setup.py').read_text(encoding='utf-8')
        filipino = filipino.replace("ASSETS = 'materials/菲律宾语/assets_tl_20261026_ready'",
            "ASSETS = 'materials/菲律宾语/assets_tl_20261105_character_conflict_v5'")
        filipino = filipino.replace("planning_source='data/jobs.tl.20261026.json'",
            "planning_source=ASSETS + '/schedule.json'")
        archive.writestr(PREFIX + 'filipino_setup.py', filipino)
        launcher = (ROOT / 'start_windows.bat').read_text(encoding='utf-8')
        launcher = launcher.replace('publisher_start.py', 'six_channel_legacy_start.py')
        archive.writestr(PREFIX + 'start_windows.bat', launcher)
        for name in ('english', 'english2', 'spanish', 'korean', 'russian'):
            profile = json.loads((ROOT / 'profiles' / (name + '.json')).read_text(encoding='utf-8'))
            profile['assets_path'] = PACKS[name]
            profile['planning_source'] = PACKS[name] + '/schedule.json'
            profile.pop('start_date', None)
            archive.writestr(PREFIX + 'profiles/' + name + '.json',
                             json.dumps(profile, ensure_ascii=False, indent=2))
            if name == 'english':
                archive.writestr(PREFIX + 'config.json', json.dumps(profile, ensure_ascii=False, indent=2))
        for relative in PACKS.values():
            for path in (ROOT / relative).rglob('*'):
                if path.is_file():
                    archive.write(path, PREFIX + str(path.relative_to(ROOT)).replace('\\', '/'))
        archive.writestr(PREFIX + '使用说明.txt', GUIDE)
    print(OUT, OUT.stat().st_size)


def split_for_download():
    """Keep each downloadable ZIP below GitHub's 100 MB per-file limit."""
    with ZipFile(OUT) as source, \
         ZipFile(PART_ONE, 'w', ZIP_DEFLATED, compresslevel=6) as first, \
         ZipFile(PART_TWO, 'w', ZIP_DEFLATED, compresslevel=6) as second:
        for info in source.infolist():
            name = info.filename
            other_material = name.startswith(PREFIX + 'materials/') and not name.startswith((
                PREFIX + 'materials/英语/', PREFIX + 'materials/英语2/', PREFIX + 'materials/西语/'))
            target = second if other_material else first
            target.writestr(name, source.read(info))
        first.writestr('先读我.txt',
            '先把第1包和第2包都下载到电脑。分别右键“全部解压”，把两个包中的youtube_publisher文件夹合并到同一位置，全部解压完后再双击start_windows.bat。不要只运行第1包。')
    for path in (PART_ONE, PART_TWO):
        if path.stat().st_size >= 100_000_000:
            raise ValueError('分卷超过GitHub文件大小限制：' + str(path))
        print(path, path.stat().st_size)


if __name__ == '__main__':
    build()
    split_for_download()
