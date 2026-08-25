"""DeepSeek 消息构建/历史/截断纯逻辑测试（不发真实请求）。"""
from dafeiyu_pet.constants import DS_SYSTEM_PROMPT, MAX_HISTORY
from dafeiyu_pet.services.deepseek import ChatHistory, build_messages, truncate_reply


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
