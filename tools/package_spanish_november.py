"""Build a complete Spanish publisher that can also merge into an existing install."""
from pathlib import Path
from zipfile import ZipFile,ZIP_DEFLATED
ROOT=Path(__file__).resolve().parents[1]
OUTPUT=ROOT/'releases/spanish_publisher_complete_20261106_20261115_1080p.zip'
PACK=ROOT/'materials/西语/assets_es_20261106_two_daily'
FILES=['desktop.py','publisher_profiles.py','publisher_start.py','material_library.py','filipino_setup.py',
       'spanish_start.py','run.py','prepare.py','networking.py','requirements.txt','start_spanish_windows.bat',
       'SPANISH_NOVEMBER_GUIDE.md','profiles/spanish.json','data/jobs.es.20261106.json']
GUIDE='''西语最新整合程序：20张封面、20个新版西语标题（2026年10月27日修订）

频道UCaQI24vmsim_8jDI0NuwbEg。
2026年11月6—15日，每天北京时间00:00、05:00，共20部。

原程序升级：关闭并备份原程序，将youtube_publisher_spanish里面的文件合并到原程序目录，同名程序文件替换。保留自己的密钥、令牌、素材和local_work记录，不要删除旧目录。
双击start_spanish_windows.bat，第一次启用本版自动加载新西语素材，之后尊重你的自选素材目录。
全新安装：安装Python3.10或更新版，解压，在youtube_publisher_spanish内放入自己的client_secret.json，再双击start_spanish_windows.bat。

程序更新已上传到YouTube的私密视频，不重新上传视频文件。
核对目标频道，扫描并匹配视频，再点击发布；更新标题封面、保留原说明仅在末行加代码并定时公开。
已含右侧滚动条、频道切换、素材文件夹切换、单标题兼容及封面超时恢复补丁，无需另外下载旧补丁。
默认代理http://127.0.0.1:7897，超时120秒；旧网络设置会保留，需要时手动改为120并保存。
如旧西语11月6—15日已在Studio定时，请先核对调整，加载新包不会撤销旧的线上排期。
详细步骤见SPANISH_NOVEMBER_GUIDE.md。
'''
def build():
 base=Path('youtube_publisher_spanish')
 with ZipFile(OUTPUT,'w',ZIP_DEFLATED) as z:
  z.writestr('先读我-安装升级.txt',GUIDE)
  for name in FILES:z.write(ROOT/name,base/name)
  for p in sorted(PACK.rglob('*')):
   if p.is_file():z.write(p,base/p.relative_to(ROOT))
 print(OUTPUT.name,OUTPUT.stat().st_size,'bytes')
if __name__=='__main__':build()
