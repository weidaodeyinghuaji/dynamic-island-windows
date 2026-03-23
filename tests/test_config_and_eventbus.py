from pathlib import Path

from src.core.event_bus import EventBus
from src.utils.config import ConfigManager, DEFAULT_CONFIG


def test_config_create_and_merge(tmp_path: Path):
    path = tmp_path / "config.yaml"
    manager = ConfigManager(path)
    assert manager.get("motion")["hover_expand_delay_ms"] == 0
    manager.set("window_position", {"x": 1, "y": 2})
    manager2 = ConfigManager(path)
    assert manager2.get("window_position") == {"x": 1, "y": 2}


def test_config_merge_with_partial(tmp_path: Path):
    path = tmp_path / "config.yaml"
    path.write_text("motion:\n  hover_expand_delay_ms: 400\n", encoding="utf-8")
    manager = ConfigManager(path)
    assert manager.get("motion")["hover_expand_delay_ms"] == 400
    assert manager.get("motion")["expand_duration_ms"] == DEFAULT_CONFIG["motion"]["expand_duration_ms"]


def test_event_bus_publish_subscribe():
    bus = EventBus()
    received = []
    bus.subscribe("demo", lambda payload: received.append(payload))
    bus.publish("demo", {"ok": True})
    assert received == [{"ok": True}]
