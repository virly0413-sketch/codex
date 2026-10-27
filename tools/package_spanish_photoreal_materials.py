"""Package new photographic covers for direct viewing and existing-publisher import."""
from pathlib import Path
from zipfile import ZipFile,ZIP_DEFLATED
ROOT=Path(__file__).resolve().parents[1]
PACK=ROOT/'materials/西语/assets_es_20261106_photoreal_v4'
OUTPUT=ROOT/'releases/spanish_photoreal_covers_20_20261106_20261115_1080p.zip'
GUIDE='''西语20张写实新版封面（2026年10月27日）

对应2026年11月6—15日原西语排片，每天北京时间00:00、05:00。标题、剧集代码、日期和时间沿用当前版本。
封面1920×1080，人物为亚洲成年人；女性年轻漂亮，衣着修身且完整覆盖，采用写实影视摄影质感。动物和奇幻题材使用写实生物与影视特效表现。

只取图片：打开assets_es_20261106_photoreal_v4里面的covers文件夹，共20张JPEG。index.html可在浏览器预览。

原发布程序换素材：
1. 完整解压ZIP到新文件夹，保留里面全部文件。
2. 先双击原目录start_spanish_windows.bat启动程序，在频道列表选择西语，点击“设置所选频道素材文件夹”，选择解压后的assets_es_20261106_photoreal_v4文件夹。
3. 点击“切换频道并加载素材”，加载20张新封面及原有标题、排期。
4. 核对后按原流程匹配已上传的私密视频并点击发布。安装和加载不修改YouTube。

本包不含程序更新或账号凭据，不需要重装程序、重新授权。不要将JPEG单独覆盖进旧素材包：新包已经带有匹配的图片校验文件，应完整加载。
旧素材和local_work记录保留；本包不改英语、英语2、韩语、俄语或菲律宾语素材设置。
封面为AI生成的影视概念图，不是剧中演员截图；部分源图经缩放导出至1920×1080。
'''
def build():
 with ZipFile(OUTPUT,'w',ZIP_DEFLATED) as z:
  z.writestr('使用说明.txt',GUIDE)
  for p in sorted(PACK.rglob('*')):
   if p.is_file():z.write(p,Path(PACK.name)/p.relative_to(PACK))
 print(OUTPUT.name,OUTPUT.stat().st_size,'bytes')
if __name__=='__main__':build()
