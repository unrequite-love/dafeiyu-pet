"""系统监控阈值判定与间隔清洗测试。"""
from dafeiyu_pet.constants import (
    MONITOR_INTERVAL_S,
    MONITOR_MAX_INTERVAL_S,
    MONITOR_MIN_INTERVAL_S,
)
from dafeiyu_pet.services.monitor import clamp_interval, evaluate


def test_clamp_interval_normal():
    assert clamp_interval(10) == 10.0
    assert clamp_interval(30.5) == 30.5
    assert clamp_interval("15") == 15.0  # 手改 config.json 存成字符串也容忍


def test_clamp_interval_bounds():
    assert clamp_interval(1) == MONITOR_MIN_INTERVAL_S  # 过小钳到下限
    assert clamp_interval(99999) == MONITOR_MAX_INTERVAL_S  # 过大钳到上限
    assert clamp_interval(MONITOR_MIN_INTERVAL_S) == MONITOR_MIN_INTERVAL_S
    assert clamp_interval(MONITOR_MAX_INTERVAL_S) == MONITOR_MAX_INTERVAL_S


def test_clamp_interval_invalid_falls_back():
    assert clamp_interval(None) == MONITOR_INTERVAL_S
    assert clamp_interval("abc") == MONITOR_INTERVAL_S
    assert clamp_interval(-5) == MONITOR_INTERVAL_S
    assert clamp_interval(0) == MONITOR_INTERVAL_S
    assert clamp_interval(float("nan")) == MONITOR_INTERVAL_S


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
