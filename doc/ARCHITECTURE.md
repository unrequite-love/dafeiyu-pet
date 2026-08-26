# 大肥鱼桌宠 —— 项目架构文档

> 用途：作为同类「桌面宠物 / 常驻型桌面工具」项目的架构参考模板。
> 对应版本：v1.5.2（2026-08）

## 1. 项目概览

| 维度 | 说明 |
|------|------|
| 形态 | Windows 桌面常驻程序（透明无边框置顶窗口 + 系统托盘） |
| 技术栈 | Python 3.11+ / PySide6（Qt6） / requests / psutil / pynvml |
| 外部依赖服务 | DeepSeek API（AI 对话）、wttr.in（天气） |
| 分发方式 | 源码运行（`python -m dafeiyu_pet`）或 PyInstaller 单文件 exe |
| 代码规模 | 约 2000 行（含测试），主程序拆分为 16 个模块 |

## 2. 分层架构

```
┌─────────────────────────────────────────────┐
│  入口层  run.py / __main__.py / main.py     │  装配 QApplication、日志初始化、异常兜底
├─────────────────────────────────────────────┤
│  UI 层   ui/                                │  Qt 组件，只做「展示 + 事件分发」
│    pet_window.py   主窗口（行走/动画/交互） │
│    chat_dialog.py  聊天输入框               │
│    chat_log_dialog.py  记录回看             │
│    function_panel.py / food_panel.py        │
├─────────────────────────────────────────────┤
│  服务层  services/                          │  无 Qt 依赖，可独立单测
│    deepseek.py    AI 客户端（流式/重试/历史）│
│    weather.py     天气查询 + 中文码表       │
│    monitor.py     CPU/内存/GPU 监控         │
├─────────────────────────────────────────────┤
│  领域层  logic.py / constants.py            │  纯函数：朝向选择、气泡时长等
├─────────────────────────────────────────────┤
│  基础层  config.py / paths.py /             │  配置读写、路径解析、日志
│          logging_setup.py                   │
└─────────────────────────────────────────────┘
```

**依赖方向强制单向**：UI → 服务 → 领域/基础。服务层禁止 import Qt，
因此全部网络/解析逻辑可以在无 GUI 环境下跑单元测试。

## 3. 关键模块职责

### 3.1 入口链（三种启动形态共用）

```
run.py（PyInstaller 打包入口）
  └→ dafeiyu_pet/main.py::run()     # 唯一装配点：日志 → QApplication → PetWindow
       └→ dafeiyu_pet/__main__.py   # 支持 python -m dafeiyu_pet
```

- `main.py` 是唯一创建 `QApplication` 的地方，全局异常兜底写日志 + 弹窗
- PetWindow 延迟导入：保证日志系统先于任何可能出错的 UI 代码就绪

### 3.2 paths.py —— 双形态路径解析

程序有三种运行形态，资源/数据目录各不相同：

| 形态 | APP_DIR（配置/日志） | BUNDLE_DIR（sprites 资源） |
|------|---------------------|---------------------------|
| 源码运行 | 仓库根目录 | 仓库根目录 |
| pip 安装 | 当前工作目录 | site-packages（资源随包） |
| PyInstaller frozen | exe 所在目录 | `sys._MEIPASS` 临时解包目录 |

**要点**：用户数据（config.json / chat_history.json / logs/）永远跟着
可执行文件走，升级替换不丢数据；只读资源从解包目录读。

### 3.3 config.py —— 配置即写盘

```python
class PetConfig:
    # 读取：DEFAULTS 合并磁盘配置（未知字段保留 → 向前兼容新版本）
    # 校验：mode 非法回退默认（带日志）
    # 写入：set()/update() 变更即 json.dump 落盘
```

- **为什么**：常驻程序可能被任务管理器杀掉/崩溃，「退出时保存」必然丢数据
- DEFAULTS 字典是配置 schema 的唯一权威定义
- 越界值清洗放在使用处（如 `clamp_interval()` 钳制到 5~3600s）

### 3.4 services/deepseek.py —— AI 客户端

```
纯函数:  build_messages()  组装 system+历史+输入（历史截断可测）
         build_payload()   V4 接口请求体（thinking 模式参数互斥）
         extract_reply()   取 content 跳过 reasoning_content
         truncate_reply()  仅极端上限 120 字防失控
类:      ChatHistory       环形历史 + JSON 持久化（损坏容错、坏条目过滤）
         DeepSeekClient    Session 连接复用 + 线程锁 + chat/chat_stream
异常体系: DeepSeekError
           ├── DeepSeekTimeout        → 气泡「请求超时」
           └── DeepSeekConnectionError→ 气泡「连接失败」
```

- **重试策略**：仅 429/5xx 指数退避（0.5s/1s，共 3 次）；网络异常、4xx 快速失败
- **流式**：`chat_stream()` 生成器解析 SSE（容忍空行/心跳/坏 JSON/中途 error 事件）
- **代理**：构造参数 `use_proxy` → `session.trust_env`，被代理拦截时可直连

### 3.5 services/weather.py / monitor.py

- weather：URL 构造 / 码表翻译 / 播报格式化全是纯函数；模块级 Session 复用；
  三级回退：数字 weatherCode 码表（45 种）→ 英文描述表 → 原文 + 中英边界补空格
- monitor：`evaluate()` 纯函数判定告警优先级（CPU > 内存 > GPU），
  `read_stats()/read_gpu_temp()` 只做读取；pynvml 缺失优雅降级

### 3.6 ui/pet_window.py —— 主窗口（最大的模块）

职责分组（按注释分区）：

