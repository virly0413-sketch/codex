"""Local preset switching for the existing publisher; never authorizes remote writes."""
from pathlib import Path
import re
import run

PRESETS=(('英语','english.json','en'),('俄语','russian.json','ru'),('韩语','korean.json','ko'),('西语','spanish.json','es'),('菲律宾语','filipino.json','tl'))
STATE='local_work_publisher_ui/last_profile.json'


def available_profiles(current_path=None, known=None):
    choices=dict(known or {})
    current=run.load(current_path) if current_path else {}
    for label,name,language in PRESETS:
        path=run.ROOT/'profiles'/name
        if not path.is_file():continue
        config=run.load(path)
        key=label+' | '+config['channel_name']
        same_batch=all(current.get(k)==config.get(k) for k in ('language','planning_source','assets_path'))
        if current.get('channel_id')==config.get('channel_id') and current_path and same_batch:
            choices[key]=str(Path(current_path).resolve())
        elif key not in choices:choices[key]=str(path.resolve())
    return choices


def validate_profile(path):
    config=run.load(path)
    if not re.fullmatch(r'UC[A-Za-z0-9_-]{22}',config.get('channel_id','')):
        raise ValueError('目标频道ID无效，请先配置正确的UC频道ID')
    if not config.get('language'):raise ValueError('频道配置缺少语种，不能安全切换素材')
    source=run.ROOT/config['planning_source'];pack=run.ROOT/config['assets_path']
    if not source.is_file() or not (pack/'manifest.json').is_file():raise ValueError('缺少该频道的排片或内置素材，请完整解压新版程序')
    manifest=run.load(pack/'manifest.json')
    if manifest.get('language')!=config['language']:
        # The original English manifest predates its language field. Accept only that exact known queue.
        legacy=config['language']=='en' and manifest.get('language') is None and config['planning_source']=='data/jobs.json'
        expected={j['job_id']:j['title_zh'] for j in run.load(source)}
        actual={j['job_id']:j['title_zh'] for j in manifest.get('jobs',[])}
        if not legacy or not actual or actual!=expected:raise ValueError('内置素材语种与目标频道不一致')
    if manifest.get('channel_id') and manifest['channel_id']!=config['channel_id']:raise ValueError('内置素材属于其他频道')
    return config


def remember_profile(path):
    path=Path(path).resolve()
    if not path.is_relative_to(run.ROOT):return
    run.save(run.ROOT/STATE,{'config':str(path.relative_to(run.ROOT))})


def initial_profile():
    state=run.ROOT/STATE
    if state.is_file():
        try:
            path=(run.ROOT/run.load(state)['config']).resolve()
            if path.is_relative_to(run.ROOT) and path.is_file():return path
        except (ValueError,KeyError,TypeError):pass
    return run.ROOT/'config.json'
