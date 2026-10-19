# YouTube禁播及收益限制：单次扫描、Excel导出

Windows双击 **start_monitor_windows.bat**。首次安装依赖，需Python 3.10+及可用的Edge、Chrome或Chromium。此工具只检测，不会解除禁播或修改广告、收益和视频设置。每次点击扫描一次，无定时任务。

## 使用

1. 输入目标UC频道ID，或导入 `profiles/english.json` / `profiles/russian.json`。可以检测其他自己管理的频道，每个频道分别授权和保存报告。
2. 选择Google桌面OAuth客户端JSON，通常为原程序的 `client_secret.json`。启用YouTube Data API v3；授权设置见[使用说明](使用说明.md)。代理默认沿用 `http://127.0.0.1:7897`，根据本机实际设置。
3. 保持勾选 **“包含Studio收益检查”**，点击 **“扫描一次并导出Excel”**。
4. 首次完成Google只读OAuth授权，选择正确品牌频道。随后程序打开独立浏览器窗口，请登录该频道，等待Studio内容列表显示（最多3分钟）。不要手动更换频道、筛选、排序或翻页，程序读取收益列并自动翻页，完成后关闭此独立窗口。
5. 点击“打开Excel”或“Excel另存为…”。要再次扫描时先关闭Excel文件，避免Windows锁定文件导致无法保存。

浏览器登录状态保存在本机独立目录 `local_work_studio_monitor/频道ID/`，不读取你平时浏览器的Cookie，不提交到GitHub。可在Google网页自行退出登录；删除该目录前先关闭该浏览器。

## Excel内容

文件保留为 `blocked_reports/频道ID/blocked_videos.xlsx`，包含三个工作表：

- **需处理视频**：视频名称、视频链接两列，同一视频合并一行，链接可点击。包含禁播、上传被拒及其他API异常、Studio检测到的收益问题和收益待核对记录。
- **限制详情**：视频名称、链接、分类、原始状态文字；同一视频的多个原因分别登记。
- **检测范围**：说明是否执行Studio收益检查、检查条数及不可检测范围。未勾选收益检查时明确显示“未执行”，不能视为收入正常。

收益列可识别：收入限制（Limited/受限等）、无法创收、收益分成、检查或审核中、收益关闭。关闭可能是主动关闭，审核中可能只是暂时状态；这些均以各自分类登记，不认定全部是处罚。空白、陌生或不可识别收益文字记为 **收益待核对**。明确识别到“On/开启”等状态时不因收益列单独列为异常，但不保证其他政策和版权状态正常。

## 检测范围

**普通YouTube Data API不提供黄标、广告适宜性评级、完整收益状态或完整Content ID版权限制。** 所以收益检测依赖登录后的Studio网页可见内容，不能只靠OAuth扫描。

- API检查上传列表，识别全球/地区禁播、上传被拒、失败、删除、年龄限制及详情缺失。私密、未列出、禁止嵌入、licensedContent不单独作为禁播或收益受限。
- Studio收益检查目前只翻阅 **内容 → 视频** 普通视频列表，**不覆盖Shorts、直播或其他标签页**。这是男频长篇短剧常用的列表。
- Studio界面可能变化，收益列缺失或文字无法识别时登记待核对；登录失败、频道不匹配、视频ID无法读取或无法确认翻页完成时，整次扫描报错，不覆盖上一份成功Excel。
- 收益文字支持部分中英及其他语种标签，不承诺覆盖所有界面语言。建议Studio界面使用中文或英文。未知标签不会被当成正常。
- 内容列表查不到、被删除或已经不在上传列表中的视频，无法保证覆盖；普通API无禁播标记也不代表Studio不存在版权封锁。程序不会自动处理申诉或广告适宜性自评。
- 程序中的代理用于Google API；Edge访问Google使用Windows/浏览器自身的网络或VPN配置。若API能连但Studio打不开，请检查本机浏览器网络。

## 报告与重试

每频道独立保存在 `blocked_reports/频道ID/`：

- `blocked_videos.xlsx`：主交付Excel。
- `revenue.csv`：本次Studio收益异常及待核对记录。
- `blocked_videos.csv`：API禁播/被拒记录。
- `attention.csv`：其他API异常；`all_videos.csv`：全部API记录。
- `newly_detected.csv`：仅API禁播/被拒相对上次的新增或原因变更，不含收益变更统计。
- `report.html`：本地报告；`latest.json`及`scan_时间戳.json`保留检测范围与快照。

真实Excel须在你的电脑完成授权登录后生成，不会自动发回聊天。失败时请核对检测时间，不要把上次报告当成本次结果。失败可以修复登录/网络后重扫；本工具全程只读，无需担心重扫修改视频。不要同时运行多个实例检查同一频道。

OAuth使用独立 `token.*.monitor.json` 和youtube.readonly权限，不覆盖发布程序令牌。Studio独立浏览器仅使用页面读取与翻页，不点击收益开关，不改变视频设置。

## 命令行

仅普通API（无法检测收益）：

```sh
python blocked_monitor.py --config profiles/english.json
```

包含Studio收益检查（需要安装requirements.download.txt、浏览器及图形桌面）：

```sh
python blocked_monitor.py --config profiles/russian.json --studio
```

可用 `--studio-browser chrome` 选择本机Chrome；默认auto自动查找。`--output 目录` 指定报告根目录，`--reauth` 重新授权。无定时轮询参数。

## 验证

已通过离线与模拟测试，覆盖API分页/只读、分类、失败保留、Excel去重和文字安全，以及收益标签分类、未知状态、合并Excel及未检查标记。**未在用户真实Studio页面验证网页选择器、分页或实际黄标状态**；首次请对照Studio人工检查几条已知受限视频和Excel。网页无法识别时会报错或登记待核对，不能宣称收益全部正常。

## 找不到Edge / msedge.exe

新版浏览器默认选auto：查找系统级和用户级Edge/Chrome安装位置，再尝试已安装的专用Chromium，不再只依赖当前用户的Edge路径。

- 电脑已有浏览器：在“选择浏览器EXE”中选择真实的 `msedge.exe` 或 `chrome.exe`，不要选择桌面快捷方式。常见位置为 `C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe` 或 `C:\Program Files\Google\Chrome\Application\chrome.exe`。
- 没有可用浏览器：关闭程序，双击包内 **install_monitor_browser_windows.bat** 安装专用Chromium，再启动 **start_monitor_windows.bat**，浏览器保持auto。安装失败会保留错误提示，可检查网络或改用已安装的浏览器。
- 切换浏览器后可能需要重新登录Studio。程序使用自己的独立登录目录；请先关闭上次打开的程序浏览器窗口，避免登录目录占用。
- 浏览器查找、路径选择、缺失提示和启动失败处理已用模拟测试验证；没有在你的Windows机器执行安装或真实浏览器启动。
