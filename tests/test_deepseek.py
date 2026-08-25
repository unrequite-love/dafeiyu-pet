"""DeepSeek 消息构建/历史/截断/请求体纯逻辑测试（不发真实请求）。"""
import pytest

from dafeiyu_pet.constants import DS_MODEL, DS_SYSTEM_PROMPT, MAX_HISTORY
from dafeiyu_pet.services.deepseek import (
    ChatHistory,
    DeepSeekError,
    build_messages,
    build_payload,
    chat_url,
    extract_reply,
    truncate_reply,
)


def test_build_messages_structure():
    history = [
        {"role": "user", "content": "你好"},
        {"role": "assistant", "content": "你好呀"},
    ]
    msgs = build_messages(DS_SYSTEM_PROMPT, history, "吃饭了吗")
    assert msgs[0]["role"] == "system"
    assert msgs[0]["content"] == DS_SYSTEM_PROMPT
    assert msgs[-1] == {"role": "user", "content": "吃饭了吗"}
    assert len(msgs) == 4


def test_build_messages_caps_history():
    history = [{"role": "user", "content": f"m{i}"} for i in range(100)]
    msgs = build_messages(DS_SYSTEM_PROMPT, history, "hi", max_history=10)
    assert len(msgs) == 1 + 10 + 1
    assert msgs[1]["content"] == "m90"


def test_truncate_reply():
    assert truncate_reply("  短回复  ") == "短回复"
    assert truncate_reply("x" * 30) == "x" * 30          # 恰好不超
    out = truncate_reply("x" * 31)
    assert len(out) == 29  # 28 字符 + 省略号
    assert out.endswith("…")


def test_chat_history_trim():
    h = ChatHistory(max_entries=6)
    for i in range(5):
        h.append_turn(f"u{i}", f"r{i}")
    assert len(h) == 6  # 上限截断（10 条中保留最近 6 条）
    entries = h.entries()
    assert entries[0]["content"] == "u2"
    assert entries[-1]["content"] == "r4"


def test_chat_history_default_limit():
    h = ChatHistory()
    assert h.max_entries == MAX_HISTORY
    h.entries().clear()  # 返回副本，内部不受影响
    assert len(h) == 0


def test_chat_url_no_v1_prefix():
    url = chat_url()
    assert url == "https://api.deepseek.com/chat/completions"
    assert "/v1" not in url
    assert chat_url("https://api.deepseek.com/").endswith("/chat/completions")


def test_build_payload_plain_mode():
    msgs = [{"role": "user", "content": "hi"}]
    p = build_payload(msgs, thinking=False)
    assert p["model"] == DS_MODEL
    assert p["stream"] is False
    assert p["thinking"] == {"type": "disabled"}
    assert p["max_tokens"] == 100
    assert "reasoning_effort" not in p


def test_build_payload_thinking_mode():
    msgs = [{"role": "user", "content": "hi"}]
    p = build_payload(msgs, thinking=True)
    assert p["thinking"] == {"type": "enabled"}
    assert p["reasoning_effort"] == "high"
    assert p["stream"] is False
    # 思考模式不设 max_tokens（推理需余量）、不发 temperature
    assert "max_tokens" not in p
    assert "temperature" not in p


def test_extract_reply_prefers_final_content():
    data = {"choices": [{"message": {"content": "你好呀", "reasoning_content": "用户在打招呼..."}}]}
    assert extract_reply(data) == "你好呀"


def test_extract_reply_empty_raises():
    with pytest.raises(DeepSeekError):
        extract_reply({"choices": [{"message": {"content": ""}}]})
    with pytest.raises(DeepSeekError):
        extract_reply({"choices": [{"message": {"content": None}}]})
