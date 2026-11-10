"""Build the reusable six-channel Windows publisher without credentials or media."""
import json
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED

ROOT = Path(__file__).resolve().parent
OUT = ROOT / 'releases' / 'six_channel_publisher_universal_20261110_v2.zip'
BASE = '六频道自动发布程序/'
SOURCES = [
    'run.py', 'prepare.py', 'networking.py', 'desktop.py', 'publisher_start.py',
    'publisher_profiles.py', 'material_library.py', 'material_bundle.py',
    'filipino_setup.py', 'six_channel_start.py', 'requirements.txt', '启动六频道.bat',
]
PROFILES = ['english', 'english2', 'spanish', 'korean', 'russian']
GUIDE = '''六频道自动发布程序（北京时间）

1. 解压本ZIP到固定文件夹，双击“启动六频道.cmd”（或同名.bat）。首次启动会安装Python依赖；电脑需有Python 3.10或更高版本及网络。启动失败时窗口会停留，详细错误写在同目录的“启动日志.txt”。若看到@echo off等代码，表示文件被文本软件预览，并未运行。
2. 英语1、英语2、西语、韩语、俄语可直接在左上角选择。菲律宾语首次点击“首次设置菲律宾语频道ID”，输入该频道真实的UC开头24位ID。不要填写其他频道ID。
3. 选择频道，点击“导入所选频道素材ZIP”，选择该频道完整的排片＋封面＋标题整包。程序先在本机校验语种、频道、排片时间、剧集代码、标题长度和封面文件，再启用新批次。导入错误不会替换当前批次。
4. 此后每次更新，只需重复第3步；无需重新安装或替换程序文件。新整包需要包含一个manifest.json、一个schedule.json和对应封面图片；不要只给单张封面或单独标题表。
5. 点击“YouTube 官方授权”授权对应频道；先扫描频道已上传的私密视频，再选剧、视频、标题、代码及时间，点击“发布”。此程序修改已上传视频并设定发布时间，不上传视频文件。
6. 请勿把client_secret.json、token*.json或本机local_work*目录发给他人。旧排期已过的日期，发布前须修改为未来北京时间。

英语1频道：UC0koaDPTujsoVj-Tw27J0Qg
英语2频道：UCXdinQ6fQ8RyenilKIymAFA
西语频道：UCaQI24vmsim_8jDI0NuwbEg
韩语频道：UCYIkDEkNEAiaJA2HkBZtNFA
俄语频道：UC_o03Jz0Ek8xYGE_oy3zapg
菲律宾语频道：首次由你输入真实ID，程序不会猜测。
'''


def build():
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with ZipFile(OUT, 'w', ZIP_DEFLATED, compresslevel=9) as archive:
        for name in SOURCES:
            archive.write(ROOT / name, BASE + name)
        archive.write(ROOT / '启动六频道.bat', BASE + '启动六频道.cmd')
        for name in PROFILES:
            profile = json.loads((ROOT / 'profiles' / (name + '.json')).read_text(encoding='utf-8'))
            profile['planning_source'] = '未导入素材/schedule.json'
            profile['assets_path'] = '未导入素材'
            profile.pop('material_batch', None)
            profile.pop('material_source', None)
            profile.pop('material_job_count', None)
            archive.writestr(BASE + 'profiles/' + name + '.json', json.dumps(profile, ensure_ascii=False, indent=2))
        archive.writestr(BASE + '使用说明.txt', GUIDE)
    print(OUT, OUT.stat().st_size)


if __name__ == '__main__':
    build()
