"""天气查询：wttr.in，城市名 URL 编码，解析逻辑纯函数化。"""
from __future__ import annotations

import logging
from urllib.parse import quote

import requests

from dafeiyu_pet.constants import WEATHER_DESC_MAP, WEATHER_TIMEOUT_S

logger = logging.getLogger(__name__)

WTTR_BASE = "https://wttr.in"


def build_url(city: str) -> str:
    """构造 wttr.in 查询 URL；城市名（含中文/空格）需编码。"""
    return f"{WTTR_BASE}/{quote(city)}?format=j1"


def parse_weather(data: dict) -> tuple[str, str]:
    """从 wttr.in j1 响应中解析 (温度℃, 天气描述中文)。"""
    current = data["current_condition"][0]
    temp = current["temp_C"]
    raw_desc = current["weatherDesc"][0]["value"]
    return temp, WEATHER_DESC_MAP.get(raw_desc, raw_desc)


def fetch_weather(city: str, timeout: float = WEATHER_TIMEOUT_S) -> tuple[str, str]:
    """查询指定城市当前天气，失败抛 requests 异常。"""
    resp = requests.get(build_url(city), timeout=timeout, headers={"User-Agent": "Mozilla/5.0"})
    resp.raise_for_status()
    return parse_weather(resp.json())
