"""Windows browser-assisted, on-demand multi-language Baidu downloads."""
import datetime as dt
import json
import os
from pathlib import Path
import queue
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from zoneinfo import ZoneInfo

from baidu_browser import BaiduBrowser, private_error
from baidu_client import ClientDownloads, client_executable, launch_client
from baidu_download import LANGUAGES, atomic_json, build_tasks, ready_status, share_link, schedule_rows, sha256_file
from baidu_runner import run_downloads

ROOT=Path(__file__).resolve().parent
WORK=ROOT/'local_work_baidu'


class App:
    def __init__(self,root):
        self.root=root;self.events=queue.Queue();self.busy=False;self.tasks=[]
        self.stop=threading.Event();self.resume=threading.Event()
        settings_path=WORK/'settings.json'
        self.saved=json.loads(settings_path.read_text(encoding='utf-8')) if settings_path.exists() else {}
        root.title('百度网盘 · 按排片下载多个语种');root.geometry('1210x950')
        self.schedule=tk.StringVar(value=self.saved.get('schedule',''))
        self.resources=tk.StringVar(value=self.saved.get('resources',''))
        self.start=tk.StringVar(value=self.saved.get('start',dt.datetime.now(ZoneInfo('Asia/Shanghai')).date().isoformat()))
        self.days=tk.StringVar(value=str(self.saved.get('days',7)))
        self.infer_blank=tk.BooleanVar(value=False)
        self.row_info=[];self.row_languages={};self.loaded_schedule=None
        self.channel=tk.StringVar(value=self.saved.get('browser','msedge'))
        self.mode=tk.StringVar(value=self.saved.get('mode','客户端'))
        self.inbox=tk.StringVar(value=self.saved.get('inbox','D:\\短剧下载中转'))
        self.client_path=tk.StringVar(value=self.saved.get('client_exe',client_executable()))
        self.client_wait=tk.StringVar(value=str(self.saved.get('client_wait_minutes',120)))
        self.folders={x:tk.StringVar(value=self.saved.get('folders',{}).get(x,'D:\\'+x)) for x in LANGUAGES}
        self.buttons=[]
        form=ttk.Frame(root,padding=10);form.pack(fill='x')
        for i,(label,var) in enumerate([('排片表CSV',self.schedule),('剧集资源表CSV',self.resources)]):
            ttk.Label(form,text=label).grid(row=i,column=0,sticky='w',pady=3)
            ttk.Entry(form,textvariable=var,width=98).grid(row=i,column=1,columnspan=3,sticky='ew',padx=6)
            self.button(form,'选择文件',lambda v=var:self.pick_csv(v)).grid(row=i,column=4)
        ttk.Label(form,text='开始日期').grid(row=2,column=0,sticky='w')
        ttk.Entry(form,textvariable=self.start,width=18).grid(row=2,column=1,sticky='w',padx=6)
        ttk.Label(form,text='下载天数（含开始当天）').grid(row=2,column=2,sticky='e')
        ttk.Spinbox(form,textvariable=self.days,from_=1,to=366,width=8).grid(row=2,column=3,sticky='w')
        ttk.Combobox(form,textvariable=self.channel,values=['msedge','chrome','chromium'],state='readonly',width=14).grid(row=2,column=4,padx=6)
        form.columnconfigure(1,weight=1)
        rows=ttk.LabelFrame(root,text='选择原表具体行（Ctrl可多选）；语种跟随所选行',padding=5);rows.pack(fill='x',padx=10)
        self.row_picker=tk.Listbox(rows,selectmode='extended',exportselection=False,height=3)
        self.row_picker.pack(side='left',fill='x',expand=True)
        self.row_picker.bind('<<ListboxSelect>>',self.row_selected)
        controls=ttk.Frame(rows);controls.pack(side='left',padx=8)
        self.button(controls,'读取/刷新排片行',self.load_rows).pack()
        self.row_language=tk.StringVar()
        language_box=ttk.Combobox(controls,textvariable=self.row_language,values=list(LANGUAGES),state='readonly',width=12)
        language_box.pack();language_box.bind('<<ComboboxSelected>>',self.set_row_language)
        ttk.Checkbutton(rows,text='允许空白日期逐日顺延\n默认不推算',variable=self.infer_blank).pack(side='left',padx=5)

        client=ttk.LabelFrame(root,text='下载方式：默认交给本机百度网盘客户端',padding=6);client.pack(fill='x',padx=10,pady=4)
        ttk.Combobox(client,textvariable=self.mode,values=['客户端','浏览器'],state='readonly',width=12).grid(row=0,column=0,padx=5)
        ttk.Label(client,text='客户端中转目录').grid(row=0,column=1)
        ttk.Entry(client,textvariable=self.inbox,width=48).grid(row=0,column=2,sticky='ew',padx=5)
        self.button(client,'选择中转目录',self.pick_inbox).grid(row=0,column=3)
        ttk.Label(client,text='单文件最长等待/分钟').grid(row=0,column=4,padx=4)
        ttk.Entry(client,textvariable=self.client_wait,width=6).grid(row=0,column=5)
        ttk.Label(client,text='客户端EXE').grid(row=1,column=0,sticky='w')
        ttk.Entry(client,textvariable=self.client_path,width=68).grid(row=1,column=1,columnspan=2,sticky='ew',padx=5,pady=4)
        self.button(client,'选择EXE',self.pick_client).grid(row=1,column=3)
        self.button(client,'打开百度客户端',self.open_client).grid(row=1,column=4,columnspan=2)
        ttk.Label(client,text='首次请在百度客户端设置里，将默认下载位置设为上面的中转目录；完成后程序分类到各语种目录。').grid(row=2,column=0,columnspan=6,sticky='w')
        client.columnconfigure(2,weight=1)
        languages=ttk.LabelFrame(root,text='各语种保存目录（实际语种由上面所选排片行确定）',padding=8);languages.pack(fill='x',padx=10)
        for i,name in enumerate(LANGUAGES):
            ttk.Label(languages,text=name).grid(row=i,column=0,sticky='w')
            ttk.Entry(languages,textvariable=self.folders[name],width=100).grid(row=i,column=1,sticky='ew',padx=6)
            self.button(languages,'选择目录',lambda n=name:self.pick_folder(n)).grid(row=i,column=2)
        languages.columnconfigure(1,weight=1)
        bar=ttk.Frame(root,padding=10);bar.pack(fill='x')
        for label,callback in [('读取排片生成任务',self.import_tasks),('登录百度网盘',self.login),
                ('仅扫描匹配文件',lambda:self.start_work(True)),('开始下载',self.start_work),
                ('打开下载记录Excel',self.open_report)]:
            self.button(bar,label,callback).pack(side='left',padx=4)
        ttk.Button(bar,text='停止后续/停止等待',command=self.request_stop).pack(side='left',padx=4)
        self.continue_button=ttk.Button(bar,text='已处理，继续',command=self.resume.set,state='disabled')
        self.continue_button.pack(side='left',padx=4)
        ttk.Label(root,text='按文件名末尾的语种或明确的语种文件夹筛选；只下载视频。所有文件直接放入对应语种目录，文件名加剧名防覆盖。',wraplength=1170).pack(anchor='w',padx=12)
        ttk.Label(root,text='网页用于定位文件并唤起官方客户端；首次登录/系统打开应用提示需处理。程序等待完成文件后分类，不把已发起任务当下载成功。',wraplength=1170).pack(anchor='w',padx=12)
        self.tree=ttk.Treeview(root,columns=('date','source','language','title','code','status'),show='headings',height=8)
        for key,label,width in [('date','排片日期',115),('source','原表位置',110),('language','语种',80),('title','剧名',460),('code','代码',150),('status','状态',290)]:
            self.tree.heading(key,text=label);self.tree.column(key,width=width)
        self.tree.pack(fill='both',expand=True,padx=10,pady=8);self.tree.bind('<<TreeviewSelect>>',self.select_task)
        edit=ttk.Frame(root,padding=10);edit.pack(fill='x')
        self.code=tk.StringVar();self.link=tk.StringVar();self.password=tk.StringVar()
        ttk.Label(edit,text='选中任务的版本代码').grid(row=0,column=0,sticky='w')
        self.code_box=ttk.Combobox(edit,textvariable=self.code,state='readonly',width=24);self.code_box.grid(row=0,column=1,sticky='w',padx=5)
        ttk.Label(edit,text='提取码').grid(row=0,column=2);ttk.Entry(edit,textvariable=self.password,width=8,show='*').grid(row=0,column=3)
        ttk.Label(edit,text='百度分享链接').grid(row=1,column=0,sticky='w')
        ttk.Entry(edit,textvariable=self.link,width=100).grid(row=1,column=1,columnspan=3,sticky='ew',padx=5,pady=4)
        self.button(edit,'保存选中任务的版本/链接',self.edit_task).grid(row=1,column=4,padx=5)
        self.code_box.bind('<<ComboboxSelected>>',self.select_code)
        edit.columnconfigure(1,weight=1)
        self.status=tk.StringVar(value='尚未读取排片；本程序不定时运行，也不修改YouTube。')
        ttk.Label(root,textvariable=self.status,wraplength=1170).pack(anchor='w',padx=12)
        self.log=tk.Text(root,height=6,wrap='word');self.log.pack(fill='both',padx=10,pady=8)
        root.after(150,self.poll);root.protocol('WM_DELETE_WINDOW',self.close)

    def button(self,parent,text,callback):
        b=ttk.Button(parent,text=text,command=callback);self.buttons.append(b);return b

    def pick_csv(self,var):
        path=filedialog.askopenfilename(filetypes=[('CSV','*.csv')])
        if path:
            var.set(path)
            if var is self.schedule:self.load_rows()

    def pick_folder(self,name):
        path=filedialog.askdirectory()
        if path:self.folders[name].set(path)

    def pick_inbox(self):
        path=filedialog.askdirectory()
        if path:self.inbox.set(path)

    def pick_client(self):
        path=filedialog.askopenfilename(filetypes=[('百度网盘客户端','*.exe')])
        if path:self.client_path.set(path)

    def open_client(self):
        try:
            launch_client(self.client_path.get().strip())
            self.status.set('请在百度客户端登录，并将默认下载位置设为：'+self.inbox.get())
        except Exception as exc:messagebox.showerror('打开客户端失败',private_error(exc))

    def load_rows(self):
        try:
            info=schedule_rows(self.schedule.get().strip())
            self.row_info=info;self.row_languages={r['row']:r['language'] for r in info}
            self.row_picker.delete(0,'end')
            for r in info:self.row_picker.insert('end',f"第{r['row']}行 | {r['label']} | {r['language'] or '请设置语种'}")
            self.loaded_schedule=(str(Path(self.schedule.get().strip()).resolve()),sha256_file(self.schedule.get().strip()))
            self.tasks=[];self.refresh()
            self.status.set('请选中需要的原表行，填写开始日期和天数，再生成任务。')
        except Exception as exc:messagebox.showerror('无法读取行',private_error(exc))

    def row_selected(self,event=None):
        selected=self.row_picker.curselection()
        if selected:
            self.row_language.set(self.row_languages.get(self.row_info[selected[0]]['row']) or '')

    def set_row_language(self,event=None):
        selected=self.row_picker.curselection()
        if len(selected)!=1:
            messagebox.showinfo('请选择一行','修改行语种时请仅选中一行；已明确标注语种的行不能改为其他语种。');return
        r=self.row_info[selected[0]]
        if r['language'] and r['language']!=self.row_language.get():
            self.row_language.set(r['language']);messagebox.showerror('语种不一致','该行已标注为'+r['language']);return
        self.row_languages[r['row']]=self.row_language.get()

    def signature(self,s):
        return (str(Path(s['schedule']).resolve()),sha256_file(s['schedule']),
                str(Path(s['resources']).resolve()),sha256_file(s['resources']),s['start'],s['days'],
                s['infer_blank'],tuple((r['row'],r['language']) for r in s['rows']))

    def settings(self):
        current=(str(Path(self.schedule.get().strip()).resolve()),sha256_file(self.schedule.get().strip()))
        if self.loaded_schedule!=current:raise ValueError('请重新读取排片行；文件已更换或内容已更新。')
        selections=[dict(row=self.row_info[i]['row'],language=self.row_languages.get(self.row_info[i]['row']))
                    for i in self.row_picker.curselection()]
        if not selections or any(not r['language'] for r in selections):raise ValueError('请明确选择排片行，并为未知行设置语种。')
        languages=list(dict.fromkeys(r['language'] for r in selections))
        if not self.start.get().strip():raise ValueError('请填写开始日期，例如2026-10-20。')
        dt.date.fromisoformat(self.start.get().strip())
        days=int(self.days.get())
        if not 1<=days<=366:raise ValueError('天数须为1—366。')
        folders={n:self.folders[n].get().strip() for n in languages}
        if any(not p for p in folders.values()):raise ValueError('每个所选语种都需要保存目录。')
        if os.name=='nt' and any(not Path(p).is_absolute() for p in folders.values()):
            raise ValueError('请使用完整目录，例如D:\\俄语。')
        if len({os.path.normcase(str(Path(p).resolve())) for p in folders.values()})!=len(folders):
            raise ValueError('不同语种请选择不同目录，以免混放。')
        minutes=int(self.client_wait.get())
        if minutes<1:raise ValueError('最长等待分钟数至少为1。')
        if self.mode.get()=='客户端':
            inbox=Path(self.inbox.get().strip()).resolve()
            if not self.inbox.get().strip():raise ValueError('请设置客户端下载中转目录。')
            for p in folders.values():
                folder=Path(p).resolve()
                if inbox==folder or inbox in folder.parents or folder in inbox.parents:
                    raise ValueError('中转目录与语种保存目录必须独立，不能相同或相互包含。')
        settings=dict(schedule=self.schedule.get().strip(),resources=self.resources.get().strip(),
            start=self.start.get().strip(),days=days,rows=selections,infer_blank=self.infer_blank.get(),languages=languages,
            folders={n:v.get().strip() for n,v in self.folders.items()},browser=self.channel.get(),
            mode=self.mode.get(),inbox=self.inbox.get().strip(),client_exe=self.client_path.get().strip(),
            client_wait_minutes=minutes)
        atomic_json(WORK/'settings.json',settings)
        return settings

    def import_tasks(self):
        try:
            s=self.settings()
            tasks=build_tasks(s['schedule'],s['resources'],start=s['start'],days=s['days'],row_selections=s['rows'],infer_blank=s['infer_blank'])
            old={t['id']:t for t in self.tasks}
            if (WORK/'plan.json').exists():old.update({t['id']:t for t in json.loads((WORK/'plan.json').read_text(encoding='utf-8'))})
            for task in tasks:
                previous=old.get(task['id'])
                if previous and previous.get('schedule_sha256')==task['schedule_sha256'] and previous.get('resource_sha256')==task['resource_sha256'] and previous.get('manual_override') and previous.get('code') in [c['code'] for c in task['candidates']]:
                    for key in ('share','code','manual_override'):task[key]=previous[key]
                    task['status']=ready_status(task)
            self.tasks=tasks;self.saved=s
            self.plan_settings=self.signature(s)
            self.persist();self.refresh()
            inferred=sum(t['inferred_date'] for t in tasks)
            end=(dt.date.fromisoformat(s['start'])+dt.timedelta(days=s['days']-1)).isoformat()
            self.status.set(f"{s['start']}—{end}（{s['days']}个日历日）；选中{len(s['rows'])}行，共{len(tasks)}部。推算日期{inferred}条；空白日期默认跳过。请核对下面原表位置和剧名。")
        except Exception as exc:messagebox.showerror('无法生成任务',private_error(exc))

    def persist(self):atomic_json(WORK/'plan.json',self.tasks)

    def refresh(self):
        for i in self.tree.get_children():self.tree.delete(i)
        for t in self.tasks:self.tree.insert('', 'end',iid=t['id'],values=(t['date'],t.get('source_cell','')+('（推算）' if t.get('inferred_date') else ''),t['language'],t['title'],t['code'],t['status']))

    def current(self):
        selected=self.tree.selection()
        return next((t for t in self.tasks if selected and t['id']==selected[0]),None)

    def select_task(self,event=None):
        t=self.current()
        if not t:return
        self.code_box['values']=[c['code'] for c in t['candidates']]
        self.code.set(t['code']);self.link.set((t.get('share') or {}).get('url',''))
        self.password.set((t.get('share') or {}).get('password',''))

    def select_code(self,event=None):
        t=self.current()
        if not t:return
        entry=next((c for c in t['candidates'] if c['code']==self.code.get()),None)
        if entry:
            self.link.set((entry.get('share') or {}).get('url',''))
            self.password.set((entry.get('share') or {}).get('password',''))

    def edit_task(self):
        try:
            t=self.current()
            if not t:raise ValueError('请先选择任务。')
            if self.code.get() not in [c['code'] for c in t['candidates']]:raise ValueError('请先选择资源版本；无匹配剧需在资源表补充后重新导入。')
            share=share_link(self.link.get()+' 提取码：'+self.password.get().strip())
            if not share:raise ValueError('请输入唯一有效百度分享链接和提取码（如需要）。')
            # An edited extraction code must take precedence over a stale URL query code.
            if self.password.get().strip():
                import re
                if not re.fullmatch('[A-Za-z0-9]{4}',self.password.get().strip()):raise ValueError('提取码应为4位字母数字。')
                share['password']=self.password.get().strip()
            t.update(code=self.code.get(),share=share,manual_override=True)
            t['status']=ready_status(t);self.persist();self.refresh()
        except Exception as exc:messagebox.showerror('无法保存',private_error(exc))

    def pause(self,message):
        self.resume.clear();self.events.put(('pause',message))
        while not self.resume.wait(.2):
            if self.stop.is_set():raise InterruptedError('已停止。')
        self.events.put(('resumed',None))

    def launch(self,operation):
        if self.busy:return
        self.busy=True;self.stop.clear()
        for b in self.buttons:b.configure(state='disabled')
        def worker():
            try:operation();self.events.put(('success',None))
            except Exception as exc:self.events.put(('error',private_error(exc)))
            finally:self.events.put(('done',None))
        threading.Thread(target=worker,daemon=True).start()

    def browser(self,channel):
        return BaiduBrowser(WORK/'browser_profile',self.pause,self.stop.is_set,
            log=lambda text:self.events.put(('log',text)),channel=channel)

    def login(self):
        channel=self.channel.get()
        def work():
            with self.browser(channel) as browser:browser.login()
        self.launch(work)

    def start_work(self,scan_only=False):
        try:
            s=self.settings()
            signature=self.signature(s)
            if not self.tasks or getattr(self,'plan_settings',None)!=signature:
                raise ValueError('请先点击“读取排片生成任务”；修改表格、行、天数、日期或推算设置后需重新生成。')
            if not any(ready_status(t)=='待扫描' for t in self.tasks):
                raise ValueError('暂无可扫描任务，请先补充有效百度链接或选择正确版本代码。')
            tasks=json.loads(json.dumps(self.tasks));folders={n:s['folders'][n] for n in s['languages']}
        except Exception as exc:messagebox.showerror('请检查任务',private_error(exc));return
        def work():
            if not scan_only and s['mode']=='客户端' and s['client_exe']:
                launch_client(s['client_exe'])
            with self.browser(s['browser']) as browser:
                backend=ClientDownloads(browser,s['inbox'],WORK,cancelled=self.stop.is_set,
                    log=lambda text:self.events.put(('log',text)),timeout_seconds=s['client_wait_minutes']*60) if not scan_only and s['mode']=='客户端' else browser
                records=run_downloads(tasks,folders,WORK,backend,scan_only=scan_only,
                    cancelled=self.stop.is_set,log=lambda text:self.events.put(('log',text)))
            self.events.put(('records',records))
        self.status.set('正在扫描匹配…' if scan_only else '正在下载；只处理所选排片行的语种与剧目。')
        self.launch(work)

    def request_stop(self):
        self.stop.set();self.status.set('已请求停止；客户端里的任务不自动取消。网页直接下载时，当前文件结束后停止。')

    def open_report(self):
        path=WORK/'download_report.xlsx'
        if not path.exists():messagebox.showinfo('尚无记录','先扫描或下载一次。');return
        import subprocess,sys
        try:
            if sys.platform=='win32':os.startfile(path)
            elif sys.platform=='darwin':subprocess.Popen(['open',str(path)])
            else:subprocess.Popen(['xdg-open',str(path)])
        except Exception as exc:messagebox.showerror('打开失败',private_error(exc))

    def poll(self):
        try:
            while True:
                kind,value=self.events.get_nowait()
                if kind=='log':self.log.insert('end',value+'\n');self.log.see('end')
                elif kind=='pause':self.status.set(value);self.continue_button.configure(state='normal')
                elif kind=='resumed':self.continue_button.configure(state='disabled')
                elif kind=='records':
                    statuses={}
                    for row in value:statuses.setdefault((row['日期'],row['语种'],row['剧名']),set()).add(row['状态'])
                    for t in self.tasks:
                        t['status']='；'.join(sorted(statuses.get((t['date'],t['language'],t['title']),{'未处理'})))
                    self.persist();self.refresh()
                elif kind=='success':self.status.set('本次操作结束；结果以下载记录Excel中的状态为准。不自动再次运行。')
                elif kind=='error':self.status.set('操作未全部完成：'+value);self.log.insert('end','错误：'+value+'\n');self.log.see('end')
                elif kind=='done':
                    self.busy=False;self.continue_button.configure(state='disabled')
                    for b in self.buttons:b.configure(state='normal')
        except queue.Empty:pass
        self.root.after(150,self.poll)

    def close(self):
        if self.busy:
            messagebox.showinfo('任务运行中','请先点击“停止后续/停止等待”，待本程序停止后关闭；客户端任务可继续下载。');return
        self.root.destroy()


if __name__=='__main__':
    root=tk.Tk();App(root);root.mainloop()
