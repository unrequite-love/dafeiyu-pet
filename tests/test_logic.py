"""朝向选择、精灵映射、气泡时长等纯逻辑测试。"""
import pytest

from dafeiyu_pet.constants import BUBBLE_MAX_SECONDS, BUBBLE_SECONDS
from dafeiyu_pet.logic import bubble_duration, choose_direction, sprite_key


def test_bubble_duration_scales_with_length():
    assert bubble_duration("") == pytest.approx(BUBBLE_SECONDS)  # 空文本=基础时长
    short = bubble_duration("你好呀")
    longer = bubble_duration("这是一条比较长的回复，需要更多阅读时间哦～")
    assert BUBBLE_SECONDS < short < longer
    # 每字符 0.12s
    assert bubble_duration("x" * 10) == pytest.approx(BUBBLE_SECONDS + 1.2)


def test_bubble_duration_capped():
    assert bubble_duration("x" * 200) == pytest.approx(BUBBLE_MAX_SECONDS)


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
