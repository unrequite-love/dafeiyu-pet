"""无 Qt 依赖的纯逻辑，便于单元测试。"""
from __future__ import annotations

DIRECTION_TO_SPRITE = {"left": "侧面", "right": "侧面", "up": "背面", "down": "正面"}
HORIZONTAL = ("left", "right")


def choose_direction(dx: float, dy: float) -> tuple[str, int | None]:
    """根据位移选择朝向：水平优先（1.15 倍系数）。

    返回 (方向, 镜像)。镜像：1=原图朝左，-1=水平翻转朝右，None=不适用。
    """
    if abs(dx) > abs(dy) * 1.15:
        return ("left", 1) if dx < 0 else ("right", -1)
    return ("up", None) if dy < 0 else ("down", None)


def sprite_key(direction: str, facing: int, height: int) -> tuple[str, int, int]:
    """朝向 → (精灵图名, 高度, 有效镜像)；仅水平方向应用镜像。"""
    effective = facing if direction in HORIZONTAL else 1
    return (DIRECTION_TO_SPRITE[direction], height, effective)
