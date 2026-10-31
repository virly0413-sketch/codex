"""Build the credential-free Filipino 22-job complete publisher."""
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / 'releases/filipino_publisher_complete_22_fixed_single_title_1080p.zip'
PACK = ROOT / 'materials/菲律宾语/assets_tl_20261105_character_conflict_v5'
FILES = ['desktop.py', 'publisher_profiles.py', 'material_library.py',
         'filipino_setup.py', 'filipino_latest_start.py', 'run.py', 'prepare.py',
         'networking.py', 'requirements.txt', 'start_filipino_latest_windows.bat',
         'FILIPINO_LATEST_GUIDE.md']


def build():
    base = Path('youtube_publisher_filipino')
    with ZipFile(OUTPUT, 'w', ZIP_DEFLATED) as archive:
        archive.write(ROOT / 'FILIPINO_LATEST_GUIDE.md', '先读我-安装使用.md')
        for name in FILES:
            archive.write(ROOT / name, base / name)
        for path in sorted(PACK.rglob('*')):
            if path.is_file():
                archive.write(path, base / path.relative_to(ROOT))
    print(OUTPUT.name, OUTPUT.stat().st_size, 'bytes')
    patch = ROOT / 'releases/filipino_single_title_fix.zip'
    with ZipFile(patch, 'w', ZIP_DEFLATED) as archive:
        for name in FILES:
            archive.write(ROOT / name, name)
    print(patch.name, patch.stat().st_size, 'bytes')


if __name__ == '__main__':
    build()
