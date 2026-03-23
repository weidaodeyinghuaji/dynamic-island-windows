import time
from unittest.mock import MagicMock

from PySide6.QtCore import QEvent, QPoint, QEasingCurve, Qt
from PySide6.QtGui import QEnterEvent, QWheelEvent

from src.plugins.manager import plugin_manager
from src.ui.island_window import DynamicIslandWindow
from src.utils.config import config_manager


def _patch(monkeypatch, motion=None):
    motion = motion or {}
    monkeypatch.setattr(plugin_manager, "load_all_plugins", lambda parent: None)
    monkeypatch.setattr(plugin_manager, "plugins", {})
    monkeypatch.setattr(DynamicIslandWindow, "_init_tray", lambda self: None)

    def fake_get(key, default=None):
        if key == "motion":
            return motion
        if key == "window_position":
            return {"x": 100, "y": 10}
        if key == "plugins_visibility":
            return {}
        if key == "shortcut_presets":
            return [{}, {}, {}]
        return default

    monkeypatch.setattr(config_manager, "get", fake_get)
    monkeypatch.setattr(config_manager, "set", lambda key, value: None)


def test_hover_delay_allows_fast_expand(monkeypatch, qapp):
    _patch(monkeypatch, {"hover_expand_delay_ms": 80})
    window = DynamicIslandWindow()
    assert window._motion.hover_expand_delay_ms == 80


def test_motion_duration_is_capped_for_smoothness(monkeypatch, qapp):
    _patch(monkeypatch, {"expand_duration_ms": 600, "collapse_duration_ms": 500})
    window = DynamicIslandWindow()
    assert window._motion.expand_duration_ms == 220
    assert window._motion.collapse_duration_ms == 180


def test_cubic_bezier_supported(monkeypatch, qapp):
    _patch(monkeypatch, {"expand_easing": "cubic-bezier(0.4, 0, 0.2, 1)"})
    window = DynamicIslandWindow()
    assert window._expand_curve.type() == QEasingCurve.Type.BezierSpline


def test_expand_collapse_center_symmetry(monkeypatch, qapp):
    _patch(monkeypatch)
    window = DynamicIslandWindow()
    window.setGeometry(100, 10, 132, 34)
    window._anchor_x = 500.0
    window._anim_start_geo = window.geometry()
    window._anim_target_w = 260
    window._anim_target_h = 34
    for tick in (0.0, 0.2, 0.5, 0.8, 1.0):
        window._on_geometry_tick(tick)
        assert abs((window.x() + window.width() / 2.0) - 500.0) <= 0.5


def test_quick_hover_repeat_no_flash_expand(monkeypatch, qapp):
    _patch(monkeypatch, {"hover_expand_delay_ms": 80})
    window = DynamicIslandWindow()
    point = window.rect().center()
    window.enterEvent(QEnterEvent(point, point, point))
    assert window._is_expanded
    assert not window.expand_timer.isActive()
    window.leaveEvent(QEvent(QEvent.Type.Leave))
    assert not window._is_expanded


def test_hover_delay_zero_expands_immediately(monkeypatch, qapp):
    _patch(monkeypatch, {"hover_expand_delay_ms": 0})
    window = DynamicIslandWindow()
    point = window.rect().center()
    window.enterEvent(QEnterEvent(point, point, point))
    assert window._is_expanded
    assert not window.expand_timer.isActive()


def test_edge_slide_leave_starts_pending_collapse(monkeypatch, qapp):
    _patch(monkeypatch, {"min_dwell_ms": 300})
    window = DynamicIslandWindow()
    monkeypatch.setattr(window, "mapFromGlobal", lambda _: QPoint(-999, -999), raising=False)
    window._is_expanded = True
    window._expanded_since = time.monotonic()
    window.leaveEvent(QEvent(QEvent.Type.Leave))
    assert window._pending_collapse is True


