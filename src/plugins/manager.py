from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType

from src.plugins.base import IslandPlugin


class PluginManager:
    def __init__(self):
        self.plugins: dict[str, IslandPlugin] = {}

    def load_all_plugins(self, parent) -> None:
        self.plugins.clear()
        plugins_dir = Path(__file__).resolve().parents[2] / "plugins"
        plugins_dir.mkdir(parents=True, exist_ok=True)
        for file_path in sorted(plugins_dir.glob("*.py")):
            if file_path.name.startswith("_"):
                continue
            module = self._load_module(file_path)
            if module is None:
                continue
            for value in module.__dict__.values():
                if isinstance(value, type) and issubclass(value, IslandPlugin) and value is not IslandPlugin:
                    plugin = value(parent)
                    self.plugins[value.plugin_name] = plugin

    def _load_module(self, file_path: Path) -> ModuleType | None:
        spec = importlib.util.spec_from_file_location(file_path.stem, file_path)
        if spec is None or spec.loader is None:
            return None
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module


plugin_manager = PluginManager()
