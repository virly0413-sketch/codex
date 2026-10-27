"""Package30 new photographic English covers for existing-publisher material switching."""
from pathlib import Path
from zipfile import ZipFile,ZIP_DEFLATED
ROOT=Path(__file__).resolve().parents[1]
PACK=ROOT/'materials/英语/assets_en_20261101_fusion_v4'
OUTPUT=ROOT/'releases/english_fusion_covers_30_20261101_20261115_1080p.zip'
GUIDE='''英语1新版30张封面：写实亚洲人物、得体曲线穿搭、剧情动作与电影特效

频道：Supreme Hero Flicks / UC0koaDPTujsoVj-Tw27J0Qg。英语2不变。
对应2026年11月1—15日每天北京时间17:00、21:00原排片，共30部；原有首尾表情英文标题、剧集代码和排期保持不变。
女主为漂亮亚洲成年人，通过合身剪裁、腰线与自然动作体现曲线；胸前完整覆盖，下装为长裤或适度长裙，避免低领、透布料和过短下装。老人角色仍保留年长形象，人物保持写实影视质感。

看图：打开assets_en_20261101_fusion_v4中的covers文件夹，共30张1920×1080 JPEG。index.html可在浏览器预览全部封面。

原程序导入：
1. 将ZIP完整解压到新文件夹，保留全部文件。
2. 双击原目录start_english_windows.bat启动程序，核对为英语1频道Supreme Hero Flicks。
3. 点击“设置所选频道素材文件夹”，选择解压后的assets_en_20261101_fusion_v4文件夹。
4. 点击“切换频道并加载素材”，加载30张新封面与原英文标题、排期。无需重装程序或重新授权。
5. 按原流程匹配已上传的私密视频、核对后点击发布。加载素材不会自动修改YouTube。

包内带有新图片匹配的校验文件，请完整加载，不要单独把JPEG覆盖到旧素材包里。
保留旧包、token和全部local_work操作记录；西语、英语2及其他频道素材设置不变。
封面是AI生成的影视概念图，不是剧中演员截图；部分源图经缩放导出至1920×1080。
'''
def build():
 with ZipFile(OUTPUT,'w',ZIP_DEFLATED) as z:
  z.writestr('使用说明.txt',GUIDE)
  for p in sorted(PACK.rglob('*')):
   if p.is_file():z.write(p,Path(PACK.name)/p.relative_to(PACK))
 print(OUTPUT.name,OUTPUT.stat().st_size,'bytes')
if __name__=='__main__':build()
