# Changelog

本项目遵守 [Semantic Versioning](https://semver.org/)。

## [1.1.1] - 2026-08-25

### 变更

- 默认模型 `deepseek-v4-pro` → `deepseek-v4-flash`（响应结构与 V4 Pro 一致，解析逻辑无需调整：普通模式也可能返回 `reasoning_content`，已按既定逻辑跳过）

## [1.1.0] - 2026-08-25

### 变更

- DeepSeek 接口迁移至 V4 Pro 规范：
  - 端点 `https://api.deepseek.com/v1/chat/completions` → `https://api.deepseek.com/chat/completions`（去掉 `/v1` 前缀）
  - 模型 `deepseek-chat` → `deepseek-v4-pro`
  - 请求体显式携带 `stream: false`

### 新增

- 「深度思考」开关（右键菜单，存于 `config.json` 的 `ds_thinking`，默认关闭）：
  - 开启时发送 `thinking: {"type": "enabled"}` + `reasoning_effort: "high"`，不设 `max_tokens`（避免推理 token 耗尽 100 上限导致空回复）、不发送 `temperature`，超时放宽至 60 秒
  - 关闭时 `thinking: disabled`，保持原短平快参数（`max_tokens=100` + `temperature=0.9`）
- 响应解析跳过 `reasoning_content`（思考过程不上屏），`content` 为空时明确报错

## [1.0.0] - 2026-08-25

结构化重构版本，功能与原版保持一致，另补全进食动画。

### 新增

- 标准包结构 `dafeiyu_pet/`（services / ui 分层），取代 1000+ 行单文件
- pytest 单元测试（配置 / 台词 / 朝向逻辑 / AI 消息构建 / 天气解析 / 监控阈值）
- ruff lint + GitHub Actions CI（lint、测试、手动触发的 exe 打包）
- 滚动文件日志 `logs/pet.log` 替代 print 调试输出
- `pyproject.toml` 项目元数据与版本号，依赖加上版本上限
- 双击喂食真正播放进食挤压/咀嚼动画（原 `eat_t` 赋值后从未使用）
- 右键菜单新增「设置城市」（原先只能手改 config.json）
- 天气查询移入后台线程，不再卡住 UI 最多 10 秒
- `CHANGELOG.md`

### 变更

- 文件全部改英文名：`桌宠.py` → 包结构，`启动桌宠.bat` → `start_pet.bat`（纯 ASCII，修复 GBK 编码乱码问题，并增加 Python 缺失提示）
- 配置**修改即落盘**（原版仅退出时保存，崩溃丢失全部改动）
- API Key 输入改为密文回显（防肩窥）
- `preprocess*.py` / `make_zip.py` 参数化（argparse），去除硬编码 `D:\` 个人路径
- 城市名 URL 编码后再请求 wttr.in
- 精灵图缺失时启动报明确错误（原为静默空白窗口）
- `.gitignore` 不再忽略 `*.spec`，打包配置入库

### 修复

- 删除死代码：未使用的 `load_config()`、注释掉的 IP 定位、无用状态变量
- 裸 `except:` 改为 `except Exception` 并记录日志
- `check_system_status` 方法体错误缩进
- `eat_t` 未初始化即可能被引用的隐患
- DeepSeek 网络异常分类（超时/连接失败/API 错误），工作线程兜底日志
