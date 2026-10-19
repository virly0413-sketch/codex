"""Manual one-click shared-folder scan and private upload UI."""
import datetime as dt
import json
import queue
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from baidu_download import LANGUAGES, atomic_json, build_tasks, schedule_rows
from network_upload import inventory, matches, existing_uploads, upload_private
from prepare import normalize
from run import ROOT, auth, upload_lock

WORK = ROOT/'local_work_network'

class App:
    def __init__(self, root):
        self.root=root; self.events=queue.Queue(); self.stop=threading.Event(); self.tasks=[]; self.rows=[]; self.busy=False
        settings=WORK/'settings.json'
        self.saved=json.loads(settings.read_text(encoding='utf-8')) if settings.exists() else {}
        root.title('网络共享片源 · 排片扫描与YouTube私密上传'); root.geometry('1180x760')
        form=ttk.Frame(root,padding=10); form.pack(fill='x'); form.columnconfigure(1,weight=1)
        self.vars={}
        defaults=dict(schedule='',resources='',share=r'\\JCHD\海外运营',start=dt.date.today().isoformat(),days='7')
        for i,(key,label) in enumerate([('schedule','排片CSV'),('resources','资源CSV'),('share','网络片源目录'),('start','开始日期 YYYY-MM-DD'),('days','天数（含当天）')]):
            var=tk.StringVar(value=self.saved.get(key,defaults[key])); self.vars[key]=var
            ttk.Label(form,text=label).grid(row=i,column=0,sticky='w'); ttk.Entry(form,textvariable=var).grid(row=i,column=1,sticky='ew',padx=5,pady=3)
            if key in ('schedule','resources','share'):
                ttk.Button(form,text='选择',command=lambda k=key:self.pick(k)).grid(row=i,column=2)
        self.infer=tk.BooleanVar(value=False)
        ttk.Checkbutton(form,text='允许空白日期逐日顺延（默认关闭）',variable=self.infer).grid(row=5,column=1,sticky='w')
        ttk.Button(form,text='读取排片行',command=self.load_rows).grid(row=6,column=0)
        self.rowbox=tk.Listbox(form,selectmode='extended',exportselection=False,height=5); self.rowbox.grid(row=6,column=1,sticky='ew')
        ttk.Label(root,text='Ctrl选择多个频道行。每行语种从名称识别；未知名称请先在CSV中标明语种。').pack(anchor='w',padx=10)
        self.channels={}; group=ttk.LabelFrame(root,text='语种对应的目标频道ID（英语/俄语已填；其他频道请填写）',padding=6); group.pack(fill='x',padx=10)
        for i,language in enumerate(LANGUAGES):
            default={'俄语':'UC_o03Jz0Ek8xYGE_oy3zapg','英语':'UC0koaDPTujsoVj-Tw27J0Qg'}.get(language,'')
            var=tk.StringVar(value=self.saved.get('channels',{}).get(language,default)); self.channels[language]=var
            ttk.Label(group,text=language).grid(row=i//3,column=(i%3)*2); ttk.Entry(group,textvariable=var,width=32).grid(row=i//3,column=(i%3)*2+1,padx=3,pady=2)
        proxy=ttk.Frame(root); proxy.pack(fill='x',padx=10)
        ttk.Label(proxy,text='Google代理（可留空）').pack(side='left'); self.proxy=tk.StringVar(value=self.saved.get('proxy','http://127.0.0.1:7897'))
        ttk.Entry(proxy,textvariable=self.proxy,width=45).pack(side='left')
        bar=ttk.Frame(root,padding=10); bar.pack(fill='x')
        self.actions=[]
        for text,command in [('扫描共享目录',self.scan),('选择文件/版本',self.choose),('上传选中任务（私密）',self.upload)]:
            b=ttk.Button(bar,text=text,command=command); b.pack(side='left',padx=4); self.actions.append(b)
        ttk.Button(bar,text='停止',command=self.stop.set).pack(side='left')
        self.tree=ttk.Treeview(root,columns=('date','cell','lang','title','code','path','status'),show='headings',selectmode='extended')
        for col,label,width in [('date','日期',95),('cell','原表位置',70),('lang','语言',70),('title','剧名',240),('code','代码',100),('path','文件',320),('status','状态',190)]:
            self.tree.heading(col,text=label); self.tree.column(col,width=width)
        self.tree.pack(fill='both',expand=True,padx=10)
        self.status=tk.StringVar(value='先扫描；无匹配、多个文件或多个资源版本均不会自动上传。只读取共享文件，不移动、不删除。')
        ttk.Label(root,textvariable=self.status,wraplength=1130).pack(fill='x',padx=10,pady=8)
        ttk.Label(root,text='上传后为私密，保留中文剧名供原发布程序匹配，说明为剧集代码。标题/封面/定时公开仍由原发布程序处理。').pack(anchor='w',padx=10)
        root.after(150,self.poll); root.protocol('WM_DELETE_WINDOW',self.close)

    def close(self):
        if self.busy: self.stop.set(); self.status.set('正在停止，请等待当前网络请求结束。')
        else: self.root.destroy()

    def pick(self,key):
        p=filedialog.askdirectory() if key=='share' else filedialog.askopenfilename(filetypes=[('CSV','*.csv')])
        if p: self.vars[key].set(p)

    def load_rows(self):
        try:
            from baidu_download import sha256_file
            path=self.vars['schedule'].get(); self.rows=schedule_rows(path); self.row_hash=sha256_file(path)
            self.rowbox.delete(0,'end')
            for r in self.rows: self.rowbox.insert('end',f"第{r['row']}行 | {r['label']} | {r['language'] or '未知语种'}")
            self.tasks=[]; self.refresh()
        except Exception as exc: messagebox.showerror('读取失败',str(exc))

    def refresh(self):
        self.tree.delete(*self.tree.get_children())
        for t in self.tasks:
            self.tree.insert('', 'end',iid=t['id'],values=(t['date'],t['source_cell']+(' 推算' if t['inferred_date'] else ''),t['language'],t['title'],t['code'],t.get('selected',{}).get('path',''),t['status']))

    def work(self,fn):
        if self.busy:return
        self.busy=True; self.stop.clear()
        for b in self.actions:b.config(state='disabled')
        def run():
            try: fn()
            except Exception as exc:self.events.put(('error',str(exc)))
            finally:self.events.put(('done',''))
        threading.Thread(target=run,daemon=True).start()

    def signature(self):
        from baidu_download import sha256_file
        return (tuple((k,v.get().strip()) for k,v in self.vars.items()),
                sha256_file(self.vars['schedule'].get().strip()),
                sha256_file(self.vars['resources'].get().strip()),
                tuple(self.rowbox.curselection()),self.infer.get())

    def scan(self):
        try:
            from baidu_download import sha256_file
            s={k:v.get().strip() for k,v in self.vars.items()}
            if not self.rows or sha256_file(s['schedule'])!=self.row_hash:raise ValueError('请先重新读取排片行。')
            selections=[self.rows[i] for i in self.rowbox.curselection()]
            tasks=build_tasks(s['schedule'],s['resources'],start=s['start'],days=int(s['days']),row_selections=selections,infer_blank=self.infer.get())
            if not tasks: raise ValueError('所选日期和行没有排片任务。')
            settings=dict(s,channels={k:v.get().strip() for k,v in self.channels.items()},proxy=self.proxy.get().strip())
            atomic_json(WORK/'settings.json',settings)
            self.plan_signature=self.signature()
        except Exception as exc:messagebox.showerror('无法扫描',str(exc));return
        self.tasks=[];self.refresh()
        def run():
            self.events.put(('status','正在遍历共享目录，请稍候…'))
            files=inventory(s['share'],self.stop)
            for t in tasks:
                candidates=matches(t,files);t['files']=candidates
                if len(candidates)==1:t['selected']=candidates[0]
                t['status']='可上传' if len(candidates)==1 and t['code'] else ('未找到对应剧名和语言' if not candidates else '请选择文件/版本')
            self.events.put(('tasks',tasks))
        self.work(run)

    def choose(self):
        ids=self.tree.selection()
        if len(ids)!=1:messagebox.showinfo('请选择一项','请选择一项任务进行文件/版本选择。');return
        task=next(t for t in self.tasks if t['id']==ids[0])
        dialog=tk.Toplevel(self.root);dialog.title('明确选择片源及剧集版本');dialog.geometry('1000x360')
        box=tk.Listbox(dialog,exportselection=False);box.pack(fill='both',expand=True)
        for f in task['files']:box.insert('end',f['path'])
        code=tk.StringVar(value=task['code']);ttk.Label(dialog,text='资源版本代码（需与所选视频对应）').pack()
        ttk.Combobox(dialog,textvariable=code,values=[c['code'] for c in task['candidates']],state='readonly').pack()
        def save():
            if not box.curselection() or not code.get():return
            task['selected']=task['files'][box.curselection()[0]];task['code']=code.get();task['status']='可上传';self.refresh();dialog.destroy()
        ttk.Button(dialog,text='使用此文件和版本',command=save).pack(pady=6)

    def upload(self):
        try:
            if self.signature()!=self.plan_signature:raise ValueError('排片、目录或日期选择已变更，请重新扫描。')
        except Exception as exc:
            messagebox.showerror('请重新扫描',str(exc));return
        ids=set(self.tree.selection());tasks=[dict(t) for t in self.tasks if t['id'] in ids]
        if not tasks or any(not t.get('selected') or not t['code'] for t in tasks):
            messagebox.showerror('无法上传','请选择已明确文件与剧集代码的任务。');return
        configs={}
        import re
        for t in tasks:
            language=t['language'];channel=self.channels[language].get().strip()
            if not re.fullmatch(r'UC[A-Za-z0-9_-]{22}',channel):messagebox.showerror('频道错误',language+'请填写正确UC频道ID。');return
            configs[language]=dict(channel_id=channel,channel_name=language,oauth_client='client_secret.json',oauth_token='token.network.'+channel+'.json',proxy_url=self.proxy.get().strip(),http_timeout_seconds=60)
        def run():
            with upload_lock(WORK):
                for language,config in configs.items():
                    youtube=auth(config);existing=existing_uploads(youtube,config['channel_id'])
                    for t in [t for t in tasks if t['language']==language]:
                        if self.stop.is_set():return
                        self.events.put(('status','正在处理：'+t['title']))
                        known=existing.get(normalize(t['title'])) or existing.get('code:'+t['code'])
                        if known:
                            vid=known[0];status='频道已有同名或同代码视频，跳过'
                        else:
                            vid=upload_private(youtube,config,t,t['selected'],WORK/'uploads.json',self.stop,lambda text:self.events.put(('status',t['title']+'：'+text)))
                            existing.setdefault(normalize(t['title']),[]).append(vid);status='已私密上传'
                        self.events.put(('result',(t['id'],status+' https://youtu.be/'+vid)))
        self.work(run)

    def poll(self):
        try:
            while True:
                kind,value=self.events.get_nowait()
                if kind=='tasks':self.tasks=value;self.refresh();self.status.set('扫描完成；请检查原表位置、语言和文件，再选中要上传的任务。')
                elif kind=='result':
                    for t in self.tasks:
                        if t['id']==value[0]:t['status']=value[1]
                    self.refresh();self.status.set(value[1])
                elif kind=='status':self.status.set(value)
                elif kind=='error':self.status.set(value);messagebox.showerror('操作未完成',value)
                elif kind=='done':
                    self.busy=False
                    for b in self.actions:b.config(state='normal')
        except queue.Empty:pass
        self.root.after(150,self.poll)

if __name__=='__main__':
    root=tk.Tk();App(root);root.mainloop()
