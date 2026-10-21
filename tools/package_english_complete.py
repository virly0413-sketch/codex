"""Complete English publisher with the latest action covers; no local credentials/state."""
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED

ROOT=Path(__file__).resolve().parents[1]
OUTPUT=ROOT/'releases/english_publisher_complete_action_v2_20261026_20261115_1080p.zip'
PACK=ROOT/'materials/英语/assets_en_20261026_action_v2'
FILES=['desktop.py','publisher_profiles.py','publisher_start.py','material_library.py',
       'filipino_setup.py','english_start.py','run.py','prepare.py','networking.py',
       'requirements.txt','start_english_windows.bat','ENGLISH_LATEST_GUIDE.md',
       'profiles/english.json','data/jobs.en.20261026.json']
GUIDE='''英语完整程序：最新版42张动作互动封面 + 126个英文标题

频道：Supreme Hero Flicks / @bikan29-v8f / UC0koaDPTujsoVj-Tw27J0Qg
排期：2026年10月26日—11月15日，每天北京时间17:00、21:00各一部。

1. 安装Python 3.10或更新版本，完整解压ZIP到新目录。
2. 打开youtube_publisher_english文件夹，将自己的OAuth桌面客户端文件client_secret.json放入。
3. 双击start_english_windows.bat，首次自动联网安装依赖并加载42部标题封面。
4. 点击YouTube官方授权，选择上述英语频道。代理默认127.0.0.1:7897，可在程序里修改或清空。
5. 扫描已上传视频，核对剧名对应关系，选标题和封面，点击发布一次即可更新并定时公开。

不需要OpenAI API，不需要额外1080p补丁。视频不用重新上传，原说明保留，仅末行追加剧集代码。
若要合并升级原程序、切换其他语种或配置专属素材文件夹，请先读ENGLISH_LATEST_GUIDE.md。
预览和Excel位于materials/英语/assets_en_20261026_action_v2下。
首次启动本版本会将英语素材目录切至包内materials/英语；之后尊重你设置的英语专属目录。
不要覆盖或删除自己的密钥、token、其他频道配置或local_work操作记录。
'''


def build():
    base=Path('youtube_publisher_english')
    with ZipFile(OUTPUT,'w',ZIP_DEFLATED) as z:
        z.writestr('先读我-安装使用.txt',GUIDE)
        z.write(ROOT/'profiles/english.json',base/'config.json')
        z.write(ROOT/'start_english_windows.bat',base/'start_windows.bat')
        for name in FILES:z.write(ROOT/name,base/name)
        for p in sorted(PACK.rglob('*')):
            if p.is_file():z.write(p,base/p.relative_to(ROOT))
    print(OUTPUT.name,OUTPUT.stat().st_size,'bytes')


if __name__=='__main__':build()
