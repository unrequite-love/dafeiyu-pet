"""sprite_tools.py —— 白底精灵图预处理工具箱（单文件、零项目依赖，可直接拷贝复用）。

依赖：Python 3.10+ 、Pillow（pip install Pillow）。除标准库与 PIL 外不依赖任何项目内模块，
把这一个文件复制到其他项目即可直接使用（import 或命令行）。

功能（针对「白底立绘 → 透明精灵图」场景）：
1. cutout_white      白底泛洪抠图 + 去白边 + 裁空白边（不缩放）
2. decontaminate     边缘像素对白底去混合，恢复真实颜色（消除旋转/移动时的白晕）
3. premult_resize    预乘 alpha 缩放（黑底/白底双采样），缩放后边缘不发白不发黑
4. sprite_from_white_bg / build_sizes / process_directory  组合流水线

库用法：
    from sprite_tools import sprite_from_white_bg, build_sizes, premult_resize

    base = sprite_from_white_bg("raw/正面.png", height=340)      # 抠图+去污+统一高度
    for h, im in build_sizes(base, [187, 238, 306]).items():      # 生成多尺寸
        im.save(f"sprites/正面_{h}.png")
    premult_resize(base, 64).save("sprites/正面_icon.png")        # 该图的图标候选

命令行用法：
    python sprite_tools.py --src raw_sprites --out sprites --height 340 ^
        --sizes 187,238,306 --icon 64
        （--icon 为每张图各生成 {name}_icon.png，便于挑选最终图标）
    python sprite_tools.py --src raw --out out --names front,side,back
        （--names 缺省时自动扫描 src 下全部 *.png）
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from PIL import Image, ImageDraw

__all__ = [
    "cutout_white",
    "decontaminate",
    "premult_resize",
    "resize_to_height",
    "sprite_from_white_bg",
    "build_sizes",
    "process_directory",
]


# ---------------- 核心操作（每个函数独立可用） ----------------


def cutout_white(
    im: Image.Image,
    thresh: int = 30,
    edge_light: int = 215,
    edge_rounds: int = 3,
) -> Image.Image:
    """白底抠图：泛洪背景变透明 → 去白边 → 裁掉空白边（不缩放，保持原尺寸）。

    - im: RGBA 图（传 RGB 会自动转换）；要求背景为白色且接触图像四边
    - thresh: 泛洪容差（相邻像素与种子差值小于该值视为背景）
    - edge_light: 「亮像素」阈值，贴着透明区的亮像素视为抗锯齿白边一并清除
    - edge_rounds: 白边腐蚀轮数（每轮清除一层贴边亮像素）
    """
    im = im.convert("RGBA")
    w, h = im.size
    # 1) 从四角做连通域泛洪，把背景整片变透明（人物内部的白不受影响）
    for sx, sy in ((0, 0), (w - 1, 0), (0, h - 1), (w - 1, h - 1)):
        ImageDraw.floodfill(im, (sx, sy), (0, 0, 0, 0), thresh=thresh)
    # 2) 去白边：贴着透明区的亮像素也变透明（消除抗锯齿白晕）
    neighbors = ((1, 0), (-1, 0), (0, 1), (0, -1), (1, 1), (-1, -1), (1, -1), (-1, 1))
    for _ in range(edge_rounds):
        px = im.load()
        changed = False
        for y in range(h):
            for x in range(w):
                r, g, b, a = px[x, y]
                if a == 0:
                    continue
                if r > edge_light and g > edge_light and b > edge_light:
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
        raise ValueError("抠图后为空：图像在泛洪后没有任何不透明像素（背景是全图？）")
    return im.crop(bbox)


def decontaminate(im: Image.Image, min_alpha: int = 40) -> Image.Image:
    """边缘像素对白底去混合：pixel = fg*a + 255*(1-a) → fg = (pixel - 255*(1-a)) / a。

    - im: 已抠图的 RGBA 图（半透明边缘像素混有白底成分）
    - min_alpha: alpha 低于该值的极淡边缘直接置透明，避免除噪放大
    """
    im = im.convert("RGBA")
    px = im.load()
    w, h = im.size
    for y in range(h):
        for x in range(w):
            r, g, b, a = px[x, y]
            if 0 < a < 255:
                t = a / 255.0
                if a < min_alpha:
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


def premult_resize(im: Image.Image, height: int, min_alpha: int = 6) -> Image.Image:
    """预乘 alpha 缩放：黑底/白底各缩放一次，再解出真实颜色 + alpha。

    普通缩放会让半透明边缘混入透明色（发灰/发白/发黑）；本方法对纯黑与纯白
    两个极端背景分别合成后缩放，由两者差值反解覆盖度，边缘颜色干净。
    - im: RGBA 图
    - height: 目标高度(px)，宽度按原比例计算
    - min_alpha: 解出的 alpha 低于该值直接透明
    """
    im = im.convert("RGBA")
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
            if a < min_alpha:
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


def resize_to_height(im: Image.Image, height: int) -> Image.Image:
    """普通 LANCZOS 等比缩放到指定高度（质量要求不高时的平替）。"""
    w, h = im.size
    nw = max(1, round(w * height / h))
    return im.convert("RGBA").resize((nw, height), Image.LANCZOS)


# ---------------- 组合流水线 ----------------


def sprite_from_white_bg(
    path: str | os.PathLike[str],
    height: int | None = None,
    *,
    decontaminate_edges: bool = True,
    premultiplied: bool = True,
    **kwargs,
) -> Image.Image:
    """完整流水线：读取白底图 → 抠图 →（可选）去污 →（可选）预乘缩放到指定高度。

    - height: 目标高度；None 表示不缩放（返回抠图后的原始尺寸）
    - decontaminate_edges: 是否做白底去混合（推荐 True，配合 premultiplied）
    - premultiplied: True 用 premult_resize（边缘干净），False 用普通 LANCZOS
    - kwargs: 透传给 cutout_white（thresh / edge_light / edge_rounds）
    """
    im = cutout_white(Image.open(path), **kwargs)
    if decontaminate_edges:
        im = decontaminate(im)
    if height is not None:
        im = premult_resize(im, height) if premultiplied else resize_to_height(im, height)
    return im


def build_sizes(
    im: Image.Image, heights: list[int], premultiplied: bool = True
) -> dict[int, Image.Image]:
    """从基准图生成多个尺寸版本：{高度: 图像}。"""
    out: dict[int, Image.Image] = {}
    for h in heights:
        out[h] = premult_resize(im, h) if premultiplied else resize_to_height(im, h)
    return out


def process_directory(
    src: str | os.PathLike[str],
    out: str | os.PathLike[str],
    names: list[str] | None = None,
    height: int = 340,
    sizes: list[int] | None = None,
    icon: int | None = None,
    decontaminate_edges: bool = True,
) -> list[Path]:
    """批量处理目录：src 下的白底 PNG → out 下的基准图 + 各尺寸 +（可选）图标。

    - names: 指定文件名列表（不含扩展名）；None 则自动扫描 src 下全部 *.png
    - height: 基准高度，输出 {name}.png
    - sizes: 附加尺寸高度列表，输出 {name}_{h}.png
    - icon: 附加为**每张图**生成 {name}_icon.png（预乘缩放，保持宽高比），
      便于用户预览对比后挑选合适的一张作为最终图标
    - decontaminate_edges: 是否做白底去混合（推荐 True）
    返回生成的文件路径列表。
    """
    src_dir, out_dir = Path(src), Path(out)
    out_dir.mkdir(parents=True, exist_ok=True)
    if names is None:
        names = sorted(p.stem for p in src_dir.glob("*.png"))
    if not names:
        raise FileNotFoundError(f"{src_dir} 下没有找到 PNG 文件")

    written: list[Path] = []
    for name in names:
        base = sprite_from_white_bg(
            src_dir / f"{name}.png", height, decontaminate_edges=decontaminate_edges
        )
        p = out_dir / f"{name}.png"
        base.save(p)
        written.append(p)
        print(f"{name}: {base.size} -> {p}")
        if sizes:
            for h, im in build_sizes(base, sizes).items():
                p = out_dir / f"{name}_{h}.png"
                im.save(p)
                written.append(p)
                print(f"{name}_{h}: {im.size} -> {p}")
        if icon is not None:
            icon_im = premult_resize(base, icon)
            p = out_dir / f"{name}_icon.png"
            icon_im.save(p)
            written.append(p)
            print(f"{name}_icon: {icon_im.size} -> {p}")
    return written


# ---------------- 命令行入口 ----------------


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="白底精灵图预处理工具箱（抠图/去污/预乘 alpha 多尺寸）",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--src", default="raw_sprites", help="白底原图目录")
    parser.add_argument("--out", default="sprites", help="输出目录")
    parser.add_argument(
        "--names", default=None, help="文件名列表（逗号分隔，不含扩展名）；缺省扫描全部 PNG"
    )
    parser.add_argument("--height", type=int, default=340, help="基准高度(px)")
    parser.add_argument("--sizes", default="", help="附加尺寸高度列表（逗号分隔），如 187,238,306")
    parser.add_argument(
        "--icon", type=int, default=None,
        help="为每张图生成图标尺寸(px)，输出 {name}_icon.png，便于挑选最终图标",
    )
    parser.add_argument("--no-decontam", action="store_true", help="跳过白底去混合（一般不建议）")
    args = parser.parse_args(argv)

    names = [s.strip() for s in args.names.split(",") if s.strip()] if args.names else None
    sizes = [int(s) for s in args.sizes.split(",") if s.strip()] or None

    process_directory(
        args.src, args.out, names, args.height, sizes, args.icon,
        decontaminate_edges=not args.no_decontam,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
