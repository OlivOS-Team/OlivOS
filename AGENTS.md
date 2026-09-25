# AGENTS.md

面向在本仓库中工作的 AI Coding Agent。仓库中不存在 `CLAUDE.md` / `CONTRIBUTING.md`，
因此本文件是唯一的 Agent 指令来源。

- `README.md` 面向使用者，不能当作开发规范。
- `tests/README.md` 是测试策略、用例映射与覆盖率现状的权威说明，改测试前必读。
- 插件侧公开契约（框架事件、消息格式、插件/进程接口、WebUI 页面）的权威文档在 `OlivOSDoc` 文档仓库
  （`OlivOS-Team/OlivOSDoc`，即 OlivOS README 链接的文档站源码）。若工作区中同时存在该仓库，
  改这些面向前插件的接口前先读 `docs/DevPlugin/*`；插件开发模板是 `OlivOS-Team/OlivOSPluginTemplate`。
- 本文件中的结论来自源码、配置与 CI 文件；如果源码与本文件冲突，以源码为准，并顺手更正本文件。

## 0. 三条硬性前提

1. **兼容性优先于美观（Compatibility > aesthetic refactoring）。** OlivOS 有大量仓库外插件与历史代码，
   公共行为一旦破坏，代价远高于“代码更整洁”。
2. **先找现有抽象与调用方，再动手。** 不要新建平行的 Event / Dispatcher / Plugin Context / Adapter /
   Message / Queue 体系；仓库里已经有承担这些职责的对象（见第 5 节）。
3. **只用可验证的信息下结论。** 不要因为目录叫 `adapter` 就推定分层，不要因为项目是 Python 就假定
   asyncio / pytest / type hints / 现代 packaging——都必须逐项从仓库确认。

## 1. 项目速览

OlivOS（Witness Union）是一个跨平台异步文本流交互栈：把即时通讯、直播弹幕、网络聊天室、
命令行等场景统一到「多进程 + 消息队列 + 插件」的模型中。

启动链路：

```text
main.py
  → OlivOS.bootAPI.Entity(basic_conf='./conf/basic.json', patch_conf='./conf/config.json').start()
  → 读取/合并配置 → 创建队列 → Control 主循环按 model 的 type 逐个初始化进程
```

核心特征（均已验证）：

- 常驻组件几乎都继承 `OlivOS.API.Proc_templet`，以线程或子进程方式运行（`start_unity`）。
- 组件之间通过 `multiprocessing.Queue` 传递 `OlivOS.API.Control.packet`，由 `bootAPI` 主循环路由。
- 平台差异集中在 `OlivOS/adapter/*`；通用抽象集中在 `OlivOS/core/*`。
- 插件从 `./plugin/app/` 加载，通过 `plugin.main.Event` 的回调接收 `OlivOS.API.Event`。

## 2. 常用命令

在仓库根目录执行（路径依赖当前工作目录，见第 8 节）：

```bash
pip install .                # 运行依赖
pip install .[dev]           # flake8 / black / ruff / pytest
pip install .[test]          # pytest / pytest-cov / selenium（Windows 用 .[test,win]）

python main.py               # 启动
python -m pytest             # 全量功能测试（默认离线，不需要真实账号）
python script/flake8_check.py            # CI 使用的风格检查，输出 flake8_output.log
python script/embed_webui.py             # 重新内嵌 WebUI 前端资源到 staticData.py
```

浏览器用例（真实 Chrome）与覆盖率统计：

```bash
# Linux/macOS
OLIVOS_WEBUI_BROWSER=1 python -m pytest -m browser
# PowerShell
$env:OLIVOS_WEBUI_BROWSER='1'; python -m pytest -m browser

python -m pytest --cov=OlivOS --cov-branch --cov-context=test \
  --cov-report=term --cov-report=xml:test-results/coverage.xml \
  --cov-report=html:test-results/html --cov-report=json:test-results/coverage.json \
  --junitxml=test-results/junit.xml
python script/coverage_summary.py test-results/coverage.json
```

CI 顺序为 **Lint → Test → Build**（`.github/workflows/build.yml`），任何一个前置阶段失败后面都不会跑。
`lint.yml` 会额外执行 `python ./script/embed_webui.py` 并 `git diff --exit-code -- OlivOS/webUI/staticData.py`。

## 3. 仓库结构

