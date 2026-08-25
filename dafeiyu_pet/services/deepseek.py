"""DeepSeek 对话服务：消息构建/截断为纯函数，网络调用封装为客户端。"""
from __future__ import annotations

import logging
import threading
from typing import Any

import requests

from dafeiyu_pet.constants import (
    DS_BASE_URL,
    DS_MAX_TOKENS,
    DS_MODEL,
    DS_REPLY_MAX_LEN,
    DS_SYSTEM_PROMPT,
    DS_TEMPERATURE,
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


class DeepSeekClient:
    """DeepSeek 客户端：同步调用，内部锁保证线程安全。"""

    def __init__(
        self,
        api_key: str,
        base_url: str = DS_BASE_URL,
        model: str = DS_MODEL,
        timeout: float = DS_TIMEOUT_S,
    ) -> None:
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout = timeout
        self._lock = threading.Lock()

    def chat(self, messages: list[dict[str, str]]) -> str:
        """调用对话接口，返回（已截断的）回复文本。

        失败抛 DeepSeekError 及其子类，网络异常会被翻译为对应子类。
        """
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "max_tokens": DS_MAX_TOKENS,
            "temperature": DS_TEMPERATURE,
        }
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        try:
            with self._lock:
                resp = requests.post(
                    f"{self.base_url}/chat/completions",
                    json=payload,
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
        reply = resp.json()["choices"][0]["message"]["content"]
        return truncate_reply(reply)
