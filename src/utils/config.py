from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import yaml


DEFAULT_CONFIG = {
    "window_position": {"x": None, "y": None},
    "window_locked": False,
    "shortcut_presets": [{}, {}, {}],
    "plugins_visibility": {},
    "motion": {
        "hover_expand_delay_ms": 0,
        "min_dwell_ms": 0,
        "expand_duration_ms": 220,
        "collapse_duration_ms": 180,
        "expand_easing": "cubic-bezier(0.4, 0, 0.2, 1)",
        "collapse_easing": "cubic-bezier(0.4, 0, 0.2, 1)",
    },
    "performance_thresholds": {
        "cpu": 85,
        "memory": 90,
        "gpu_temp": 85,
    },
}


class ConfigManager:
    def __init__(self, path: Path):
        self.path = path
        self.data = {}
        self.load()

    def load(self) -> None:
        if not self.path.exists():
            self.data = DEFAULT_CONFIG.copy()
            self.save()
            return
        content = yaml.safe_load(self.path.read_text(encoding="utf-8")) or {}
        self.data = self._merge(DEFAULT_CONFIG, content)

    def save(self) -> None:
        self.path.write_text(yaml.safe_dump(self.data, allow_unicode=True, sort_keys=False), encoding="utf-8")

    def get(self, key: str, default: Any = None) -> Any:
        return self.data.get(key, default)

    def set(self, key: str, value: Any) -> None:
        self.data[key] = value
        self.save()

    def _merge(self, base: Any, custom: Any) -> Any:
        if isinstance(base, dict) and isinstance(custom, dict):
            merged = dict(base)
            for key, value in custom.items():
                merged[key] = self._merge(base.get(key), value) if key in base else value
            return merged
        return custom if custom is not None else base

def _config_path() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent / "config.yaml"
    return Path(__file__).resolve().parents[2] / "config.yaml"


config_manager = ConfigManager(_config_path())
