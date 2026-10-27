"""Package photographic-cast/action-VFX fusion covers for the existing publisher."""
from pathlib import Path
from zipfile import ZipFile,ZIP_DEFLATED
ROOT=Path(__file__).resolve().parents[1]
PACK=ROOT/'materials/西语/assets_es_20261106_fusion_v5'
OUTPUT=ROOT/'releases/spanish_fusion_covers_20_20261106_20261115_1080p.zip'
GUIDE='''西语20张融合版封面：第二版写实人物 + 第一版特效与动作构图

对应2026年11月6—15日20部西语排片，每天北京时间00:00、05:00。沿用当前标题、剧集代码与排期。
以第二版亚洲成年人物面容、身材和得体穿搭为基础，融合第一版更鲜明的剧情动作、构图及电影特效，人物保持写实摄影质感。

只取封面：打开assets_es_20261106_fusion_v5里的covers文件夹，共20张1920×1080 JPEG。浏览器打开index.html可预览。

原发布程序切换素材：
1. 完整解压ZIP到新文件夹，保留里面全部文件。
2. 双击原目录start_spanish_windows.bat启动程序，选择西语。
3. 点击“设置所选频道素材文件夹”，选择解压后的assets_es_20261106_fusion_v5文件夹。
4. 点击“切换频道并加载素材”，加载20张融合版封面及原标题、排期。无需重装程序或重新授权。
5. 按原流程匹配已上传的私密视频、核对后点击发布。加载不会自动修改YouTube。

本包附匹配的新图片校验文件，应完整加载，不要只把图片覆盖到旧素材包里。
旧包、账号令牌和local_work操作记录全部保留；其他语种素材不变。
封面是AI生成的影视概念图，不是剧中演员截图；部分源图经缩放导出至1920×1080。
'''
def build():
 with ZipFile(OUTPUT,'w',ZIP_DEFLATED) as z:
  z.writestr('使用说明.txt',GUIDE)
  for p in sorted(PACK.rglob('*')):
   if p.is_file():z.write(p,Path(PACK.name)/p.relative_to(PACK))
 print(OUTPUT.name,OUTPUT.stat().st_size,'bytes')
if __name__=='__main__':build()
