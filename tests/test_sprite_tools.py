"""sprite_tools 工具箱测试：合成白底图验证算法，不依赖真实素材。

需要 Pillow；缺失时整文件跳过（保持核心测试零额外依赖）。
"""
import pytest

pytest.importorskip("PIL")

from PIL import Image, ImageDraw  # noqa: E402

from sprite_tools import (  # noqa: E402
    build_sizes,
    cutout_white,
    decontaminate,
    premult_resize,
    process_directory,
    resize_to_height,
    sprite_from_white_bg,
)


def make_white_bg_ellipse(w=200, h=150, color=(200, 40, 40)) -> Image.Image:
    """合成测试图：白底 + 中央红色椭圆（模拟白底立绘）。"""
    im = Image.new("RGBA", (w, h), (255, 255, 255, 255))
    d = ImageDraw.Draw(im)
    d.ellipse((40, 30, w - 40, h - 30), fill=color + (255,))
    return im


def test_cutout_white_transparent_bg_and_crop():
    im = cutout_white(make_white_bg_ellipse())
    # 四角透明（背景已抠掉）
    w, h = im.size
    for corner in ((0, 0), (w - 1, 0), (0, h - 1), (w - 1, h - 1)):
        assert im.getpixel(corner)[3] == 0
    # 中心不透明且保留原色
    assert im.getpixel((w // 2, h // 2)) == (200, 40, 40, 255)
    # 已裁掉空白边：尺寸小于原图
    assert im.size < (200, 150)


def test_cutout_white_all_background_raises():
    blank = Image.new("RGBA", (50, 50), (255, 255, 255, 255))
    with pytest.raises(ValueError):
        cutout_white(blank)


def test_decontaminate_keeps_opaque_pixels():
    im = make_white_bg_ellipse()
    out = decontaminate(cutout_white(im))
    w, h = out.size
    # 全不透明像素颜色不变
    assert out.getpixel((w // 2, h // 2)) == (200, 40, 40, 255)


def test_premult_resize_dimensions_and_alpha():
    im = cutout_white(make_white_bg_ellipse(200, 100))
    out = premult_resize(im, 50)
    assert out.height == 50
    assert out.width == round(im.width * 50 / im.height)
    # 中心仍不透明
    cx, cy = out.width // 2, out.height // 2
    assert out.getpixel((cx, cy))[3] == 255


def test_resize_to_height():
    im = Image.new("RGBA", (100, 50), (255, 0, 0, 255))
    out = resize_to_height(im, 100)
    assert out.size == (200, 100)


def test_sprite_from_white_bg_no_resize(tmp_path):
    p = tmp_path / "t.png"
    make_white_bg_ellipse().save(p)
    out = sprite_from_white_bg(p, height=None)
    assert out.height > 0  # 仅抠图不缩放


def test_sprite_from_white_bg_with_resize(tmp_path):
    p = tmp_path / "t.png"
    make_white_bg_ellipse(200, 150).save(p)
    out = sprite_from_white_bg(p, height=60)
    assert out.height == 60
    cx, cy = out.width // 2, 30
    assert out.getpixel((cx, cy))[3] == 255


def test_build_sizes_multiple():
    base = cutout_white(make_white_bg_ellipse(200, 100))
    sizes = build_sizes(base, [40, 60])
    assert sorted(sizes) == [40, 60]
    assert all(im.height == h for h, im in sizes.items())


def test_process_directory_end_to_end(tmp_path, capsys):
    src = tmp_path / "raw"
    src.mkdir()
    make_white_bg_ellipse(200, 150).save(src / "front.png")
    make_white_bg_ellipse(180, 150, color=(40, 40, 200)).save(src / "side.png")

    out = tmp_path / "out"
    written = process_directory(
        src, out, names=["front", "side"], height=100, sizes=[50], icon=32
    )

    stems = sorted(p.name for p in written)
    # 每张图各生成一个图标候选（front_icon / side_icon），不再是单一 icon.png
    assert stems == [
        "front.png",
        "front_50.png",
        "front_icon.png",
        "side.png",
        "side_50.png",
        "side_icon.png",
    ]
    assert Image.open(out / "front_icon.png").height == 32  # 等比缩放，只锁定目标高度
    assert Image.open(out / "side_icon.png").height == 32
    assert capsys.readouterr().out.count("->") == 6


def test_process_directory_auto_scan(tmp_path):
    src = tmp_path / "raw"
    src.mkdir()
    make_white_bg_ellipse().save(src / "a.png")
    make_white_bg_ellipse().save(src / "b.png")
    written = process_directory(src, tmp_path / "out", height=64)
    assert len(written) == 2


def test_process_directory_empty_dir_raises(tmp_path):
    src = tmp_path / "raw"
    src.mkdir()
    with pytest.raises(FileNotFoundError):
        process_directory(src, tmp_path / "out")
