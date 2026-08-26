"""ChatDialog 焦点回归测试（锁定 v1.1.2 修复的 Bug：popup 后键盘输入无效）。

需要 PySide6 + pytest-qt；任一缺失时整文件跳过（保持核心测试零 GUI 依赖）。
"""
import pytest

pytest.importorskip("PySide6")
pytest.importorskip("pytestqt")

from PySide6.QtWidgets import QApplication, QLineEdit  # noqa: E402

from dafeiyu_pet.ui.chat_dialog import ChatDialog  # noqa: E402


def test_popup_at_activates_window_and_focuses_input(qtbot):
    dlg = ChatDialog()
    qtbot.addWidget(dlg)
    dlg.popup_at(200, 400)
    # activateWindow 是异步请求；处理事件循环后应成为活动窗口
    for _ in range(10):
        QApplication.processEvents()
    assert QApplication.activeWindow() is dlg
    assert dlg.input.hasFocus()
    assert dlg.input.focusWidget() is dlg.input or dlg.input.hasFocus()


def test_input_accepts_keyboard(qtbot):
    dlg = ChatDialog()
    qtbot.addWidget(dlg)
    dlg.popup_at(100, 200)
    QApplication.processEvents()
    qtbot.keyClicks(dlg.input, "hello")
    assert dlg.input.text() == "hello"


def test_empty_submit_is_noop(qtbot):
    dlg = ChatDialog()
    qtbot.addWidget(dlg)
    dlg.popup_at(100, 200)
    QApplication.processEvents()
    qtbot.keyClicks(dlg.input, "   ")
    dlg._on_submit()
    # 空白输入不应关闭对话框（accept 未被调用 → 仍可见）
    assert dlg.isVisible()
    assert isinstance(dlg.input, QLineEdit)
