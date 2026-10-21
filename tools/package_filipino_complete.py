"""Reproducible Filipino publisher distribution, excluding local credentials and state."""
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED
import json

ROOT=Path(__file__).resolve().parents[1]
OUTPUT=ROOT/'releases/filipino_publisher_complete_20261026_20261115_1080p.zip'
FILES=['desktop.py','publisher_profiles.py','publisher_start.py','material_library.py',
       'filipino_setup.py','run.py','prepare.py','networking.py','requirements.txt',
       'start_windows.bat','start_filipino_windows.bat','FILIPINO_GUIDE.md',
       'data/jobs.tl.20261026.json']
PACK=ROOT/'materials/菲律宾语/assets_tl_20261026_ready'
GUIDE='''菲律宾语完整程序（含最新版封面和标题）

1. 完整解压，打开youtube_publisher_filipino文件夹。
2. 安装Python 3.10或更新版本。将你自己的Google OAuth桌面客户端文件client_secret.json放在此目录。
3. 双击start_filipino_windows.bat。首次安装依赖、输入菲律宾语UC频道ID，之后无需重复填写。点击YouTube官方授权并选择该频道。
4. 内置21部排片（2026年10月26日—11月15日，每天北京时间17:00）、63个菲律宾语标题、21张1920×1080最新版无字封面。
5. 扫描已上传视频，选对应视频、标题和封面，点击发布一次，更新标题/封面、在原说明末行追加剧集代码并定时公开。不需要再次上传视频，也不用额外审核。

已有原程序的升级合并方法、语种切换和固定素材文件夹用法见FILIPINO_GUIDE.md。
素材预览：materials/菲律宾语/assets_tl_20261026_ready/index.html
标题Excel：materials/菲律宾语/assets_tl_20261026_ready/titles.xlsx

本包未绑定任何英、俄、韩、西语频道。菲律宾语频道在本机首次设置，OAuth会核对真实频道ID。本包没有账号、token或密钥，也不需要OpenAI API。
'''


def build():
    base=Path('youtube_publisher_filipino')
    # An intentionally unbound local default invokes the one-time setup, never a guessed UC ID.
    config={'channel_id':'','channel_name':'菲律宾语男频','language':'tl',
            'planning_source':'data/jobs.tl.20261026.json',
            'assets_path':str(PACK.relative_to(ROOT)),'work':'local_work_tl_unconfigured',
            'proxy_url':'http://127.0.0.1:7897','http_timeout_seconds':30}
    with ZipFile(OUTPUT,'w',ZIP_DEFLATED) as z:
        z.writestr('先读我-安装使用.txt',GUIDE)
        z.writestr(str(base/'config.json'),json.dumps(config,ensure_ascii=False,indent=2)+'\n')
        for name in FILES:z.write(ROOT/name,base/name)
        for path in sorted(PACK.rglob('*')):
            if path.is_file():z.write(path,base/path.relative_to(ROOT))
    print(OUTPUT.name,OUTPUT.stat().st_size,'bytes')


if __name__=='__main__':build()