| 路径 | 职责 |
| --- | --- |
| `main.py` | 启动入口，构造 `bootAPI.Entity`。 |
| `OlivOS/__init__.py` | 总装配：导入全部 core 模块与 adapter，并把 `OlivOS.xxxSDK` / `OlivOS.xxxLinkServerAPI` 等名字暴露到包命名空间。 |
| `OlivOS/core/core/API.py` | 通用运行核心：`Control` / `Control.packet`、`bot_info_T`、`Event`、`Proc_templet`、`StoppableThread`。 |
| `OlivOS/core/core/pluginAPI.py` | 插件加载与调度器 `shallow`、全局 `gProc`、`rx_packet`。 |
| `OlivOS/core/core/messageAPI.py` | `Message_templet` 与 `PARA` 消息段（CQ / OP / OBV12 / Milky / 各平台字符串）。 |
| `OlivOS/core/core/accountAPI.py` | 账号读写、启停过滤、`accountFix`、端口分配。 |
| `OlivOS/core/core/accountMetadataAPI.py` | 账号编辑元数据（sdk/platform/model/server type 的合法组合），GUI 与 WebUI 依赖它。 |
| `OlivOS/core/core/diagnoseAPI.py` | 日志进程 `logger`、日志分级、终端/文件输出模式。 |
| `OlivOS/core/core/{contentAPI,metadataAPI}.py` | API 结果模板与事件日志元数据表。 |
| `OlivOS/core/boot/bootAPI.py` | 配置加载、队列创建、主控制循环、各 `type` 模型的进程装配、进程清理。 |
| `OlivOS/core/boot/bootDataAPI.py` | `default_Conf`：队列名、模型表、`init` 顺序与 `account_update` 事件表。 |
| `OlivOS/core/{web,L10N,info,inlineData}` | 更新检查与 web 工具、本地化、版本常量、内嵌二进制资源（`inlineData/data.py` 勿手改）。 |
| `OlivOS/adapter/*` | 具体协议接入：SDK 事件映射、协议 API、连接/会话进程。 |
| `OlivOS/userModule/UserConfDB.py` | 插件配置数据库（SQLite），按插件 namespace 建表。 |
| `OlivOS/webUI/*` | 浏览器 UI 后端（Flask + WebSocket + gevent）、页面资源缓存、`staticData.py`（生成物）。 |
| `OlivOS/nativeGUI/*` | Windows 原生 GUI（Tk 终端、托盘、pywebview）。 |
| `OlivOS/libBooter/*` | Windows 下启动/管理外部协议程序（NapCat、go-cqhttp 等）。 |
| `OlivOS/thirdPartyModule/*` | 内置第三方实现（blivedm、mhyVilaProto）；不基于 PyPI 引入的第三方模块统一放这里，flake8 与覆盖率均排除。 |
| `plugin/{app,conf,data,tmp}` | 插件目录；`app` 放源码或 `.opk`，运行期数据在 `data/<namespace>/`。 |
| `conf/` | `account.json`、`config.json`（补丁配置）；`basic.json`、`webui_token.txt` 由运行期生成。 |
| `script/` | 打包、flake8 检查、WebUI 资源内嵌、覆盖率汇总脚本。 |
| `tests/` | pytest 功能测试，策略见 `tests/README.md`。 |
| `hook/` | PyInstaller 运行时 hook。 |

## 4. 架构与数据流

### 4.1 入站：平台 → 插件

```text
平台
 → adapter 的连接进程（*LinkServerAPI.py / *HostServerAPI.py / *PollServerAPI.py /
   *WebhookServerAPI.py / flaskServerAPI.py）维护会话、收发原始报文
 → adapter 的 SDK event 对象（如 onebotSDK.event(raw)），自带 platform={'sdk','platform','model'}
 → OlivOS.pluginAPI.shallow.rx_packet(sdk_event) 包装后放入协议进程的 Proc_info.tx_queue
   （即全局 OlivOS_rx_queue）
 → 插件进程 shallow.run() 取出，构造 OlivOS.API.Event(sdk_event)
 → API.Event.get_Event_from_SDK() 按 sdk_event 的具体类型分派到对应 SDK 的 get_Event_from_SDK()
   设置 base_info / platform / plugin_info['func_type'] / data
 → API.Event.get_Event_on_Plugin() 按插件 message_mode / compatible_svn 生成插件可见的 message
 → shallow.run_plugin() 用 bot_hash 找 bot_info、按插件 support 过滤、按 priority 顺序调用
   plugin_event_router() → plugin.main.Event.<func_type>(plugin_event=..., Proc=...)
```

回调抛异常会被捕获、记 ERROR 日志并 `plugin_event.set_block()`，不会中断其它插件。

### 4.2 出站：插件 → 平台

