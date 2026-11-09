"""Package the 14 all-new English2 covers and titles for the existing 18:00 schedule."""
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

ROOT = Path(__file__).resolve().parents[1]
PACK = ROOT / 'materials/英语2/assets_en2_20261102_1800_bestseller_v2'
OUTPUT = ROOT / 'releases/english2_materials_bestseller_v2_14_20261102_20261115_1080p.zip'


def build():
    with ZipFile(OUTPUT, 'w', ZIP_DEFLATED) as archive:
        archive.writestr('先读我.txt', (PACK / '使用说明.txt').read_text())
        for source in sorted(PACK.rglob('*')):
            if source.is_file():
                archive.write(source, Path(PACK.name) / source.relative_to(PACK))
    print(OUTPUT.name, OUTPUT.stat().st_size, 'bytes')


if __name__ == '__main__':
    build()
