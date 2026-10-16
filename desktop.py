"""Local desktop controls. Generation is performed in ChatGPT; this app imports assets."""
import argparse
import contextlib
import io
import threading
import tkinter as tk
from tkinter import ttk, messagebox
from pathlib import Path

import run
from networking import proxy_url, timeout_seconds


class App:
    def __init__(self, root):
        self.root = root
        self.config = run.load(run.ROOT / 'config.json')
        self.jobs = {}
        self.busy = False
        root.title('Supreme Hero Flicks · 已上传视频匹配、审核与定时发布（无需生成 API）')
        root.geometry('1160x900')
        bar = ttk.Frame(root); bar.pack(fill='x', padx=10, pady=8)
        self.buttons = []
        for label, callback in [('导入内置素材', self.import_assets), ('YouTube 官方授权', self.authorize),
                                ('切换授权频道', self.switch_channel),
                                ('扫描频道已上传视频', self.scan_channel), ('刷新列表', self.refresh)]:
            button = ttk.Button(bar, text=label, command=callback)
            button.pack(side='left', padx=5); self.buttons.append(button)
        ttk.Label(root, text='素材由当前对话生成；此程序不调用 OpenAI，不会自动批准。所有时间为北京时间。').pack(anchor='w', padx=15)
        network = ttk.Frame(root); network.pack(fill='x', padx=10, pady=4)
        self.proxy = tk.StringVar(value=self.config.get('proxy_url', ''))
        self.timeout = tk.StringVar(value=str(self.config.get('http_timeout_seconds', 30)))
        ttk.Label(network, text='程序代理（可留空）').pack(side='left')
        ttk.Entry(network, textvariable=self.proxy, width=34).pack(side='left', padx=5)
        ttk.Label(network, text='超时秒数').pack(side='left')
        ttk.Entry(network, textvariable=self.timeout, width=5).pack(side='left', padx=5)
        for label, callback in [('保存网络设置', self.save_network), ('诊断连接', self.diagnose)]:
            button=ttk.Button(network,text=label,command=callback)
            button.pack(side='left',padx=4); self.buttons.append(button)
        self.tree = ttk.Treeview(root, columns=('date', 'title', 'code'), show='headings', height=9)
        for key, label, width in [('date', '原排期（北京）', 190), ('title', '剧名', 460), ('code', '候选剧集代码', 320)]:
            self.tree.heading(key, text=label); self.tree.column(key, width=width)
        self.tree.pack(fill='x', padx=10, pady=8)
        self.tree.bind('<<TreeviewSelect>>', self.select)
        form = ttk.Frame(root); form.pack(fill='x', padx=10)
        self.video, self.publish = tk.StringVar(), tk.StringVar()
        self.title = tk.StringVar(); self.code = tk.StringVar()
        ttk.Label(form, text='YouTube 已上传视频').grid(row=0, column=0, sticky='w')
        self.video_box = ttk.Combobox(form, textvariable=self.video, width=95)
        self.video_box.grid(row=0, column=1, sticky='ew', pady=4)
        ttk.Label(form, text='先扫描频道；按中文剧名匹配，多条/无匹配时选择，或直接输入视频ID').grid(row=1, column=1, sticky='w')
        ttk.Label(form, text='英语标题').grid(row=2, column=0, sticky='w')
        self.title_box = ttk.Combobox(form, textvariable=self.title, state='readonly', width=95)
        self.title_box.grid(row=2, column=1, sticky='ew', pady=4)
        ttk.Label(form, text='剧集版本代码').grid(row=3, column=0, sticky='w')
        self.code_box = ttk.Combobox(form, textvariable=self.code, state='readonly')
        self.code_box.grid(row=3, column=1, sticky='w', pady=4)
        ttk.Label(form, text='发布时间（北京）').grid(row=4, column=0, sticky='w')
        ttk.Entry(form, textvariable=self.publish, width=35).grid(row=4, column=1, sticky='w', pady=4)
        ttk.Label(form, text='格式 2026-10-17T17:00:00；过期排期需明确修改后重新审核').grid(row=5, column=1, sticky='w')
        form.columnconfigure(1, weight=1)
        self.preview = ttk.Label(root); self.preview.pack(pady=4)
        controls = ttk.Frame(root); controls.pack(fill='x', padx=10)
        for label, callback in [('① 生成修改前后审核单', self.make_review),
                                ('② 我已审核，批准此版本', self.approve), ('③ 应用到已上传视频并定时公开', self.apply)]:
            button = ttk.Button(controls, text=label, command=callback)
            button.pack(side='left', padx=5); self.buttons.append(button)
        self.log = tk.Text(root, height=14, wrap='word')
        self.log.pack(fill='both', expand=True, padx=10, pady=8)
        self.refresh()
        root.protocol('WM_DELETE_WINDOW', self.close)

    def close(self):
        if self.busy:
            messagebox.showwarning('操作正在运行', '请等待当前操作结束，避免中断修改。')
            return
        self.root.destroy()

    def scan_channel(self):
        self.task(lambda: run.scan(self.config), self.select_if_any)

    def select_if_any(self):
        if self.tree.selection(): self.select()

    def selected(self):
        ids = self.tree.selection()
        if not ids: raise ValueError('请先选择一部剧')
        return ids[0]

    def task(self, fn, after=None):
        if self.busy: return
        self.busy = True
        for button in self.buttons: button.configure(state='disabled')
        self.log.insert('end', '\n处理中，请等待；不要重复点击或关闭操作窗口。\n')
        def append(text):
            self.log.insert('end',text); self.log.see('end')
        app=self
        class ProgressStream:
            def write(self,text):
                if text: app.root.after(0,lambda value=text:append(value))
                return len(text)
            def flush(self): pass
        def work():
            try:
                with contextlib.redirect_stdout(ProgressStream()): fn()
                error = None
            except Exception as exc:
                error = str(exc)[:500]
            def finish():
                self.busy = False
                for button in self.buttons: button.configure(state='normal')
                self.log.insert('end', ('\n错误：' + error if error else '\n完成。') + '\n')
                self.log.see('end')
                if error: messagebox.showerror('操作未完成', error)
                elif after: after()
            self.root.after(0, finish)
        threading.Thread(target=work, daemon=True).start()

    def save_network(self):
        try:
            config=dict(self.config,proxy_url=self.proxy.get().strip(),http_timeout_seconds=int(self.timeout.get()))
            proxy_url(config);timeout_seconds(config)
            run.save(run.ROOT/'config.json',config);self.config=config
            self.log.insert('end','\n网络设置已保存。下一次授权/扫描使用新设置。\n')
            return True
        except Exception as exc:
            messagebox.showerror('网络设置错误',str(exc));return False

    def diagnose(self):
        if self.save_network(): self.task(lambda:run.diagnose(self.config))

    def import_assets(self):
        def operation():
            run.plan(self.config)
            run.import_pack(self.config, argparse.Namespace(pack=str(run.ROOT / 'assets')))
        self.task(operation, self.refresh)

    def authorize(self):
        self.task(lambda: run.auth(self.config))

    def switch_channel(self):
        if messagebox.askyesno('切换授权频道', '将重新打开 Google 授权页面，请选择管理 Supreme Hero Flicks 的账号和品牌频道。\n只在频道ID匹配成功后保存新授权，不修改任何视频。'):
            self.task(lambda: run.auth(self.config, reauthorize=True))

    def refresh(self):
        for iid in self.tree.get_children(): self.tree.delete(iid)
        queue = run.ROOT / self.config['work'] / 'queue.json'
        if not queue.exists(): return
        self.jobs = {j['job_id']: j for j in run.load(queue)}
        for iid, j in self.jobs.items():
            if not (run.ROOT / self.config['work'] / iid / 'creative.json').exists(): continue
            self.tree.insert('', 'end', iid=iid, values=(j['publish_local'], j['title_zh'],
                ' | '.join(c['drama_code'] for c in j['candidates'])))

    def select(self, event=None):
        try:
            iid = self.selected(); j = self.jobs[iid]
            directory = run.ROOT / self.config['work'] / iid
            creative = run.load(directory / 'creative.json')
            self.title_box['values'] = creative['titles']; self.title.set(creative['titles'][0])
            self.code_box['values'] = [c['drama_code'] for c in j['candidates']]
            self.code.set(creative.get('drama_code') or '')
            self.publish.set(j['publish_local'][:19] if j['publish_local'] else '')
            cache = run.ROOT / self.config['work'] / 'channel_videos.json'
            videos = run.load(cache) if cache.exists() else []
            private = [v for v in videos if v['status'].get('privacyStatus') == 'private']
            matches = run.match_videos(j['title_zh'], private)
            ordered = matches + [v for v in private if v not in matches]
            self.video_box['values'] = [v['id'] + ' | ' + v['snippet']['title'] for v in ordered]
            self.video.set(matches[0]['id'] + ' | ' + matches[0]['snippet']['title'] if len(matches) == 1 else '')
            from PIL import Image, ImageTk
            with Image.open(directory / 'cover_1.jpg') as im:
                im.thumbnail((480, 220)); self.photo = ImageTk.PhotoImage(im)
            self.preview.configure(image=self.photo)
        except Exception as exc: messagebox.showerror('读取失败', str(exc))

    def make_review(self):
        try:
            iid = self.selected()
            creative = run.load(run.ROOT / self.config['work'] / iid / 'creative.json')
            args = argparse.Namespace(job=iid, video_id=self.video.get().split(' | ', 1)[0].strip() or None,
                title=creative['titles'].index(self.title.get())+1, cover=1, code=self.code.get(),
                publish_local=self.publish.get())
        except Exception as exc: messagebox.showerror('请检查输入', str(exc)); return
        self.task(lambda: run.review(self.config, args))

    def approve(self):
        try:
            iid = self.selected()
            package = run.load(run.ROOT / self.config['work'] / iid / 'review.json')
        except Exception as exc: messagebox.showerror('请先生成审核单', str(exc)); return
        message = ('请先阅读日志中的完整审核单（含说明修改前后），核对视频链接、原标题、新标题、封面、现有说明末行代码和时间。\n\n'
            + package['title'] + '\n' + package['publish_local'] + '\n代码：' + package['drama_code']
            + '\n\n确认该审核单正确，且已核实英语音轨、片源版本、授权与禁播状态？\n'
            + '此批准只针对已生成的审核单；界面新选择需重新生成审核单。')
        if not messagebox.askyesno('明确批准此版本', message): return
        args = argparse.Namespace(job=iid, fingerprint=run.fingerprint(package))
        self.task(lambda: run.approve(self.config, args))

    def apply(self):
        try:
            iid = self.selected()
            package = run.load(run.ROOT / self.config['work'] / iid / 'review.json')
        except Exception as exc: messagebox.showerror('请选择任务', str(exc)); return
        if not messagebox.askyesno('应用已审核修改', '仅修改已上传视频，不重新上传。确认执行此审核单？\n' + package['video_url'] + '\n'
            + package['title'] + '\n' + package['publish_local']
            + '\n未批准、封面变化或线上内容变化会自动阻止。'): return
        def operation():
            with run.upload_lock(run.ROOT / self.config['work'] / iid):
                run.apply_changes(self.config, argparse.Namespace(job=iid))
        self.task(operation)


if __name__ == '__main__':
    window = tk.Tk(); App(window); window.mainloop()
