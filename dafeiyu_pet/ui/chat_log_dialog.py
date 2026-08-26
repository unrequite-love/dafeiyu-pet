"""聊天记录回看窗口：查看/清空与 DeepSeek 的对话历史。"""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QHBoxLayout,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
)

ROLE_LABELS = {"user": "你", "assistant": "大肥鱼"}


def format_history(entries: list[dict[str, str]]) -> str:
    """把对话历史格式化为纯文本（空历史给出提示）。"""
    if not entries:
        return "（还没有聊过天～点鱼弹出的 🗨️ 开始对话吧）"
    lines = []
    for e in entries:
        label = ROLE_LABELS.get(e.get("role", ""), e.get("role", "?"))
        lines.append(f"{label}：{e.get('content', '')}")
    return "\n".join(lines)


class ChatLogDialog(QDialog):
    """聊天记录窗口（只读文本 + 清空/关闭）。"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.Tool
            | Qt.WindowType.WindowStaysOnTopHint
        )
        self.setFixedSize(400, 440)
        self.setStyleSheet(
            """
            QDialog {
                background: white;
                border-radius: 16px;
                border: 1px solid #e5e7eb;
            }
            """
        )

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(10)

        self.text_view = QTextEdit()
        self.text_view.setReadOnly(True)
        self.text_view.setFont(QFont("Microsoft YaHei UI", 10))
        self.text_view.setStyleSheet(
            "QTextEdit { background: #fafafa; border: 1px solid #ececf2;"
            " border-radius: 10px; padding: 8px; color: #333; }"
        )
        layout.addWidget(self.text_view)

        btns = QHBoxLayout()
        btns.addStretch(1)
        clear_btn = QPushButton("清空记录")
        clear_btn.setFixedHeight(30)
        clear_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        clear_btn.setStyleSheet(
            "QPushButton { background:#fff0f3; border:1px solid #ffc2cf;"
            " border-radius:15px; color:#c0405a; padding:0 14px; }"
            "QPushButton:hover { background:#ffe0e8; }"
        )
        clear_btn.clicked.connect(self._on_clear)
        btns.addWidget(clear_btn)

        close_btn = QPushButton("关闭")
        close_btn.setFixedHeight(30)
        close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        close_btn.setStyleSheet(
            "QPushButton { background:#eef1ff; border:1px solid #c9d4ff;"
            " border-radius:15px; color:#4a63d8; padding:0 18px; }"
            "QPushButton:hover { background:#dde4ff; }"
        )
        close_btn.clicked.connect(self.hide)
        btns.addWidget(close_btn)
        layout.addLayout(btns)

    def _on_clear(self):
        owner = self.parent()
        if owner is not None and len(owner.history) > 0:
            owner.history.clear()
            self.refresh(owner.history.entries())
            owner.say("聊天记录已清空")

    def refresh(self, entries: list[dict[str, str]]) -> None:
        self.text_view.setPlainText(format_history(entries))
        sb = self.text_view.verticalScrollBar()
        sb.setValue(sb.maximum())  # 滚动到最新

    def popup_at(self, x, y):
        # 越界保护：优先完整显示在屏幕内
        screen = self.screen() or QApplication.primaryScreen()
        geo = screen.availableGeometry()
        px = max(geo.left(), min(geo.right() - self.width(), int(x - self.width() / 2)))
        py = max(geo.top(), int(y - self.height() - 10))
        self.move(px, py)
        self.show()
        self.raise_()
        self.activateWindow()
