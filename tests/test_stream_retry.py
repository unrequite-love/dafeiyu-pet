"""流式（SSE）与重试逻辑测试：模拟 Session 响应，不发真实网络请求。"""
from __future__ import annotations

import json

import pytest
import requests

from dafeiyu_pet.services.deepseek import (
    DeepSeekClient,
    DeepSeekConnectionError,
    DeepSeekError,
)


class FakeResponse:
    def __init__(self, status_code=200, chunks: list[str] | None = None, text=""):
        self.status_code = status_code
        self._chunks = chunks or []
        self.text = text

    def iter_lines(self, decode_unicode=True):
        yield from self._chunks

    def json(self):
        raise ValueError("not json")

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


class FakeSession:
    def __init__(self, response):
        self.response = response
        self.calls: list[dict] = []

    def post(self, url, json=None, headers=None, timeout=None, stream=False):
        self.calls.append({"json": json, "stream": stream})
        return self.response


def _client(session):
    c = DeepSeekClient("k")
    c._session = session
    return c


def _sse(*events) -> list[str]:
    lines = []
    for ev in events:
        lines.append("data: " + json.dumps(ev, ensure_ascii=False))
    lines.append("data: [DONE]")
    return lines


def test_chat_stream_yields_content_deltas():
    chunks = _sse(
        {"choices": [{"delta": {"reasoning_content": "thinking..."}}]},
        {"choices": [{"delta": {"content": "你好"}}]},
        {"choices": [{"delta": {"content": "呀～"}}]},
        {"choices": [{"delta": {}}]},
    )
    c = _client(FakeSession(FakeResponse(chunks=chunks)))
    assert list(c.chat_stream([{"role": "user", "content": "hi"}])) == ["你好", "呀～"]
    # 请求体应显式 stream=True
    sent = c._session.calls[0]
    assert sent["stream"] is True and sent["json"]["stream"] is True


def test_chat_stream_http_error_raises():
    c = _client(FakeSession(FakeResponse(status_code=401, text="denied")))
    with pytest.raises(DeepSeekError):
        list(c.chat_stream([{"role": "user", "content": "hi"}]))


def test_chat_stream_midstream_error_event():
    chunks = _sse({"choices": [{"delta": {"content": "部分"}}]})[:-1] + [
        "data: " + json.dumps({"error": {"message": "rate limited"}})
    ]
    c = _client(FakeSession(FakeResponse(chunks=chunks)))
    gen = c.chat_stream([{"role": "user", "content": "hi"}])
    assert next(gen) == "部分"
    with pytest.raises(DeepSeekError):
        next(gen)


def test_chat_stream_tolerates_junk_lines():
    chunks = ["", ": keep-alive", "not-data", "data: {bad json}"] + _sse(
        {"choices": [{"delta": {"content": "ok"}}]}
    )
    c = _client(FakeSession(FakeResponse(chunks=chunks)))
    assert list(c.chat_stream([{"role": "user", "content": "hi"}])) == ["ok"]


def test_chat_retries_on_5xx_then_succeeds():
    class FlakySession:
        def __init__(self):
            self.n = 0

        def post(self, url, json=None, headers=None, timeout=None, stream=False):
            self.n += 1
            if self.n < 3:
                return FakeOKResponseText(
                    status_code=503, body='{"choices":[{"message":{"content":"never"}}]}'
                )
            return FakeOKResponseText(
                status_code=200, body='{"choices":[{"message":{"content":"第3次成了"}}]}'
            )

    class FakeOKResponseText:
        def __init__(self, status_code, body):
            self.status_code = status_code
            self.text = body

        def json(self):
            return json.loads(self.text)

    c = _client(FlakySession())
    assert c.chat([{"role": "user", "content": "hi"}]) == "第3次成了"
    assert c._session.n == 3  # 两次 503 + 一次成功


def test_chat_no_retry_on_4xx(monkeypatch):
    class OnceSession:
        n = 0

        def post(self, url, json=None, headers=None, timeout=None, stream=False):
            type(self).n += 1
            return FakeResponse(status_code=401, text="denied")

    c = _client(OnceSession())
    with pytest.raises(DeepSeekError):
        c.chat([{"role": "user", "content": "hi"}])
    assert OnceSession.n == 1  # 4xx 不重试


def test_network_error_not_retried():
    class DeadSession:
        n = 0

        def post(self, url, **kw):
            type(self).n += 1
            raise requests.exceptions.ConnectionError("boom")

    c = _client(DeadSession())
    with pytest.raises(DeepSeekConnectionError):
        c.chat([{"role": "user", "content": "hi"}])
    assert DeadSession.n == 1  # 网络异常不重试（重试仅针对 429/5xx）
