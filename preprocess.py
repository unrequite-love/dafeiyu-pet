"""三视图抠图+规格化（第一步）：白底 → 透明 PNG，统一高度，裁掉空白边。

用法：
    python preprocess.py --src 原图目录 --out sprites --height 340
原图目录需包含：正面.png / 侧面.png / 背面.png（白底三视图）。
"""
from __future__ import annotations

import argparse

from PIL import Image, ImageDraw

NAMES = ["正面", "侧面", "背面"]


def cutout(path: str, target_h: int) -> Image.Image:
    im = Image.open(path).convert("RGBA")
    w, h = im.size
    # 1) 从四角做连通域泛洪，把背景整片变透明（人物内部的白不受影响）
    for sx, sy in [(0, 0), (w - 1, 0), (0, h - 1), (w - 1, h - 1)]:
        ImageDraw.floodfill(im, (sx, sy), (0, 0, 0, 0), thresh=30)
    # 2) 去白边：贴着透明区的亮像素也变透明（消除抗锯齿白晕）
    for _ in range(3):
        px = im.load()
        changed = False
        for y in range(h):
            for x in range(w):
                r, g, b, a = px[x, y]
                if a == 0:
                    continue
                if r > 215 and g > 215 and b > 215:
                    # 检查邻域是否有透明像素
                    neighbors = (
                        (1, 0), (-1, 0), (0, 1), (0, -1),
                        (1, 1), (-1, -1), (1, -1), (-1, 1),
                    )
                    for dx, dy in neighbors:
                        nx, ny = x + dx, y + dy
                        if 0 <= nx < w and 0 <= ny < h and px[nx, ny][3] == 0:
                            px[x, y] = (0, 0, 0, 0)
                            changed = True
                            break
        if not changed:
            break
    # 3) 裁掉透明边
    bbox = im.getbbox()
    if bbox is None:
        raise RuntimeError(f"{path}: 抠图后为空！")
    im = im.crop(bbox)
    # 4) 统一高度
    w2, h2 = im.size
    scale = target_h / h2
    return im.resize((max(1, round(w2 * scale)), target_h), Image.LANCZOS)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--src", default="raw_sprites", help="三视图原图目录（白底）")
    parser.add_argument("--out", default="sprites", help="输出目录")
    parser.add_argument("--height", type=int, default=340, help="目标高度(px)")
    args = parser.parse_args()

    for name in NAMES:
        im = cutout(f"{args.src}/{name}.png", args.height)
        im.save(f"{args.out}/{name}.png")
        print(f"{name}: {im.size} -> {args.out}/{name}.png")

    # 托盘小图标
    icon = cutout(f"{args.src}/正面.png", args.height).resize((64, 64), Image.LANCZOS)
    icon.save(f"{args.out}/icon.png")
    print("icon: 64x64")


if __name__ == "__main__":
    main()
