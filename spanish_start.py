"""Open the complete Spanish release; all preparation is local and offline."""
import tkinter as tk
from tkinter import messagebox
import run
from desktop import App
from material_library import load_materials, set_material_folder
from publisher_profiles import initial_profile, remember_profile

CHANNEL='UCaQI24vmsim_8jDI0NuwbEg'
RELEASE_STATE='local_work_publisher_ui/spanish_release.json'
RELEASE_ID='spanish_fusion_emoji_v6_20261028'


def prepare_spanish():
    config=run.load(run.ROOT/'profiles/spanish.json')
    if config.get('language')!='es' or config.get('channel_id')!=CHANNEL:
        raise ValueError('西语配置与本素材绑定频道不一致，请重新解压完整更新包。')
    previous=initial_profile()
    if previous.is_file():
        old=run.load(previous)
        if old.get('language')=='es' and old.get('channel_id')==CHANNEL:
            for key in ('oauth_client','oauth_token','proxy_url','http_timeout_seconds'):
                if key in old:config[key]=old[key]
    pack=run.ROOT/config['assets_path']
    marker=run.ROOT/RELEASE_STATE
    state=run.load(marker) if marker.is_file() else {}
    # Activate this shipped release once, avoiding a stale legacy folder on first upgrade.
    # Later starts respect any custom Spanish folder chosen by the user.
    # Point at this exact pack on first upgrade so old sibling packs can remain untouched.
    if state.get('release')!=RELEASE_ID:
        manifest=run.load(pack/'manifest.json')
        if manifest.get('language')!='es' or manifest.get('channel_id')!=CHANNEL:
            raise ValueError('西语素材与频道不一致。')
        set_material_folder('es',pack)
    path=load_materials(config)
    remember_profile(path)
    run.save(marker,{'release':RELEASE_ID})
    return path


def start():
    window=tk.Tk();window.withdraw()
    try:path=prepare_spanish()
    except Exception as exc:
        messagebox.showerror('西语素材加载失败',str(exc),parent=window)
        window.destroy();return
    window.deiconify();App(window,path);window.mainloop()


if __name__=='__main__':start()
