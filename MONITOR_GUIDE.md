# YouTube禁播及异常视频：单次扫描、Excel导出

Windows双击 **start_monitor_windows.bat**。需Python 3.10+，点击一次扫描一次。此入口已按要求恢复首次使用的API扫描流程，不打开额外的自动化浏览器，不需要安装Edge、Chromium或浏览器扩展。

## 使用

1. 输入目标UC频道ID，或导入 `profiles/english.json` / `profiles/russian.json`。
2. 选择Google桌面OAuth客户端JSON（通常是原有 `client_secret.json`），按本机需要填写代理地址。
3. 点击“扫描一次并导出Excel”。首次或令牌失效时，仍需在系统默认浏览器完成正常Google OAuth授权；与第一次的授权方式相同，不是独立的Playwright浏览器。可把Chrome设为Windows默认浏览器以使用平时的浏览器授权。
4. 扫描后点击“打开Excel”或“Excel另存为…”。再次扫描前关闭已打开的Excel以避免文件占用。

可选择不同的自己管理的频道；授权频道必须与目标UC ID一致。只读授权独立保存，不覆盖发布程序令牌；已有有效授权通常无须再次登录。

## 登记内容

`blocked_reports/频道ID/blocked_videos.xlsx` 包含：

- **需处理视频**：名称、链接两列，按视频去重。
- **限制详情**：登记全球/地区禁播、上传被拒、年龄限制、上传失败、删除、详情未返回等API可见异常及原因。
- **检测范围**：明确记录收益检查未执行，不能认定未列出的视频收益正常。

年龄限制可能影响广告投放，但本工具不会把年龄限制直接认定为已黄标。私密、未列出、关闭嵌入或licensedContent=true不会单独被认定为禁播或收入限制。

**此方式无法自动抓取黄标、广告受限、收益分成或完整版权声明。** 普通YouTube Data API不提供这些状态。原来的程序也没有这项能力。一般的桌面Python程序不能直接读取普通方式启动且已登录的Chrome标签页；若要读取页面，需要浏览器扩展、调试连接或手工提供页面数据等额外接入。本入口按用户要求不添加这些接入，也不新开自动化浏览器。因此本版本只扩展登记API可见异常，不宣称完成实际收益限制检测。

## 报告与范围

默认本机目录 `blocked_reports/频道ID/`，含Excel、禁播CSV、其他异常attention.csv、全部API记录all_videos.csv、本地HTML报告和JSON快照。收益检查未执行时revenue.csv为空，仅保留表头，不代表收入无问题。

检测仅覆盖上传列表中API仍可返回的视频；未返回禁播标记不代表无版权限制。网络或API失败时不以零异常覆盖最近成功报告。报告只存本机，不自动发送到聊天。程序不定时运行，不自动解禁，不修改收益、广告评级、可见性或视频内容。

## 命令行及兼容模块

普通单次扫描：

```sh
python blocked_monitor.py --config profiles/russian.json
```

`--output 目录`指定报告位置，`--reauth`重新授权。之前提供的Studio模块和安装脚本作为兼容文件保留，**Windows默认入口不调用它们**。无需运行install_monitor_browser_windows.bat。

## 验证

已通过离线/模拟检查，覆盖分页、地区限制、异常区分、Excel合并及去重、导出安全和失败保留。新增GUI流程测试检查默认扫描不依赖Studio、Playwright或浏览器安装。没有访问用户真实账号，本次未修改任何YouTube视频。
