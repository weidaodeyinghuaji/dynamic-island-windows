import time

from PySide6.QtCore import QEvent, QPoint, Qt, QEasingCurve, QRect
from PySide6.QtGui import QCloseEvent, QContextMenuEvent, QEnterEvent, QMouseEvent, QPaintEvent
from PySide6.QtWidgets import QWidget

from src.plugins.manager import plugin_manager
from src.ui.island_window import DynamicIslandWindow
from src.utils.config import config_manager
from src.utils.theme import theme_manager


def _patch(monkeypatch):
    monkeypatch.setattr(plugin_manager, "load_all_plugins", lambda parent: None)
    monkeypatch.setattr(plugin_manager, "plugins", {})
    monkeypatch.setattr(DynamicIslandWindow, "_init_tray", lambda self: None)
    monkeypatch.setattr(
        config_manager,
        "get",
        lambda key, default=None: {
            "motion": {
                "hover_expand_delay_ms": 320,
                "min_dwell_ms": 200,
                "expand_duration_ms": 280,
                "collapse_duration_ms": 220,
                "expand_easing": "OutCubic",
                "collapse_easing": "InCubic",
            },
            "window_position": {"x": 100, "y": 10},
            "shortcut_presets": [{}, {}, {}],
            "plugins_visibility": {},
        }.get(key, default),
    )
    monkeypatch.setattr(config_manager, "set", lambda key, value: None)


def test_theme_and_menu(monkeypatch, qapp):
    _patch(monkeypatch)
    window = DynamicIslandWindow()
    menu_css = []
    monkeypatch.setattr(window, "_apply_menu_theme", lambda menu: menu_css.append("ok"))
    window.tray_menu = type("Dummy", (), {"setStyleSheet": lambda self, s: None})()
    window.on_theme_changed("light")
    window.on_theme_changed("dark")
    assert menu_css == ["ok", "ok"]


def test_init_position_always_top_center(monkeypatch, qapp):
    _patch(monkeypatch)

    class FakeScreen:
        @staticmethod
        def availableGeometry():
            return QRect(0, 0, 1200, 800)

    monkeypatch.setattr("src.ui.island_window.QApplication.primaryScreen", staticmethod(lambda: FakeScreen()))
    window = DynamicIslandWindow()
    assert window.x() == (1200 - window.NORMAL_WIDTH) // 2
    assert window.y() == 12


def test_expand_and_collapse_paths(monkeypatch, qapp):
    _patch(monkeypatch)
    window = DynamicIslandWindow()
    window._expand_from_hover()
    assert window._is_expanded
    window._start_content_fade()
    assert window._content_opacity <= 1.0
    monkeypatch.setattr(window, "mapFromGlobal", lambda _: QPoint(-999, -999), raising=False)
    window._pending_collapse = True
    window._collapse_if_needed()
    assert not window._is_expanded


def test_expand_activates_plugins_immediately(monkeypatch, qapp):
    _patch(monkeypatch)
    window = DynamicIslandWindow()
    called = {"plugins": 0, "fade": 0}
    monkeypatch.setattr(window, "_activate_plugins", lambda: called.__setitem__("plugins", called["plugins"] + 1))
    monkeypatch.setattr(window, "_start_content_fade", lambda: called.__setitem__("fade", called["fade"] + 1))
    window._expand_from_hover()
    assert called["plugins"] == 1
    assert called["fade"] == 1


def test_enter_leave_state(monkeypatch, qapp):
    _patch(monkeypatch)
    window = DynamicIslandWindow()
    point = window.rect().center()
    window.enterEvent(QEnterEvent(point, point, point))
    assert window._is_expanded
    assert not window.expand_timer.isActive()
    window._is_expanded = True
    window._expanded_since = time.monotonic() - 1
    monkeypatch.setattr(window, "mapFromGlobal", lambda _: QPoint(-999, -999), raising=False)
    window.leaveEvent(QEvent(QEvent.Type.Leave))
    assert window._state == "Idle"


