"""Start the original publisher with its last selected local channel preset."""
import argparse
import tkinter as tk
from desktop import App
from publisher_profiles import initial_profile, remember_profile
import run


def start(config_path=None, filipino=False):
    window=tk.Tk()
    path=config_path or initial_profile()
    config=run.load(path) if not filipino else {'language':'tl'}
    if filipino or config.get('language')=='tl':
        from filipino_setup import ensure_profile, valid_channel
        from material_library import load_materials
        from tkinter import messagebox
        window.withdraw()
        try:
            if filipino or not valid_channel(config.get('channel_id')):
                path=ensure_profile(window)
                if path is None:
                    window.destroy()
                    return
                target=run.load(path)
                previous=initial_profile()
                if previous.is_file():
                    saved=run.load(previous)
                    if saved.get('language')=='tl' and saved.get('channel_id')==target['channel_id']:
                        path=previous
            path=load_materials(run.load(path))
            remember_profile(path)
        except Exception as exc:
            messagebox.showerror('菲律宾语素材加载失败',str(exc),parent=window)
            window.destroy()
            return
        window.deiconify()
    App(window,path)
    window.mainloop()

if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--config')
    parser.add_argument('--filipino',action='store_true',help='打开菲律宾语素材，首次填写频道ID')
    args=parser.parse_args()
    start(args.config,args.filipino)