```text
插件
 → plugin_event.reply(...) / send(send_type, target_id, message, host_id=...) /
   delete_msg(...) / get_...(...)        （OlivOS.API.Event 的公共方法）
 → API.Event 内部按 platform['sdk'] + platform['model'] 分派到 adapter 的 event_action
   （部分 sdk 还要用 onebotV11LinkServerAPI.gCheckList 之类的名单区分模型）
 → adapter 的 api 对象（如 onebotSDK.api.send_msg）决定通信方式：
   · HTTP/Post 模型：直接 requests 请求平台；
   · WebSocket/链接模型：把 Control.packet('send', {...}) 放入
     plugin_event.plugin_info['control_queue']（全局控制队列）
 → bootAPI 主控制循环按 target.type（模型 type，如 'onebotV11_link'）与可选 target.hash
   （账号 bot hash，用于一个账号一个进程）投递到目标进程的 control_rx_queue 和/或 rx_queue
 → 协议进程的发送循环（如 link server 的 tx_link）从 rx_queue 取出并写回网络
```

`dodobot_ea` 是例外：它不经过全局控制队列，而是直接写 `plugin_event.plugin_info['tx_queue']`。

### 4.3 platform 三元组（最容易误判的地方）

每个 SDK event 自带 `platform = {'sdk': ..., 'platform': ..., 'model': ...}`，它同时决定：
插件 `support` 过滤、`API.Event` 的出站分派、账号 hash 识别。

`sdk` **不对应** adapter 目录。已确认：`onebotSDK`、`onebotV12SDK`、`milkySDK`、`OPQBotSDK`、
`qqRedSDK` 都上报 `sdk='onebot'`，靠 `model` 区分（`default` / `onebotV12` / `milky_default` /
`opqbot_default` / `red`）。

结论：不要把 OlivOS 等同于 OneBot；不要在通用代码里写 `sdk == 'onebot'` 就当成 OneBot V11；
不要把某个平台的私有字段塞进通用 `Event` 或 `Message_templet`。

### 4.4 进程与队列模型

- `Proc_templet` 提供：`Proc_info.rx_queue`（数据面）、`tx_queue`、`control_queue`（全局控制队列）、
  `control_rx_queue`（进程内控制收件箱）、`logger_proc`、`scan_interval`、`dead_interval`。
- 队列方向是**从协议进程视角**命名的，容易反直觉：对 `*_link` 进程，**入站**事件经
  `Proc_info.tx_queue` 进入全局 `OlivOS_rx_queue`；**出站**指令从 `Proc_info.rx_queue` 读出后发给平台。
  改任何队列方向前，先读目标进程的 `run()` / `rx_link()` / `tx_link()`。
- `start_unity(mode)`：`threading` → `start_lite()`（`StoppableThread`），`processing` →
  `start()`（`multiprocessing.Process`）。`bootDataAPI.default_Conf` 中模型的 `type` 与
  `system.proc_mode` 决定实际模式；Windows 下依赖 `multiprocessing.freeze_support()`。
- 跨进程通信只传可 pickle 的对象（`Control.packet`、SDK event、简单数据结构）。不要依赖进程内全局变量；
  `OlivOS.pluginAPI.gProc` 只在插件进程内有效。
- 队列写入普遍采用 `block=False` + 捕获异常后丢弃（`rx_link` 在队列满时直接丢弃）。不要单方面把它改成阻塞写。
- `Control.packet('send', {'target': {'type': <模型 type>, 'hash': <bot hash>}, 'data': {...},
  'fliter': 'all'|'control_only'|'rx_only'})` 是标准寻址方式；`fliter` 缺省为 `all`。
  组件实际名称的两种后缀：`=<bot hash>` 指定账号实例，`+<子名>` 指定动态创建的子组件（如按需创建的 webview 页）。
- 控制面与数据面分开：`on_control_rx()` 只接收控制包，`rx_queue` 承载数据。混用会导致状态机错乱。

### 4.5 抽象边界

- `OlivOS/core/core/API.py` 只做编排，不发起网络请求（该文件没有 requests/websockets/flask 导入）。
- 协议 I/O 只在 `OlivOS/adapter/*`；WebUI 与更新检查的网络访问在 `OlivOS/webUI/*`、
  `OlivOS/core/web/updateAPI.py`。
- 通用抽象在 core：Event / Proc / Queue / Message / Plugin API / 账号 / 日志 / L10N。
- 具体协议对象、模型差异、平台 API 在 adapter。
- `OlivOS.API.inde_interface_T`（及其子类，如 `kaiheilaSDK.inde_interface`、
  `qqGuildv2SDK.inde_interface`、`mhyVilaSDK.inde_interface`）是「该平台独有能力」的入口，
  插件通过 `plugin_event.indeAPI.hasAPI(...)` 探测后调用。平台独有能力不要提升为通用 Event 方法。

## 5. 修改前必须知道的现有抽象

