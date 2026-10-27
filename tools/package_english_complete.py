"""Build current complete English publisher; safe to merge into an existing install."""
from pathlib import Path
from zipfile import ZipFile,ZIP_DEFLATED
ROOT=Path(__file__).resolve().parents[1]
OUTPUT=ROOT/'releases/english_publisher_complete_20261101_20261115_1080p.zip'
PACK=ROOT/'materials/英语/assets_en_20261101_action_v3'
FILES=['desktop.py','publisher_profiles.py','publisher_start.py','material_library.py','filipino_setup.py',
       'english_start.py','run.py','prepare.py','networking.py','requirements.txt','start_english_windows.bat',
       'ENGLISH_LATEST_GUIDE.md','profiles/english.json','data/jobs.en.20261101.json']
GUIDE='''英语1新版整合程序：30张全新封面、30个首尾表情英文标题

频道Supreme Hero Flicks / @bikan29-v8f / UC0koaDPTujsoVj-Tw27J0Qg。
2026年11月1—15日，每天北京时间17:00、21:00，共30部。英语2不变。

原程序升级：关闭并备份原程序，将youtube_publisher_english里面的文件合并到原程序目录，同名程序文件替换。保留自己的密钥、令牌、其他频道文件和全部local_work记录，不要删除旧目录。
双击start_english_windows.bat，首次启用此版自动加载新英语素材，之后尊重你设置的素材路径。
全新安装：安装Python3.10或更新版，完整解压，将自己的client_secret.json放入youtube_publisher_english，再双击start_english_windows.bat。

扫描匹配已上传的私密视频后，核对当前频道与视频，点击发布一次更新标题封面、保留原说明末行追加代码并定时公开。不重新上传视频文件。
已整合封面超时恢复、右侧滚动条、频道切换和单标题支持，不需要另外下载补丁。无需OpenAI API，封面已经放入包内。
代理默认http://127.0.0.1:7897，超时120秒；旧网络设置会保留，需要时手动修改并保存。
10月31日及之前素材留在旧批次，本包只处理11月1日起；若已在Studio定时，加载新包不会自动修改线上内容。
详细安装、预览和换素材步骤见ENGLISH_LATEST_GUIDE.md。
'''
def build():
 base=Path('youtube_publisher_english')
 with ZipFile(OUTPUT,'w',ZIP_DEFLATED) as z:
  z.writestr('先读我-安装使用.txt',GUIDE)
  for name in FILES:z.write(ROOT/name,base/name)
  for p in sorted(PACK.rglob('*')):
   if p.is_file():z.write(p,base/p.relative_to(ROOT))
 print(OUTPUT.name,OUTPUT.stat().st_size,'bytes')
if __name__=='__main__':build()
