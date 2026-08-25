"""功能面板：单击桌宠后弹出的 🗨️ 入口。"""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QPushButton, QVBoxLayout


class FunctionPanel(QFrame):
    """左键弹出的功能列表（白底矩形，仅一个 🗨️ 图标）。"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.Tool
            | Qt.WindowType.WindowStaysOnTopHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setStyleSheet(
            """
            QFrame {
                background: rgba(255, 255, 255, 0.92);
                border-radius: 14px;
                border: 1px solid rgba(0,0,0,0.06);
            }
            QPushButton {
                background: transparent;
                border: none;
                font-size: 28px;
                padding: 10px 16px;
                border-radius: 10px;
            }
            QPushButton:hover { background: rgba(0,0,0,0.04); }
            QPushButton:pressed { background: rgba(0,0,0,0.08); }
            """
        )
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 6, 8, 6)
        layout.setSpacing(0)

        self.chat_btn = QPushButton("🗨️")
        self.chat_btn.setFixedSize(52, 48)
        self.chat_btn.clicked.connect(self._on_chat_clicked)
        layout.addWidget(self.chat_btn)

        self.setFixedSize(68, 60)
        self.hide()

    def _on_chat_clicked(self):
        self.hide()
        owner = self.parent()
        if owner is not None:
            owner.show_chat_dialog()

    def popup_at(self, x, y):
        self.move(int(x), int(y))
        self.show()
        self.raise_()
