# 大肥鱼桌宠 🐋

DeepSeek V4 Pro 二创形象「鲸鱼娘·大肥鱼」的透明桌面宠物。

基于三视图素材（正面 / 侧面 / 背面），用 Python + PySide6 实现，无边框透明置顶窗口。

> **平台要求：Windows**（鼠标穿透 / 开机自启等依赖 Win32 API）。需要 **Python 3.11+**。

## 功能

- **三视图行走**：左右走用侧面（自动镜像）、向上走用背面、向下走用正面
- **三种模式**：自由散步 / 跟随鼠标 / 原地待着（右键菜单切换）
- **互动**：
  - 左键按住：拖拽（会侧身朝向拖动方向，松手会说话）
  - 单击：蹦跳 + 回嘴（互动台词）+ 弹出 🗨️ 聊天面板
  - 双击：喂食面板（小鱼干 / 蛋糕 / 棒棒糖 / 团子 / 钻石），投喂有进食挤压动画
  - 右键：完整菜单（模式 / 大小 / 设置 Key / 设置城市 / 查看天气 / 显示隐藏 / 鼠标穿透 / 置顶 / 开机自启 / 退出；托盘右键同款，穿透后可从托盘解除）
- **台词系统**：日常随机台词 + 互动回嘴 + 思维链心声（灰色斜体括号气泡），取材自社区 DS 梗
- **细节**：呼吸 / 摇摆 / 蹦跳 / 进食动画、转向交叉淡化、加减速惯性、散步自动休息、说话冷却
- **AI 对话**：调用 DeepSeek API（`deepseek-v4-flash`，新端点无 `/v1` 前缀），风格贱兮兮但可爱（Prompt 建议简短，但超长回复不截断、气泡自动换行完整显示并按字数延长停留时间）；历史保留最近 40 条；Key 经右键菜单「设置 Key」输入（密文回显，保存后即时验证），存于本地 `config.json`（已 gitignore，勿分享）；「深度思考」可在右键菜单开关（开启后回复更聪明但更慢，超时放宽到 60 秒）；等待回复时头顶显示 💭 思考气泡；连接复用降低延迟；「使用系统代理」可开关（代理拦截导致超时时关闭走直连，对天气查询同样生效）
- **天气查询**：右键菜单「查看天气」→ wttr.in，城市可经「设置城市」修改
- **系统监控**（默认关闭，右键菜单「系统监控」开启）：CPU > 90% / 内存 > 95% / NVIDIA 显卡 > 80°C 时气泡提醒；检测间隔可经「监控间隔」手动修改（默认 10 秒，范围 5~3600 秒），配置存 `config.json`（`monitor_enabled` / `monitor_interval_s`）
- 托盘图标、窗口置顶、鼠标穿透、开机自启；**配置修改即时落盘**，崩溃不丢失

## 运行

```bash
pip install -r requirements.txt
```

然后双击 `start_pet.bat`，或：

```bash
python -m dafeiyu_pet
```

日志写入 `logs/pet.log`（滚动，排查问题用）。

## 开发

```bash
pip install -e .[dev]
ruff check .   # lint
pytest         # 单元测试
```

## 打包成独立 exe

```bash
pip install pyinstaller
pyinstaller --noconfirm dafeiyu_pet.spec
```

产物在 `dist/dafeiyu-pet.exe`，双击即用，无需安装 Python。
（杀毒软件可能对 PyInstaller 产物误报，加信任即可。）

## 更换形象

把新的三视图（白底）放到 `raw_sprites/` 目录（正面.png / 侧面.png / 背面.png），然后：

```bash
python preprocess.py --src raw_sprites --out sprites          # 白底抠图 + 统一高度
python preprocess2.py --src raw_sprites --out sprites         # 边缘去污 + 预乘 alpha 生成各尺寸
```

## 项目结构

```
dafeiyu_pet/
├── constants.py            # 全部常量与台词（无魔法数字）
├── config.py               # 配置读写（向后兼容、修改即落盘）
├── paths.py                # 源码/打包双形态路径解析
├── logging_setup.py        # 滚动文件日志
├── logic.py                # 纯逻辑（朝向选择等，可单测）
├── services/               # AI 对话 / 天气 / 系统监控
├── ui/                     # 主窗口 + 聊天框 / 功能面板 / 喂食面板
└── main.py                 # 应用入口
tests/                      # pytest 单元测试
run.py                      # 根级入口（PyInstaller / python run.py）
start_pet.bat               # 启动脚本（ASCII，自动选 venv / 系统 Python）
dafeiyu_pet.spec            # PyInstaller 打包配置
preprocess.py / preprocess2.py  # 素材预处理（argparse 参数化）
```

## 致谢

- **AI 对话 / 天气查询 / 系统监控 / PyInstaller 打包配置**：由 [Cpanoe](https://github.com/Cpanoe) 通过 [PR#3](https://github.com/1190fasheqi/dafeiyu-pet/pull/3) 贡献。
- 桌面宠物朝向修复由 [B-A-A-GE](https://github.com/B-A-A-GE) 通过 [PR#1](https://github.com/1190fasheqi/dafeiyu-pet/pull/1) 提交。
- 台词取自 DeepSeek / 鲸鱼娘 / 大肥鱼社区梗（D指导去吃饭、吃白饭、"才不是大肥鱼"、思维链心声等），感谢社区整活。

## 协议

MIT
