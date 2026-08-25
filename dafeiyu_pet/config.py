"""配置管理：向后兼容旧 config.json，任何修改立即落盘。"""
from __future__ import annotations

import json
import logging
import os
from typing import Any

logger = logging.getLogger(__name__)

DEFAULTS: dict[str, Any] = {
    "mode": "wander",
    "size": 0.7,
    "topmost": True,
    "passthrough": False,
    "autostart": False,
    "x": None,
    "y": None,
    "ds_api_key": "",
    "ds_thinking": False,
    "city": "深圳",
}

VALID_MODES = ("wander", "follow", "still")


class PetConfig:
    """桌宠配置。

    - 读取时合并默认值，旧版本字段全部兼容；
    - set/update 修改后立即写盘，崩溃也不丢配置。
    """

    def __init__(self, path: str | os.PathLike[str]) -> None:
        self.path = os.fspath(path)
        self.data = self._load()

    def _load(self) -> dict[str, Any]:
        merged = dict(DEFAULTS)
        if os.path.exists(self.path):
            try:
                with open(self.path, encoding="utf-8") as f:
                    loaded = json.load(f)
                if isinstance(loaded, dict):
                    # 保留未知字段，向前兼容新版本写入的配置
                    merged.update(loaded)
            except (OSError, json.JSONDecodeError) as e:
                logger.warning("配置读取失败，使用默认值: %s", e)
        if merged["mode"] not in VALID_MODES:
            logger.warning("配置中的 mode=%r 非法，回退为 %r", merged["mode"], DEFAULTS["mode"])
            merged["mode"] = DEFAULTS["mode"]
        return merged

    def get(self, key: str, default: Any = None) -> Any:
        return self.data.get(key, default)

    def __getitem__(self, key: str) -> Any:
        return self.data[key]

    def set(self, key: str, value: Any) -> None:
        if self.data.get(key) == value:
            return
        self.data[key] = value
        self.save()

    def update(self, **kwargs: Any) -> None:
        changed = {k: v for k, v in kwargs.items() if self.data.get(k) != v}
        if not changed:
            return
        self.data.update(changed)
        self.save()

    def save(self) -> None:
        try:
            with open(self.path, "w", encoding="utf-8") as f:
                json.dump(self.data, f, ensure_ascii=False, indent=2)
        except OSError as e:
            logger.error("配置写入失败: %s", e)
