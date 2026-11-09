"""Package English2's original 14-drama order shifted to Nov 16-29 at 18:00."""
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

ROOT = Path(__file__).resolve().parents[1]
PACK = ROOT / 'materials/英语2/assets_en2_20261116_1800_original14_v3'
OUTPUT = ROOT / 'releases/english2_original14_retimed_20261116_20261129_1800.zip'


def build():
    with ZipFile(OUTPUT, 'w', ZIP_DEFLATED) as archive:
        archive.writestr('先读我.txt', (PACK / '使用说明.txt').read_text())
        for source in sorted(PACK.rglob('*')):
            if source.is_file():
                archive.write(source, Path(PACK.name) / source.relative_to(PACK))
    print(OUTPUT.name, OUTPUT.stat().st_size, 'bytes')


if __name__ == '__main__':
    build()
