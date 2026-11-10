"""Build the Nov 16-20 Spanish titles and generated cover material pack."""
import hashlib
import json
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED

from PIL import Image
from openpyxl import Workbook

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'schedules/spanish_20261116_20261120_two_daily/schedule.json'
PACK = ROOT / 'materials/西语/assets_es_20261116_20261120_latest10_v1'
RELEASE = ROOT / 'releases/spanish_materials_20261116_20261120_titles_covers_v1.zip'
CREATIVES = [
    ('exec-9243de51-ed24-4d4d-a31e-580cf4d30718.png',
     '🐒 Salvó a un mono y recibió tres pelos divinos; al quemar uno, todo el pueblo tembló 🔥',
     '救下小猴得到三根神毫；烧掉第一根，全村震惊。',
     '果园救猴、金毫召唤猴群、反派退缩'),
    ('exec-c3b8adba-521c-441f-80d8-787911c68359.png',
     '🌊 Su familia lo echó; la bañera de su casa escondía un palacio submarino lleno de oro 💰',
     '家人把他赶走，家中浴缸竟藏着满是黄金的海底龙宫。',
     '都市浴缸通海底、妻子陪同、势利亲戚震惊'),
    ('exec-9306d686-e856-406b-8f7d-46c43745c320.png',
     '☄️ Su esposa lo lanzó al abismo; renació como un meteorito capaz de devorar planetas 🤯',
     '妻子将他推下悬崖，他竟重生为能吞噬星球的陨石。',
     '悬崖背叛、陨石坠落、男主宇宙力量苏醒'),
    ('exec-9dc6a9ec-b216-4526-b604-fe6f295b8a1c.png',
     '💍 Ella aceptó casarse solo de nombre; él salvó a su abuelo y reveló el complot ⚡',
     '她只愿名义结婚，他却救下爷爷并揭穿家族阴谋。',
     '豪门婚约、道术医治、家族反派败露'),
    ('exec-cad2257a-0680-4226-a15e-2c145696dbb9.png',
     '👁️ El maestro ciego enseñó a un mono; siglos después, hasta los dioses le temieron 🐒',
     '盲眼老师教出神猴，数百年后连天神也畏惧。',
     '盲眼男主、神猴弟子、仙界大军'),
    ('exec-1d15e52e-7048-4109-8cfc-a914d4694680.png',
     '🔫 Recién casados, una bala se curvó ante él: su esposa descubrió al tirador más temido 😱',
     '新婚当日子弹竟在他面前拐弯，妻子发现他是最可怕的枪神。',
     '都市婚礼、银币挡弹、男主护妻'),
    ('exec-88e91fd4-47e6-4edd-a682-dacb1754df73.png',
     '🫏 Reencarnó en un burro; el día de la ejecución volvió para salvar a su familia 🔥',
     '重生为驴的战神在行刑当天归来救全家。',
     '古代刑场、神驴与男主双重形象、家人获救'),
    ('exec-0c129585-3ebd-4c46-809b-bd299de6e00c.png',
     '⚔️ Salió de prisión y detuvo la boda de su prometida; nadie sabía quién era 🤯',
     '他出狱闯入未婚妻婚礼，满场权贵不知他的真实身份。',
     '豪门婚宴、男主闯入、未婚妻与反派对峙'),
    ('exec-70fcc973-5767-4005-8c61-c6b0d0e62146.png',
     '📺 En la aldea de los 80, elegir mal una bombilla podía matarlo; él vio la regla oculta 👻',
     '八零村落选错灯泡就会丧命，他看穿了隐藏规则。',
     '八零乡村、电视灯泡谜题、男女主识破怪谈'),
    ('exec-d736f08e-158b-4a6c-a784-f7036b27bee3.png',
     '👑 Solo quería irse lejos; una sequía obligó al príncipe a salvar a todo un reino 🔥',
     '他只想去封地，却被一场大旱逼成救国王爷。',
     '大明宫廷、男主谋划赈灾、皇帝与朝臣震惊'),
]