| 需求 | 现有抽象（复用，不要重造） |
| --- | --- |
| 事件分发、回复、发消息、平台查询 | `OlivOS.API.Event`（`reply` / `send` / `delete_msg` / `get_*` / `set_*`） |
| 长驻组件与线程/进程 | `OlivOS.API.Proc_templet`、`StoppableThread`、`Proc_start` |
| 控制包与寻址 | `OlivOS.API.Control` / `Control.packet` |
| 插件加载、调度、阻断、重启 | `OlivOS.pluginAPI.shallow`、`plugin_event.set_block()`、`Proc.set_restart()` |
| 消息解析与生成 | `OlivOS.messageAPI.Message_templet`、`PARA`、`PARA_templet` |
| 账号配置 | `OlivOS.accountAPI`、`OlivOS.accountMetadataAPI` |
| 日志 | `OlivOS.diagnoseAPI.logger`；组件内用 `self.log(level, msg, segment)` |
| 插件配置持久化 | `OlivOS.userModule.UserConfDB.DataBaseAPI`（`Proc.database`） |
| 本地化文案 | `OlivOS.L10NAPI.getTrans(...)` |
| 版本与兼容闸门 | `OlivOS/core/info/infoAPI.py` 的 `OlivOS_Version` / `OlivOS_SVN` / `OlivOS_SVN_Compatible` |

新增功能前先在这些文件里 `rg` 同类实现；如果在两处看到同义逻辑，优先抽到已有抽象而不是再造一个。

## 6. 插件系统

- 插件位于 `./plugin/app/`，可以是源码目录或 `.opk`（zip）；加载器递归查找 `app.json`，最大深度 10。
- `app.json` 必填：`priority`、`name`、`support`；可选：`namespace`（缺省用目录名）、`menu_config`、
  `webui_config`、`message_mode`、`author`、`svn`、`version`、`info`、`compatible_svn`。
- 插件必须有 `main.Event`，否则被跳过；模块导入异常也同样跳过并记日志。插件以顶层模块导入
  （`plugin/app`、`plugin/tmp` 会在 `pluginAPI` 导入时被加入 `sys.path`），模块名/namespace 冲突
  会按 Python 的模块覆盖规则互相影响，命名时避免与现有插件重名。
- 调用顺序按 `(priority, namespace)` 排序（`priority` 小的先执行）；同一事件中插件可
  `plugin_event.set_block()` 阻断后续插件。
- 过滤依据 `support` 列表，每项形如 `{'sdk': ..., 'platform': ..., 'model': ...}`，`'all'` 为通配。
- 框架回调：`init`（插件导入成功后）、`init_after`（全部插件加载后）、`save`（自动重启前）、
  `menu`（菜单事件）。另外加载器会把插件自带的 `data/` 复制到 `plugin/data/<namespace>/data`
  （时机在单个插件的 `init` 之后、全局 `init_after` 之前；日志里写作 `release_data`，
  但这不是插件需要实现的函数）。
- 事件回调名必须落在 `API.Event` 已支持的 `func_type` 集合内：
  `private_message`、`private_message_sent`、`group_message`、`group_message_sent`、
  `group_file_upload`、`group_admin`、`group_member_decrease`、`group_member_increase`、`group_ban`、
  `group_message_recall`、`private_message_recall`、`poke`、`group_lucky_king`、`group_honor`、
  `friend_add`、`friend_add_request`、`group_add_request`、`group_invite_request`、`lifecycle`、
  `heartbeat`、`menu`。
  新增 `func_type` 必须同时改 `API.Event.do_init_log`、`pluginAPI.plugin_event_router` 与相关 SDK 映射。
  `fake_event` 不是插件回调：它由 `contentAPI.fake_sdk_event` 生成，用于在事件之外主动调用接口。
- 插件看到的消息格式由 `message_mode` 决定（缺省 `old_string`，即 CQ 码；另有 `olivos_string`、
  `olivos_para`、`obv12_para`、`milky_para_*` 等）。`compatible_svn < OlivOS_SVN_Compatible` 时，
  `get_Event_on_Plugin()` 会为老插件裁剪字段（如 at 段移除 `name`），不要绕过这一步。
- 插件需要在事件之外主动发消息或调用接口时，按官方做法构造 `OlivOS.API.Event(
  OlivOS.contentAPI.fake_sdk_event(bot_info=Proc.Proc_data['bot_info_dict'][bot_hash], fakename=...),
  Proc.log)`（见 `docs/DevPlugin/Note.md`），不要自行伪造 SDK event，也不要复用过期的事件对象。
- CQ/OP 码是 `[CQ:类型,参数=值]` / `[OP:类型,参数=值]` 文本；参数值里的 `&`、`[`、`]`、`,` 必须按
  HTML 实体转义（`&amp;`、`&#91;`、`&#93;`、`&#44;`）。构造或解析这类字符串时不要跳过转义规则。