def test_touchpad_multifinger_wheel_not_trigger_expand(monkeypatch, qapp):
    _patch(monkeypatch)
    window = DynamicIslandWindow()
    event = QWheelEvent(
        window.rect().center(),
        window.mapToGlobal(window.rect().center()),
        QPoint(0, 0),
        QPoint(0, 120),
        Qt.MouseButton.NoButton,
        Qt.KeyboardModifier.NoModifier,
        Qt.ScrollPhase.ScrollUpdate,
        False,
    )
    window.wheelEvent(event)
    assert not window._is_expanded


def test_min_dwell_avoids_immediate_collapse(monkeypatch, qapp):
    _patch(monkeypatch, {"min_dwell_ms": 300})
    window = DynamicIslandWindow()
    monkeypatch.setattr(window, "mapFromGlobal", lambda _: QPoint(-999, -999), raising=False)
    collapse = MagicMock()
    monkeypatch.setattr(window, "_collapse_now", collapse)
    window._is_expanded = True
    window._expanded_since = time.monotonic()
    window.leaveEvent(QEvent(QEvent.Type.Leave))
    collapse.assert_not_called()


def test_expand_then_collapse_returns_exact_origin(monkeypatch, qapp):
    _patch(monkeypatch)
    window = DynamicIslandWindow()
    window.setGeometry(240, 20, window.NORMAL_WIDTH, window.NORMAL_HEIGHT)
    origin_x = window.x()
    window._start_animation(window.EXPAND_WIDTH, window.EXPAND_HEIGHT, True)
    window._on_geometry_tick(1.0)
    window._start_animation(window.NORMAL_WIDTH, window.NORMAL_HEIGHT, False)
    window._on_geometry_tick(1.0)
    assert window.x() == origin_x


def test_repeat_expand_collapse_no_right_drift(monkeypatch, qapp):
    _patch(monkeypatch)
    window = DynamicIslandWindow()
    window.setGeometry(320, 20, window.NORMAL_WIDTH, window.NORMAL_HEIGHT)
    origin_x = window.x()
    for _ in range(12):
        window._start_animation(window.EXPAND_WIDTH, window.EXPAND_HEIGHT, True)
        window._on_geometry_tick(1.0)
        window._start_animation(window.NORMAL_WIDTH, window.NORMAL_HEIGHT, False)
        window._on_geometry_tick(1.0)
    assert window.x() == origin_x


def test_rapid_hover_toggle_no_right_drift(monkeypatch, qapp):
    _patch(monkeypatch)
    window = DynamicIslandWindow()
    window.setGeometry(320, 20, window.NORMAL_WIDTH, window.NORMAL_HEIGHT)
    origin_x = window.x()
    for _ in range(8):
        window._start_animation(window.EXPAND_WIDTH, window.EXPAND_HEIGHT, True)
        window._on_geometry_tick(0.35)
        window._start_animation(window.NORMAL_WIDTH, window.NORMAL_HEIGHT, False)
        window._on_geometry_tick(0.65)
        window._is_expanded = False
        window._on_geometry_finished()
    assert window.x() == origin_x


def test_min_dwell_zero_allows_immediate_collapse(monkeypatch, qapp):
    _patch(monkeypatch, {"min_dwell_ms": 0})
    window = DynamicIslandWindow()
    monkeypatch.setattr(window, "mapFromGlobal", lambda _: QPoint(-999, -999), raising=False)
    collapse = MagicMock()
    monkeypatch.setattr(window, "_collapse_now", collapse)
    window._is_expanded = True
    window._expanded_since = time.monotonic()
    window.leaveEvent(QEvent(QEvent.Type.Leave))
    collapse.assert_called_once()


def test_leave_during_expand_animation_uses_grace_timer(monkeypatch, qapp):
    _patch(monkeypatch, {"min_dwell_ms": 0})
    window = DynamicIslandWindow()
    monkeypatch.setattr(window, "mapFromGlobal", lambda _: QPoint(-999, -999), raising=False)
    monkeypatch.setattr("src.ui.island_window.QCursor.pos", lambda: QPoint(int(window._stable_anchor_x), window.y() + 10))
    window._expand_from_hover()
    collapse = MagicMock()
    monkeypatch.setattr(window, "_collapse_now", collapse)
    window.leaveEvent(QEvent(QEvent.Type.Leave))
    collapse.assert_not_called()
    assert window.collapse_timer.isActive()
