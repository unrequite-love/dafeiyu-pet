"""应用入口：装配 QApplication 并启动主窗口。"""
from __future__ import annotations

import logging
import sys

from PySide6.QtWidgets import QApplication, QMessageBox

from dafeiyu_pet.logging_setup import configure_logging

logger = logging.getLogger(__name__)


def run() -> None:
    configure_logging()
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)

    from dafeiyu_pet.ui.pet_window import PetWindow  # 延迟导入：日志先就绪

    PetWindow()
    sys.exit(app.exec())


if __name__ == "__main__":
    try:
        run()
    except Exception as ex:
        logger.exception("大肥鱼桌宠启动失败")
        try:
            app = QApplication.instance() or QApplication(sys.argv)
            QMessageBox.critical(None, "大肥鱼桌宠出错", str(ex))
        except Exception:
            pass
        raise
