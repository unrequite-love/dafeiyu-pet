"""DeepSeek 对话服务：V4 Pro 接口（无 /v1 前缀，支持 thinking 深度思考）。"""
from __future__ import annotations

import json
import logging
import threading
import time
from collections.abc import Iterator
from typing import Any

import requests

from dafeiyu_pet.constants import (
    DS_BASE_URL,
    DS_MAX_TOKENS,
    DS_MODEL,
    DS_REASONING_EFFORT,
    DS_REPLY_HARD_CAP,
    DS_RETRIABLE_STATUSES,
    DS_RETRIES,
    DS_RETRY_BACKOFF_S,
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


def truncate_reply(reply: str, limit: int = DS_REPLY_HARD_CAP) -> str:
    """仅当回复超过极端上限时截断（防模型失控刷屏）；正常回复完整返回。

    气泡本身支持自动换行，按字数动态延长显示时间，无需为显示而截断内容。
    """
    reply = reply.strip()
    if len(reply) > limit:
        reply = reply[: limit - 1] + "…"
    return reply


class ChatHistory:
    """对话历史：仅保留最近 max_entries 条（用户+回复各算一条）。

    传入 path 时启用持久化：启动加载、每轮追加即存盘。
    """

    def __init__(self, max_entries: int = MAX_HISTORY, path: str | None = None) -> None:
        self.max_entries = max_entries
        self.path = path
        self._entries: list[dict[str, str]] = []
        if path:
            self._load()

    def _load(self) -> None:
        assert self.path is not None
        try:
            with open(self.path, encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, list):
                self._entries = [
                    e for e in data if isinstance(e, dict) and e.get("role") and e.get("content")
                ][-self.max_entries :]
        except FileNotFoundError:
            pass
        except (OSError, json.JSONDecodeError) as e:
            logger.warning("对话历史读取失败，从空开始: %s", e)

    def save(self) -> None:
        if not self.path:
            return
        try:
            with open(self.path, "w", encoding="utf-8") as f:
                json.dump(self._entries, f, ensure_ascii=False, indent=2)
        except OSError as e:
            logger.warning("对话历史写入失败: %s", e)

    def append_turn(self, user_msg: str, reply: str) -> None:
        self._entries.append({"role": "user", "content": user_msg})
        self._entries.append({"role": "assistant", "content": reply})
        if len(self._entries) > self.max_entries:
            del self._entries[: len(self._entries) - self.max_entries]
        self.save()

    def clear(self) -> None:
        self._entries.clear()
        self.save()

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
    """DeepSeek 客户端：同步调用，内部锁保证线程安全。

    - 持有 requests.Session 复用 TCP/TLS 连接，省去每次握手延迟；
    - use_proxy=False 时 session.trust_env=False，绕过系统/环境代理直连
      （代理拦截 api.deepseek.com 导致超时时用）。
    """

    def __init__(
        self,
        api_key: str,
        base_url: str = DS_BASE_URL,
        model: str = DS_MODEL,
        thinking: bool = False,
        timeout: float | None = None,
        use_proxy: bool = True,
    ) -> None:
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.thinking = thinking
        if timeout is None:
            timeout = DS_THINKING_TIMEOUT_S if thinking else DS_TIMEOUT_S
        self.timeout = timeout
        self._lock = threading.Lock()
        self._session = requests.Session()
        self._session.trust_env = use_proxy

    def _post(self, payload: dict[str, Any]) -> requests.Response:
        """发起请求；429/5xx 按指数退避重试（网络异常不在此处重试，直接上抛分类）。"""
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        url = chat_url(self.base_url)
        resp: requests.Response | None = None
        for attempt in range(DS_RETRIES):
            try:
                resp = self._session.post(url, json=payload, headers=headers, timeout=self.timeout)
            except requests.exceptions.Timeout as e:
                raise DeepSeekTimeout from e
            except requests.exceptions.ConnectionError as e:
                raise DeepSeekConnectionError from e
            if resp.status_code not in DS_RETRIABLE_STATUSES:
                break
            if attempt < DS_RETRIES - 1:
                delay = DS_RETRY_BACKOFF_S * (2**attempt)
                logger.warning(
                    "DeepSeek 返回 %s，%.1fs 后重试（%d/%d）",
                    resp.status_code, delay, attempt + 1, DS_RETRIES - 1,
                )
                time.sleep(delay)
        assert resp is not None
        return resp

    def _parse(self, resp: requests.Response) -> str:
        if resp.status_code != 200:
            try:
                msg = resp.json().get("error", {}).get("message", str(resp.status_code))
            except ValueError:
                msg = f"HTTP {resp.status_code}"
            logger.warning(
                "DeepSeek API 错误: %s %s | 响应: %s", resp.status_code, msg, resp.text[:300]
            )
            raise DeepSeekError(msg)
        try:
            data = resp.json()
        except ValueError as e:
            raise DeepSeekError(f"HTTP {resp.status_code} 响应非 JSON") from e
        return truncate_reply(extract_reply(data))

    def chat(self, messages: list[dict[str, str]]) -> str:
        """调用对话接口（非流式），返回（已截断的）回复文本。

        失败抛 DeepSeekError 及其子类，网络异常会被翻译为对应子类。
        """
        with self._lock:
            resp = self._post(build_payload(messages, model=self.model, thinking=self.thinking))
        return self._parse(resp)

    def chat_stream(self, messages: list[dict[str, str]]) -> Iterator[str]:
        """流式调用：逐段 yield 最终回复的增量文本（reasoning 思考段不上屏）。

        失败抛 DeepSeekError 及其子类。
        """
        payload = build_payload(messages, model=self.model, thinking=self.thinking)
        payload["stream"] = True
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        try:
            with self._lock, self._session.post(
                chat_url(self.base_url), json=payload, headers=headers,
                timeout=self.timeout, stream=True,
            ) as resp:
                if resp.status_code != 200:
                    # 流式错误响应体小，直接读出排错
                    body = resp.text[:300]
                    logger.warning(
                        "DeepSeek 流式 API 错误: %s | 响应: %s", resp.status_code, body
                    )
                    try:
                        msg = resp.json().get("error", {}).get("message", str(resp.status_code))
                    except ValueError:
                        msg = f"HTTP {resp.status_code}"
                    raise DeepSeekError(msg)
                for raw in resp.iter_lines(decode_unicode=True):
                    if not raw or not raw.startswith("data:"):
                        continue
                    data_str = raw[5:].strip()
                    if data_str == "[DONE]":
                        break
                    try:
                        chunk = json.loads(data_str)
                    except json.JSONDecodeError:
                        continue
                    if chunk.get("error"):
                        raise DeepSeekError(str(chunk["error"].get("message", "stream error")))
                    try:
                        delta = chunk["choices"][0].get("delta") or {}
                    except (KeyError, IndexError):
                        continue
                    content = delta.get("content") or ""
                    if content:
                        yield content
        except requests.exceptions.Timeout as e:
            raise DeepSeekTimeout from e
        except requests.exceptions.ConnectionError as e:
            raise DeepSeekConnectionError from e