- 插件 WebUI 页面的请求复用 `Event.menu`（不是新回调）：网页请求带 `plugin_event.data.webui`
  （`request_id` / `payload` / 宿主管理的 `session`）和 `payload`，回包用
  `plugin_event.send('webui', request_id, payload)`；此时 `bot_info` 为 `None`，`session` 不得写日志或返回页面。
  细节见 `docs/DevPlugin/WebUI.md`。
- 插件数据在 `./plugin/data/<namespace>/`，`UserConfDB` 的 SQLite 文件在 `./plugin/conf/UserConfAll.db`；
  OPK 会先解包到 `plugin/tmp/` 再按 namespace 重命名，导入完成后清理。
- `message_mode`、`compatible_svn`、`func_type`、`data.message` / `data.raw_message` 的既有语义
  属于插件生态的公共契约。历史插件会用 `[CQ:xxx]` 字符串做正则匹配（见 `tests/test_adapters.py`
  的 NapCat 用例），任何改动都要面向“老插件仍能工作”评估。

## 7. Adapter / 协议 / SDK 分层

### 7.1 各文件角色

| 文件 | 角色 |
| --- | --- |
| `adapter/<x>/<x>SDK.py` | 协议事件 → OlivOS 事件的映射（`get_Event_from_SDK`）、`platform` 三元组、供通用 API 调用的 `event_action`、协议 `api` 类、`get_SDK_bot_info_from_Plugin_bot_info` / `get_SDK_bot_info_from_Event`。 |
| `adapter/<x>/*LinkServerAPI.py` | 客户端连接型协议（正向 WS/HTTP 会话），维护连接、重连、收发队列。 |
| `adapter/<x>/*HostServerAPI.py` | 反向 WebSocket 服务端（等待平台接入）。 |
| `adapter/<x>/*WebhookServerAPI.py` | HTTP 回调型协议（如 QQ 官方机器人，含 Ed25519 验签）。 |
| `adapter/<x>/*PollServerAPI.py` | 轮询型协议（Telegram、Fanbook 等）。 |
| `adapter/onebotV11/flaskServerAPI.py` | OneBot HTTP 上报入口。 |
| `adapter/<x>/*Type.py` | 协议类型定义/枚举（如 `milkyType.py`）。 |

命名与依赖约定（`docs/DevGuild/File.md`，源码亦符合）：`**SDK.py` 实现协议本身，`**API.py` 负责
运行时并尽量只调用本 adapter 的 SDK；文件名形如 `{协议名}{连接方式}ServerAPI.py`，WebSocket 用
`Link`、长轮询用 `Poll`（早期模块如 `onebotV11/flaskServerAPI.py` 不遵守）。不同 adapter 之间不要交叉调用。

### 7.2 判定规则

- 一个 adapter 可以覆盖多个 `model`：`onebotSDK.py` 用 `napcatModelMap`、`llonebotModelMap`、
  `lagrangeModelMap`、`paraMsgMap`（含 Shamrock）等名单区分实现差异。
  **改 `onebotSDK.py` 等于同时改多个平台实现，必须逐个核对模型名单。**
- 出站能力是否可用由「SDK + gCheckList」共同决定（例如 `onebotV11LinkServerAPI.gCheckList`、
  `onebotV11HostServerAPI.gCheckList`、`flaskServerAPI.gCheckList` 分别列出各自支持的模型）。
- 网络 I/O 只允许出现在协议进程/线程或 SDK 的 HTTP 调用路径中；不要在 `core/`、插件回调、
  主控制循环里做阻塞网络请求。

### 7.3 新增一个 adapter 需要经过的层（缺一不可）

1. `OlivOS/adapter/<name>/`：`__init__.py` + SDK + 连接/服务进程文件。
2. `OlivOS/adapter/__init__.py` 注册子包。
3. `OlivOS/__init__.py` 导出 `OlivOS.<name>SDK` / `OlivOS.<name>LinkServerAPI` 等名字
   （SDK 之间通过 `OlivOS.xxxSDK` 互相引用，漏了会 ImportError）。
4. `OlivOS/core/core/accountMetadataAPI.py`：账号编辑元数据（sdk / platform / model / server type）。
5. `OlivOS/core/boot/bootDataAPI.py`：`default_Conf` 的 `system.init`、`system.event.account_update`、
   `system.type_event`、`queue`、`models`（含 `rx_queue` / `tx_queue` / `control_queue` / `logger_proc`）。
6. `OlivOS/core/boot/bootAPI.py`：按新 `type` 增加装配分支（按账号过滤、一账号一进程、队列名
   `<queue>=<bot_hash>` 的约定）。
7. `OlivOS/core/core/API.py`：`Event.get_Event_from_SDK()` 分支、必要时 `__init_inde_interface()`、
   以及出站分派（`__send` / `delete_msg` / `get_*` …）。
