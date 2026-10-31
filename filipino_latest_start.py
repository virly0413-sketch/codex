"""Activate the bundled Filipino22 release once; retain local channel and credentials."""
import tkinter as tk
from tkinter import messagebox
import run
from desktop import App
from filipino_setup import ensure_profile, valid_channel
from material_library import load_materials, set_material_folder
from publisher_profiles import initial_profile, remember_profile

PACK = 'materials/菲律宾语/assets_tl_20261105_character_conflict_v5'
STATE = 'local_work_publisher_ui/filipino_latest_release.json'
RELEASE = 'filipino22_conflict_v5_20261105_20261115'


def prepare_latest(parent=None):
    profile = ensure_profile(parent)
    if profile is None:
        return None
    config = run.load(profile)
    if config.get('language') != 'tl' or not valid_channel(config.get('channel_id')):
        raise ValueError('菲律宾语频道配置无效。')
    previous = initial_profile()
    if previous.is_file():
        saved = run.load(previous)
        if saved.get('language') == 'tl' and saved.get('channel_id') == config['channel_id']:
            for key in ('oauth_client', 'oauth_token', 'proxy_url', 'http_timeout_seconds'):
                if key in saved:
                    config[key] = saved[key]
    config['assets_path'] = PACK
    config['planning_source'] = PACK + '/schedule.json'
    config.setdefault('http_timeout_seconds', 120)
    marker = run.ROOT / STATE
    state = run.load(marker) if marker.is_file() else {}
    if state.get('release') != RELEASE or state.get('channel_id') != config['channel_id']:
        set_material_folder('tl', run.ROOT / PACK)
    active = load_materials(config)
    # Keep the channel switcher pointed at the validated current batch.
    run.save(profile, run.load(active))
    remember_profile(active)
    run.save(marker, {'release': RELEASE, 'channel_id': config['channel_id']})
    return active


def start():
    window = tk.Tk()
    window.withdraw()
    try:
        path = prepare_latest(window)
        if path is None:
            window.destroy()
            return
    except Exception as exc:
        messagebox.showerror('菲律宾语新版加载失败', str(exc), parent=window)
        window.destroy()
        return
    window.deiconify()
    App(window, path)
    window.mainloop()


if __name__ == '__main__':
    start()
