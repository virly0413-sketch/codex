"""Locate installed browsers without requiring a per-user Edge installation."""
import os
import shutil
from pathlib import Path


KINDS = ('msedge', 'chrome', 'chromium')


def installed_paths(kind):
    relative = {'msedge': 'Microsoft/Edge/Application/msedge.exe',
                'chrome': 'Google/Chrome/Application/chrome.exe',
                'chromium': 'Chromium/Application/chrome.exe'}[kind]
    paths = []
    for variable in ('PROGRAMFILES', 'PROGRAMFILES(X86)', 'LOCALAPPDATA', 'ProgramFiles', 'ProgramFiles(x86)'):
        base = os.environ.get(variable)
        if base: paths.append(Path(base)/relative)
    executable = shutil.which({'msedge':'msedge','chrome':'google-chrome','chromium':'chromium'}[kind])
    if executable: paths.append(Path(executable))
    if os.name == 'nt' and kind in ('msedge','chrome'):
        import winreg
        exe = 'msedge.exe' if kind=='msedge' else 'chrome.exe'
        for hive in (winreg.HKEY_CURRENT_USER,winreg.HKEY_LOCAL_MACHINE):
            for view in (winreg.KEY_WOW64_64KEY,winreg.KEY_WOW64_32KEY):
                try:
                    with winreg.OpenKey(hive, 'SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\App Paths\\'+exe,0,winreg.KEY_READ|view) as key:
                        value,_=winreg.QueryValueEx(key,None)
                        paths.append(Path(os.path.expandvars(value.strip('"'))))
                except OSError: pass
    seen=set()
    for path in paths:
        if path.is_file() and str(path).casefold() not in seen:
            seen.add(str(path).casefold());yield path


def launch_studio_browser(chromium, profile, browser='auto', executable='', progress=print):
    if browser not in ('auto',)+KINDS: raise ValueError('未知浏览器类型')
    options=dict(headless=False)
    if executable:
        path=Path(executable).expanduser()
        if not path.is_file(): raise ValueError('指定浏览器文件不存在，请重新选择浏览器EXE。')
        if os.name=='nt' and path.name.casefold() not in ('msedge.exe','chrome.exe','chromium.exe'):
            raise ValueError('请选择msedge.exe、chrome.exe或chromium.exe。')
        progress('使用指定浏览器：'+str(path))
        return chromium.launch_persistent_context(str(Path(profile).resolve()),executable_path=str(path),**options)
    candidates=[]
    for kind in (KINDS if browser=='auto' else (browser,)):
        candidates.extend((kind,path) for path in installed_paths(kind))
        if kind=='chromium' and Path(chromium.executable_path).is_file():
            candidates.append((kind,Path(chromium.executable_path)))
    # Playwright may know a managed browser location beyond our system paths.
    if not candidates:
        kinds=KINDS if browser=='auto' else (browser,)
        for kind in kinds:
            try:
                return chromium.launch_persistent_context(str(Path(profile).resolve()),channel=kind,**options)
            except Exception as exc:
                message=str(exc).casefold()
                if not any(x in message for x in ('not found', "doesn't exist", 'does not exist', 'executable doesn', 'distribution')):
                    raise  # Profile locks and other startup failures must not be hidden.
        raise ValueError('没有找到可用的浏览器。请点击“选择浏览器EXE”指定已安装的Edge/Chrome；或关闭程序，双击 install_monitor_browser_windows.bat 安装专用Chromium，完成后重新启动。')
    kind,path=candidates[0]
    progress('使用浏览器：'+kind+' | '+str(path))
    return chromium.launch_persistent_context(str(Path(profile).resolve()),executable_path=str(path),**options)
