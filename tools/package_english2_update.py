"""Allowlisted English2 overlay; never includes credentials or other channel configs."""
from pathlib import Path
from zipfile import ZipFile,ZIP_DEFLATED
ROOT=Path(__file__).resolve().parents[1]
OUTPUT=ROOT/'releases/english2_channel_update_with_materials_1080p.zip'
FILES=['desktop.py','publisher_profiles.py','publisher_start.py','material_library.py',
       'filipino_setup.py','run.py','prepare.py','networking.py','requirements.txt',
       'english2_start.py','start_english2_windows.bat','profiles/english2.json',
       'data/jobs.en2.current.json','ENGLISH2_GUIDE.md']
def build():
    base=Path('youtube_publisher_update')
    with ZipFile(OUTPUT,'w',ZIP_DEFLATED) as z:
        z.writestr('先读我-升级步骤.txt',
            '关闭并备份原程序。将youtube_publisher_update里面的文件合并到原程序目录，同名程序文件选择替换。\n'
            '双击start_english2_windows.bat，首次授权选择英语2频道UCXdinQ6fQ8RyenilKIymAFA。\n'
            '含14张封面、14个标题。2026年10月24日—11月6日每天北京时间13:00。扫描匹配已上传的私密视频后点击发布。\n'
            '请阅读ENGLISH2_GUIDE.md。保留自己的密钥、令牌和其他频道文件。\n')
        for name in FILES:z.write(ROOT/name,base/name)
        for p in sorted((ROOT/'materials/英语2/assets_en2_current_14').rglob('*')):
            if p.is_file():z.write(p,base/p.relative_to(ROOT))
    print(OUTPUT.name,OUTPUT.stat().st_size)
if __name__=='__main__':build()