def build():
    jobs = json.loads(SOURCE.read_text(encoding='utf-8'))
    if len(jobs) != len(CREATIVES) or len({job['job_id'] for job in jobs}) != 10:
        raise ValueError('排片不是本批10部。')
    covers = PACK / 'covers'
    covers.mkdir(parents=True, exist_ok=True)
    entries, hashes, rows = [], {}, []
    for job, (png, title, gloss, note) in zip(jobs, CREATIVES):
        if not title.strip() or len(title.encode('utf-16-le')) // 2 > 100:
            raise ValueError('西语标题超过100字符：' + job['title_zh'])
        source = Path('/workspace/generated_images') / png
        if not source.is_file():
            raise FileNotFoundError(source)
        code = job['candidates'][0]['drama_code']
        relative = f"covers/{job['date']}_{'0000' if job['slot'] == 1 else '0500'}_{job['title_zh']}.jpg"
        output = PACK / relative
        with Image.open(source) as image:
            if image.width * 9 != image.height * 16:
                # The image generator delivers a nearly exact 16:9 frame; only a
                # subpixel edge is cropped to honor the YouTube thumbnail size.
                from PIL import ImageOps
                image = ImageOps.fit(image.convert('RGB'), (1920, 1080), Image.Resampling.LANCZOS)
            else:
                image = image.convert('RGB').resize((1920, 1080), Image.Resampling.LANCZOS)
            image.save(output, format='JPEG', quality=90, optimize=True, subsampling=0)
        if output.stat().st_size >= 2 * 1024 * 1024:
            raise ValueError('封面超过YouTube 2MB限制：' + relative)
        hashes[relative] = hashlib.sha256(output.read_bytes()).hexdigest()
        entries.append({
            'job_id': job['job_id'], 'title_zh': job['title_zh'], 'date': job['date'],
            'language': 'es', 'drama_code': code, 'titles': [title],
            'title_zh_gloss': gloss, 'recommended_title': 1, 'covers': [relative],
            'publish_local': job['publish_local'], 'thumbnail_text_mode': 'none',
            'thumbnail_resolution': [1920, 1080], 'creative_note': note,
        })
        rows.append([job['date'], '00:00' if job['slot'] == 1 else '05:00',
                     job['title_zh'], code, title, gloss, relative, note])
    manifest = {
        'version': 2, 'language': 'es', 'channel': '西语男频',
        'channel_id': 'UCaQI24vmsim_8jDI0NuwbEg', 'titles_per_job': 1,
        'preserve_thumbnail_resolution': True, 'thumbnail_resolution': [1920, 1080],
        'scope': '2026年11月16—20日，每天北京时间00:00、05:00，共10部。',
        'cover_style': '全新写实真人电影感；年轻亚洲男女主，剧情冲突与特效；无封面文字。',
        'title_revision': '2026-11-10按最新排片制作，一剧一个西语标题，首尾表情与多样化钩子。',
        'jobs': entries, 'sha256': hashes,
    }
    (PACK / 'manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding='utf-8')
    (PACK / 'schedule.json').write_text(json.dumps(jobs, ensure_ascii=False, indent=2), encoding='utf-8')
    book = Workbook()
    sheet = book.active
    sheet.title = '西语封面标题对应表'
    sheet.append(['日期', '北京时间', '中文剧名', '剧集代码', '西语标题', '标题中文意思', '封面文件', '封面画面'])
    for row in rows:
        sheet.append(row)
    sheet.freeze_panes = 'A2'
    for column in sheet.columns:
        sheet.column_dimensions[column[0].column_letter].width = min(90, max(14, max(len(str(cell.value or '')) for cell in column) + 2))
    book.save(PACK / '西语标题与封面对应表.xlsx')
    (PACK / 'README.md').write_text(
        '西语频道11月16—20日完整素材包：10张全新1920×1080 JPEG封面，10条西语标题，排片schedule.json。'
        '解压后在六频道程序选择“西语”，设置所选频道素材文件夹为本文件夹，再点击“切换频道并加载素材”。'
        '更换素材只在本地生效，不自动修改YouTube；旧包仍可保留并切回。\n', encoding='utf-8')
    RELEASE.parent.mkdir(parents=True, exist_ok=True)
    with ZipFile(RELEASE, 'w', ZIP_DEFLATED, compresslevel=6) as archive:
        for path in sorted(PACK.rglob('*')):
            if path.is_file():
                archive.write(path, PACK.name + '/' + str(path.relative_to(PACK)).replace('\\', '/'))
    print(RELEASE, RELEASE.stat().st_size)


if __name__ == '__main__':
    build()
