# 功能测试与覆盖率

维护者在 [PR #209 的 review](https://github.com/OlivOS-Team/OlivOS/pull/209#issuecomment-5771809901)
要求构建时运行测试，失败时阻止继续构建。本目录统一使用 pytest；一个独立行为对应一个
`test_*` 函数，同一行为的格式、平台或输入边界使用参数化，不把所有功能串在一个大型流程里。

## 运行

使用 Python 3.11 和项目已有依赖。Linux/macOS：

```sh
python -m pip install '.[test]'
python -m pytest
```

Windows 安装 `.[test,win]`。不需要真实机器人账号或平台凭据；文件写入测试临时目录，
平台请求使用替身，本地 HTTP/WebSocket 测试监听回环地址和临时端口。

Chrome 浏览器测试单独通过环境变量开启。Linux CI 自动安装兼容的 Chrome 和 ChromeDriver：

```sh
OLIVOS_WEBUI_BROWSER=1 python -m pytest -m browser
```

PowerShell 使用 `$env:OLIVOS_WEBUI_BROWSER='1'` 后运行同一 pytest 命令。
已有浏览器/驱动可通过 `OLIVOS_CHROME_BINARY`、`OLIVOS_CHROMEDRIVER` 指定路径。
原生 Tk 界面用例只在 Windows 运行，窗口保持隐藏；不启动托盘或真实协议程序。

## 覆盖率

```sh
python -m pytest --cov=OlivOS --cov-branch --cov-context=test \
  --cov-report=term --cov-report=xml:test-results/coverage.xml \
  --cov-report=html:test-results/html --cov-report=json:test-results/coverage.json \
  --junitxml=test-results/junit.xml
python script/coverage_summary.py test-results/coverage.json
```

HTML 入口为 `test-results/html/index.html`，可查看每个文件执行过/未执行的行、缺失分支，
以及经过该行的测试上下文。XML 供覆盖率工具读取，JSON 用于统计，JUnit XML 用于定位失败用例。
CI 上传这些报告和原始 `.coverage`，并在 job summary 中列出行、分支覆盖率及缺口最大的模块。

统计范围为整个 `OlivOS/` Python 代码，含未执行的协议适配器和平台专用代码。
仅排除第三方内置库、二进制/图片内嵌数据和生成的 `staticData.py`，不排除难测的业务代码。
Python 覆盖率不计量 JavaScript；前端行为由真实浏览器用例验证。
不同平台的报告分别保存，不能简单平均成一个全平台覆盖率。

2026-09-22 本地验收基线（Windows、干净 Python 3.11 环境，同时开启 Chrome）：
21 个测试文件、177 个独立测试函数，经参数化后 **413 项通过，0 失败、0 跳过**。
行覆盖率 **34.43%**（10352/30067），分支覆盖率 **16.15%**（1799/11142），
coverage.py 行与分支综合指标 **29.49%**。此基线不是远端 Linux/ARM64 CI 的执行结果。

当前先建立真实基线，不设置未经评估的全仓库百分比门槛。后续改良优先顺序：

1. 新缺陷先添加能够失败的回归测试，再修复，保留能验证用户行为的断言。
2. 根据缺失行/分支报告补齐常用 SDK 的发送请求、错误响应、超时和连接重试。
3. 补充启动调度、协议进程停止与重建、原生账号编辑的完整交互。
4. 核心模块基线稳定后，评估分模块覆盖率门槛，避免单纯用导入、常量断言或扩大排除项提高数字。

## 功能与用例映射

| 功能范围 | 测试文件 | 检查内容 |
| --- | --- | --- |
| 账号配置 | `test_accounts.py` | 保存/读取、启停过滤、身份隔离、安全读取、端口分配 |
| 消息结构 | `test_messages.py` | CQ/OP、OneBot V12、Milky、文本/提及/媒体/轻应用转换、无效输入 |
| 插件调度 | `test_plugin_dispatch.py` | 调用顺序、阻断、平台过滤、异常捕获、未知账号和重载请求 |
| 插件 WebUI 资源 | `test_opk_webui_lifecycle.py` | 源码/OPK、路径与 namespace、init 资源、重载/卸载、文件占用、越界和链接限制 |
| 账号与 SDK 边界 | `test_adapters.py` | 20 个适配器的账号映射、OneBot 消息/通知/请求、虚拟终端、活动时间、QQ webhook 验签 |
| 全部 SDK 事件 | `test_sdk_events.py` | 全部 20 个事件入口的事件映射、文本转换、不支持输入及后续恢复；新增 SDK 漏测检查 |
| 协议连接 | `test_onebot_connection.py` | 反向 WebSocket 认证、断开后取消另一任务及连接计数 |
| QQ 官方机器人消息 | `test_qqguildv2_messages.py` | 图片卡片、合并转发、未知卡片类型与无效图片回退 |
| QQ 官方机器人分享链接 | `test_qqguildv2_share_links.py` | 请求构造、输入限制与服务端失败响应 |
| 协议启动器 | `test_protocol_booters.py` | Windows 启动器日志路由、NapCat 配置生成，不运行外部程序 |
| 数据存储 | `test_user_database.py`, `test_legacy_config.py` | SQLite 持久化/隔离/并发/序列化，以及旧用户/群配置接口 |
| 启动与辅助功能 | `test_boot_and_metadata.py` | 配置合并、启动顺序、元数据、本地化、资源定位、更新请求与进程终止边界 |
| 日志 | `test_logging.py` | 文本清理、队列满、等级过滤、文件批量写入、GUI 转发 |
| 原生终端 | `test_native_terminal.py` | 坏历史记录、特殊字符串、控件异常、限频与轮转、后续记录继续显示 |
| 原生账号管理 | `test_native_accounts.py` | 托盘入口、编辑草稿隔离、新建/修改/删除、保存与热重载总线 |
| WebUI 后端 | `test_webui.py` | HTTP/WS 认证、账号保存与状态、日志与终端、插件事件、监听端口和重启反馈 |
| WebUI 登录 | `test_webui_auth.py` | 凭据生命周期、并发登录、重启、错误提示、短暂断网和跨标签退出 |
| WebUI 导航 | `test_webui_navigation.py` | 分组、重名、页面保活、消息回包、关闭、刷新恢复、响应布局、外部链接 |
| WebUI 环境配置 | `test_webui_environment.py` | 监听覆盖、无效输入、端口 0 与实际监听地址 |
| 插件消息桥 | `test_webui_plugin_template.py` | 宿主菜单事件、浏览器 payload、会话隔离回包，无相邻仓库依赖 |

SDK 最低覆盖统一放在 `test_sdk_events.py`，参数化测试名称会显示具体 SDK。
覆盖 OneBot V11/V12、Milky、虚拟终端、QQ Guild/V2、Discord、Telegram、Fanbook、
DoDo Poll/Link/EA、KOOK、黑盒语音、B站直播、OPQ、米游社大别野、Red、hackChat 和钉钉。
每个入口都实际执行 SDK 事件构造、`OlivOS.API.Event` 分发和消息转换；网络访问被禁止，
需要远端查询的机器人/成员资料通过缓存或查询替身提供，不替换事件转换函数。
未知事件应被忽略，后续正常消息仍可处理；DoDo EA 没有事件类型字段，改测不合法的消息记录。
对不存在相同功能的平台，不强行套用 QQ 分享链接或其他平台特有接口测试。

这是必要功能的初始回归集合，不代表所有平台接口和实际连接场景均已验证。
真实平台登录、外部可执行文件安装、服务端协议变化、完整重连和完整桌面操作仍有覆盖缺口。
旧 `IOStream` 输入流实现尚无功能覆盖，其历史文件操作/状态机需要单独梳理；该文件仍计入覆盖率分母。

## 旧测试取舍

- 保留已跟踪的认证、导航、OPK 和环境测试；把浏览器大流程拆成独立功能用例。
- 纳入原先被 `.gitignore` 忽略的 WebUI 后端与 QQ 分享/卡片测试；修正旧网页 URL、
  缺失的资源声明和文本换行假设；去除对工作目录下真实配置文件的依赖。
- 旧模板测试依赖仓库旁边的 `OlivOSPluginTemplate`，不能在干净 checkout 运行。
  用自包含的消息桥测试替换，OPK 加载与挂载交给已有生命周期测试，避免重复。
- 移除调用不存在的 `sync_plugins` 的三个草稿测试。当前默认启动顺序先创建 WebUI、后启动插件，
  由启动顺序和真实广播转发测试覆盖；没有为了让旧断言通过而新增生产接口。
- 原始本地测试在整理前已做恢复备份；缓存、覆盖率数据与测试报告保持忽略，测试源码不再忽略。

## CI 与构建关系

`test.yml` 是可复用 workflow，`build.yml`、`build-dispatch.yml`、`pypiPublish.yml` 的构建 job
通过 `needs: tests` 等待测试成功。测试失败不会进入后续构建或发布；失败报告仍上传。
保留上游新合并的 Linux ARM64 构建与产物发布逻辑。

测试矩阵：Python 3.11，Linux x64（含 Chrome）、Linux ARM64、Windows（含原生 GUI）。
这是构建前的公共功能检查，不表示已在每个旧 Python 构建版本上运行测试。
发布权限和发布动作沿用已有 workflow，测试只需仓库只读权限。
