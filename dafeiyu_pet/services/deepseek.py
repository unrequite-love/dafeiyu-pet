"""DeepSeek 对话服务：V4 Pro 接口（无 /v1 前缀，支持 thinking 深度思考）。"""
from __future__ import annotations

import logging
import threading
from typing import Any

import requests

from dafeiyu_pet.constants import (
    DS_BASE_URL,
    DS_MAX_TOKENS,
    DS_MODEL,
    DS_REASONING_EFFORT,
    DS_REPLY_MAX_LEN,
    DS_SYSTEM_PROMPT,
    DS_TEMPERATURE,
    DS_THINKING_TIMEOUT_S,
    DS_TIMEOUT_S,
    MAX_HISTORY,
)

logger = logging.getLogger(__name__)


class DeepSeekError(Exception):
    """DeepSeek 调用失败（API 错误 / 网络）。"""


class DeepSeekTimeout(DeepSeekError):
    """请求超时。"""


class DeepSeekConnectionError(DeepSeekError):
    """连接失败。"""


def chat_url(base_url: str = DS_BASE_URL) -> str:
    """对话接口完整 URL（注意：新版接口无 /v1 前缀）。"""
    return f"{base_url.rstrip('/')}/chat/completions"


def build_messages(
    system: str = DS_SYSTEM_PROMPT,
    history: list[dict[str, str]] | None = None,
    user_msg: str = "",
    max_history: int = MAX_HISTORY,
) -> list[dict[str, str]]:
    """组装请求消息：system + 最近 N 条历史 + 当前用户输入。"""
    messages: list[dict[str, str]] = [{"role": "system", "content": system}]
    if history:
        messages.extend(history[-max_history:])
    messages.append({"role": "user", "content": user_msg})
    return messages


def truncate_reply(reply: str, limit: int = DS_REPLY_MAX_LEN) -> str:
    """回复超长时截断（末尾以省略号收尾），保证气泡不撑爆。"""
    reply = reply.strip()
    if len(reply) > limit:
        reply = reply[: limit - 2] + "…"
    return reply


class ChatHistory:
    """对话历史：仅保留最近 max_entries 条（用户+回复各算一条）。"""

    def __init__(self, max_entries: int = MAX_HISTORY) -> None:
        self.max_entries = max_entries
        self._entries: list[dict[str, str]] = []

    def append_turn(self, user_msg: str, reply: str) -> None:
        self._entries.append({"role": "user", "content": user_msg})
        self._entries.append({"role": "assistant", "content": reply})
        if len(self._entries) > self.max_entries:
            del self._entries[: len(self._entries) - self.max_entries]

    def entries(self) -> list[dict[str, str]]:
        return list(self._entries)

    def __len__(self) -> int:
        return len(self._entries)


def build_payload(
    messages: list[dict[str, str]],
    model: str = DS_MODEL,
    thinking: bool = False,
    reasoning_effort: str = DS_REASONING_EFFORT,
    max_tokens: int = DS_MAX_TOKENS,
    temperature: float = DS_TEMPERATURE,
) -> dict[str, Any]:
    """构造请求体（对齐 V4 Pro 接口）。

    - stream 恒为 False（气泡逐句展示，无需流式）；
    - 深度思考模式：thinking=enabled + reasoning_effort；不设 max_tokens
      （给推理 token 留余量，否则 100 上限会被思考耗尽导致空回复），不发 temperature；
    - 普通模式：thinking=disabled，限输出长度并带温度，短平快。
    """
    payload: dict[str, Any] = {
        "model": model,
        "messages": messages,
        "stream": False,
        "thinking": {"type": "enabled" if thinking else "disabled"},
    }
    if thinking:
        payload["reasoning_effort"] = reasoning_effort
    else:
        payload["max_tokens"] = max_tokens
        payload["temperature"] = temperature
    return payload


def extract_reply(data: dict) -> str:
    """取最终回复（reasoning_content 是思考过程，不展示）。"""
    msg = data["choices"][0]["message"]
    reply = (msg.get("content") or "").strip()
    if not reply:
        raise DeepSeekError("回复为空")
    return reply


class DeepSeekClient:
    """DeepSeek 客户端：同步调用，内部锁保证线程安全。"""

    def __init__(
        self,
        api_key: str,
        base_url: str = DS_BASE_URL,
        model: str = DS_MODEL,
        thinking: bool = False,
        timeout: float | None = None,
    ) -> None:
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.thinking = thinking
        if timeout is None:
            timeout = DS_THINKING_TIMEOUT_S if thinking else DS_TIMEOUT_S
        self.timeout = timeout
        self._lock = threading.Lock()

    def chat(self, messages: list[dict[str, str]]) -> str:
        """调用对话接口，返回（已截断的）回复文本。

        失败抛 DeepSeekError 及其子类，网络异常会被翻译为对应子类。
        """
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        try:
            with self._lock:
                resp = requests.post(
                    chat_url(self.base_url),
                    json=build_payload(messages, model=self.model, thinking=self.thinking),
                    headers=headers,
                    timeout=self.timeout,
                )
        except requests.exceptions.Timeout as e:
            raise DeepSeekTimeout from e
        except requests.exceptions.ConnectionError as e:
            raise DeepSeekConnectionError from e

        if resp.status_code != 200:
            try:
                msg = resp.json().get("error", {}).get("message", str(resp.status_code))
            except ValueError:
                msg = f"HTTP {resp.status_code}"
            logger.warning("DeepSeek API 错误: %s %s", resp.status_code, msg)
            raise DeepSeekError(msg)
        try:
            data = resp.json()
        except ValueError as e:
            raise DeepSeekError(f"HTTP {resp.status_code} 响应非 JSON") from e
        return truncate_reply(extract_reply(data))
