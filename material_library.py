"""Per-language material folders and immutable, validated local batch imports."""
import argparse
import datetime as dt
import re
import shutil
import tempfile
from pathlib import Path
import run

SETTINGS='local_work_publisher_ui/material_folders.json'
LABELS={'en':'英语','en2':'英语2','ru':'俄语','ko':'韩语','es':'西语','tl':'菲律宾语'}


def material_key(config):
    """Separate same-language channels without changing existing language folder settings."""
    return config.get('material_key') or config['language']


def material_folder(config):
    settings=run.ROOT/SETTINGS
    folders=run.load(settings) if settings.exists() else {}
    key=material_key(config)
    if folders.get(key):return Path(folders[key])
    default=run.ROOT/'materials'/LABELS.get(key,key)
    return default if default.is_dir() else Path(run.ROOT/config['assets_path'])


def set_material_folder(language,path):
    path=Path(path).resolve()
    if not path.is_dir():raise ValueError('请选择已存在的素材文件夹')
    settings=run.ROOT/SETTINGS
    folders=run.load(settings) if settings.exists() else {}
    folders[language]=str(path)
    run.save(settings,folders)


def find_pack(folder):
    folder=Path(folder).resolve()
    if not folder.is_dir():raise ValueError('素材文件夹不存在，请重新设置该语种的素材文件夹')
    manifests=list(folder.rglob('manifest.json'))
    if len(manifests)!=1:
        raise ValueError('该语种文件夹内必须只有一个素材包；请移走旧包，解压新包（需要manifest.json），再加载。当前找到：'+str(len(manifests)))
    return manifests[0].parent


def _schedule(config,pack,manifest):
    if (pack/'schedule.json').is_file():
        jobs=run.load(pack/'schedule.json')
    else:
        # Backwards compatibility only for exact known bundled schedules, never infer dates/codes.
        legacy={'en':'data/jobs.json','ru':'data/jobs.ru.20261020.json','ko':'data/jobs.ko.20261026.json'}
        source=run.ROOT/legacy.get(config['language'],'missing')
        if not source.is_file():raise ValueError('素材包缺少schedule.json排片文件，请使用完整素材包')
        jobs=run.load(source)
    entries=manifest.get('jobs',[])
    if not isinstance(jobs,list) or not jobs or not isinstance(entries,list) or not entries:
        raise ValueError('素材包排片为空或格式错误')
    expected={j['job_id']:j for j in jobs}
    if len(expected)!=len(jobs) or len({j['job_id'] for j in entries})!=len(entries) or set(expected)!={j['job_id'] for j in entries}:
        raise ValueError('排片与素材任务不一致；新批次必须附带匹配的schedule.json')
    for entry in entries:
        job=expected[entry['job_id']]
        if not re.fullmatch(r'[A-Za-z0-9_-]{1,100}',job['job_id']):raise ValueError('素材任务ID无效')
        if job['title_zh']!=entry['title_zh'] or job['date']!=entry.get('date',job['date']):raise ValueError('剧名或日期与素材排片不一致')
        language=job.get('language',config['language'])
        if language!=config['language'] or entry.get('language',config['language'])!=config['language']:
            raise ValueError('排片语种与目标频道不一致')
        codes=[c['drama_code'] for c in job['candidates']]
        if entry.get('drama_code') and entry['drama_code'] not in codes:raise ValueError('剧集代码与排片不一致')
        if any(c.get('audio_language',config['language'])!=config['language'] for c in job['candidates']):raise ValueError('配音语种与目标频道不一致')
        if job.get('channel_id') and job['channel_id']!=config['channel_id']:raise ValueError('排片属于其他频道')
        if job.get('timezone','Asia/Shanghai')!='Asia/Shanghai':raise ValueError('排片时区必须是北京时间Asia/Shanghai')
        if job.get('schedule_mode')=='manual':
            if manifest.get('allow_manual_schedule') is not True or entry.get('schedule_mode')!='manual':
                raise ValueError('手动排期必须由完整素材包明确声明')
            if job.get('publish_local') is not None or job.get('publish_at') is not None:
                raise ValueError('手动排期不得夹带未确认的发布时间')
            if job.get('date') is not None:
                try:
                    if dt.date.fromisoformat(job['date']).isoformat()!=job['date']:raise ValueError()
                except (TypeError,ValueError):raise ValueError('排片日期格式错误')
            job.setdefault('blockers',[])
            continue
        local=dt.datetime.fromisoformat(job['publish_local'])
        utc=dt.datetime.fromisoformat(job['publish_at'].replace('Z','+00:00'))
        if local.utcoffset()!=dt.timedelta(hours=8) or local.date().isoformat()!=job['date'] or utc.utcoffset()!=dt.timedelta(0) or local!=utc:
            raise ValueError('排片日期或北京时间与UTC不一致')
        job.setdefault('blockers',[])
    return jobs


