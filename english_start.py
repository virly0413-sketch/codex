"""Open the complete English release; all preparation is local and offline."""
import tkinter as tk
from tkinter import messagebox
import run
from desktop import App
from material_library import load_materials, set_material_folder
from publisher_profiles import initial_profile, remember_profile

CHANNEL='UC0koaDPTujsoVj-Tw27J0Qg'
RELEASE_STATE='local_work_publisher_ui/english_release.json'
RELEASE_ID='english_action_v3_20261101_20261115'


def prepare_english():
    config=run.load(run.ROOT/'profiles/english.json')
    if config.get('language')!='en' or config.get('channel_id')!=CHANNEL:
        raise ValueError('英语配置与本素材绑定频道不一致，请重新解压完整更新包。')
    previous=initial_profile()
    if previous.is_file():
        old=run.load(previous)
        if old.get('language')=='en' and old.get('channel_id')==CHANNEL:
            for key in ('oauth_client','oauth_token','proxy_url','http_timeout_seconds'):
                if key in old:config[key]=old[key]
    pack=run.ROOT/config['assets_path']
    marker=run.ROOT/RELEASE_STATE
    state=run.load(marker) if marker.is_file() else {}
    # Activate this shipped release once, avoiding a stale legacy folder on first upgrade.
    # Later starts respect any custom English folder chosen by the user.
    if state.get('release')!=RELEASE_ID:
        manifest=run.load(pack/'manifest.json')
        if manifest.get('language')!='en' or manifest.get('channel_id')!=CHANNEL:
            raise ValueError('英语素材与频道不一致。')
        set_material_folder('en',pack)
    path=load_materials(config)
    remember_profile(path)
    run.save(marker,{'release':RELEASE_ID})
    return path


def start():
    window=tk.Tk();window.withdraw()
    try:path=prepare_english()
    except Exception as exc:
        messagebox.showerror('英语素材加载失败',str(exc),parent=window)
        window.destroy();return
    window.deiconify();App(window,path);window.mainloop()


if __name__=='__main__':start()
