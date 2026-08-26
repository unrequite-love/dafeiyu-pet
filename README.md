# 大肥鱼桌宠 🐋

DeepSeek V4 Pro 二创形象「鲸鱼娘·大肥鱼」的透明桌面宠物。

基于三视图素材（正面 / 侧面 / 背面），用 Python + PySide6 实现，无边框透明置顶窗口。

> **平台要求：Windows**（鼠标穿透 / 开机自启等依赖 Win32 API）。需要 **Python 3.11+**。
> 当前版本：**v1.5.2**（变更见 [CHANGELOG.md](CHANGELOG.md)）

## 快速开始

```bash
pip install -r requirements.txt
```

然后双击 `start_pet.bat`，或：

```bash
python -m dafeiyu_pet
```

首次使用 AI 对话：右键 →「设置 ▸ 设置 Key」填入 [platform.deepseek.com](https://platform.deepseek.com) 的 API Key（保存后自动验证）。

## 交互一览

| 操作 | 效果 |
|------|------|
| 左键按住拖动 | 拖拽桌宠（侧身朝向拖动方向，松手说话） |
| 单击 | 蹦跳 + 回嘴，弹出 🗨️ 入口 |
| 双击 | 喂食面板（🐟🍰🍭🍡💎，投喂有进食动画） |
| 右键 | 完整菜单（托盘右键同款；开启鼠标穿透后从托盘操作） |

## 功能

### 桌宠本体

- **三视图行走**：左右走用侧面（自动镜像）、向上走用背面、向下走用正面
- **三种模式**：自由散步 / 跟随鼠标 / 原地待着
- **台词系统**：日常随机台词 + 互动回嘴 + 思维链心声（灰色斜体气泡），取材自社区 DS 梗
- **细节动画**：呼吸 / 摇摆 / 蹦跳 / 进食挤压、转向交叉淡化、加减速惯性、散步自动休息、说话冷却
- **气泡显示**：自动换行，按字数动态延长停留时间（长回复不会被截断）

### AI 对话（DeepSeek）

- 模型 `deepseek-v4-flash`，新端点无 `/v1` 前缀；人设贱兮兮但可爱
- **流式回复**：逐段显示在气泡上，等待期头顶冒 💭 思考气泡
- **对话历史**：持久化到本地（`chat_history.json`），重启恢复上下文；右键「聊天记录」可回看 / 清空
- **深度思考**：右键开关，开启后发送 `reasoning_effort=high`，回复更聪明但更慢（超时放宽到 60 秒）
- **稳定性**：429/5xx 自动指数退避重试；连接复用降低延迟；Key 保存后即时验证
- **排障**：右键「测试DS连接」一键诊断（真实发一条消息，弹窗显示结果与建议）
- **代理**：右键「使用系统代理」可开关——被代理/VPN 拦截导致超时时，关闭即直连（对天气查询同样生效）

### 天气查询

- 右键「查看天气」→ wttr.in，中文播报（如「深圳今天 30°C，天气局部有雨」，45 种天气码全覆盖）
- 城市经「设置 ▸ 设置城市」修改

### 系统监控（默认关闭）

- 右键「系统监控」开启：CPU > 90% / 内存 > 95% / NVIDIA 显卡（多卡取最高温）> 80°C 时气泡提醒
- 检测间隔经「设置 ▸ 监控间隔」修改（默认 10 秒，范围 5~3600 秒）

### 系统集成

- 托盘图标、窗口置顶、鼠标穿透、开机自启、回到屏幕内、显示/隐藏
- **配置修改即时落盘**（`config.json`，已 gitignore），崩溃不丢失

### 右键菜单结构

```
模式 ▸            自由散步 / 跟随鼠标 / 原地待着
大小 ▸            小 / 中 / 大
设置 ▸            设置 Key / 设置城市 / 监控间隔
测试DS连接        一键诊断 AI 连通性
聊天记录          回看 / 清空对话历史
使用系统代理 ☐    代理拦截超时时关闭
深度思考 ☐        更聪明但更慢
查看天气
系统监控 ☐        默认关闭
显示/隐藏 · 回到屏幕内 · 鼠标穿透 ☐ · 窗口置顶 ☐ · 开机自启 ☐
退出
```

## 开发

```bash
pip install -e .[dev]
ruff check .   # lint
pytest         # 单元测试（66 个用例，含 SSE/重试/持久化/GUI 焦点回归）
```

## 打包成独立 exe

```bash
pyinstaller --noconfirm dafeiyu_pet.spec   # 需先 pip install pyinstaller
```

或直接双击 `build.bat` 一键完成（自动安装 dev 依赖）。

产物在 `dist/dafeiyu-pet.exe`，双击即用，无需安装 Python。
（杀毒软件可能对 PyInstaller 产物误报，加信任即可。）

## 常见问题

- **AI 请求超时 / 无回复**：多为代理或 VPN 拦截。先右键「测试DS连接」看弹窗结果；若报连接失败，关闭「使用系统代理」再试。详细原因见 `logs/pet.log`
- **Key 安全吗**：Key 只存本地 `config.json`（已 gitignore，不会入库/分享）；「聊天记录」窗口不显示 Key；分享源码包（`make_zip.py`）不含任何本地数据
- **系统监控怎么不提示了**：v1.4.0 起默认关闭，右键菜单「系统监控」手动开启

## 更换形象

把新的三视图（白底）放到 `raw_sprites/` 目录（正面.png / 侧面.png / 背面.png），然后二选一：

```bash
# 方式一：独立工具箱一条命令（推荐，抠图+去污+多尺寸+图标全流程）
python sprite_tools.py --src raw_sprites --out sprites --height 340 --sizes 187,238,306 --icon 64

# 方式二：分两步走（与原流程等价）
python preprocess.py --src raw_sprites --out sprites    # 白底抠图 + 统一高度
python preprocess2.py --src raw_sprites --out sprites   # 边缘去污 + 预乘 alpha 生成各尺寸
```

> `sprite_tools.py` 是**单文件零项目依赖**的工具箱（仅依赖 Pillow），可直接拷贝到其他项目复用；`preprocess*.py` 是基于它的本项目薄封装。

## 项目结构

```
dafeiyu_pet/
├── constants.py            # 全部常量与台词（无魔法数字）
├── config.py               # 配置读写（向后兼容、修改即落盘）
├── paths.py                # 源码/打包双形态路径解析
├── logging_setup.py        # 滚动文件日志
├── logic.py                # 纯逻辑（朝向选择 / 气泡时长，可单测）
├── services/
│   ├── deepseek.py         # AI 客户端（流式 SSE / 重试 / 历史持久化）
│   ├── weather.py          # wttr.in 查询 + 中文天气码表
│   └── monitor.py          # CPU / 内存 / 多卡 GPU 监控
├── ui/
│   ├── pet_window.py       # 主窗口（行走 / 动画 / 交互 / 托盘菜单）
│   ├── chat_dialog.py      # 聊天输入框
│   ├── chat_log_dialog.py  # 聊天记录回看窗口
│   ├── function_panel.py   # 单击弹出的 🗨️ 功能面板
│   └── food_panel.py       # 双击弹出的喂食面板
└── main.py                 # 应用入口
tests/                      # pytest 单元测试（纯逻辑 + GUI 回归）
doc/                        # 架构文档 / 设计思路 / 功能清单（复用模板）
run.py                      # 根级入口（PyInstaller / python run.py）
start_pet.bat               # 启动脚本（ASCII，自动选 venv / 系统 Python）
build.bat                   # 一键打包 exe
dafeiyu_pet.spec            # PyInstaller 打包配置
preprocess.py / preprocess2.py  # 素材预处理薄封装（核心算法在 sprite_tools）
sprite_tools.py             # 独立精灵图工具箱（单文件可拷贝复用：抠图/去污/预乘缩放/CLI）
make_zip.py                 # 源码分享包（不含本地数据）
```

## 致谢

- **AI 对话 / 天气查询 / 系统监控 / PyInstaller 打包配置**：由 [Cpanoe](https://github.com/Cpanoe) 通过 [PR#3](https://github.com/1190fasheqi/dafeiyu-pet/pull/3) 贡献。
- 桌面宠物朝向修复由 [B-A-A-GE](https://github.com/B-A-A-GE) 通过 [PR#1](https://github.com/1190fasheqi/dafeiyu-pet/pull/1) 提交。
- 台词取自 DeepSeek / 鲸鱼娘 / 大肥鱼社区梗（D指导去吃饭、吃白饭、"才不是大肥鱼"、思维链心声等），感谢社区整活。

## 协议

MIT