def test_mouse_drag_and_release(monkeypatch, qapp):
    _patch(monkeypatch)
    window = DynamicIslandWindow()
    saved = []
    monkeypatch.setattr(config_manager, "set", lambda key, value: saved.append((key, value)))
    press = QMouseEvent(
        QMouseEvent.Type.MouseButtonPress,
        window.rect().center(),
        window.mapToGlobal(window.rect().center()),
        window.mapToGlobal(window.rect().center()),
        Qt.MouseButton.LeftButton,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
    )
    move = QMouseEvent(
        QMouseEvent.Type.MouseMove,
        window.rect().center(),
        window.mapToGlobal(window.rect().center() + QPoint(8, 0)),
        window.mapToGlobal(window.rect().center() + QPoint(8, 0)),
        Qt.MouseButton.LeftButton,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
    )
    release = QMouseEvent(
        QMouseEvent.Type.MouseButtonRelease,
        window.rect().center(),
        window.mapToGlobal(window.rect().center()),
        window.mapToGlobal(window.rect().center()),
        Qt.MouseButton.LeftButton,
        Qt.MouseButton.NoButton,
        Qt.KeyboardModifier.NoModifier,
    )
    window.mousePressEvent(press)
    window.mouseMoveEvent(move)
    window.mouseReleaseEvent(release)
    assert saved and saved[0][0] == "window_position"
    assert window._stable_anchor_x > 0


def test_close_event_saves_window_position(monkeypatch, qapp):
    _patch(monkeypatch)
    saved = []
    monkeypatch.setattr(config_manager, "set", lambda key, value: saved.append((key, value)))
    window = DynamicIslandWindow()
    window.setGeometry(222, 33, window.NORMAL_WIDTH, window.NORMAL_HEIGHT)
    window._collapsed_origin_x = 222
    window.closeEvent(QCloseEvent())
    assert saved and saved[-1][0] == "window_position"
    assert saved[-1][1]["x"] == 222
    assert saved[-1][1]["y"] == 33


def test_drag_when_expanded_keeps_new_anchor(monkeypatch, qapp):
    _patch(monkeypatch)
    window = DynamicIslandWindow()
    window.setGeometry(100, 10, window.EXPAND_WIDTH, window.EXPAND_HEIGHT)
    window._is_expanded = True
    initial_center = window.x() + window.width() / 2.0
    press = QMouseEvent(
        QMouseEvent.Type.MouseButtonPress,
        window.rect().center(),
        window.mapToGlobal(window.rect().center()),
        window.mapToGlobal(window.rect().center()),
        Qt.MouseButton.LeftButton,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
    )
    move = QMouseEvent(
        QMouseEvent.Type.MouseMove,
        window.rect().center(),
        window.mapToGlobal(window.rect().center() + QPoint(40, 0)),
        window.mapToGlobal(window.rect().center() + QPoint(40, 0)),
        Qt.MouseButton.LeftButton,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
    )
    release = QMouseEvent(
        QMouseEvent.Type.MouseButtonRelease,
        window.rect().center(),
        window.mapToGlobal(window.rect().center()),
        window.mapToGlobal(window.rect().center()),
        Qt.MouseButton.LeftButton,
        Qt.MouseButton.NoButton,
        Qt.KeyboardModifier.NoModifier,
    )
    window.mousePressEvent(press)
    window.mouseMoveEvent(move)
    window.mouseReleaseEvent(release)
    moved_center = window.x() + window.width() / 2.0
    assert moved_center != initial_center
    expected_collapse_x = int(round(moved_center - window.NORMAL_WIDTH / 2.0))
    window._start_animation(window.NORMAL_WIDTH, window.NORMAL_HEIGHT, False)
    window._on_geometry_tick(1.0)
    assert window.x() == expected_collapse_x


