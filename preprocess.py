"""三视图抠图+规格化（第一步）：白底 → 透明 PNG，统一高度。

核心算法在 sprite_tools.py（独立工具箱，可单独拷贝复用），本脚本仅是
面向本项目三视图的薄封装。

用法：
    python preprocess.py --src 原图目录 --out sprites --height 340
原图目录需包含：正面.png / 侧面.png / 背面.png（白底三视图）。
"""
from __future__ import annotations

import argparse
import os

from PIL import Image

from sprite_tools import cutout_white, resize_to_height

NAMES = ["正面", "侧面", "背面"]


def cutout(path: str, target_h: int) -> Image.Image:
    """白底抠图 + 裁边 + 普通缩放到目标高度（第一步不做去污，见 preprocess2.py）。"""
    return resize_to_height(cutout_white(Image.open(path)), target_h)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--src", default="raw_sprites", help="三视图原图目录（白底）")
    parser.add_argument("--out", default="sprites", help="输出目录")
    parser.add_argument("--height", type=int, default=340, help="目标高度(px)")
    args = parser.parse_args()
    os.makedirs(args.out, exist_ok=True)

    for name in NAMES:
        im = cutout(os.path.join(args.src, f"{name}.png"), args.height)
        out_path = os.path.join(args.out, f"{name}.png")
        im.save(out_path)
        print(f"{name}: {im.size} -> {out_path}")

    # 托盘小图标
    icon = cutout(os.path.join(args.src, "正面.png"), args.height).resize((64, 64), Image.LANCZOS)
    icon.save(os.path.join(args.out, "icon.png"))
    print("icon: 64x64")


if __name__ == "__main__":
    main()
