"""Package Korean22 fresh-v3 covers and single titles for the confirmed two-daily schedule."""
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED

ROOT = Path(__file__).resolve().parents[1]
PACK = ROOT / 'materials/韩语/assets_ko_20261110_fresh_v3'
OUTPUT = ROOT / 'releases/korean_materials_fresh_v3_22_20261110_20261120_1080p.zip'


def build():
    with ZipFile(OUTPUT, 'w', ZIP_DEFLATED) as archive:
        archive.writestr('先读我.txt', (PACK / '使用说明.txt').read_text())
        for source in sorted(PACK.rglob('*')):
            if source.is_file():
                archive.write(source, Path(PACK.name) / source.relative_to(PACK))
    print(OUTPUT.name, OUTPUT.stat().st_size, 'bytes')


if __name__ == '__main__':
    build()
