"""路径解析：兼容源码运行 / pip 安装 / PyInstaller 打包三种形态。"""
from __future__ import annotations

import shutil
import sys
from pathlib import Path

if getattr(sys, "frozen", False):
    # PyInstaller 打包：配置放 exe 旁，资源在临时解包目录
    APP_DIR = Path(sys.executable).resolve().parent
    BUNDLE_DIR = Path(getattr(sys, "_MEIPASS", APP_DIR))
    PYTHONW = sys.executable
else:
    _pkg_parent = Path(__file__).resolve().parent.parent
    # pip 安装形态（site-packages 内）：退回当前工作目录存放配置
    APP_DIR = Path.cwd() if _pkg_parent.name == "site-packages" else _pkg_parent
    BUNDLE_DIR = APP_DIR

    _venv_pythonw = APP_DIR / ".venv" / "Scripts" / "pythonw.exe"
    # 找不到绝对路径时为 None，开机自启设置需据此提示
    PYTHONW = str(_venv_pythonw) if _venv_pythonw.exists() else shutil.which("pythonw")

SPRITE_DIR = BUNDLE_DIR / "sprites"
CONFIG_PATH = APP_DIR / "config.json"
LOG_DIR = APP_DIR / "logs"