8. `OlivOS/core/core/messageAPI.py`：若协议有专属消息格式，增加 mode 与 PARA 转换。
9. `tests/test_sdk_events.py`（`SDK_PLATFORMS` + fixture；有测试强制覆盖全部分发分支）与
   `tests/test_adapters.py`（账号映射等）。
10. 需要新文案时补 `OlivOS/core/L10N`；需要 WebUI 页面时在 `app.json` 的 `webui_config` 声明。

## 8. 配置系统

- `conf/basic.json` 是基础配置；`conf/config.json` 是补丁配置，启动时由 `bootAPI.get_patch_config`
  深合并；两者不存在时退化为 `bootDataAPI.default_Conf`。
- 队列名、模型表、初始化顺序、账号更新时要通知哪些模型，全部由 `default_Conf` + `bootAPI` 的分支共同决定，
  两边必须保持一致。
- `conf/account.json` 存账号（`id` / `enable` / `password` / `sdk_type` / `platform_type` /
  `model_type` / `server` / `extends` / `debug`）；字段合法性由 `accountMetadataAPI` 约束，
  账号读取/保存走 `accountAPI.Account.load/save`，不要自己解析 JSON 后落盘。
- WebUI 监听地址可由环境变量覆盖（`OLIVOS_WEBUI_HOST` / `OLIVOS_WEBUI_PORT`，见
  `webUI/serverAPI.apply_environment_config`）；token 文件默认 `conf/webui_token.txt`。
- 运行期路径都是相对当前工作目录：`./conf`、`./plugin/*`、`./data/*`、`./logfile`、`./lib/*`。
  必须在仓库根目录执行 `python main.py`；测试通过 `tests/conftest.py` 自动 chdir 到临时目录，
  不要在测试或代码里写死仓库绝对路径。
- 只 `import OlivOS` 就会创建 `./plugin/app`、`./plugin/tmp`、`./lib/Lib`、`./lib/DLLs`
  等目录（`pluginAPI` 的模块级副作用）。这是既有行为，不要“优化”掉，也不要在仓库外胡乱运行。
- 不要提交本地运行产物与凭据：`conf/basic.json`、`conf/webui_token.txt`、`conf/*.webui-backup`、
  `logfile/*`、`data/`、`plugin/{app,conf,data,tmp}/*`、`test-results/`、`flake8_output.log`。

## 9. 版本与兼容性

- 运行期版本与兼容闸门在 `OlivOS/core/info/infoAPI.py`：
  `OlivOS_Version`、`OlivOS_SVN`、`OlivOS_SVN_Compatible`、`OlivOS_SVN_OldCompatible`、
  `OlivOS_compatible_svn_default`。插件 `compatible_svn` 低于 `OldCompatible` 会被跳过，
  介于两者之间会告警；改变事件字段/行为时应考虑是否需要抬升 `OlivOS_SVN_Compatible`。
- 版本号分散在 `pyproject.toml`（`[project].version`）、`setup.py`（`version`）与
  `infoAPI.OlivOS_Version`，`pypiPublish.yml` 使用 `setup.py` 发布。三者当前并不一致。
  除非任务明确要求发版，**不要顺手改版本号**；必须改时至少要核对这三处与发布工作流。
- 仓库没有成文的分支/发版规范。提交历史显示改动经 PR 合入（如 `Merge pull request #214 from
  Desom-fu/dev`），提交信息使用 Conventional Commits（`fix(onebot):`、`feat(webUI):`、`ci:`、
  `test:`、`docs:`，正文多为中文）。跟随这些约定，不要擅自切换分支、变基或合并他人的工作。

### 9.1 改动前必须搜调用方的对象

- Plugin API：`API.Event` 的公共方法、`plugin_event.indeAPI`、`plugin_info` 的键。
- Event 结构：`base_info` / `plugin_info` / `data` 字段与 `func_type` 语义。
- Adapter API：`event_action` / `api` 类名、`gCheckList`、`get_SDK_bot_info_from_*`。
- Message：`Message_templet` 的 mode 字符串与 `PARA` 段字段。
- 配置格式：`conf/*.json` 字段、`default_Conf` 模型字段、`app.json` 字段语义。
- Process / Queue：`Proc_templet` 接口、`Control.packet` 结构与 `target.type` 字符串。
- 插件回调：`init` / `init_after` / `save` / `menu` 的调用时机与参数。

插件在仓库外，`rg` 只能覆盖仓库内调用方。对以上对象优先做**增量修改**：
新增可选参数、新增字段、新增分支；不要重命名、不要改变既有默认值，也不要改变
`data.message` 在既有 `message_mode` 下的取值形态。

## 10. 开发工作流