def test_lock_prevents_drag(monkeypatch, qapp):
    _patch(monkeypatch)
    window = DynamicIslandWindow()
    window._is_locked = True
    before = window.pos()
    saved = []
    monkeypatch.setattr(config_manager, "set", lambda key, value: saved.append((key, value)))
    press = QMouseEvent(
        QMouseEvent.Type.MouseButtonPress,
        window.rect().center(),
        window.mapToGlobal(window.rect().center()),
        window.mapToGlobal(window.rect().center()),
        Qt.MouseButton.LeftButton,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
    )
    move = QMouseEvent(
        QMouseEvent.Type.MouseMove,
        window.rect().center(),
        window.mapToGlobal(window.rect().center() + QPoint(40, 0)),
        window.mapToGlobal(window.rect().center() + QPoint(40, 0)),
        Qt.MouseButton.LeftButton,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
    )
    release = QMouseEvent(
        QMouseEvent.Type.MouseButtonRelease,
        window.rect().center(),
        window.mapToGlobal(window.rect().center()),
        window.mapToGlobal(window.rect().center()),
        Qt.MouseButton.LeftButton,
        Qt.MouseButton.NoButton,
        Qt.KeyboardModifier.NoModifier,
    )
    window.mousePressEvent(press)
    window.mouseMoveEvent(move)
    window.mouseReleaseEvent(release)
    assert window.pos() == before
    assert not saved


def test_context_menu_actions(monkeypatch, qapp):
    _patch(monkeypatch)
    window = DynamicIslandWindow()

    class DummyMenu:
        def __init__(self):
            self._toggle = object()
            self._quit = object()

        def setStyleSheet(self, style):
            return None

        def addAction(self, text):
            if "切换" in text:
                return self._toggle
            return self._quit

        def exec(self, pos):
            return self._toggle

    monkeypatch.setattr("src.ui.island_window.QMenu", lambda parent=None: DummyMenu())
    toggled = []
    monkeypatch.setattr(theme_manager, "set_theme", lambda v: toggled.append(v))
    center = window.rect().center()
    global_center = window.mapToGlobal(center)
    ev = QContextMenuEvent(QContextMenuEvent.Reason.Mouse, center, global_center)
    window.contextMenuEvent(ev)
    assert toggled


def test_uncovered_branches(monkeypatch, qapp):
    class DummyPlugin(QWidget):
        def __init__(self):
            super().__init__()
            self.expands = 0
            self.collapses = 0
            self.theme_calls = []

        def on_expand(self):
            self.expands += 1

        def on_collapse(self):
            self.collapses += 1

        def on_theme_changed(self, theme):
            self.theme_calls.append(theme)

    plugin = DummyPlugin()
    monkeypatch.setattr(plugin_manager, "load_all_plugins", lambda parent: None)
    monkeypatch.setattr(plugin_manager, "plugins", {"dummy": plugin})
    monkeypatch.setattr(
        config_manager,
        "get",
        lambda key, default=None: {
            "motion": {
                "hover_expand_delay_ms": 320,
                "min_dwell_ms": 200,
                "expand_duration_ms": 280,
                "collapse_duration_ms": 220,
                "expand_easing": "invalid",
                "collapse_easing": "cubic-bezier(1.2, 0, 0.2, 1)",
            },
            "window_position": {"x": None, "y": None},
            "shortcut_presets": [{}, {}, {}],
            "plugins_visibility": {},
        }.get(key, default),
    )
    monkeypatch.setattr(
        "src.ui.island_window.QInputDialog.getItem",
        lambda *args, **kwargs: ("清空配置", True),
    )
    window = DynamicIslandWindow()
    window._on_dot_edit_requested(1)
    assert window._state == "Edit-1"
    assert window._resolve_curve("x", QEasingCurve.Type.InCubic).type() == QEasingCurve.Type.InCubic
    assert window._resolve_curve("cubic-bezier(1.3,0,0,1)", QEasingCurve.Type.OutCubic).type() == QEasingCurve.Type.OutCubic
    window.on_theme_changed("dark")
    assert plugin.theme_calls
    theme_manager.set_theme("dark")
    window._is_expanded = True
    window._expand_from_hover()
    window._is_expanded = False
    window._expand_from_hover()
    window._activate_plugins()
    assert plugin.expands >= 1
    monkeypatch.setattr("src.ui.island_window.QCursor.pos", lambda: window.mapToGlobal(window.rect().center()))
    window._pending_collapse = True
    window._collapse_if_needed()
    assert window._pending_collapse is False
    monkeypatch.setattr(window, "mapFromGlobal", lambda _: QPoint(0, 0), raising=False)
    window.leaveEvent(QEvent(QEvent.Type.Leave))
    assert window._state in {"Idle", "Hover", "Expanded", "Edit-1"}
    quit_called = []

    class MenuQuit:
        def __init__(self):
            self.toggle = object()
            self.quit = object()

        def setStyleSheet(self, text):
            return None

        def addAction(self, text):
            return self.quit if "退出" in text else self.toggle

        def exec(self, pos):
            return self.quit

    monkeypatch.setattr("src.ui.island_window.QMenu", lambda parent=None: MenuQuit())
    monkeypatch.setattr("src.ui.island_window.QApplication.quit", lambda: quit_called.append(True))
    center = window.rect().center()
    global_center = window.mapToGlobal(center)
    window.contextMenuEvent(QContextMenuEvent(QContextMenuEvent.Reason.Mouse, center, global_center))
    assert quit_called
    window.set_content_opacity(0.5)
    _ = window.first_frame_time_ms
    window._is_expanded = True
    window.paintEvent(QPaintEvent(window.rect()))


