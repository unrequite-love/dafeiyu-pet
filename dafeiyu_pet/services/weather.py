"""天气查询：wttr.in，城市名 URL 编码，解析逻辑纯函数化。"""
from __future__ import annotations

import logging
import re
from urllib.parse import quote

import requests

from dafeiyu_pet.constants import (
    WEATHER_CODE_MAP,
    WEATHER_DESC_MAP,
    WEATHER_TIMEOUT_S,
)

logger = logging.getLogger(__name__)

WTTR_BASE = "https://wttr.in"

# 中↔英/数字边界（残留英文时自动补空格，避免中英文粘连）
_CJK = r"\u4e00-\u9fff"
_LATIN = r"A-Za-z0-9°"
_EDGE_PATTERNS = (
    re.compile(rf"(?<=[{_CJK}])(?=[{_LATIN}])"),
    re.compile(rf"(?<=[{_LATIN}])(?=[{_CJK}])"),
)


def pad_cjk_boundaries(text: str) -> str:
    """在中英文/数字交界处插入空格：「今天30C」→「今天 30C」。"""
    for pat in _EDGE_PATTERNS:
        text = pat.sub(" ", text)
    return text


def build_url(city: str) -> str:
    """构造 wttr.in 查询 URL；城市名（含中文/空格）需编码。"""
    return f"{WTTR_BASE}/{quote(city)}?format=j1"


def describe_condition(current: dict) -> str:
    """天气描述转中文：weatherCode 码表（主）→ 英文描述表（次）→ 原文补空格（兜底）。"""
    code = str(current.get("weatherCode", "") or "")
    if code in WEATHER_CODE_MAP:
        return WEATHER_CODE_MAP[code]
    raw = current["weatherDesc"][0]["value"]
    return WEATHER_DESC_MAP.get(raw, pad_cjk_boundaries(raw))


def parse_weather(data: dict) -> tuple[str, str]:
    """从 wttr.in j1 响应中解析 (温度℃, 天气描述中文)。"""
    current = data["current_condition"][0]
    return current["temp_C"], describe_condition(current)


def format_weather(city: str, temp: str, desc: str) -> str:
    """组装播报文本：「深圳今天 30°C，天气局部有雨」。"""
    return f"{city}今天 {temp}°C，天气{desc}"


_session: requests.Session | None = None
_session_trust_env: bool | None = None


def _get_session(use_proxy: bool) -> requests.Session:
    """模块级 Session 复用；代理设置变化时重建。"""
    global _session, _session_trust_env
    if _session is None or _session_trust_env != use_proxy:
        _session = requests.Session()
        _session.trust_env = use_proxy
        _session_trust_env = use_proxy
    return _session


def fetch_weather(
    city: str, timeout: float = WEATHER_TIMEOUT_S, use_proxy: bool = True
) -> tuple[str, str]:
    """查询指定城市当前天气，失败抛 requests 异常。"""
    resp = _get_session(use_proxy).get(
        build_url(city), timeout=timeout, headers={"User-Agent": "Mozilla/5.0"}
    )
    resp.raise_for_status()
    return parse_weather(resp.json())
