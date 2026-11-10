"""Launch the familiar publisher UI with six independently selected material folders."""
import tkinter as tk
from tkinter import messagebox

import run
from desktop import App
from filipino_setup import ensure_profile
from material_library import load_materials, set_material_folder
from publisher_profiles import initial_profile, remember_profile


PACKS = {
    'en': 'materials/英语/assets_en_20261115_20261125_story_v1',
    'en2': 'materials/英语2/assets_en2_20261116_1800_original14_v3',
    'es': 'materials/西语/assets_es_20261106_fusion_titles_v6',
    'ko': 'materials/韩语/assets_ko_20261110_fresh_v3',
    'ru': 'materials/俄语/assets_ru_20261107_two_daily28',
    'tl': 'materials/菲律宾语/assets_tl_20261105_character_conflict_v5',
}
MARKER = 'local_work_publisher_ui/six_channel_material_folders_v1.json'


def prepare():
    marker = run.ROOT / MARKER
    if not marker.is_file():
        # Run once: old folders stay on disk and can be selected later in the familiar UI.
        for key, relative in PACKS.items():
            folder = run.ROOT / relative
            if not (folder / 'manifest.json').is_file() or not (folder / 'schedule.json').is_file():
                raise ValueError('缺少完整素材文件夹：' + relative)
            set_material_folder(key, folder)
        run.save(marker, {'materials': PACKS})
    previous = initial_profile()
    path = previous if previous.is_file() else run.ROOT / 'config.json'
    config = run.load(path)
    active = load_materials(config)
    remember_profile(active)
    return active


def main():
    window = tk.Tk()
    window.withdraw()
    try:
        # The real Filipino channel ID is private to this installation; cancellation
        # still permits the other five channels to open.
        ensure_profile(window)
        path = prepare()
    except Exception as exc:
        messagebox.showerror('六频道素材加载失败', str(exc), parent=window)
        window.destroy()
        return
    window.deiconify()
    App(window, path)
    window.mainloop()


if __name__ == '__main__':
    main()
