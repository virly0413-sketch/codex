"""Package the completed English2 Nov5-15 material folder without credentials."""
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED

ROOT = Path(__file__).resolve().parents[1]
PACK = ROOT / 'materials/英语2/assets_en2_20261105_costume_11'
OUTPUT = ROOT / 'releases/english2_materials_11_20261105_20261115_1080p.zip'


def build():
    with ZipFile(OUTPUT, 'w', ZIP_DEFLATED) as archive:
        archive.writestr('先读我.txt', (PACK / '使用说明.txt').read_text())
        for source in sorted(PACK.rglob('*')):
            if source.is_file():
                archive.write(source, Path(PACK.name) / source.relative_to(PACK))
    print(OUTPUT.name, OUTPUT.stat().st_size, 'bytes')


if __name__ == '__main__':
    build()
