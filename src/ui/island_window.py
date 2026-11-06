from __future__ import annotations

import math
import re
import time
from dataclasses import dataclass

from PySide6.QtCore import (
    QAbstractAnimation,
    QPoint,
    QPointF,
    QPropertyAnimation,
    QRect,
    Qt,
    QTimer,
    QVariantAnimation,
    QEasingCurve,
    Signal,
    Property,
)
from PySide6.QtGui import QAction, QCloseEvent, QColor, QCursor, QKeySequence, QLinearGradient, QMouseEvent, QPainter, QPainterPath, QPen, QRadialGradient, QShortcut, QWheelEvent
from PySide6.QtWidgets import QApplication, QGraphicsOpacityEffect, QHBoxLayout, QInputDialog, QMenu, QSystemTrayIcon, QWidget

from src.plugins.manager import plugin_manager
from src.ui.shortcut_dots import ShortcutDots
from src.utils.config import config_manager
from src.utils.theme import theme_manager


@dataclass
class MotionProfile:
    hover_expand_delay_ms: int
    min_dwell_ms: int
    expand_duration_ms: int
    collapse_duration_ms: int
    expand_easing: str
    collapse_easing: str


class DynamicIslandWindow(QWidget):
    state_changed = Signal(str)

    def __init__(self):
        super().__init__()
        self.MARGIN_X = 12
        self.NORMAL_WIDTH = 132
        self.NORMAL_HEIGHT = 34
        self.EXPAND_WIDTH = 260
        self.EXPAND_HEIGHT = 34
        self._drag_pos: QPoint | None = None
        self._drag_start_global: QPoint | None = None
        self._is_dragging = False
        self._is_expanded = False
        self._state = "Idle"
        self._shimmer_x = -120.0
        self._content_opacity = 0.0
        self._expanded_since = 0.0
        self._pending_collapse = False
        self._animation_started_at = 0.0
        self._first_frame_time_ms = 0.0
        self._first_frame_captured = False
        self._pending_expand_request = False
        self._window_ready = False
        self._motion = self._load_motion_profile()
        self._expand_curve = self._resolve_curve(self._motion.expand_easing, QEasingCurve.Type.OutCubic)
        self._collapse_curve = self._resolve_curve(self._motion.collapse_easing, QEasingCurve.Type.InCubic)
        self._bg_color = QColor(18, 18, 20, 232) if theme_manager.current_theme == "dark" else QColor(244, 244, 246, 238)
        self._anchor_x = 0.0
        self._stable_anchor_x = 0.0
        self._collapsed_origin_x = 0
        self._is_locked = bool(config_manager.get("window_locked", False))
        self._anim_start_geo = QRect()
        self._anim_target_w = self.NORMAL_WIDTH
        self._anim_target_h = self.NORMAL_HEIGHT
        self._anim_target_x = 0
        self._use_target_x_lerp = False
        self._keep_anchor_during_anim = False
        self._timer_enabled = False
        self._timer_mode = "off"  # off | countup | countdown
        self._timer_started_at = 0.0
        self._timer_paused = False
        self._timer_pause_acc = 0.0
        self._timer_countdown_total = 0.0
        self._timer_last_text = ""
        self._accent_phase = 0.0
        self._pulse_started_at = 0.0
        self._build_ui()
        self._apply_plugin_visibility()
        self._init_position()
        self._init_animation()
        self._init_tray()
        self._init_timers()
        self._init_shortcuts()
        self._window_ready = True
        if self._pending_expand_request:
            self._pending_expand_request = False
            QTimer.singleShot(0, self._force_expand)
        theme_manager.theme_changed.connect(self.on_theme_changed)
        self.set_state("Idle")

    def _build_ui(self) -> None:
        self.setWindowFlags(Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.FramelessWindowHint | Qt.WindowType.Tool)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.resize(self.NORMAL_WIDTH, self.NORMAL_HEIGHT)
        self.shortcut_dots = ShortcutDots(self)
        self.shortcut_dots.edit_requested.connect(self._on_dot_edit_requested)
        self._center_gap = max(self.shortcut_dots.width() + 16, 80)
        
        self.left_panel = QWidget(self)
        self.left_layout = QHBoxLayout(self.left_panel)
        self.left_layout.setContentsMargins(0, 0, 0, 0)
        self.left_layout.setSpacing(8)
        self.left_layout.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        
        self.right_panel = QWidget(self)
        self.right_layout = QHBoxLayout(self.right_panel)
        self.right_layout.setContentsMargins(0, 0, 0, 0)
        self.right_layout.setSpacing(8)
        self.right_layout.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        
        plugin_manager.load_all_plugins(self)
        plugin_list = list(plugin_manager.plugins.values())
        split_at = (len(plugin_list) + 1) // 2
        
        for plugin in plugin_list[:split_at]:
            self.left_layout.addWidget(plugin)
            plugin.on_theme_changed(theme_manager.current_theme)
            effect = QGraphicsOpacityEffect(plugin)
            plugin.setGraphicsEffect(effect)
            effect.setOpacity(0.0)
            plugin.hide()
        self.left_layout.addStretch()
        
        self.right_layout.addStretch()
        for plugin in plugin_list[split_at:]:
            self.right_layout.addWidget(plugin)
            plugin.on_theme_changed(theme_manager.current_theme)
            effect = QGraphicsOpacityEffect(plugin)
            plugin.setGraphicsEffect(effect)
            effect.setOpacity(0.0)
            plugin.hide()
            
        self._recalculate_expand_width()
        self._position_shortcut_dots()
        self.left_panel.show()
        self.right_panel.show()
        self.shortcut_dots.raise_()

    def _recalculate_expand_width(self) -> None:
        # 强制让所有插件计算其最合适的宽度，而不是被压缩
        left_req = 0
        for i in range(self.left_layout.count()):
            item = self.left_layout.itemAt(i)
            widget = item.widget()
            if widget:
                # 即使隐藏也尝试获取其建议宽度
                layout = widget.layout()
                if layout is not None:
                    layout.activate()  # 强制布局更新
                hint = widget.sizeHint().width()
                if hint > 0:
                    left_req += hint + self.left_layout.spacing()
        
        right_req = 0
        for i in range(self.right_layout.count()):
            item = self.right_layout.itemAt(i)
            widget = item.widget()
            if widget:
                layout = widget.layout()
                if layout is not None:
                    layout.activate()
                hint = widget.sizeHint().width()
                if hint > 0:
                    right_req += hint + self.right_layout.spacing()

        # 减去最后多加的一个 spacing
        left_req = max(0, left_req - self.left_layout.spacing())
        right_req = max(0, right_req - self.right_layout.spacing())
        
        # 左右两侧取最大值以保持中心对称
        max_side = max(left_req, right_req, 40)
        
        # 动态调整中间红绿灯/歌名区域的宽度计算
        center_width = max(self.shortcut_dots.width() + 16, 80)
        self._center_gap = center_width
        
        # 计算展开后的理想总宽度，减少额外的缓冲空间以缩小长度
        ideal_width = max_side * 2 + self._center_gap + self.MARGIN_X * 2 + 8
        
        # 更新 EXPAND_WIDTH，但不小于默认值
        self.EXPAND_WIDTH = max(260, int(ideal_width))
        
        # 如果当前已经展开，需要更新当前窗口尺寸
        if self._is_expanded:
            self.resize(self.EXPAND_WIDTH, self.height())

    def _position_shortcut_dots(self) -> None:
        if hasattr(self, "shortcut_dots") and hasattr(self.shortcut_dots, "set_compact_mode"):
            self.shortcut_dots.set_compact_mode(not self._is_expanded)
        x = int(round((self.width() - self.shortcut_dots.width()) / 2.0))
        if not self._is_expanded:
            x = int(self.width() - self.MARGIN_X - self.shortcut_dots.width())
        y = int(round((self.height() - self.shortcut_dots.height()) / 2.0))
        self.shortcut_dots.move(x, y)

    def _init_position(self) -> None:
        screen = QApplication.primaryScreen() or QApplication.screens()[0]
        rect = screen.availableGeometry()
        x = int(round(rect.x() + (rect.width() - self.NORMAL_WIDTH) / 2.0))
        self.move(x, rect.y() + 12)
        self._collapsed_origin_x = self.x()
        self._stable_anchor_x = float(rect.x() + rect.width() / 2.0)

    def _init_animation(self) -> None:
        self.geometry_anim = QVariantAnimation(self)
        self.geometry_anim.setStartValue(0.0)
        self.geometry_anim.setEndValue(1.0)
        self.geometry_anim.valueChanged.connect(self._on_geometry_tick)
        self.geometry_anim.finished.connect(self._on_geometry_finished)
        self.shimmer_anim = QPropertyAnimation(self, b"shimmer_x")
        self.shimmer_anim.setDuration(560)
        self.shimmer_anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self.content_anim = QPropertyAnimation(self, b"content_opacity")
        self.content_anim.setDuration(180)
        self.content_anim.setEasingCurve(QEasingCurve.Type.InOutCubic)
        self.accent_anim = QPropertyAnimation(self, b"accent_phase")
        self.accent_anim.setStartValue(0.0)
        self.accent_anim.setEndValue(1.0)
        self.accent_anim.setDuration(5200)
        self.accent_anim.setLoopCount(-1)
        self.accent_anim.setEasingCurve(QEasingCurve.Type.InOutSine)
        self.accent_anim.start()

    def _init_tray(self) -> None:
        self.tray_icon = QSystemTrayIcon(self)
        self.tray_icon.setIcon(QApplication.style().standardIcon(QApplication.style().StandardPixmap.SP_DesktopIcon))
        self.tray_menu = QMenu()
        quit_action = QAction("退出", self.tray_menu)
        quit_action.triggered.connect(QApplication.quit)
        theme_action = QAction("切换明暗主题", self.tray_menu)
        theme_action.triggered.connect(self._toggle_theme)
        self.lock_action = QAction("", self.tray_menu)
        self.lock_action.triggered.connect(self._toggle_lock)
        self.shortcut_menu = QMenu("自定义三点按键", self.tray_menu)
        self.shortcut_menu.addAction("配置红点", lambda: self._on_dot_edit_requested(0))
        self.shortcut_menu.addAction("配置黄点", lambda: self._on_dot_edit_requested(1))
        self.shortcut_menu.addAction("配置绿点", lambda: self._on_dot_edit_requested(2))
        self.timer_menu = QMenu("计时器", self.tray_menu)
        self._populate_timer_menu(self.timer_menu)
        self.plugins_menu = QMenu("显示模块", self.tray_menu)
        self._populate_plugins_menu(self.plugins_menu)
        self.tray_menu.addAction(theme_action)
        self.tray_menu.addAction(self.lock_action)
        self.tray_menu.addMenu(self.timer_menu)
        self.tray_menu.addMenu(self.plugins_menu)
        self.tray_menu.addMenu(self.shortcut_menu)
        self.tray_menu.addSeparator()
        self.tray_menu.addAction(quit_action)
        self._refresh_lock_actions()
        self._apply_menu_theme(self.tray_menu)
        self.tray_icon.setContextMenu(self.tray_menu)
        self.tray_icon.show()

    def _init_timers(self) -> None:
        self.expand_timer = QTimer(self)
        self.expand_timer.setSingleShot(True)
        self.expand_timer.timeout.connect(self._expand_from_hover)
        self.collapse_timer = QTimer(self)
        self.collapse_timer.setSingleShot(True)
        self.collapse_timer.timeout.connect(self._collapse_if_needed)
        self.fade_timer = QTimer(self)
        self.fade_timer.setSingleShot(True)
        self.fade_timer.setInterval(24)
        self.fade_timer.timeout.connect(self._start_content_fade)
        self.timer_tick = QTimer(self)
        self.timer_tick.setTimerType(Qt.TimerType.PreciseTimer)
        self.timer_tick.setInterval(100)
        self.timer_tick.timeout.connect(self._on_timer_tick)

    def _load_motion_profile(self) -> MotionProfile:
        motion = config_manager.get("motion", {}) or {}
        return MotionProfile(
            hover_expand_delay_ms=max(0, int(motion.get("hover_expand_delay_ms", 0))),
            min_dwell_ms=max(0, int(motion.get("min_dwell_ms", 0))),
            expand_duration_ms=min(220, max(120, int(motion.get("expand_duration_ms", 220)))),
            collapse_duration_ms=min(180, max(120, int(motion.get("collapse_duration_ms", 180)))),
            expand_easing=str(motion.get("expand_easing", "cubic-bezier(0.4, 0, 0.2, 1)")),
            collapse_easing=str(motion.get("collapse_easing", "cubic-bezier(0.4, 0, 0.2, 1)")),
        )

    def _init_shortcuts(self) -> None:
        self.expand_shortcut = QShortcut(QKeySequence("Meta+Shift+I"), self)
        self.expand_shortcut.activated.connect(self._force_expand)
        self.expand_shortcut_alt = QShortcut(QKeySequence("Win+Shift+I"), self)
        self.expand_shortcut_alt.activated.connect(self._force_expand)
        self.clipboard_shortcut = QShortcut(QKeySequence("Ctrl+Shift+V"), self)
        self.clipboard_shortcut.activated.connect(self._open_clipboard_panel)

    def _force_expand(self) -> None:
        if not self._window_ready or not hasattr(self, "expand_timer") or not hasattr(self, "geometry_anim"):
            self._pending_expand_request = True
            return
        self.expand_timer.stop()
        self.collapse_timer.stop()
        self._pending_collapse = False
        if not self._is_expanded:
            self._expand_from_hover()

    def _open_clipboard_panel(self) -> None:
        self._force_expand()
        clipboard = plugin_manager.plugins.get("clipboard")
        if clipboard and hasattr(clipboard, "activate_panel"):
            clipboard.activate_panel()

    def _resolve_curve(self, value: str, fallback: QEasingCurve.Type) -> QEasingCurve:
        mapping = {
            "Linear": QEasingCurve.Type.Linear,
            "InCubic": QEasingCurve.Type.InCubic,
            "OutCubic": QEasingCurve.Type.OutCubic,
            "InOutCubic": QEasingCurve.Type.InOutCubic,
            "OutBack": QEasingCurve.Type.OutBack,
        }
        if value in mapping:
            return QEasingCurve(mapping[value])
        match = re.match(
            r"^cubic-bezier\(\s*([01]?(?:\.\d+)?)\s*,\s*([01]?(?:\.\d+)?)\s*,\s*([01]?(?:\.\d+)?)\s*,\s*([01]?(?:\.\d+)?)\s*\)$",
            value,
            re.IGNORECASE,
        )
        if not match:
            return QEasingCurve(fallback)
        x1, y1, x2, y2 = [float(v) for v in match.groups()]
        if not all(0.0 <= n <= 1.0 for n in (x1, y1, x2, y2)):
            return QEasingCurve(fallback)
        curve = QEasingCurve(QEasingCurve.Type.BezierSpline)
        curve.addCubicBezierSegment(QPointF(x1, y1), QPointF(x2, y2), QPointF(1.0, 1.0))
        return curve

    def set_state(self, state: str) -> None:
        if self._state == state:
            return
        self._state = state
        self.state_changed.emit(state)

    def _toggle_theme(self) -> None:
        theme_manager.set_theme("light" if theme_manager.current_theme == "dark" else "dark")

    def _sync_anchor_to_geometry(self) -> None:
        self._stable_anchor_x = self._anchor_center_x()
        if not self._is_expanded:
            self._collapsed_origin_x = self.x()

    def _toggle_lock(self) -> None:
        self._is_locked = not self._is_locked
        config_manager.set("window_locked", self._is_locked)
        self._refresh_lock_actions()

    def _refresh_lock_actions(self) -> None:
        if hasattr(self, "lock_action"):
            self.lock_action.setText("解锁位置" if self._is_locked else "锁定位置")

    def on_theme_changed(self, theme: str) -> None:
        self._bg_color = QColor(18, 18, 20, 232) if theme == "dark" else QColor(244, 244, 246, 238)
        if hasattr(self, "tray_menu"):
            self._apply_menu_theme(self.tray_menu)
        for plugin in plugin_manager.plugins.values():
            plugin.on_theme_changed(theme)
        self.update()

    def _apply_menu_theme(self, menu: QMenu) -> None:
        if theme_manager.current_theme == "dark":
            menu.setStyleSheet("QMenu{background:#1f2229;color:#f2f2f2;border:1px solid #393f4a;padding:6px;}QMenu::item:selected{background:#3d4554;}")
        else:
            menu.setStyleSheet("QMenu{background:#f6f7f9;color:#20242b;border:1px solid #d0d4dc;padding:6px;}QMenu::item:selected{background:#e3e8f1;}")

    @staticmethod
    def _plugin_display_name(key: str) -> str:
        mapping = {
            "weather": "实时天气与空气质量",
            "music": "音乐/播客控制条",
            "clipboard": "系统剪切板历史",
            "battery": "笔记本电池健康度与剩余时间",
            "sys_monitor": "System Monitor",
            "connection_status": "系统连接状态",
            "productivity_tools": "生产力快捷工具",
        }
        return mapping.get(key, key)

    def _plugin_visibility_config(self) -> dict:
        data = config_manager.get("plugins_visibility", {}) or {}
        return data if isinstance(data, dict) else {}

    def _is_plugin_visible(self, key: str) -> bool:
        visibility = self._plugin_visibility_config()
        if key in visibility:
            return bool(visibility.get(key))
        display = self._plugin_display_name(key)
        if display in visibility:
            return bool(visibility.get(display))
        return True

    def _apply_plugin_visibility(self) -> None:
        for key, plugin in plugin_manager.plugins.items():
            if self._is_plugin_visible(key):
                if self._is_expanded:
                    plugin.on_expand()
            else:
                plugin.hide()

    def _set_plugin_visible(self, key: str, visible: bool) -> None:
        visibility = self._plugin_visibility_config()
        visibility[key] = bool(visible)
        config_manager.set("plugins_visibility", visibility)
        self._apply_plugin_visibility()

    def _populate_plugins_menu(self, menu: QMenu) -> None:
        menu.clear()
        for key in plugin_manager.plugins.keys():
            action = menu.addAction(self._plugin_display_name(key))
            action.setCheckable(True)
            action.setChecked(self._is_plugin_visible(key))
            action.toggled.connect(lambda checked, k=key: self._set_plugin_visible(k, checked))

    def _on_dot_edit_requested(self, index: int) -> None:
        self.set_state(f"Edit-{index}")
        dot_name = ("红点", "黄点", "绿点")[index] if 0 <= index <= 2 else f"按键{index + 1}"
        mode, ok = QInputDialog.getItem(
            self,
            f"配置{dot_name}",
            "选择动作类型",
            ["发送快捷键", "打开网址", "启动程序", "运行脚本", "清空配置"],
            0,
            False,
        )
        if not ok:
            return
        presets = config_manager.get("shortcut_presets", [{}, {}, {}])
        if not isinstance(presets, list):
            presets = [{}, {}, {}]
        while len(presets) < 3:
            presets.append({})
        if mode == "清空配置":
            presets[index] = {}
            config_manager.set("shortcut_presets", presets)
            return
        if mode == "发送快捷键":
            hotkey, ok = QInputDialog.getText(
                self,
                f"配置{dot_name}",
                "输入快捷键组合（如 Ctrl+Shift+S / Win+Shift+S / F5）",
                text="Win+Shift+S",
            )
            if ok and hotkey.strip():
                presets[index] = {"type": "hotkey", "target": hotkey.strip()}
                config_manager.set("shortcut_presets", presets)
            return
        target, ok = QInputDialog.getText(
            self,
            f"配置{dot_name}",
            "输入目标内容",
        )
        if not ok or not target.strip():
            return
        mapping = {"打开网址": "url", "启动程序": "exe", "运行脚本": "script"}
        mode_value = mapping.get(mode)
        if mode_value:
            presets[index] = {"type": mode_value, "target": target.strip()}
            config_manager.set("shortcut_presets", presets)

    def request_expand(self) -> None:
        try:
            self._force_expand()
        except AttributeError:
            self._pending_expand_request = True

    def set_recording_mode(self, active: bool) -> None:
        self.shortcut_dots.set_recording_indicator(active)
        if active:
            self._collapse_now()
            self.set_state("Recording")
        elif not self._is_expanded:
            self.set_state("Idle")

    def _open_plugin(self, key: str) -> None:
        self.request_expand()
        plugin = plugin_manager.plugins.get(key)
        if plugin and hasattr(plugin, "focus_tools"):
            plugin.focus_tools()

    def _anchor_center_x(self) -> float:
        return float(self.x()) + float(self.width()) / 2.0

    def _target_x_for_anchor(self, width: int) -> int:
        return int(round(self._anchor_x - float(width) / 2.0))

    def _is_cursor_inside_window(self) -> bool:
        return self.rect().contains(self.mapFromGlobal(QCursor.pos()))

    def _on_geometry_tick(self, value) -> None:
        t = float(value)
        start = self._anim_start_geo
        width = int(round(start.width() + (self._anim_target_w - start.width()) * t))
        height = int(round(start.height() + (self._anim_target_h - start.height()) * t))
        if self._keep_anchor_during_anim:
            target_x = self._target_x_for_anchor(width)
        elif self._use_target_x_lerp:
            target_x = int(round(self._anim_start_geo.x() + (self._anim_target_x - self._anim_start_geo.x()) * t))
        else:
            target_x = self._target_x_for_anchor(width)
        self.setGeometry(target_x, start.y(), width, height)
        if not self._first_frame_captured:
            self._first_frame_captured = True
            self._first_frame_time_ms = (time.perf_counter() - self._animation_started_at) * 1000

    def _on_geometry_finished(self) -> None:
        if self._is_expanded and self._content_opacity <= 0.0:
            self._start_content_fade()
            return
        if not self._is_expanded:
            self.setGeometry(self._collapsed_origin_x, self.y(), self.NORMAL_WIDTH, self.NORMAL_HEIGHT)
            self._stable_anchor_x = float(self._collapsed_origin_x + self.NORMAL_WIDTH / 2.0)
        self._keep_anchor_during_anim = False
        self._use_target_x_lerp = False

    def _start_animation(self, target_w: int, target_h: int, expanding: bool) -> None:
        was_animating = self.geometry_anim.state() == QAbstractAnimation.State.Running
        self.geometry_anim.stop()
        self.shimmer_anim.stop()
        self._animation_started_at = time.perf_counter()
        self._first_frame_captured = False
        self._anim_start_geo = QRect(self.geometry())
        self._anim_target_w = int(target_w)
        self._anim_target_h = int(target_h)
        if expanding:
            is_stable_collapsed = (not was_animating) and abs(self.width() - self.NORMAL_WIDTH) <= 1
            if is_stable_collapsed:
                self._collapsed_origin_x = self.x()
        if self._stable_anchor_x <= 0.0:
            self._stable_anchor_x = float(self._collapsed_origin_x + self.NORMAL_WIDTH / 2.0)
        self._anchor_x = self._stable_anchor_x
        if expanding:
            self._anim_target_x = self._target_x_for_anchor(self._anim_target_w)
            self._keep_anchor_during_anim = True
            self._use_target_x_lerp = False
        else:
            self._anim_target_x = int(self._collapsed_origin_x)
            self._keep_anchor_during_anim = False
            self._use_target_x_lerp = True
        self.geometry_anim.setDuration(self._motion.expand_duration_ms if expanding else self._motion.collapse_duration_ms)
        self.geometry_anim.setEasingCurve(self._expand_curve if expanding else self._collapse_curve)
        self.geometry_anim.start()
        if expanding:
            self.shimmer_anim.setStartValue(-120.0)
            self.shimmer_anim.setEndValue(float(target_w + 120))
            self.shimmer_anim.start()
        else:
            self._shimmer_x = -120.0
            self.update()

    def _expand_from_hover(self) -> None:
        if self._is_expanded:
            return
        self._is_expanded = True
        self._expanded_since = time.monotonic()
        self.set_state("Expanded")
        self._trigger_pulse()
        self.set_content_opacity(0.0)
        self._activate_plugins()
        self._recalculate_expand_width() # 重新计算展开宽度，因为插件可能刚刚变为可见
        self._start_content_fade()
        self._start_animation(self.EXPAND_WIDTH, self.EXPAND_HEIGHT, True)

    def _activate_plugins(self) -> None:
        if not self._is_expanded:
            return
        for key, plugin in plugin_manager.plugins.items():
            if self._is_plugin_visible(key):
                plugin.on_expand()
            else:
                plugin.hide()

    def _start_content_fade(self) -> None:
        if not self._is_expanded:
            return
        self.content_anim.stop()
        self.content_anim.setStartValue(self._content_opacity)
        self.content_anim.setEndValue(1.0)
        self.content_anim.start()

    def _collapse_if_needed(self) -> None:
        if self._is_cursor_inside_window():
            self._pending_collapse = False
            return
        self._pending_collapse = False
        self._collapse_now()

    def _collapse_now(self) -> None:
        self._is_expanded = False
        self.set_state("Idle")
        self.fade_timer.stop()
        self.content_anim.stop()
        self.set_content_opacity(0.0)
        self._start_animation(self.NORMAL_WIDTH, self.NORMAL_HEIGHT, False)
        for plugin in plugin_manager.plugins.values():
            plugin.on_collapse()

    def _save_window_position(self) -> None:
        x = self._collapsed_origin_x if self._is_expanded else self.x()
        config_manager.set("window_position", {"x": int(x), "y": int(self.y())})

    def enterEvent(self, event):
        self.collapse_timer.stop()
        self._pending_collapse = False
        if not self._is_expanded and not self.expand_timer.isActive():
            self.set_state("Hover")
            self.expand_timer.stop()
            self._expand_from_hover()
        super().enterEvent(event)

    def leaveEvent(self, event):
        if self._is_cursor_inside_window():
            super().leaveEvent(event)
            return
        self.expand_timer.stop()
        if self._is_expanded:
            if self.geometry_anim.state() == QAbstractAnimation.State.Running:
                cursor_pos = QCursor.pos()
                future_local_rect = QRect(0, 0, self.EXPAND_WIDTH, self.EXPAND_HEIGHT).adjusted(-10, -6, 10, 6)
                anchor_x = int(round(self._stable_anchor_x))
                anchor_band = abs(cursor_pos.x() - anchor_x) <= 64 and (self.y() - 12) <= cursor_pos.y() <= (self.y() + self.EXPAND_HEIGHT + 12)
                if anchor_band or future_local_rect.contains(self.mapFromGlobal(cursor_pos)):
                    self._pending_collapse = True
                    self.collapse_timer.start(140)
                    super().leaveEvent(event)
                    return
            elapsed = int((time.monotonic() - self._expanded_since) * 1000)
            remain = max(0, self._motion.min_dwell_ms - elapsed)
            if remain > 0:
                self._pending_collapse = True
                self.collapse_timer.start(remain)
            else:
                self._collapse_now()
        else:
            self.set_state("Idle")
        super().leaveEvent(event)

    def contextMenuEvent(self, event):
        menu = QMenu(self)
        self._apply_menu_theme(menu)
        quick_timer_action = None
        quick_timer_stop = None
        if self._timer_enabled and self._timer_mode != "off":
            quick_timer_action = menu.addAction("继续计时" if self._timer_paused else "暂停计时")
            quick_timer_stop = menu.addAction("停止计时")
            if hasattr(menu, "addSeparator"):
                menu.addSeparator()
        else:
            quick_timer_action = menu.addAction("开始 25 分钟倒计时")
            if hasattr(menu, "addSeparator"):
                menu.addSeparator()
        if hasattr(menu, "addMenu"):
            plugins_menu = menu.addMenu("显示模块")
            self._populate_plugins_menu(plugins_menu)
            timer_menu = menu.addMenu("计时器")
            self._populate_timer_menu(timer_menu)
        toggle = menu.addAction("切换主题")
        lock_action = menu.addAction("解锁位置" if self._is_locked else "锁定位置")
        quit_action = menu.addAction("退出灵动岛")
        action = menu.exec(event.globalPos())
        if action == quick_timer_action:
            if self._timer_enabled and self._timer_mode != "off":
                self._toggle_pause_timer()
            else:
                self._start_count_down(25 * 60)
        if action == quick_timer_stop:
            self._stop_timer()
        if action == toggle:
            self._toggle_theme()
        if action == lock_action:
            self._toggle_lock()
        if action == quit_action:
            QApplication.quit()

    def mousePressEvent(self, event: QMouseEvent):
        if event.button() == Qt.MouseButton.LeftButton and self._timer_badge_rect().contains(event.position().toPoint()):
            if self._timer_enabled and self._timer_mode != "off":
                self._toggle_pause_timer()
            else:
                self._start_count_down(25 * 60)
            event.accept()
            return
        if event.button() == Qt.MouseButton.LeftButton and not self._is_locked:
            self.geometry_anim.stop()
            self.shimmer_anim.stop()
            self._drag_pos = event.globalPosition().toPoint() - self.pos()
            self._drag_start_global = event.globalPosition().toPoint()
            self._is_dragging = False
        super().mousePressEvent(event)

    def wheelEvent(self, event: QWheelEvent) -> None:
        if not self._is_expanded and self._timer_badge_rect().contains(event.position().toPoint()):
            delta = event.angleDelta().y()
            if delta == 0:
                super().wheelEvent(event)
                return
            steps = int(delta / 120)
            minutes_delta = steps
            if self._timer_mode != "countdown" or not self._timer_enabled:
                self._start_count_down(25 * 60)
            self._adjust_countdown_minutes(minutes_delta)
            event.accept()
            return
        super().wheelEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent):
        if self._drag_pos is not None and event.buttons() & Qt.MouseButton.LeftButton:
            if not self._is_dragging and self._drag_start_global is not None:
                delta = event.globalPosition().toPoint() - self._drag_start_global
                if delta.manhattanLength() < 6:
                    super().mouseMoveEvent(event)
                    return
                self._is_dragging = True
            self.move(event.globalPosition().toPoint() - self._drag_pos)
            self._sync_anchor_to_geometry()
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent):
        if event.button() == Qt.MouseButton.LeftButton and self._drag_pos is not None:
            dragged = self._is_dragging
            self._drag_pos = None
            self._drag_start_global = None
            self._is_dragging = False
            if dragged:
                self._sync_anchor_to_geometry()
                if self._is_expanded:
                    self._collapsed_origin_x = int(round(self.x() + (self.width() - self.NORMAL_WIDTH) / 2.0))
                else:
                    self._collapsed_origin_x = self.x()
                self._save_window_position()
        super().mouseReleaseEvent(event)

    def resizeEvent(self, event):
        self._position_shortcut_dots()
        if hasattr(self, 'left_panel') and hasattr(self, 'right_panel'):
            wing_width = max(0, (self.width() - self._center_gap - self.MARGIN_X * 2) / 2.0)
            self.left_panel.setGeometry(self.MARGIN_X, 0, int(wing_width), self.height())
            self.right_panel.setGeometry(self.width() - self.MARGIN_X - int(wing_width), 0, int(wing_width), self.height())
        super().resizeEvent(event)

    def closeEvent(self, event: QCloseEvent) -> None:
        self._save_window_position()
        super().closeEvent(event)

    def mouseDoubleClickEvent(self, event: QMouseEvent):
        if event.button() == Qt.MouseButton.LeftButton:
            self._open_plugin("productivity_tools")
        super().mouseDoubleClickEvent(event)

    def get_shimmer_x(self) -> float:
        return self._shimmer_x

    def set_shimmer_x(self, value: float) -> None:
        self._shimmer_x = float(value)
        self.update()

    shimmer_x = Property(float, get_shimmer_x, set_shimmer_x)

    def get_content_opacity(self) -> float:
        return self._content_opacity

    def set_content_opacity(self, value: float) -> None:
        self._content_opacity = max(0.0, min(1.0, float(value)))
        for plugin in plugin_manager.plugins.values():
            effect = plugin.graphicsEffect()
            if isinstance(effect, QGraphicsOpacityEffect):
                effect.setOpacity(self._content_opacity)

    content_opacity = Property(float, get_content_opacity, set_content_opacity)

    @property
    def first_frame_time_ms(self) -> float:
        return self._first_frame_time_ms

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        path = QPainterPath()
        radius = min(self.width(), self.height()) / 2.0
        path.addRoundedRect(0, 0, self.width(), self.height(), radius, radius)
        painter.fillPath(path, self._bg_color)
        if self._is_expanded or (self._timer_enabled and self._timer_mode != "off") or self._state == "Recording":
            phase = float(self._accent_phase)
            hue = int((phase * 360.0) % 360.0)
            if self._state == "Recording":
                hue = 0
            elif self._timer_enabled and self._timer_mode != "off":
                hue = 140
            c1 = QColor.fromHsv(hue, 210, 255)
            c2 = QColor.fromHsv((hue + 60) % 360, 210, 255)
            c3 = QColor.fromHsv((hue + 130) % 360, 210, 255)
            overlay = QLinearGradient(0, 0, self.width(), 0)
            shift = phase
            overlay.setColorAt(0.0, QColor(c1.red(), c1.green(), c1.blue(), 0))
            overlay.setColorAt(min(1.0, max(0.0, shift)), QColor(c2.red(), c2.green(), c2.blue(), 70 if self._is_expanded else 54))
            overlay.setColorAt(1.0, QColor(c3.red(), c3.green(), c3.blue(), 0))
            painter.fillPath(path, overlay)
            glow = (0.35 if self._is_expanded else 0.24) + 0.10 * (0.5 + 0.5 * math.sin(phase * math.tau))
            glow_alpha = int(round(255 * glow))
            glow_color = QColor(c2.red(), c2.green(), c2.blue(), min(140, glow_alpha))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.setPen(QPen(glow_color, 2))
            painter.drawPath(path)
            if self._pulse_started_at > 0.0:
                t = time.monotonic() - float(self._pulse_started_at)
                if 0.0 <= t <= 0.55:
                    k = 1.0 - (t / 0.55)
                    pr = float(min(self.width(), self.height())) * (0.45 + 0.85 * (t / 0.55))
                    pulse = QRadialGradient(self.width() / 2.0, self.height() / 2.0, pr)
                    pulse.setColorAt(0.0, QColor(c2.red(), c2.green(), c2.blue(), int(round(120 * k))))
                    pulse.setColorAt(1.0, QColor(c2.red(), c2.green(), c2.blue(), 0))
                    painter.fillPath(path, pulse)
                elif t > 0.60:
                    self._pulse_started_at = 0.0
        if self._is_expanded:
            gradient = QLinearGradient(self._shimmer_x - 70, 0, self._shimmer_x + 70, 0)
            hue = int((float(self._accent_phase) * 360.0) % 360.0)
            highlight = QColor.fromHsv(hue, 160, 255)
            gradient.setColorAt(0.0, QColor(highlight.red(), highlight.green(), highlight.blue(), 0))
            gradient.setColorAt(0.5, QColor(highlight.red(), highlight.green(), highlight.blue(), 64))
            gradient.setColorAt(1.0, QColor(highlight.red(), highlight.green(), highlight.blue(), 0))
            painter.fillPath(path, gradient)
        if not self._is_expanded:
            painter.save()
            badge_rect = self._timer_badge_rect()
            if self._timer_enabled and self._timer_mode != "off" and self._timer_paused:
                badge_bg = QColor(255, 255, 255, 70) if theme_manager.current_theme == "dark" else QColor(0, 0, 0, 40)
            else:
                badge_bg = QColor(255, 255, 255, 40) if theme_manager.current_theme == "dark" else QColor(0, 0, 0, 24)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(badge_bg)
            painter.drawRoundedRect(badge_rect, 8, 8)
            painter.setPen(QColor(255, 255, 255, 220) if theme_manager.current_theme == "dark" else QColor(32, 32, 32, 220))
            font = painter.font()
            font.setPointSize(9)
            font.setBold(True)
            painter.setFont(font)
            text = self._format_timer_text()
            painter.drawText(badge_rect, int(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignHCenter), text)
            painter.restore()

    def get_accent_phase(self) -> float:
        return float(self._accent_phase)

    def set_accent_phase(self, value: float) -> None:
        self._accent_phase = float(value)
        if self._is_expanded or (self._timer_enabled and self._timer_mode != "off") or self._state == "Recording":
            self.update()

    accent_phase = Property(float, get_accent_phase, set_accent_phase)

    def _timer_badge_rect(self) -> QRect:
        w = 46
        h = 22
        x = 8
        y = int(round((self.height() - h) / 2.0))
        return QRect(x, y, w, h)

    def _format_timer_text(self) -> str:
        if not self._timer_enabled or self._timer_mode == "off":
            return "计时"
        if self._timer_mode == "countup":
            elapsed = self._elapsed_seconds_int()
            return f"{elapsed // 60:02d}:{elapsed % 60:02d}"
        if self._timer_mode == "countdown":
            remain = self._remain_seconds_int()
            return f"{remain // 60:02d}:{remain % 60:02d}"
        return ""

    def _elapsed_seconds_float(self) -> float:
        if not self._timer_enabled or self._timer_mode == "off":
            return 0.0
        if self._timer_paused:
            return float(self._timer_pause_acc)
        return float(self._timer_pause_acc) + (time.monotonic() - float(self._timer_started_at))

    def _elapsed_seconds_int(self) -> int:
        return max(0, int(self._elapsed_seconds_float()))

    def _remain_seconds_int(self) -> int:
        if self._timer_mode != "countdown":
            return 0
        remain_f = float(self._timer_countdown_total) - self._elapsed_seconds_float()
        if remain_f <= 0.0:
            return 0
        return int(remain_f + 0.999)

    def _on_timer_tick(self) -> None:
        if not self._timer_enabled or self._timer_mode == "off":
            return
        if self._timer_mode == "countdown":
            if self._elapsed_seconds_float() >= float(self._timer_countdown_total):
                self._timer_enabled = False
                self._timer_mode = "off"
                self.timer_tick.stop()
                self._timer_last_text = ""
                self.update()
                return
        text = self._format_timer_text()
        if text != self._timer_last_text:
            self._timer_last_text = text
            self.update()

    def _populate_timer_menu(self, menu: QMenu) -> None:
        menu.clear()
        start_up = menu.addAction("开始正计时")
        start_pomodoro = menu.addAction("开始倒计时 25:00")
        start_custom = menu.addAction("自定义倒计时…")
        pause = menu.addAction("暂停" if (self._timer_enabled and not self._timer_paused) else "继续")
        stop = menu.addAction("停止")
        start_up.triggered.connect(self._start_count_up)
        start_pomodoro.triggered.connect(lambda: self._start_count_down(25 * 60))
        start_custom.triggered.connect(self._start_custom_countdown)
        pause.triggered.connect(self._toggle_pause_timer)
        stop.triggered.connect(self._stop_timer)

    def _start_count_up(self) -> None:
        self._timer_mode = "countup"
        self._timer_enabled = True
        self._timer_paused = False
        self._timer_pause_acc = 0.0
        self._timer_started_at = time.monotonic()
        self._timer_last_text = ""
        self._trigger_pulse()
        self.timer_tick.start()
        self.update()

    def _start_count_down(self, seconds: int) -> None:
        self._timer_mode = "countdown"
        self._timer_countdown_total = float(max(1, int(seconds)))
        self._timer_enabled = True
        self._timer_paused = False
        self._timer_pause_acc = 0.0
        self._timer_started_at = time.monotonic()
        self._timer_last_text = ""
        self._trigger_pulse()
        self.timer_tick.start()
        self.update()

    def _trigger_pulse(self) -> None:
        self._pulse_started_at = time.monotonic()
        self.update()

    def _adjust_countdown_minutes(self, minutes_delta: int) -> None:
        if minutes_delta == 0:
            return
        elapsed = self._elapsed_seconds_float()
        remain = max(0.0, float(self._timer_countdown_total) - elapsed)
        remain = remain + float(minutes_delta) * 60.0
        remain = max(60.0, min(600.0 * 60.0, remain))
        self._timer_mode = "countdown"
        self._timer_countdown_total = float(elapsed) + float(remain)
        self._timer_last_text = ""
        self.update()

    def _start_custom_countdown(self) -> None:
        minutes, ok = QInputDialog.getInt(self, "倒计时", "输入分钟数", 25, 1, 600, 1)
        if ok:
            self._start_count_down(minutes * 60)

    def _toggle_pause_timer(self) -> None:
        if not self._timer_enabled or self._timer_mode == "off":
            return
        if self._timer_paused:
            self._timer_started_at = time.monotonic()
            self._timer_paused = False
        else:
            self._timer_pause_acc = self._elapsed_seconds_float()
            self._timer_paused = True
        self._timer_last_text = ""
        self.update()

    def _stop_timer(self) -> None:
        self._timer_enabled = False
        self._timer_mode = "off"
        self._timer_paused = False
        self._timer_pause_acc = 0.0
        self.timer_tick.stop()
        self.update()