def load_materials(config):
    """Offline only. Invalid replacement cannot change the active config/batch."""
    language=config['language'];channel=config['channel_id']
    if not re.fullmatch(r'UC[A-Za-z0-9_-]{22}',channel):raise ValueError('目标频道ID无效')
    pack=find_pack(material_folder(config));manifest=run.load(pack/'manifest.json')
    if manifest.get('channel_id') and manifest['channel_id']!=channel:raise ValueError('素材包属于其他频道')
    # Legacy English manifest is accepted only after exact schedule validation below.
    if manifest.get('language')!=language and not (language=='en' and manifest.get('language') is None):
        raise ValueError('素材包语种与目标频道不一致')
    jobs=_schedule(config,pack,manifest)
    if manifest.get('language') is None and (pack/'schedule.json').exists():
        raise ValueError('新素材包必须声明language语种')
    relative_files=set()
    for entry in manifest['jobs']:
        for relative in entry['covers']:
            source=(pack/relative).resolve()
            if not source.is_relative_to(pack) or not source.is_file():raise ValueError('素材图片路径无效')
            if run.digest(source)!=manifest.get('sha256',{}).get(relative):raise ValueError('素材图片校验失败，请重新解压完整素材包')
            relative_files.add(relative)
    batch=run.fingerprint({'manifest':manifest,'schedule':jobs})
    parent=run.ROOT/'local_work_materials'/language/channel
    target=parent/batch
    parent.mkdir(parents=True,exist_ok=True)
    if not target.exists():
        with tempfile.TemporaryDirectory(prefix='import-',dir=parent) as temp:
            stage=Path(temp);assets=stage/'assets';assets.mkdir()
            run.save(assets/'manifest.json',manifest)
            run.save(stage/'schedule.json',jobs)
            for relative in relative_files:
                dest=assets/relative;dest.parent.mkdir(parents=True,exist_ok=True)
                shutil.copyfile(pack/relative,dest)
                if run.digest(dest)!=manifest['sha256'][relative]:raise ValueError('素材正在被替换，请等待复制完成后再加载')
            staged=dict(config,assets_path=str(assets),planning_source=str(stage/'schedule.json'),work=str(stage/'work'))
            staged.pop('start_date',None)
            run.plan(staged)
            run.import_pack(staged,argparse.Namespace(pack=str(assets)))
            prepared=dict(config,assets_path=str((target/'assets').relative_to(run.ROOT)),
                planning_source=str((target/'schedule.json').relative_to(run.ROOT)),
                work=str((target/'work').relative_to(run.ROOT)),material_batch=batch,
                material_source=str(pack),material_job_count=len(jobs))
            prepared.pop('start_date',None)
            run.save(stage/'config.json',prepared)
            stage.rename(target)
    # Retain current local OAuth/network preferences even when returning to an existing batch.
    prepared=run.load(target/'config.json')
    for key in ('oauth_client','oauth_token','proxy_url','http_timeout_seconds'):
        if key in config:prepared[key]=config[key]
    run.save(target/'config.json',prepared)
    print('已加载',LABELS.get(material_key(config),language),'素材：',len(jobs),'部；批次',batch[:12],'。未修改YouTube。')
    return target/'config.json'
