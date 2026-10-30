"""Package the bright urban daylight fourth-version Filipino Nov5–15 material replacement folder only."""
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED

ROOT = Path(__file__).resolve().parents[1]
PACK = ROOT / 'materials/菲律宾语/assets_tl_20261105_city_daylight_v4'
OUTPUT = ROOT / 'releases/filipino_materials_v4_city_daylight_22_20261105_20261115_1080p.zip'


def build():
    with ZipFile(OUTPUT, 'w', ZIP_DEFLATED) as archive:
        archive.writestr('先读我.txt', (PACK / '使用说明.txt').read_text())
        for source in sorted(PACK.rglob('*')):
            if source.is_file():
                archive.write(source, Path(PACK.name) / source.relative_to(PACK))
    print(OUTPUT.name, OUTPUT.stat().st_size, 'bytes')


if __name__ == '__main__':
    build()
