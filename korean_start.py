"""Bind the Korean asset batch to a user-specified channel before opening the existing publisher."""
import argparse
from pathlib import Path
import re
import tkinter as tk
from tkinter import messagebox, simpledialog

import run
from desktop import App

SETTINGS=run.ROOT/'local_work_korean_launcher/config.json'


def korean_config(channel_id):
    channel_id=channel_id.strip()
    if not re.fullmatch(r'UC[A-Za-z0-9_-]{22}',channel_id):
        raise ValueError('请填写完整24位的UC频道ID，不是@标识名。')
    config=run.load(run.ROOT/'profiles/korean.json')
    base=Path(config.get('work','local_work_ko_20261026'))
    if config.get('channel_id') and base.name==config['channel_id']:base=base.parent
    config.update(channel_id=channel_id,work=str(base/channel_id),
                  oauth_token='token.ko.'+channel_id+'.json')
    return config


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--channel-id')
    parser.add_argument('--change-channel',action='store_true')
    args=parser.parse_args()
    window=tk.Tk();window.withdraw()
    try:
        saved=run.load(SETTINGS) if SETTINGS.exists() else None
        if args.channel_id:
            config=korean_config(args.channel_id)
        elif saved and not args.change_channel:
            expected=korean_config(saved['channel_id'])
            # Always use this Korean batch, keeping locally saved network/client choices only.
            config=dict(expected,**{k:saved[k] for k in ('proxy_url','http_timeout_seconds','oauth_client') if k in saved})
        elif not saved and not args.change_channel and run.load(run.ROOT/'profiles/korean.json').get('channel_id'):
            config=korean_config(run.load(run.ROOT/'profiles/korean.json')['channel_id'])
        else:
            while True:
                channel_id=simpledialog.askstring('绑定韩语频道',
                    '韩语频道：무협역전숏드\n请输入该频道UC开头的完整频道ID。\n此步骤仅保存本机配置，不修改YouTube。',
                    initialvalue=saved.get('channel_id','') if saved else run.load(run.ROOT/'profiles/korean.json').get('channel_id',''),parent=window)
                if channel_id is None:window.destroy();return
                try:config=korean_config(channel_id);break
                except ValueError as exc:messagebox.showerror('频道ID格式错误',str(exc),parent=window)
        run.save(SETTINGS,config)
        window.deiconify();App(window,SETTINGS);window.mainloop()
    except Exception as exc:
        messagebox.showerror('韩语程序无法启动',str(exc),parent=window);window.destroy()

if __name__=='__main__':main()
