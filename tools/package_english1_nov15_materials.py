"""Package the 22 English1 material entries for the revised Nov 15-25 schedule."""
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

ROOT = Path(__file__).resolve().parents[1]
PACK = ROOT / 'materials/英语/assets_en_20261115_20261125_story_v1'
OUTPUT = ROOT / 'releases/english1_materials_22_20261115_20261125_story_1080p.zip'


def build():
    with ZipFile(OUTPUT, 'w', ZIP_DEFLATED) as archive:
        archive.writestr('先读我.txt', (PACK / '使用说明.txt').read_text())
        for source in sorted(PACK.rglob('*')):
            if source.is_file():
                archive.write(source, Path(PACK.name) / source.relative_to(PACK))
    print(OUTPUT.name, OUTPUT.stat().st_size, 'bytes')


if __name__ == '__main__':
    build()
