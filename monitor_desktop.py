"""Desktop interface for the read-only YouTube restriction monitor."""
import contextlib
from pathlib import Path
import queue
import re
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
import webbrowser

import blocked_monitor as monitor
import run
from networking import proxy_url


class App:
    def __init__(self, root):
        self.root, self.events = root, queue.Queue()
        self.busy, self.folder = False, None
        self.config = run.load(run.ROOT / 'config.json')
        root.title('YouTube 禁播及可能影响收益视频 · 只读')
        root.geometry('1120x760')
        self.channel = tk.StringVar(value=self.config['channel_id'])
        self.name = tk.StringVar(value=self.config.get('channel_name', ''))
        self.proxy = tk.StringVar(value=self.config.get('proxy_url', ''))
        self.client = tk.StringVar(value=self.config.get('oauth_client', 'client_secret.json'))
        top = ttk.Frame(root, padding=12); top.pack(fill='x')
        self.buttons = []
        for row, (label, var) in enumerate([('频道ID（UC开头）', self.channel), ('频道名称', self.name),
                                           ('程序代理', self.proxy), ('OAuth客户端文件', self.client)]):
            ttk.Label(top, text=label).grid(row=row, column=0, sticky='w', pady=4)
            ttk.Entry(top, textvariable=var, width=72).grid(row=row, column=1, sticky='ew', padx=8)
        for label, callback, row in [('导入频道配置', self.load_config, 0), ('选择客户端文件', self.choose_client, 3)]:
            button = ttk.Button(top, text=label, command=callback); button.grid(row=row, column=2)
            self.buttons.append(button)
        top.columnconfigure(1, weight=1)
        ttk.Label(root, text='点击一次扫描一次，完成后生成视频名单及限制详情Excel。首次需浏览器只读授权；请选中目标品牌频道。').pack(anchor='w', padx=12)
        ttk.Label(root, text=monitor.LIMITATION, wraplength=1070).pack(anchor='w', padx=12, pady=6)
        controls = ttk.Frame(root, padding=12); controls.pack(fill='x')
        for label, callback in [('扫描一次并导出Excel', self.start), ('打开Excel', self.open_excel),
                                ('Excel另存为…', self.save_excel), ('切换授权账号/频道', self.reauth),
                                ('打开本地报告', self.open_report), ('打开报告目录', self.open_folder)]:
            button = ttk.Button(controls, text=label, command=callback); button.pack(side='left', padx=4)
            self.buttons.append(button)
        self.status = tk.StringVar(value='尚未检测')
        ttk.Label(root, textvariable=self.status).pack(anchor='w', padx=12)
        self.tree = ttk.Treeview(root, columns=('title', 'category', 'reason', 'url'), show='headings', height=13)
        for key, label, width in [('title','视频名称',290),('category','分类',110),('reason','限制详情',360),('url','视频链接',300)]:
            self.tree.heading(key,text=label);self.tree.column(key,width=width)
        self.tree.pack(fill='both',expand=True,padx=12,pady=8)
        self.tree.bind('<Double-1>', self.open_video)
        self.log = tk.Text(root,height=9,wrap='word');self.log.pack(fill='both',padx=12,pady=8)
        root.after(150,self.poll)
        root.protocol('WM_DELETE_WINDOW',self.close)

    def load_config(self):
        path=filedialog.askopenfilename(initialdir=run.ROOT/'profiles',filetypes=[('JSON','*.json')])
        if not path:return
        try:
            config=run.load(path)
            self.channel.set(config['channel_id']);self.name.set(config.get('channel_name',''))
            self.proxy.set(config.get('proxy_url',''));self.client.set(config.get('oauth_client','client_secret.json'))
            self.config=config
        except Exception as exc:messagebox.showerror('配置读取失败',str(exc))

    def choose_client(self):
        path=filedialog.askopenfilename(filetypes=[('JSON','*.json')])
        if path:self.client.set(path)

    def settings(self):
        channel=self.channel.get().strip()
        if not re.fullmatch(r'UC[A-Za-z0-9_-]{22}',channel):raise ValueError('请输入完整24字符的UC频道ID。')
        config=dict(self.config,channel_id=channel,channel_name=self.name.get().strip(),
            proxy_url=self.proxy.get().strip(),oauth_client=self.client.get().strip(),
            oauth_token='token.'+channel+'.json')
        proxy_url(config)
        if not (run.ROOT/config['oauth_client']).is_file():raise ValueError('请先选择Google桌面OAuth客户端JSON文件。')
        return config

    def start(self, reauthorize=False):
        if self.busy:return
        try:config=self.settings()
        except Exception as exc:
            messagebox.showerror('请检查设置',str(exc));return
        self.busy=True
        for b in self.buttons:b.configure(state='disabled')
        self.status.set('正在扫描，请等待…')
        events=self.events
        class Stream:
            def write(self,text):
                if text:events.put(('log',text))
                return len(text)
            def flush(self):pass
        def worker():
            try:
                with contextlib.redirect_stdout(Stream()):
                    api=monitor.monitor_auth(config,reauthorize=reauthorize)
                    result=monitor.scan(config,youtube=api)
                events.put(('result',result))
            except Exception as exc:events.put(('error',str(exc)))
            finally:events.put(('done',None))
        threading.Thread(target=worker,daemon=True).start()

    def reauth(self):self.start(reauthorize=True)

    def poll(self):
        try:
            while True:
                event,value=self.events.get_nowait()
                if event=='log':self.log.insert('end',value);self.log.see('end')
                elif event=='result':
                    report,self.folder=value
                    for iid in self.tree.get_children():self.tree.delete(iid)
                    for row in report['registered']:
                        self.tree.insert('', 'end',values=(row['视频名称'],row['分类'],row['限制详情'],row['视频链接']))
                    self.status.set(f"{report['channel_name']} | {report['checked_at']} | 扫描{report['upload_list_count']}条 | Excel登记{report['excel_video_count']}个 | 收益待核对不等于已确认受限")
                    self.log.insert('end','\nExcel已生成：'+str(self.folder/'blocked_videos.xlsx')+'\n点击“打开Excel”查看，或点击“Excel另存为…”保存到桌面。\n')
                    self.log.see('end')
                elif event=='error':
                    self.status.set('检测失败；当前列表/报告保留上次结果，不代表本次状态。')
                    self.log.insert('end','\n错误：'+value+'\n');self.log.see('end')
                elif event=='done':
                    self.busy=False
                    for b in self.buttons:b.configure(state='normal')
        except queue.Empty:pass
        self.root.after(150,self.poll)

    def open_excel(self):
        if not self.folder:
            messagebox.showinfo('尚无Excel','先点击“扫描一次并导出Excel”。');return
        path=self.folder/'blocked_videos.xlsx'
        try:
            import os,sys,subprocess
            if sys.platform=='win32':os.startfile(path)
            elif sys.platform=='darwin':subprocess.Popen(['open',str(path)])
            else:subprocess.Popen(['xdg-open',str(path)])
        except Exception as exc:messagebox.showerror('无法打开Excel',str(exc)+'\n文件位置：'+str(path))

    def save_excel(self):
        if not self.folder:
            messagebox.showinfo('尚无Excel','先点击“扫描一次并导出Excel”。');return
        path=filedialog.asksaveasfilename(defaultextension='.xlsx',initialfile='禁播及可能影响收益视频.xlsx',
            filetypes=[('Excel工作簿','*.xlsx')])
        if path:
            try:
                import shutil
                source=self.folder/'blocked_videos.xlsx'
                if source.resolve()!=Path(path).resolve():shutil.copyfile(source,path)
                self.log.insert('end','\nExcel已另存为：'+path+'\n');self.log.see('end')
            except Exception as exc:messagebox.showerror('保存失败',str(exc))

    def open_video(self,event=None):
        item=self.tree.selection()
        if item:webbrowser.open(self.tree.item(item[0],'values')[3])

    def open_report(self):
        if self.folder:webbrowser.open((self.folder/'report.html').as_uri())
        else:messagebox.showinfo('尚无报告','先完成一次检测。')

    def open_folder(self):
        if self.folder:
            import os,sys,subprocess
            if sys.platform=='win32':os.startfile(self.folder)
            elif sys.platform=='darwin':subprocess.Popen(['open',str(self.folder)])
            else:subprocess.Popen(['xdg-open',str(self.folder)])
        else:messagebox.showinfo('尚无报告','先完成一次检测。')

    def close(self):
        if self.busy:
            messagebox.showinfo('检测中','请等待本次只读扫描完成后关闭。');return
        self.root.destroy()


if __name__=='__main__':
    root=tk.Tk();App(root);root.mainloop()
