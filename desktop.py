"""Local desktop controls. Generation is performed in ChatGPT; this app imports assets."""
import argparse
import contextlib
import io
import threading
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from pathlib import Path

import run


class App:
    def __init__(self, root):
        self.root = root
        self.config = run.load(run.ROOT / 'config.json')
        self.jobs = {}
        self.busy = False
        root.title('Supreme Hero Flicks · 素材审核与定时上传（无需生成 API）')
        root.geometry('1160x900')
        bar = ttk.Frame(root); bar.pack(fill='x', padx=10, pady=8)
        self.buttons = []
        for label, callback in [('导入内置素材', self.import_assets), ('YouTube 官方授权', self.authorize),
                                ('刷新列表', self.refresh)]:
            button = ttk.Button(bar, text=label, command=callback)
            button.pack(side='left', padx=5); self.buttons.append(button)
        ttk.Label(root, text='素材由当前对话生成；此程序不调用 OpenAI，不会自动批准。所有时间为北京时间。').pack(anchor='w', padx=15)
        self.tree = ttk.Treeview(root, columns=('date', 'title', 'code'), show='headings', height=9)
        for key, label, width in [('date', '原排期（北京）', 190), ('title', '剧名', 460), ('code', '候选剧集代码', 320)]:
            self.tree.heading(key, text=label); self.tree.column(key, width=width)
        self.tree.pack(fill='x', padx=10, pady=8)
        self.tree.bind('<<TreeviewSelect>>', self.select)
        form = ttk.Frame(root); form.pack(fill='x', padx=10)
        self.video, self.description, self.publish = tk.StringVar(), tk.StringVar(), tk.StringVar()
        self.title = tk.StringVar(); self.code = tk.StringVar()
        for row, (label, variable) in enumerate([('完整视频', self.video), ('现有说明 UTF-8 文本文件', self.description)]):
            ttk.Label(form, text=label).grid(row=row, column=0, sticky='w', pady=4)
            ttk.Entry(form, textvariable=variable, width=95).grid(row=row, column=1, sticky='ew')
            ttk.Button(form, text='选择', command=lambda v=variable: self.browse(v)).grid(row=row, column=2)
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
                                ('② 我已审核，批准此版本', self.approve), ('③ 上传并定时公开', self.upload)]:
            button = ttk.Button(controls, text=label, command=callback)
            button.pack(side='left', padx=5); self.buttons.append(button)
        self.log = tk.Text(root, height=14, wrap='word')
        self.log.pack(fill='both', expand=True, padx=10, pady=8)
        self.refresh()
        root.protocol('WM_DELETE_WINDOW', self.close)

    def close(self):
        if self.busy:
            messagebox.showwarning('操作正在运行', '请等待当前操作结束，避免中断上传。')
            return
        self.root.destroy()

    def browse(self, variable):
        path = filedialog.askopenfilename()
        if path: variable.set(path)

    def selected(self):
        ids = self.tree.selection()
        if not ids: raise ValueError('请先选择一部剧')
        return ids[0]

    def task(self, fn, after=None):
        if self.busy: return
        self.busy = True
        for button in self.buttons: button.configure(state='disabled')
        self.log.insert('end', '\n处理中，请等待；不要重复点击或关闭上传窗口。\n')
        def work():
            output = io.StringIO()
            try:
                with contextlib.redirect_stdout(output): fn()
                error = None
            except Exception as exc:
                error = str(exc)[:500]
            def finish():
                self.busy = False
                for button in self.buttons: button.configure(state='normal')
                self.log.insert('end', output.getvalue() + ('\n错误：' + error if error else '\n完成。') + '\n')
                self.log.see('end')
                if error: messagebox.showerror('操作未完成', error)
                elif after: after()
            self.root.after(0, finish)
        threading.Thread(target=work, daemon=True).start()

    def import_assets(self):
        def operation():
            run.plan(self.config)
            run.import_pack(self.config, argparse.Namespace(pack=str(run.ROOT / 'assets')))
        self.task(operation, self.refresh)

    def authorize(self):
        self.task(lambda: run.auth(self.config))

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
            self.video.set(''); self.description.set('')
            from PIL import Image, ImageTk
            with Image.open(directory / 'cover_1.jpg') as im:
                im.thumbnail((480, 220)); self.photo = ImageTk.PhotoImage(im)
            self.preview.configure(image=self.photo)
        except Exception as exc: messagebox.showerror('读取失败', str(exc))

    def make_review(self):
        try:
            iid = self.selected()
            creative = run.load(run.ROOT / self.config['work'] / iid / 'creative.json')
            args = argparse.Namespace(job=iid, video=self.video.get(), description=self.description.get(),
                title=creative['titles'].index(self.title.get())+1, cover=1, code=self.code.get(),
                publish_local=self.publish.get())
        except Exception as exc: messagebox.showerror('请检查输入', str(exc)); return
        self.task(lambda: run.review(self.config, args))

    def approve(self):
        try:
            iid = self.selected()
            package = run.load(run.ROOT / self.config['work'] / iid / 'review.json')
        except Exception as exc: messagebox.showerror('请先生成审核单', str(exc)); return
        message = ('请先阅读日志中的完整审核单（含说明修改前后），核对视频、封面、标题、代码和时间。\n\n'
            + package['title'] + '\n' + package['publish_local'] + '\n代码：' + package['drama_code']
            + '\n\n确认该审核单正确，且已核实英语音轨、片源版本、授权与禁播状态？\n'
            + '此批准只针对已生成的审核单；界面新选择需重新生成审核单。')
        if not messagebox.askyesno('明确批准此版本', message): return
        args = argparse.Namespace(job=iid, fingerprint=run.fingerprint(package))
        self.task(lambda: run.approve(self.config, args))

    def upload(self):
        try:
            iid = self.selected()
            package = run.load(run.ROOT / self.config['work'] / iid / 'review.json')
        except Exception as exc: messagebox.showerror('请选择任务', str(exc)); return
        if not messagebox.askyesno('上传', '执行已批准审核单的上传与定时公开？\n'
            + package['title'] + '\n' + package['publish_local']
            + '\n未批准或文件变化会自动阻止。'): return
        def operation():
            with run.upload_lock(run.ROOT / self.config['work'] / iid):
                run.upload(self.config, argparse.Namespace(job=iid))
        self.task(operation)


if __name__ == '__main__':
    window = tk.Tk(); App(window); window.mainloop()
