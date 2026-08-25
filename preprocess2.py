"""精灵精修（第二步）：边缘去污 + 预乘 alpha 缩放出各尺寸精灵。

用法：
    python preprocess2.py --src 原图目录 --out sprites
需要先运行 preprocess.py 生成统一高度的透明底三视图。
"""
from __future__ import annotations

import argparse
import os

from PIL import Image, ImageDraw

NAMES = ["正面", "侧面", "背面"]
SIZES = {0.55: 187, 0.7: 238, 0.9: 306}


def decontaminate(im: Image.Image) -> Image.Image:
    """边缘像素对白底去混合：pixel = fg*a + 255*(1-a) → fg = (pixel - 255*(1-a))/a"""
    im = im.convert("RGBA")
    px = im.load()
    w, h = im.size
    for y in range(h):
        for x in range(w):
            r, g, b, a = px[x, y]
            if 0 < a < 255:
                t = a / 255.0
                if a < 40:  # 极淡边缘直接透明，避免除噪放大
                    px[x, y] = (0, 0, 0, 0)
                    continue
                nr = (r - 255 * (1 - t)) / t
                ng = (g - 255 * (1 - t)) / t
                nb = (b - 255 * (1 - t)) / t
                px[x, y] = (
                    int(max(0, min(255, nr))),
                    int(max(0, min(255, ng))),
                    int(max(0, min(255, nb))),
                    a,
                )
    return im


def cutout(path: str) -> Image.Image:
    """白底泛洪抠图（沿用第一版逻辑）"""
    im = Image.open(path).convert("RGBA")
    w, h = im.size
    for sx, sy in [(0, 0), (w - 1, 0), (0, h - 1), (w - 1, h - 1)]:
        ImageDraw.floodfill(im, (sx, sy), (0, 0, 0, 0), thresh=30)
    return im.crop(im.getbbox())


def premult_resize(im: Image.Image, height: int) -> Image.Image:
    """预乘alpha缩放：黑底/白底各缩放一次，再解出真实颜色+alpha"""
    w0, h0 = im.size
    nw = max(1, round(w0 * height / h0))
    black = Image.new("RGBA", im.size, (0, 0, 0, 255))
    white = Image.new("RGBA", im.size, (255, 255, 255, 255))
    b_img = Image.alpha_composite(black, im).resize((nw, height), Image.LANCZOS)
    w_img = Image.alpha_composite(white, im).resize((nw, height), Image.LANCZOS)
    bp, wp = b_img.load(), w_img.load()
    out = Image.new("RGBA", (nw, height))
    op = out.load()
    for y in range(height):
        for x in range(nw):
            br, bg, bb, _ = bp[x, y]
            wr, wg, wb, _ = wp[x, y]
            a = 255 - max(wr - br, wg - bg, wb - bb)  # 覆盖度
            if a < 6:
                op[x, y] = (0, 0, 0, 0)
                continue
            t = a / 255.0
            op[x, y] = (
                int(max(0, min(255, br / t))),
                int(max(0, min(255, bg / t))),
                int(max(0, min(255, bb / t))),
                a,
            )
    return out


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--src", default="raw_sprites", help="白底三视图原图目录")
    parser.add_argument("--out", default="sprites", help="输出目录")
    args = parser.parse_args()
    os.makedirs(args.out, exist_ok=True)

    for name in NAMES:
        raw = cutout(os.path.join(args.src, f"{name}.png"))
        clean = decontaminate(raw)
        for h in SIZES.values():
            im = premult_resize(clean, h)
            im.save(os.path.join(args.out, f"{name}_{h}.png"))
            print(f"{name}_{h}.png {im.size}")

    # 托盘图标（用最小档再缩）
    icon = Image.open(os.path.join(args.out, "正面_187.png")).convert("RGBA")
    icon = premult_resize(icon, 64)
    icon.save(os.path.join(args.out, "icon.png"))
    print("icon 64x64")


if __name__ == "__main__":
    main()
