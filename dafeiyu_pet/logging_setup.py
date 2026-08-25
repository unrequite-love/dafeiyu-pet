"""日志配置：滚动文件日志（pythonw 无控制台时仍可排查问题）。"""
from __future__ import annotations

import logging
import logging.handlers
import sys

from dafeiyu_pet.paths import LOG_DIR


def configure_logging(level: int = logging.INFO) -> None:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    handlers: list[logging.Handler] = [
        logging.handlers.RotatingFileHandler(
            LOG_DIR / "pet.log", maxBytes=512 * 1024, backupCount=2, encoding="utf-8"
        )
    ]
    if sys.stderr is not None:  # pythonw 下 stderr 为 None
        handlers.append(logging.StreamHandler())
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        handlers=handlers,
    )
