"""台词与常量完整性测试。"""
from dafeiyu_pet.constants import (
    DRAG_LINES,
    FOOD_LINES,
    FOODS,
    INNER_LINES,
    LINES,
    REACT_LINES,
    SIZE_LEVELS,
)


def test_line_lists_nonempty():
    for lines in (LINES, REACT_LINES, INNER_LINES, DRAG_LINES):
        assert len(lines) > 0
        assert all(isinstance(s, str) and s for s in lines)


def test_food_lines_cover_all_foods():
    assert set(FOOD_LINES) == set(FOODS)
    for food in FOODS:
        assert all(isinstance(s, str) and s for s in FOOD_LINES[food])


def test_size_levels_valid():
    assert sorted(SIZE_LEVELS.values()) == sorted(set(SIZE_LEVELS.values()))  # 无重复倍率
    assert all(0 < v < 1.5 for v in SIZE_LEVELS.values())
