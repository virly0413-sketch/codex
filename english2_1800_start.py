"""Open the English2 fourteen-drama November2 18:00 release without overwriting local accounts."""
import tkinter as tk
from tkinter import messagebox
import run
from desktop import App
from material_library import load_materials, set_material_folder
from publisher_profiles import initial_profile, remember_profile

CHANNEL = 'UCXdinQ6fQ8RyenilKIymAFA'
PACK = 'materials/英语2/assets_en2_20261102_1800_modern14'
STATE = 'local_work_publisher_ui/english2_1800_release.json'
RELEASE = 'english2_modern14_nov2_1800_20261031'
PROFILE = 'profiles/english2.json'


def prepare_latest():
    if 1 not in getattr(run, 'SUPPORTED_TITLE_COUNTS', ()):
        raise ValueError('检测到旧版run.py，请完整覆盖本更新包的程序文件后再启动；本批每剧只有一个标题。')
    config = dict(channel_id=CHANNEL, channel_name='英语2', language='en', material_key='en2',
                  oauth_client='client_secret.json', oauth_token='token.en2.' + CHANNEL + '.json',
                  proxy_url='http://127.0.0.1:7897', http_timeout_seconds=120,
                  work='local_work_en2/' + CHANNEL, thumbnail_text_mode='none')
    profile = run.ROOT / PROFILE
    # The saved profile and last active batch can retain local settings only for this exact channel.
    for path in (profile, initial_profile()):
        if not path.is_file():
            continue
        old = run.load(path)
        if old.get('channel_id') == CHANNEL and old.get('language') == 'en' and old.get('material_key') == 'en2':
            for key in ('oauth_client', 'oauth_token', 'proxy_url', 'http_timeout_seconds'):
                if key in old:
                    config[key] = old[key]
    config.update(assets_path=PACK, planning_source=PACK + '/schedule.json')
    marker = run.ROOT / STATE
    state = run.load(marker) if marker.is_file() else {}
    if state.get('release') != RELEASE:
        manifest = run.load(run.ROOT / PACK / 'manifest.json')
        if manifest.get('channel_id') != CHANNEL or manifest.get('language') != 'en' or manifest.get('material_key') != 'en2':
            raise ValueError('英语2素材绑定不匹配，停止加载。')
        set_material_folder('en2', run.ROOT / PACK)
    path = load_materials(config)
    run.save(profile, run.load(path))
    remember_profile(path)
    run.save(marker, {'release': RELEASE})
    return path


def start():
    window = tk.Tk()
    window.withdraw()
    try:
        path = prepare_latest()
    except Exception as exc:
        messagebox.showerror('英语2新版加载失败', str(exc), parent=window)
        window.destroy()
        return
    window.deiconify()
    App(window, path)
    window.mainloop()


if __name__ == '__main__':
    start()
