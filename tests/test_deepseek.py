"""DeepSeek 消息构建/历史/截断/请求体纯逻辑测试（不发真实请求）。"""
import json

import pytest

from dafeiyu_pet.constants import DS_MODEL, DS_SYSTEM_PROMPT, MAX_HISTORY
from dafeiyu_pet.services.deepseek import (
    ChatHistory,
    DeepSeekClient,
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
    assert truncate_reply("x" * 30) == "x" * 30   # 30 字不截断（正常回复完整显示）
    assert truncate_reply("x" * 120) == "x" * 120  # 恰好达到上限不截断
    out = truncate_reply("x" * 121)               # 仅极端上限（120）才截断
    assert len(out) == 120
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


def test_client_session_reuse_and_proxy():
    client = DeepSeekClient("k")
    assert client._session.trust_env is True  # 默认走系统代理
    direct = DeepSeekClient("k", use_proxy=False)
    assert direct._session.trust_env is False  # 直连模式
    assert client._session is not None


def test_client_timeout_defaults():
    assert DeepSeekClient("k").timeout == 10.0
    assert DeepSeekClient("k", thinking=True).timeout == 60.0
    assert DeepSeekClient("k", timeout=5.0).timeout == 5.0


# ---- 历史持久化（#5） ----


def test_history_persistence_roundtrip(tmp_path):
    path = tmp_path / "chat_history.json"
    h = ChatHistory(path=str(path))
    h.append_turn("你好", "你好呀")
    h.append_turn("吃饭没", "吃了小鱼干")
    on_disk = json.loads(path.read_text(encoding="utf-8"))
    assert len(on_disk) == 4

    restored = ChatHistory(path=str(path))  # 模拟重启加载
    assert restored.entries() == h.entries()
    assert restored.entries()[0] == {"role": "user", "content": "你好"}


def test_history_persistence_corrupt_file(tmp_path):
    path = tmp_path / "chat_history.json"
    path.write_text("{broken", encoding="utf-8")
    h = ChatHistory(path=str(path))
    assert len(h) == 0  # 损坏文件 → 从空开始，不崩溃


def test_history_persistence_bad_entries_filtered(tmp_path):
    path = tmp_path / "chat_history.json"
    path.write_text(
        json.dumps([{"role": "user", "content": "ok"}, {"bad": 1}, "junk", None]),
        encoding="utf-8",
    )
    h = ChatHistory(path=str(path))
    assert h.entries() == [{"role": "user", "content": "ok"}]


def test_history_clear_persists(tmp_path):
    path = tmp_path / "chat_history.json"
    h = ChatHistory(path=str(path))
    h.append_turn("a", "b")
    h.clear()
    assert len(h) == 0
    assert json.loads(path.read_text(encoding="utf-8")) == []
    assert ChatHistory(path=str(path)).entries() == []


def test_history_no_path_no_io():
    h = ChatHistory()
    h.append_turn("x", "y")
    assert len(h) == 2  # 未传 path 不做任何文件读写，不报错
