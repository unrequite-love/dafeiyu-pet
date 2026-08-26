"""聊天记录窗口纯逻辑测试（format_history，无 GUI 依赖）。"""
from dafeiyu_pet.ui.chat_log_dialog import format_history


def test_format_history_empty():
    assert "还没有聊过天" in format_history([])


def test_format_history_entries():
    entries = [
        {"role": "user", "content": "你好"},
        {"role": "assistant", "content": "你好呀，找我啥事"},
    ]
    text = format_history(entries)
    assert "你：你好" in text
    assert "大肥鱼：你好呀，找我啥事" in text


def test_format_history_unknown_role():
    text = format_history([{"role": "system", "content": "x"}])
    assert "system：x" in text