1. `__init__`：配置、精灵加载（缺失时 fail-fast 抛错）、状态变量、子面板、托盘
2. AI：`call_deepseek`（后台线程 + 队列回传）
3. 绘制：`paintEvent`（气泡 + 换行缓存 + 精灵动画状态机）
4. 逻辑：`tick()`（20ms 主循环，见 §4）
5. 鼠标事件：拖拽 / 单击双击判定（280ms 延迟定时器）
6. 菜单与功能开关

## 4. 并发模型（核心）

**唯一 Qt 原则：所有 UI 操作都在主线程。**

```
后台 worker 线程                     主线程（20ms tick 循环）
────────────────                     ──────────────────────
requests.post / SSE 迭代
    │ 成功/失败
    ├─→ _queue_say(text, duration) ──→ _say_queue → tick() 逐条 self.say()
    └─→ _post(callback) ────────────→ _main_queue → tick() 逐个执行（如弹窗）
```

- 两个队列都是「后台线程只 append，主线程 drain」的**单向消息传递**，
  借助 GIL 保证 append/clear 原子性，无需加锁
- `ds_busy` 忙标志的检查与置位都发生在主线程（UI 事件），天然无竞态
- `DeepSeekClient` 内部的 `threading.Lock` 保护 Session（连接复用必须串行）

## 5. 主循环设计（tick, 20ms）

```python
def tick(self):
    self.t += 1
    # 1. 泵后台队列（气泡/回调）——最高优先级，保证响应及时
    # 2. 系统监控检查（默认关闭；按配置间隔节流）
    # 3. 动画时间推进（jump/eat/crossfade/action 各自衰减）
    # 4. chat_paused / dragging 时提前 return（仍 update 重绘）
    # 5. 模式逻辑：follow 追鼠标 / wander 随机目标 / still 待机小动作
    # 6. 朝目标移动 + choose_direction() 纯函数决定朝向/镜像
    # 7. self.update() 触发重绘
```

**要点**：动画状态全部用「归一化时间量（0→1 衰减）+ 三角函数」表达，
没有帧序列表，天然与 TICK_MS 解耦。

## 6. 窗口与弹出层体系

| 窗口 | flags | 弹出要点 |
|------|-------|----------|
| 主窗口 | Frameless + Tool + StaysOnTop + WA_Translucent | Tool 属性：不占任务栏 |
| 聊天/记录/面板 | 同上（独立顶层） | **必须 `activateWindow()` + `setFocus`**，否则 Windows 不给键盘焦点（v1.1.2 踩坑） |
| 气泡 | 主窗口内自绘 | 换行结果缓存；时长按字数动态 |

- 鼠标穿透：Win32 `SetWindowLongPtrW` 改 `WS_EX_TRANSPARENT`（Windows 专属）
- 弹出层互斥：双击喂食前 `clear_bubble()` 清掉同位置的气泡，避免重叠

## 7. 数据与文件

| 文件 | 内容 | 生命周期 |
|------|------|----------|
| `config.json` | 全部用户配置（含 API Key） | 修改即写盘；**gitignore** |
| `chat_history.json` | 最近 40 条对话 | 每轮追加即写盘；损坏自动从空开始 |
| `logs/pet.log` | 滚动日志 512KB×3 | 排障唯一依据（pythonw 无控制台） |
| `sprites/` | 三视图 × 3 尺寸 + 图标 | 预处理脚本生成，随包分发 |

## 8. 测试架构

```
tests/
├── test_config.py          # 配置合并/兼容/损坏容错/即时落盘
├── test_constants.py       # 台词表完整性（食物表与 FOODS 对齐等）
├── test_logic.py           # 朝向选择（含 1.15 系数边界）、气泡时长
├── test_deepseek.py        # 消息构建/payload 契约/历史持久化
├── test_stream_retry.py    # SSE 解析/重试策略（FakeSession 模拟，零网络）
├── test_weather.py         # URL 编码/码表回退链/播报格式
├── test_monitor.py         # 阈值判定优先级/间隔清洗钳制
├── test_chat_log.py        # 记录窗口格式化
└── test_chat_dialog_focus.py  # pytest-qt 真实键盘焦点回归（缺依赖自动 skip）
```

**分层测试策略**：服务/领域层全部纯逻辑测试（快、稳）；GUI 仅保留
高价值回归用例（焦点 Bug 锁定）；网络交互用 Fake 对象模拟响应。

## 9. 打包与分发

- `dafeiyu_pet.spec`：入口 run.py；`collect_all` 收集 psutil/requests/pynvml
  的数据文件；单文件 windowed 模式；icon.ico
- `build.bat`：ASCII + CRLF，自动装 dev 依赖再跑 PyInstaller
- `make_zip.py`：源码分享包，文件清单白名单制——**天然排除本地数据**
  （config/chat_history/logs），防泄露 API Key

## 10. 复用此架构的检查清单

做类似项目（桌面宠物 / 常驻托盘工具 / 带外部 API 的桌面应用）时：

- [ ] 分四层：入口 / UI / services（无 Qt）/ 纯逻辑，依赖单向
- [ ] paths.py 区分 源码 / pip / frozen 三形态，用户数据跟 exe 走
- [ ] 配置：DEFAULTS 合并 + 变更即落盘 + 未知字段向前兼容
- [ ] 后台线程 → 队列 → 主线程 drain，绝不跨线程碰 UI
- [ ] 网络客户端：Session 复用、异常分类、429/5xx 才重试、代理可关
- [ ] 错误三级可见性：气泡（短）→ 持久弹窗（诊断）→ 日志（全量）
- [ ] 帧循环 = 泵队列 + 节流检查 + 动画衰减 + 模式逻辑 + update
- [ ] 无边框 Tool 弹窗必须 activateWindow + setFocus
- [ ] 纯逻辑全部可单测；GUI 只留焦点/交互回归
- [ ] 分发包白名单制，本地数据永不出机器
