from pathlib import Path
from unittest.mock import MagicMock

from PySide6.QtCore import QMimeData, QUrl

from plugins.connection_status import ConnectionStatusPlugin
from plugins.sys_monitor import SystemMonitorPlugin
from plugins.weather import WeatherPlugin
from src.plugins.manager import PluginManager, plugin_manager
from src.ui.shortcut_dots import ShortcutDots
from src.utils.config import config_manager


def test_plugin_manager_loads_plugins(qapp):
    manager = PluginManager()
    parent = ShortcutDots()
    manager.load_all_plugins(parent)
    assert "weather" in manager.plugins
    assert "music" in manager.plugins
    assert "clipboard" in manager.plugins


def test_plugin_theme_switch(qapp):
    parent = ShortcutDots()
    plugin_manager.load_all_plugins(parent)
    for plugin in plugin_manager.plugins.values():
        plugin.on_theme_changed("light")
        plugin.on_theme_changed("dark")
    assert len(plugin_manager.plugins) >= 4


def test_shortcut_exec_url(monkeypatch, qapp):
    dots = ShortcutDots()
    monkeypatch.setattr(
        config_manager,
        "get",
        lambda key, default=None: [{"type": "url", "target": "https://example.com"}, {}, {}] if key == "shortcut_presets" else default,
    )
    opened = []
    monkeypatch.setattr("webbrowser.open", lambda url: opened.append(url))
    dots.execute_shortcut(0)
    assert opened == ["https://example.com"]


def test_shortcut_exec_script(monkeypatch, qapp, tmp_path: Path):
    dots = ShortcutDots()
    script = tmp_path / "demo.py"
    script.write_text("print('ok')", encoding="utf-8")
    monkeypatch.setattr(
        config_manager,
        "get",
        lambda key, default=None: [{"type": "script", "target": str(script)}, {}, {}] if key == "shortcut_presets" else default,
    )
    called = []
    monkeypatch.setattr("subprocess.Popen", lambda args, shell=False: called.append((args, shell)))
    dots.execute_shortcut(0)
    assert called and called[0][0][0] == "py"


def test_shortcut_exec_hotkey(monkeypatch, qapp):
    dots = ShortcutDots()
    monkeypatch.setattr(
        config_manager,
        "get",
        lambda key, default=None: [{"type": "hotkey", "target": "Ctrl+Shift+S"}, {}, {}] if key == "shortcut_presets" else default,
    )
    called = []
    monkeypatch.setattr(ShortcutDots, "_send_hotkey", staticmethod(lambda combo: called.append(combo) or True))
    dots.execute_shortcut(0)
    assert called == ["Ctrl+Shift+S"]


def test_drop_local_lnk_auto_maps_to_exe(qapp, tmp_path: Path):
    lnk = tmp_path / "demo.lnk"
    lnk.write_text("x", encoding="utf-8")
    mime = QMimeData()
    mime.setUrls([QUrl.fromLocalFile(str(lnk))])
    mode_target = ShortcutDots._resolve_drop_payload(mime)
    assert mode_target == ("exe", str(lnk))


def test_drop_url_auto_maps_to_url(qapp):
    mime = QMimeData()
    mime.setText("https://example.com/tool")
    mode_target = ShortcutDots._resolve_drop_payload(mime)
    assert mode_target == ("url", "https://example.com/tool")


def test_drop_apply_then_click_exec_program(monkeypatch, qapp):
    dots = ShortcutDots()
    store = {"shortcut_presets": [{}, {}, {}]}
    monkeypatch.setattr(config_manager, "get", lambda key, default=None: store.get(key, default))
    monkeypatch.setattr(config_manager, "set", lambda key, value: store.__setitem__(key, value))
    launched = []
    monkeypatch.setattr("subprocess.Popen", lambda args, shell=False: launched.append((args, shell)))
    dots._apply_dropped_shortcut(2, "exe", r"C:\Tools\demo.lnk")
    dots.execute_shortcut(2)
    assert store["shortcut_presets"][2]["type"] == "exe"
    assert launched and launched[0][0] == [r"C:\Tools\demo.lnk"]


def test_weather_on_expand_uses_async_refresh(qapp):
    plugin = WeatherPlugin()
    plugin.refresh_async = MagicMock()
    plugin.on_expand()
    plugin.refresh_async.assert_called_once()


def test_connection_status_skips_notify_on_first_poll(monkeypatch, qapp):
    class Parent(ShortcutDots):
        def __init__(self):
            super().__init__()
            self.called = 0

        def request_expand(self):
            self.called += 1

    monkeypatch.setattr(ConnectionStatusPlugin, "_detect_wifi", lambda self: (True, "Wi-Fi"))
    monkeypatch.setattr(ConnectionStatusPlugin, "_detect_bt", lambda self: (False, "Bluetooth"))
    monkeypatch.setattr(ConnectionStatusPlugin, "_detect_bt_devices", lambda self: 0)
    monkeypatch.setattr(ConnectionStatusPlugin, "_detect_focus", lambda self: False)
    parent = Parent()
    plugin = ConnectionStatusPlugin(parent)
    assert parent.called == 0
    monkeypatch.setattr(ConnectionStatusPlugin, "_detect_wifi", lambda self: (False, "Wi-Fi"))
    plugin._poll_states()
    assert parent.called == 1


def test_connection_status_run_command_uses_hidden_kwargs(monkeypatch):
    captured = {}

    class DummyResult:
        stdout = "ok"
        stderr = ""

    monkeypatch.setattr(ConnectionStatusPlugin, "_hidden_process_kwargs", classmethod(lambda cls: {"creationflags": 1}))

    def fake_run(args, **kwargs):
        captured["args"] = args
        captured["kwargs"] = kwargs
        return DummyResult()

    monkeypatch.setattr("subprocess.run", fake_run)
    out = ConnectionStatusPlugin._run_command(["reg", "query", "x"])
    assert out == "ok\n"
    assert captured["kwargs"]["creationflags"] == 1


def test_connection_status_on_expand_not_blocking(monkeypatch, qapp):
    plugin = ConnectionStatusPlugin()
    called = []
    monkeypatch.setattr(ConnectionStatusPlugin, "_poll_states_async", lambda self: called.append(True))
    plugin.on_expand()
    assert called == [True]
    assert plugin.isVisible()


def test_sys_monitor_on_expand_not_blocking(monkeypatch, qapp):
    plugin = SystemMonitorPlugin()
    called = []
    monkeypatch.setattr(SystemMonitorPlugin, "refresh", lambda self: called.append(True))
    plugin.on_expand()
    assert called == []
    assert plugin.isVisible()