1. 读本文件；如果改动只涉及 `tests/`，同时读 `tests/README.md`。
2. 判断受影响的子系统（adapter / core / plugin 加载器 / WebUI / 原生 GUI / 构建）。
3. 用 `rg` 搜索仓库中是否已有承担相同职责的实现与抽象。
4. 追一遍相关数据流（入站或出站），确认事件从哪来、进哪个队列、被谁消费。
5. 明确抽象边界：这条逻辑属于通用 core，还是属于具体 adapter/SDK。
6. 列出兼容敏感接口（第 9.1 节），评估改动是否会被老插件感知。
7. 做**最小充分修改**：能加分支就不重写，能加可选参数就不改签名语义。
8. 跑对应验证（第 12 节），行为缺陷先补一个会失败的回归测试再修。
9. 复查 `git diff`：确认没有无关重构、没有本地运行产物、没有多余格式化。
10. 提交信息使用 Conventional Commits，一次提交只做一件事。

## 11. 代码风格

以 **flake8** 为准（CI 只跑 flake8，`python script/flake8_check.py` 实际执行
`python -m flake8 ./`）：

- `max-line-length = 120`，`extend-ignore = E203`。
- 排除 `OlivOS/thirdPartyModule/*`、`build/*`、`dist/*`。
- 豁免：`__init__.py` 与 `OlivOS/hook*.py` 的 F401；`OlivOS/core/inlineData/*` 的 E501；
  `qqGuildv2SDK*.py` 的 F403/F405。
- `pyproject.toml` 里还有 black（`line-length=120`、`skip-string-normalization`）与 ruff
  （`select = E,W,F,I,B,C4,UP`、`quote-style = single`）的配置，但 CI 不强制。
  **不要对既有文件做全量格式化**：那会产生无法审查的 diff。只让改动的行与上下文风格一致。

历史代码风格（跟随所改文件的现状，不要强行现代化）：

- 文件头有固定 banner（`@File` / `@Author` / `@Contact` / `@License` / `@Copyright` / `@Desc`），新建文件沿用相邻文件格式。
- 命名：模块/函数 `snake_case`；类 `CamelCase`；数据结构常用 `*_T` 或 `*_templet` 后缀（含历史拼写
  `templet`，保持一致）；布尔变量 `flag_xxx`；临时变量 `tmp_xxx`；模块级名单 `gXxx`；
  模块级 `modelName` 常量用于日志分段。
- 字符串多用单引号；注释、docstring、日志文案以中文为主。
- 类型标注只出现在较新的模块（如 `adapter/*LinkServerAPI.py`、`userModule/UserConfDB.py`），
  旧模块基本没有。跟随文件现状；注意 `str | dict` 这类写法要求 Python 3.10+
  （有的模块有 `from __future__ import annotations`，有的没有），插入新语法前先确认。
- `pyproject.toml` 声明 `requires-python = ">=3.7"`，构建矩阵里也仍有 3.7.5 任务，
  但现有 adapter 代码已经使用 3.10+ 语法。不要据此推断 3.7 一定可用，也不要为了“兼容 3.7”
  去改与任务无关的文件。
- 日志等级：`-1 TRACE / 0 DEBUG / 1 NOTE / 2 INFO / 3 WARN / 4 ERROR / 5 FATAL`；
  面向用户的文案走 `OlivOS.L10NAPI.getTrans(...)`。
- 代码里保留了历史注释（如 `# doOpkRemove(...)`、`# traceback.print_exc()`）。除非任务相关，
  不要顺手删除或“整理”。

## 12. 测试与验证

统一使用 pytest（`testpaths = ["tests"]`、`--strict-markers`）。`tests/conftest.py` 会把工作目录
切到临时目录、设置 `PYTHONPATH`，因此默认不需要真实机器人账号；`test_sdk_events.py` 还会把出站
网络请求替换成断言，避免事件转换偷偷联网。
测试策略、用例映射与覆盖率基线见 `tests/README.md`（基线是快照，不是门槛）。

按改动范围选择验证：

| 改动 | 建议命令 |
| --- | --- |
| 任意改动 | `python script/flake8_check.py` |
| adapter / SDK / 事件映射 / 消息 | `python -m pytest tests/test_sdk_events.py tests/test_adapters.py tests/test_messages.py` |
| 插件加载、调度、插件 WebUI 资源 | `python -m pytest tests/test_plugin_dispatch.py tests/test_opk_webui_lifecycle.py tests/test_webui_plugin_template.py` |
| 启动、配置合并、账号 | `python -m pytest tests/test_boot_and_metadata.py tests/test_accounts.py tests/test_legacy_config.py` |
| WebUI | `python -m pytest tests/test_webui.py tests/test_webui_auth.py tests/test_webui_navigation.py tests/test_webui_environment.py`（浏览器用例加 `-m browser` 与环境变量） |
| 日志 / 原生终端 / 原生账号 | `python -m pytest tests/test_logging.py tests/test_native_terminal.py tests/test_native_accounts.py` |
| `OlivOS/webUI/static/*` | `python script/embed_webui.py` 后提交重新生成的 `OlivOS/webUI/staticData.py`（CI 会校验无 diff） |

