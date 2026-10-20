"""Build an overlay for an existing publisher without credentials or local state."""
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / 'releases/spanish_publisher_latest_midnight_with_materials.zip'
FILES = [
    'desktop.py', 'material_library.py', 'publisher_profiles.py',
    'publisher_start.py', 'run.py', 'prepare.py', 'networking.py',
    'baidu_download.py', 'requirements.txt', 'start_windows.bat',
    'SPANISH_GUIDE.md', 'profiles/spanish.json', 'data/jobs.es.20261026.json',
]
GUIDE = '''西语程序升级合并包（北京时间零点版）

适用于已安装的原发布程序。包含：西语频道入口、各语种素材文件夹切换、窗口右侧滚动条、西班牙=西语识别、21部西语素材及零点排期。无需再安装此前的西语升级包或语种补丁。

1. 关闭原程序，解压本ZIP。
2. 打开解压出来的 youtube_publisher_update 文件夹，将里面全部文件和文件夹复制到原程序目录（与 start_windows.bat 同级），合并文件夹并覆盖同名文件。不要把整个 youtube_publisher_update 文件夹直接套在原目录里，也不要删除原程序目录。
3. 双击原目录 start_windows.bat，选择“西语 | 西语男频”，点击“切换频道并加载素材”。
4. 如此前设置过西语专属素材路径，程序优先使用已设置的路径：先移走该路径内旧素材包，再将本包 materials/西语/assets_es_20261026 文件夹复制进去；或者将该语种素材路径设置为原程序目录 materials/西语，再重新加载。每个路径仅保留一个 manifest.json。
5. 目标频道 UCaQI24vmsim_8jDI0NuwbEg。首次使用西语需要官方OAuth授权并选择该频道；保留已有 client_secret.json、各频道token及所有 local_work 开头的记录目录。本包不携带也不覆盖这些文件，不覆盖英俄韩频道配置。
6. 排期2026年10月26日至11月15日，每天北京时间00:00，指当天开始；日期未变。63条西语标题、21张无字成年人物封面（3840×2160放大导出，非原生4K）。
7. 扫描频道中已上传的私密视频，匹配剧名，选择标题及封面，点击发布后更新标题封面、在现有说明最后一行加代码并定时公开；不重传视频。安装和加载本包不会修改YouTube上已定时的视频。

重要：最新资源表将11月5日《从蚁王开始吞噬成神》标为禁播，请跳过该条，不要点击发布。该条仍在原排期中，本次没有替换剧目，也没有加入自动禁播拦截。

以后只更换对应语种的完整素材包（manifest.json、schedule.json、covers），再点击重新加载，无需重装程序。
'''


def build():
    base = Path('youtube_publisher_update')
    with ZipFile(OUTPUT, 'w', ZIP_DEFLATED) as z:
        z.writestr('先读我-安装说明.txt', GUIDE)
        for name in FILES:
            z.write(ROOT / name, base / name)
        pack = ROOT / 'assets_es_20261026'
        for path in sorted(pack.rglob('*')):
            if path.is_file():
                z.write(path, base / 'materials/西语/assets_es_20261026' / path.relative_to(pack))
    print(OUTPUT.name, OUTPUT.stat().st_size, 'bytes')


if __name__ == '__main__':
    build()
