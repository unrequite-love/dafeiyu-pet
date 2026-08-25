"""配置读写与向后兼容测试。"""
import json

from dafeiyu_pet.config import DEFAULTS, VALID_MODES, PetConfig


def test_defaults_when_missing(tmp_path):
    cfg = PetConfig(tmp_path / "config.json")
    assert cfg.data == DEFAULTS
    assert cfg["mode"] == "wander"
    assert cfg.get("city") == DEFAULTS["city"]


def test_old_fields_backwards_compatible(tmp_path):
    path = tmp_path / "config.json"
    old = {
        "mode": "follow",
        "size": 0.9,
        "topmost": False,
        "passthrough": True,
        "autostart": True,
        "x": 100,
        "y": 200,
        "ds_api_key": "sk-test",
        "city": "北京",
    }
    path.write_text(json.dumps(old, ensure_ascii=False), encoding="utf-8")
    cfg = PetConfig(path)
    for k, v in old.items():
        assert cfg[k] == v


def test_invalid_mode_falls_back(tmp_path):
    path = tmp_path / "config.json"
    path.write_text(json.dumps({"mode": "fly"}), encoding="utf-8")
    cfg = PetConfig(path)
    assert cfg["mode"] == DEFAULTS["mode"]
    assert DEFAULTS["mode"] in VALID_MODES


def test_corrupt_json_uses_defaults(tmp_path):
    path = tmp_path / "config.json"
    path.write_text("{not valid json", encoding="utf-8")
    cfg = PetConfig(path)
    assert cfg["mode"] == "wander"


def test_set_persists_immediately(tmp_path):
    path = tmp_path / "config.json"
    cfg = PetConfig(path)
    cfg.set("city", "上海")
    on_disk = json.loads(path.read_text(encoding="utf-8"))
    assert on_disk["city"] == "上海"


def test_update_only_writes_changed(tmp_path):
    path = tmp_path / "config.json"
    cfg = PetConfig(path)
    cfg.set("city", "上海")
    cfg.update(city="上海", mode="still")  # city 未变，不重复写
    assert cfg["mode"] == "still"
    assert cfg["city"] == "上海"


def test_unknown_keys_preserved(tmp_path):
    path = tmp_path / "config.json"
    path.write_text(json.dumps({"future_key": 1, "mode": "still"}), encoding="utf-8")
    cfg = PetConfig(path)
    assert cfg["future_key"] == 1
    cfg.set("city", "广州")
    assert json.loads(path.read_text(encoding="utf-8"))["future_key"] == 1