def test_plugin_visibility_menu_toggle(monkeypatch, qapp):
    class DummyPlugin(QWidget):
        def __init__(self):
            super().__init__()
            self.expands = 0

        def on_expand(self):
            self.expands += 1
            self.show()

        def on_collapse(self):
            self.hide()

        def on_theme_changed(self, theme):
            return None

    plugin = DummyPlugin()
    monkeypatch.setattr(plugin_manager, "load_all_plugins", lambda parent: None)
    monkeypatch.setattr(plugin_manager, "plugins", {"battery": plugin})
    store = {"plugins_visibility": {"battery": False}}
    monkeypatch.setattr(
        config_manager,
        "get",
        lambda key, default=None: {
            "motion": {
                "hover_expand_delay_ms": 0,
                "min_dwell_ms": 0,
                "expand_duration_ms": 280,
                "collapse_duration_ms": 220,
                "expand_easing": "OutCubic",
                "collapse_easing": "InCubic",
            },
            "window_position": {"x": 100, "y": 10},
            "shortcut_presets": [{}, {}, {}],
            "plugins_visibility": store["plugins_visibility"],
        }.get(key, default),
    )
    monkeypatch.setattr(config_manager, "set", lambda key, value: store.__setitem__(key, value))
    window = DynamicIslandWindow()
    window._is_expanded = True
    window._activate_plugins()
    assert plugin.expands == 0
    window._set_plugin_visible("battery", True)
    window._activate_plugins()
    assert plugin.expands > 0


def test_request_expand_during_plugin_init_not_crash(monkeypatch, qapp):
    class EarlyPlugin(QWidget):
        def __init__(self, parent=None):
            super().__init__(parent)
            if parent is not None:
                parent.request_expand()

        def on_expand(self):
            self.show()

        def on_collapse(self):
            self.hide()

        def on_theme_changed(self, theme):
            return None

    def fake_loader(parent):
        plugin_manager.plugins = {"early": EarlyPlugin(parent)}

    monkeypatch.setattr(plugin_manager, "load_all_plugins", fake_loader)
    monkeypatch.setattr(
        config_manager,
        "get",
        lambda key, default=None: {
            "motion": {
                "hover_expand_delay_ms": 0,
                "min_dwell_ms": 0,
                "expand_duration_ms": 280,
                "collapse_duration_ms": 220,
                "expand_easing": "OutCubic",
                "collapse_easing": "InCubic",
            },
            "window_position": {"x": 100, "y": 10},
            "shortcut_presets": [{}, {}, {}],
            "plugins_visibility": {},
        }.get(key, default),
    )
    monkeypatch.setattr(config_manager, "set", lambda key, value: None)
    monkeypatch.setattr(DynamicIslandWindow, "_init_tray", lambda self: None)
    window = DynamicIslandWindow()
    assert hasattr(window, "expand_timer")
    assert window._window_ready is True
