"""精灵精修（第二步）：边缘去污 + 预乘 alpha 缩放出各尺寸精灵。

核心算法在 sprite_tools.py（独立工具箱，可单独拷贝复用），本脚本仅是
面向本项目三视图+固定尺寸档的薄封装（也可直接用工具箱一条命令替代：
python sprite_tools.py --src 原图目录 --out sprites --sizes 187,238,306 --icon 64）。

用法：
    python preprocess2.py --src 原图目录 --out sprites
"""
from __future__ import annotations

import argparse
import os

from sprite_tools import build_sizes, premult_resize, sprite_from_white_bg

NAMES = ["正面", "侧面", "背面"]
SIZES = {0.55: 187, 0.7: 238, 0.9: 306}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--src", default="raw_sprites", help="白底三视图原图目录")
    parser.add_argument("--out", default="sprites", help="输出目录")
    args = parser.parse_args()
    os.makedirs(args.out, exist_ok=True)

    for name in NAMES:
        base = sprite_from_white_bg(os.path.join(args.src, f"{name}.png"))
        for h, im in build_sizes(base, list(SIZES.values())).items():
            out_path = os.path.join(args.out, f"{name}_{h}.png")
            im.save(out_path)
            print(f"{name}_{h}.png {im.size}")

    # 托盘图标（用最小档再缩）
    icon_src = sprite_from_white_bg(os.path.join(args.src, f"{NAMES[0]}.png"))
    icon = premult_resize(icon_src, 64)
    icon.save(os.path.join(args.out, "icon.png"))
    print("icon 64x64")


if __name__ == "__main__":
    main()
