"""Local-only schedule/share audit. No YouTube OAuth or upload controls."""
import os
from pathlib import Path
import queue
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from baidu_download import schedule_rows, sha256_file
from share_check import check

ROOT=Path(__file__).resolve().parent
DEFAULT=ROOT/'schedules/2026-10-26_to_2026-11-15_7day/schedule_transposed.csv'

class App:
    def __init__(self,root):
        self.root=root;self.events=queue.Queue();self.stop=threading.Event();self.busy=False;self.rows=[];self.report=None
        root.title('JCHD排片片源核对 · 只读导出Excel');root.geometry('1020x640')
        self.values={k:tk.StringVar(value=v) for k,v in dict(schedule=str(DEFAULT),share=r'\\JCHD\海外运营',start='2026-10-26',days='21').items()}
        form=ttk.Frame(root,padding=12);form.pack(fill='x');form.columnconfigure(1,weight=1)
        for i,(key,label) in enumerate([('schedule','排片表CSV'),('share','片源共享目录'),('start','开始日期'),('days','核对天数')]):
            ttk.Label(form,text=label).grid(row=i,column=0,sticky='w')
            ttk.Entry(form,textvariable=self.values[key],width=90).grid(row=i,column=1,sticky='ew',padx=6,pady=4)
            if key in ('schedule','share'):ttk.Button(form,text='选择',command=lambda k=key:self.pick(k)).grid(row=i,column=2)
        self.all_dates=tk.BooleanVar(value=False);self.infer=tk.BooleanVar(value=False)
        ttk.Checkbutton(form,text='核对所选行全部明确日期（忽略开始日期和天数）',variable=self.all_dates).grid(row=4,column=1,sticky='w')
        ttk.Checkbutton(form,text='允许空白日期按日顺延（仅在原表确认连续时勾选）',variable=self.infer).grid(row=5,column=1,sticky='w')
        ttk.Button(form,text='读取/刷新排片行',command=self.load_rows).grid(row=6,column=0)
        self.list=tk.Listbox(form,selectmode='extended',exportselection=False,height=6);self.list.grid(row=6,column=1,sticky='ew')
        ttk.Label(root,text='Ctrl多选具体频道行；语言跟随行名。不需要剧集资源表、YouTube账号或网盘登录。').pack(anchor='w',padx=12)
        bar=ttk.Frame(root,padding=12);bar.pack(fill='x')
        self.run_button=ttk.Button(bar,text='核对并保存Excel',command=self.start);self.run_button.pack(side='left')
        ttk.Button(bar,text='打开上次Excel',command=self.open_report).pack(side='left',padx=8)
        ttk.Button(bar,text='停止',command=self.stop.set).pack(side='left')
        self.status=tk.StringVar(value='默认使用此前10月26日—11月15日四频道排片，也可选择自己的最新CSV。')
        ttk.Label(root,textvariable=self.status,wraplength=980).pack(anchor='w',padx=12)
        self.log=tk.Text(root,height=12,wrap='word');self.log.pack(fill='both',expand=True,padx=12,pady=10)
        root.after(150,self.poll);root.protocol('WM_DELETE_WINDOW',self.close)
        if DEFAULT.exists():self.load_rows()
    def pick(self,key):
        path=filedialog.askdirectory() if key=='share' else filedialog.askopenfilename(filetypes=[('CSV','*.csv')])
        if path:self.values[key].set(path)
        if key=='schedule' and path:self.load_rows()
    def load_rows(self):
        if self.busy:return
        try:
            self.rows=schedule_rows(self.values['schedule'].get());self.loaded_hash=sha256_file(self.values['schedule'].get())
            self.list.delete(0,'end')
            for r in self.rows:self.list.insert('end',f"第{r['row']}行 | {r['label']} | {r['language'] or '无法识别，请修正行名'}")
            self.status.set('请选中要核对的排片行（Ctrl可多选），核对日期和目录后开始。')
        except Exception as e:messagebox.showerror('无法读取',str(e))
    def start(self):
        if self.busy:return
        try:
            s={k:v.get().strip() for k,v in self.values.items()}
            if not self.rows or sha256_file(s['schedule'])!=self.loaded_hash:raise ValueError('请重新读取排片行，文件已更换或内容已更新')
            selections=[self.rows[i] for i in self.list.curselection()]
            if not selections or any(not r['language'] for r in selections):raise ValueError('请明确选择具体排片行，且行名需能识别语言')
            start=None if self.all_dates.get() else s['start'];days=None if start is None else int(s['days']);infer=self.infer.get()
            path=filedialog.asksaveasfilename(defaultextension='.xlsx',initialfile='JCHD排片片源核对.xlsx',filetypes=[('Excel','*.xlsx')])
            if not path:return
        except Exception as e:messagebox.showerror('请检查设置',str(e));return
        self.busy=True;self.stop.clear();self.run_button.configure(state='disabled');self.status.set('正在核对，请稍候…')
        def worker():
            try:
                results=check(s['schedule'],s['share'],selections,path,start,days,infer,self.stop,lambda t:self.events.put(('log',t)))
                self.events.put(('result',(path,results)))
            except Exception as e:self.events.put(('error',str(e)))
            finally:self.events.put(('done',None))
        threading.Thread(target=worker,daemon=True).start()
    def poll(self):
        try:
            while True:
                kind,value=self.events.get_nowait()
                if kind=='log':self.log.insert('end',value+'\n');self.log.see('end')
                elif kind=='result':
                    self.report,results=value;missing=[r for r in results if not r['files']]
                    self.status.set(f'核对完成：{len(results)}条排片，{len(missing)}条未匹配对应语种；Excel：{self.report}')
                    for r in missing:self.log.insert('end',f"{r['date']} | {r['language']} | {r['title']} | {r['status']}\n")
                    self.log.see('end')
                elif kind=='error':self.status.set('核对未完成，未生成本次缺片结论');messagebox.showerror('核对失败',value)
                elif kind=='done':self.busy=False;self.run_button.configure(state='normal')
        except queue.Empty:pass
        self.root.after(150,self.poll)
    def open_report(self):
        if not self.report:messagebox.showinfo('暂无报告','请先完成一次核对');return
        try:
            if os.name=='nt':os.startfile(self.report)
            else:
                import webbrowser
                webbrowser.open(Path(self.report).resolve().as_uri())
        except Exception as e:messagebox.showerror('无法打开',str(e))
    def close(self):
        if self.busy:self.stop.set();self.status.set('正在停止，请等待当前文件读取结束')
        else:self.root.destroy()

if __name__=='__main__':
    root=tk.Tk();App(root);root.mainloop()
