"""系统监控阈值判定测试。"""
from dafeiyu_pet.services.monitor import evaluate


def test_normal_returns_none():
    assert evaluate(50, 60, 70) is None


def test_cpu_warning():
    assert evaluate(90, 60, 70) is not None
    assert evaluate(89.9, 60, 70) is None


def test_ram_warning():
    msg = evaluate(50, 95, 70)
    assert msg is not None and "内存" in msg
    assert evaluate(50, 94.9, 70) is None


def test_gpu_warning():
    msg = evaluate(50, 60, 81)
    assert msg is not None
    assert evaluate(50, 60, 80) is None   # 80 不触发（> 80 才触发）
    assert evaluate(50, 60, None) is None  # 无显卡


def test_priority_cpu_first():
    assert "CPU" in evaluate(95, 99, 99)
