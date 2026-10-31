"""Allowlisted complete English2 release, no local accounts or state."""
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED

ROOT = Path(__file__).resolve().parents[1]
PACK = ROOT / 'materials/英语2/assets_en2_20261105_new_action_v2'
OUTPUT = ROOT / 'releases/english2_publisher_complete_11_new_covers_titles_1080p.zip'
FILES = ['desktop.py', 'publisher_profiles.py', 'material_library.py', 'run.py', 'prepare.py',
         'networking.py', 'requirements.txt', 'english2_latest_start.py',
         'start_english2_latest_windows.bat', 'ENGLISH2_LATEST_GUIDE.md']


def build():
    base = Path('youtube_publisher_english2')
    with ZipFile(OUTPUT, 'w', ZIP_DEFLATED) as archive:
        archive.write(ROOT / 'ENGLISH2_LATEST_GUIDE.md', '先读我-安装使用.md')
        for name in FILES:
            archive.write(ROOT / name, base / name)
        for path in sorted(PACK.rglob('*')):
            if path.is_file():
                archive.write(path, base / path.relative_to(ROOT))
    print(OUTPUT.name, OUTPUT.stat().st_size, 'bytes')


if __name__ == '__main__':
    build()
