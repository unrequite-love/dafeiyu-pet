"""聊天输入框：单击桌宠后经功能面板唤起。"""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDialog, QHBoxLayout, QFrame, QLineEdit, QPushButton


class ChatDialog(QDialog):
    """聊天对话框（缩小版，匹配桌宠风格）。"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.Tool
            | Qt.WindowType.WindowStaysOnTopHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setFixedSize(420, 56)

        container = QFrame(self)
        container.setGeometry(0, 0, 420, 56)
        container.setStyleSheet(
            """
            QFrame {
                background: white;
                border-radius: 20px;
                border: 1px solid #e5e7eb;
            }
            """
        )

        layout = QHBoxLayout(container)
        layout.setContentsMargins(18, 0, 12, 0)
        layout.setSpacing(0)

        self.input = QLineEdit()
        self.input.setPlaceholderText("给大肥鱼发送消息")
        self.input.setStyleSheet(
            """
            QLineEdit {
                color: #1a1a1a;
                font-size: 15px;
                font-family: Arial, "Microsoft YaHei", sans-serif;
                border: none;
                background: transparent;
            }
            QLineEdit:focus {
                border: none;
            }
            """
        )
        self.input.returnPressed.connect(self._on_submit)
        self.input.textChanged.connect(self._update_button_style)
        layout.addWidget(self.input)

        self.send_btn = QPushButton()
        self.send_btn.setFixedSize(32, 32)
        self.send_btn.setText("↑")
        self.send_btn.clicked.connect(self._on_submit)
        layout.addWidget(self.send_btn)
        self._update_button_style()

    def _update_button_style(self):
        if self.input.text().strip():
            self.send_btn.setStyleSheet(
                """
                QPushButton {
                    border-radius: 16px;
                    background: #5686fe;
                    border: none;
                    color: #ffffff;
                    font-size: 20px;
                    font-weight: bold;
                }
                QPushButton:hover { background: #4575ed; }
                QPushButton:pressed { background: #3a66d9; }
                """
            )
        else:
            self.send_btn.setStyleSheet(
                """
                QPushButton {
                    border-radius: 16px;
                    background: #b9c7ff;
                    border: none;
                    color: white;
                    font-size: 20px;
                    font-weight: bold;
                }
                QPushButton:hover { background: #a8b8f0; }
                QPushButton:pressed { background: #9aacd9; }
                """
            )

    def _on_submit(self):
        text = self.input.text().strip()
        if not text:
            return
        self.input.clear()
        self.accept()
        owner = self.parent()
        if owner is not None:
            owner.chat_paused = False
            owner.call_deepseek(text)

    def showEvent(self, event):
        self.input.setFocus()
        super().showEvent(event)

    def popup_at(self, x, y):
        self.move(int(x - self.width() / 2), int(y - self.height() - 10))
        self.show()
        self.raise_()
        # 关键：无边框 Tool 窗口 show() 不会成为系统活动窗口，
        # 键盘输入不会进入输入框；必须显式请求激活 + 设焦点
        self.activateWindow()
        self.input.setFocus(Qt.FocusReason.ActiveWindowFocusReason)

    def reject(self):
        owner = self.parent()
        if owner is not None:
            owner.chat_paused = False
        super().reject()
