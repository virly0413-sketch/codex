# YouTube禁播与限制自动检测

## 下载启动

下载整个仓库ZIP并完整解压，安装Python 3.10+。Windows双击 `start_monitor_windows.bat`，首次会安装现有依赖。Mac/Linux在程序目录运行：

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python monitor_desktop.py
```

1. 填入要检测的UC频道ID和名称，或“导入频道配置”选择 `profiles/english.json`、`profiles/russian.json`。也支持输入其他自己管理的频道ID。
2. 选择Google桌面OAuth客户端JSON文件。可使用原发布程序的 `client_secret.json`；仍须启用YouTube Data API v3并在Google Auth Platform允许当前测试账号。授权设置见[使用说明](使用说明.md)。
3. 使用VPN时确认代理端口；默认沿用 `http://127.0.0.1:7897`。
4. 点击“立即检测”，首次在浏览器登录拥有目标频道权限的账号，并选择正确品牌频道。若选错，点击“切换授权账号/频道”。程序核对频道ID，不会自动改目标。
5. 完成后双击列表条目打开视频，或点击“打开本地报告”“打开报告目录”。表格列出禁播、上传被拒以及需关注的其他状态。
6. 勾选“自动检测”，默认每30分钟扫描。电脑和程序需要保持运行、网络可达；取消勾选停止后续轮询。检测结束后才开始计算下一次间隔，不会重叠扫描。

新程序只申请 `youtube.readonly`，独立保存本机 `token.*.monitor.json`，不覆盖原发布令牌，不修改、上传、删除或公开任何视频。界面可随时输入其他频道ID；每个频道分别授权、分别保存报告。GUI与CLI的令牌命名按各自配置，首次使用不同入口可能需分别授权一次。

## 能检测什么

| API返回信息 | 报告分类 |
| --- | --- |
| regionRestriction.allowed为空 | 全球禁播 |
| allowed非空或blocked非空 | 地区禁播，列出地区代码或允许地区 |
| uploadStatus=rejected | 上传被拒，附copyright、legal等原始原因（如有返回） |
| uploadStatus=failed | 上传/处理失败，单独列出 |
| uploadStatus=deleted | 已删除，不能自动推断为版权禁播 |
| ytAgeRestricted | 年龄限制，单独列出 |
| 列表存在但视频详情未返回 | 状态待核对，不能自动推断禁播/删除 |

**普通YouTube Data API不提供完整Content ID版权声明和Studio“限制”详情。** 本工具可检测API返回的地区限制和拒绝状态，不能承诺检出Studio中的所有版权封锁。没有返回标记的条目标为“API未返回禁播标记”，不能据此认定版权正常。只读取API仍能在频道上传列表中列出的条目，无法找回已经从列表消失的视频。

私密、未列出、定时尚未公开、禁止嵌入、`licensedContent=true`均不会单独被当作禁播。地区限制不能据此自动推断版权、法律或上传者策略的具体来源。

## 本机报告

默认目录为 `blocked_reports/频道ID/`：

- `blocked_videos.csv`：返回禁播/上传被拒标记的视频名称、观看链接、Studio链接、限制详情、可见性和北京时间。
- `attention.csv`：年龄限制、处理失败、已删除、详情未返回等需关注记录。
- `newly_detected.csv`：相对上次成功扫描新出现或原因改变的禁播/被拒记录。首次运行将当前检测记录全部列入；这是轮询发现，不能获取精确发生时间。
- `all_videos.csv`：本次全部扫描记录；同一视频有多个限制时会有多行。
- `report.html`：本地浏览器报告，支持点击视频链接和Studio链接。
- `latest.json`：最近成功扫描及检测范围；`scan_时间戳.json`保留每次成功快照。

网络/API读取失败时停止该次扫描，日志明确报错，不以零条限制覆盖上次成功结果。看到旧报告时请核对报告内的检测时间。报告仅保存在本机，不提交到GitHub；令牌也在忽略规则中。

## 无界面自动运行

单次扫描（默认俄语配置）：

```sh
python blocked_monitor.py
```

英语每30分钟自动检测，Ctrl+C停止：

```sh
python blocked_monitor.py --config profiles/english.json --watch --interval 1800
```

其他参数：`--output 本机目录` 指定报告根目录；`--reauth` 重新选择授权账号/品牌频道。轮询最短60秒，大频道建议30分钟或更久，避免耗尽Google API配额。频道视频逐页读取、详情每50条批量读取，不使用高消耗的搜索接口。

也可通过Windows任务计划程序定时运行单次命令：程序为解压目录下 `.venv\Scripts\python.exe`，参数为 `blocked_monitor.py --config profiles/english.json`，“起始于”填解压目录。先在界面或命令行完成对应授权，再设置计划；不要同时启动多个实例检测同一频道。

## 验证范围

提供离线模拟测试，覆盖分页、地区限制空列表含义、状态区分、增量发现、失败保留、只读授权及CSV/HTML转义。未连接用户的真实频道实测；实际API可见信息以用户本机授权后的返回为准。
