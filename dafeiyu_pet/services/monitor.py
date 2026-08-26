"""系统状态监控：CPU/内存/NVIDIA 显卡温度阈值告警。"""
from __future__ import annotations

import logging

import psutil

from dafeiyu_pet.constants import (
    CPU_WARN_PERCENT,
    GPU_WARN_TEMP_C,
    MONITOR_INTERVAL_S,
    MONITOR_MAX_INTERVAL_S,
    MONITOR_MIN_INTERVAL_S,
    RAM_WARN_PERCENT,
)

logger = logging.getLogger(__name__)


def clamp_interval(value: object, default: float = MONITOR_INTERVAL_S) -> float:
    """清洗配置中的检测间隔：非法/越界值回退默认并钳制到 [5, 3600] 秒。"""
    try:
        v = float(value)
    except (TypeError, ValueError):
        return default
    if v != v or v <= 0:  # NaN 或非正数
        return default
    return min(max(v, MONITOR_MIN_INTERVAL_S), MONITOR_MAX_INTERVAL_S)

try:
    import pynvml

    pynvml.nvmlInit()
    GPU_AVAILABLE = True
except Exception as e:  # 未安装 pynvml 或本机无 NVIDIA 显卡
    logger.debug("GPU 监控不可用: %s", e)
    GPU_AVAILABLE = False


def evaluate(cpu: float, ram: float, gpu_temp: int | None) -> str | None:
    """按优先级判定告警消息，正常返回 None。"""
    if cpu >= CPU_WARN_PERCENT:
        return "CPU跑满了，再这样下去我就卡死了"
    if ram >= RAM_WARN_PERCENT:
        return "内存爆了，快关掉几个没用的东西吧，注意，别把我关了"
    if gpu_temp is not None and gpu_temp > GPU_WARN_TEMP_C:
        return "我感觉我的鱼鳍快熟了"
    return None


def read_stats() -> tuple[float, float]:
    """读取 (CPU 占用%, 内存占用%)。"""
    return psutil.cpu_percent(), psutil.virtual_memory().percent


def read_gpu_temps() -> list[int]:
    """读取所有 NVIDIA 显卡温度(°C)，不可用/失败返回空列表。"""
    if not GPU_AVAILABLE:
        return []
    temps: list[int] = []
    try:
        count = pynvml.nvmlDeviceGetCount()
        for i in range(count):
            try:
                handle = pynvml.nvmlDeviceGetHandleByIndex(i)
                temps.append(
                    int(pynvml.nvmlDeviceGetTemperature(handle, pynvml.NVML_TEMPERATURE_GPU))
                )
            except Exception as e:  # 单卡失败不影响其余卡
                logger.debug("GPU %d 温度读取失败: %s", i, e)
    except Exception as e:
        logger.debug("GPU 枚举失败: %s", e)
    return temps


def read_gpu_temp() -> int | None:
    """读取最高显卡温度(°C)（多卡取最大），不可用时返回 None。"""
    temps = read_gpu_temps()
    return max(temps) if temps else None
