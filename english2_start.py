"""Load the English2 channel and its own materials locally before opening the existing UI."""
import tkinter as tk
from tkinter import messagebox
import run
from desktop import App
from material_library import load_materials,set_material_folder,material_key
from publisher_profiles import initial_profile,remember_profile

CHANNEL='UCXdinQ6fQ8RyenilKIymAFA'
RELEASE_ID='english2_current14_20261022'
RELEASE_STATE='local_work_publisher_ui/english2_release.json'


def prepare_english2():
    config=run.load(run.ROOT/'profiles/english2.json')
    if config.get('language')!='en' or config.get('channel_id')!=CHANNEL or material_key(config)!='en2':
        raise ValueError('英语2配置与指定频道或独立素材目录不一致，请重新解压完整更新包。')
    previous=initial_profile()
    if previous.is_file():
        old=run.load(previous)
        if old.get('channel_id')==CHANNEL and old.get('language')=='en':
            for key in ('oauth_client','oauth_token','proxy_url','http_timeout_seconds'):
                if key in old:config[key]=old[key]
    marker=run.ROOT/RELEASE_STATE
    state=run.load(marker) if marker.is_file() else {}
    if state.get('release')!=RELEASE_ID:
        pack=run.ROOT/config['assets_path'];manifest=run.load(pack/'manifest.json')
        if manifest.get('channel_id')!=CHANNEL or manifest.get('language')!='en':
            raise ValueError('英语2素材属于其他频道。')
        set_material_folder('en2',pack.parent)
    path=load_materials(config)
    remember_profile(path);run.save(marker,{'release':RELEASE_ID})
    return path


def start():
    window=tk.Tk();window.withdraw()
    try:path=prepare_english2()
    except Exception as exc:
        messagebox.showerror('英语2加载失败',str(exc),parent=window);window.destroy();return
    window.deiconify();App(window,path);window.mainloop()


if __name__=='__main__':start()
