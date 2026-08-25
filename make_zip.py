"""打源码分享 zip（排除 venv/打包产物/配置）。

用法：
    python make_zip.py --base . --out dafeiyu_pet_source.zip
"""
from __future__ import annotations

import argparse
import os
import zipfile

FILES = [
    "run.py",
    "dafeiyu_pet/__init__.py",
    "dafeiyu_pet/__main__.py",
    "dafeiyu_pet/main.py",
    "dafeiyu_pet/paths.py",
    "dafeiyu_pet/constants.py",
    "dafeiyu_pet/config.py",
    "dafeiyu_pet/logging_setup.py",
    "dafeiyu_pet/logic.py",
    "dafeiyu_pet/services/__init__.py",
    "dafeiyu_pet/services/deepseek.py",
    "dafeiyu_pet/services/weather.py",
    "dafeiyu_pet/services/monitor.py",
    "dafeiyu_pet/ui/__init__.py",
    "dafeiyu_pet/ui/chat_dialog.py",
    "dafeiyu_pet/ui/function_panel.py",
    "dafeiyu_pet/ui/food_panel.py",
    "dafeiyu_pet/ui/pet_window.py",
    "start_pet.bat",
    "dafeiyu_pet.spec",
    "preprocess.py",
    "preprocess2.py",
    "make_zip.py",
    "pyproject.toml",
    "requirements.txt",
    "README.md",
    "CHANGELOG.md",
    "LICENSE",
    "icon.ico",
    ".gitignore",
]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", default=".", help="项目根目录")
    parser.add_argument("--out", default="dafeiyu_pet_source.zip", help="输出 zip 路径")
    args = parser.parse_args()

    files = list(FILES)
    sprites = os.path.join(args.base, "sprites")
    for root, _dirs, fs in os.walk(sprites):
        for f in fs:
            files.append(os.path.relpath(os.path.join(root, f), args.base).replace(os.sep, "/"))

    with zipfile.ZipFile(args.out, "w", zipfile.ZIP_DEFLATED) as z:
        for f in files:
            z.write(os.path.join(args.base, f), f)

    print("files:", len(files))
    print("size:", os.path.getsize(args.out) // 1024, "KB")
    for f in files:
        print(" ", f)


if __name__ == "__main__":
    main()