注意事项：

- `tests/test_sdk_events.py::test_event_contract_matrix_covers_every_dispatched_sdk` 会解析
  `API.Event.get_Event_from_SDK` 的分支集合，强制每个 SDK 都有 fixture。新增 SDK 必须同步更新
  `SDK_PLATFORMS`。
- 测试只允许替换远端元数据/网络，不要替换被测的事件转换与消息解析函数。
- 一个行为一个测试函数，平台/格式/输入边界用参数化；不要写成一条超长流程。
- 标记：`browser`（真实 Chrome，需 `OLIVOS_WEBUI_BROWSER=1`）、`native_gui`（仅 Windows，隐藏窗口）。
- CI 测试矩阵只跑 Python 3.11（Ubuntu x64/ARM64、Windows x64/ARM64、macOS Intel/ARM64）；
  不要以为其它 Python 版本也被验证过。

## 13. 常见陷阱

1. **把 OneBot 当成 OlivOS。** `sdk == 'onebot'` 覆盖 OneBot V11/V12、Milky、OPQBot、Red；
   只改一个分支会让其它平台行为漂移。
2. **只改一个模型却影响全部。** `onebotSDK.py` 内部按 `napcatModelMap` / `llonebotModelMap` /
   `lagrangeModelMap` / `paraMsgMap` 分支，NapCat 专属字段还有独立回归测试。
3. **协议泄漏。** 把某平台字段加进通用 `Event` / `Message_templet` / `core`，或用目录名推断分层。
4. **绕过 Plugin API。** 插件侧应使用 `plugin_event.reply/send/...` 与 `indeAPI`；直接 import
   adapter SDK 会绕过平台过滤、日志与兼容裁剪。
5. **改动插件可见语义。** 改 `func_type`、`data.message` 格式、`app.json` 字段含义，会让仓库外老插件失效。
6. **误用 `set_block`。** 它是“阻断后续插件”，不是错误处理手段；插件回调异常已被框架捕获并阻断。
7. **队列方向搞反。** 对 `*_link` 进程，`tx_queue` 是入站（进全局 `OlivOS_rx_queue`），
   `rx_queue` 是出站指令来源；改前先读 `run()` / `rx_link()` / `tx_link()`。
8. **混用控制面与数据面。** 控制包应经 `Control.packet('send', ...)` 由主循环路由，
   不要直接 `put` 到别的组件的业务队列。
9. **在错误的位置做网络 I/O。** 主控制循环与插件回调必须保持非阻塞；网络请求放在协议进程/线程。
10. **改公共接口不搜调用方。** 见 9.1；插件在仓库外，仓库内搜索结果只是下限。
11. **重复造轮子。** 新的 Event / Dispatcher / Plugin Context / Adapter / Message / Queue 抽象
    会与现有体系并存并互相冲突。
12. **顺手大重构。** 修 bug 时批量改名、换风格、动无关文件，会让评审无法判断兼容性风险。
13. **CWD 假设。** 所有运行期路径相对工作目录；`import OlivOS` 还会创建 `plugin/`、`lib/` 目录。
14. **手改生成物/内嵌数据。** `OlivOS/webUI/staticData.py` 必须由 `script/embed_webui.py` 生成；
    `OlivOS/thirdPartyModule/*` 与 `OlivOS/core/inlineData/data.py` 不属于常规改动范围。
15. **误解 `remote=` 参数。** `API.Event` 多数公共方法的 `remote=True` 目前是占位
    （`pass` 或返回 `None`），并没有实现远程调用。
16. **顺手“修正”版本号。** `pyproject.toml` / `setup.py` / `infoAPI.py` 本就不同步，改版本属于发版动作。

## 14. 交付前检查

- `git status --short` 与 `git diff`：只包含预期改动，没有无关文件、没有运行产物、没有全文件重排。
- 新增/修改的公共行为有对应回归测试，且本地跑过相关测试与 `python script/flake8_check.py`。
- 改动 adapter 或消息逻辑时，确认所有受影响的 `model` / `sdk` 分支都被考虑到。
- 改动 `OlivOS/webUI/static/*` 时，`OlivOS/webUI/staticData.py` 已重新生成。
- 提交信息符合 Conventional Commits；不提交 `conf/basic.json`、token、日志、`data/`、`plugin/*` 运行内容。
