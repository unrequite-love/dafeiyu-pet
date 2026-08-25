"""朝向选择与精灵映射逻辑测试。"""
import pytest

from dafeiyu_pet.logic import choose_direction, sprite_key


@pytest.mark.parametrize(
    ("dx", "dy", "expected"),
    [
        (-100, 0, ("left", 1)),    # 向左：原图
        (100, 0, ("right", -1)),   # 向右：镜像
        (-100, 10, ("left", 1)),
        (0, -50, ("up", None)),    # 向上：背面
        (0, 50, ("down", None)),   # 向下：正面
        (10, -100, ("up", None)),
        (10, 100, ("down", None)),
    ],
)
def test_choose_direction(dx, dy, expected):
    assert choose_direction(dx, dy) == expected


def test_choose_direction_horizontal_bias():
    # |dx| > |dy|*1.15 才算水平：1.15 倍系数边界（dy 为负=向上）
    assert choose_direction(114, -100) == ("up", None)      # 114 < 115 → 垂直
    assert choose_direction(116, -100) == ("right", -1)     # 116 > 115 → 水平


def test_sprite_key_mapping():
    assert sprite_key("left", 1, 238) == ("侧面", 238, 1)
    assert sprite_key("right", -1, 238) == ("侧面", 238, -1)
    assert sprite_key("up", -1, 187) == ("背面", 187, 1)    # 垂直方向忽略镜像
    assert sprite_key("down", -1, 306) == ("正面", 306, 1)
