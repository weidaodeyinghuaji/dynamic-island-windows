from __future__ import annotations

import subprocess
import threading
import time

import psutil
from PySide6.QtCore import QTimer, Qt, Signal
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import QHBoxLayout, QPushButton
from PySide6.QtCore import QUrl

from src.plugins.base import IslandPlugin


class HoldButton(QPushButton):
    long_pressed = Signal()

    def __init__(self, text: str, parent=None):
        super().__init__(text, parent)
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.setInterval(520)
        self._timer.timeout.connect(self.long_pressed.emit)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._timer.start()
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event):
        self._timer.stop()
        super().mouseReleaseEvent(event)


class ConnectionStatusPlugin(IslandPlugin):
    plugin_name = "connection_status"
    states_ready = Signal(object)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._wifi_up = False
        self._bt_up = False
        self._focus_on = False
        self._wifi_iface = ""
        self._bt_iface = ""
        self._bt_device_count = 0
        self._has_polled_once = False
        self._poll_inflight = False
        self._last_change = 0.0
        self.states_ready.connect(self._apply_polled_states)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)
        self.wifi_btn = HoldButton("📶", self)
        self.bt_btn = HoldButton("🅱", self)
        self.focus_btn = HoldButton("🌙", self)
        self.wifi_btn.clicked.connect(self._toggle_wifi)
        self.bt_btn.clicked.connect(self._toggle_bt)
        self.focus_btn.clicked.connect(self._toggle_focus)
        self.wifi_btn.long_pressed.connect(lambda: self._open_setting("ms-settings:network-wifi"))
        self.bt_btn.long_pressed.connect(lambda: self._open_setting("ms-settings:bluetooth"))
        self.focus_btn.long_pressed.connect(lambda: self._open_setting("ms-settings:quiethours"))
        for w in (self.wifi_btn, self.bt_btn, self.focus_btn):
            w.setSizePolicy(w.sizePolicy().Policy.Minimum, w.sizePolicy().Policy.Fixed)
            layout.addWidget(w)
        self._poll_timer = QTimer(self)
        self._poll_timer.setInterval(3000)
        self._poll_timer.timeout.connect(self._poll_states_async)
        self._poll_timer.start()
        self._poll_states()
        self.on_theme_changed("dark")

    def _open_setting(self, url: str) -> None:
        QDesktopServices.openUrl(QUrl(url))

    def _detect_wifi(self) -> tuple[bool, str]:
        stats = psutil.net_if_stats()
        names = [name for name in stats.keys() if any(k in name.lower() for k in ("wi-fi", "wifi", "wlan"))]
        if not names:
            return False, ""
        iface = names[0]
        return bool(stats.get(iface).isup), iface

    def _detect_bt(self) -> tuple[bool, str]:
        stats = psutil.net_if_stats()
        names = []
        for name, st in stats.items():
            if "bluetooth" in name.lower():
                names.append(name)
                if st.isup:
                    return True, name
        if names:
            return False, names[0]
        return False, ""

    @staticmethod
    def _hidden_process_kwargs() -> dict:
        kwargs = {}
        creationflags = int(getattr(subprocess, "CREATE_NO_WINDOW", 0))
        if creationflags:
            kwargs["creationflags"] = creationflags
        startupinfo_factory = getattr(subprocess, "STARTUPINFO", None)
        startf_flag = int(getattr(subprocess, "STARTF_USESHOWWINDOW", 0))
        if startupinfo_factory is not None and startf_flag:
            startupinfo = startupinfo_factory()
            startupinfo.dwFlags |= startf_flag
            kwargs["startupinfo"] = startupinfo
        return kwargs

    @classmethod
    def _run_command(cls, args: list[str]) -> str:
        try:
            completed = subprocess.run(
                args,
                capture_output=True,
                text=True,
                timeout=1.2,
                check=False,
                **cls._hidden_process_kwargs(),
            )
            return f"{completed.stdout}\n{completed.stderr}"
        except Exception:
            return ""

    @classmethod
    def _spawn_command(cls, args: list[str]) -> None:
        subprocess.Popen(args, shell=False, **cls._hidden_process_kwargs())

    def _detect_bt_devices(self) -> int:
        output = self._run_command(
            [
                "powershell",
                "-NoProfile",
                "-Command",
                "(Get-PnpDevice -Class Bluetooth -Status OK -ErrorAction SilentlyContinue | Measure-Object).Count",
            ]
        ).strip()
        try:
            return max(0, int(output.splitlines()[-1].strip()))
        except Exception:
            return self._bt_device_count

    def _detect_focus(self) -> bool:
        output = self._run_command(
            [
                "reg",
                "query",
                r"HKCU\\Software\\Microsoft\\Windows\\CurrentVersion\\Notifications\\Settings",
                "/v",
                "NOC_GLOBAL_SETTING_TOASTS_ENABLED",
            ]
        ).lower()
        if "0x0" in output:
            return True
        if "0x1" in output:
            return False
        return self._focus_on

    def _notify_change(self) -> None:
        now = time.monotonic()
        if now - self._last_change < 1.0:
            return
        self._last_change = now
        parent = self.parentWidget()
        if parent and hasattr(parent, "request_expand"):
            parent.request_expand()

    def _poll_states(self) -> None:
        self._apply_polled_states(self._collect_states_snapshot())

    def _collect_states_snapshot(self) -> tuple[bool, str, bool, str, int, bool]:
        wifi_up, wifi_iface = self._detect_wifi()
        bt_up, bt_iface = self._detect_bt()
        bt_device_count = self._detect_bt_devices()
        focus_on = self._detect_focus()
        return wifi_up, wifi_iface, bt_up, bt_iface, bt_device_count, focus_on

    def _poll_states_async(self) -> None:
        if self._poll_inflight:
            return
        self._poll_inflight = True
        threading.Thread(target=self._poll_worker, daemon=True).start()

    def _poll_worker(self) -> None:
        try:
            result = self._collect_states_snapshot()
        except Exception:
            result = None
        self.states_ready.emit(result)

    def _apply_polled_states(self, result) -> None:
        self._poll_inflight = False
        if not result:
            return
        prev_wifi = self._wifi_up
        prev_bt = self._bt_up
        prev_focus = self._focus_on
        prev_bt_device_count = self._bt_device_count
        self._wifi_up, self._wifi_iface, self._bt_up, self._bt_iface, self._bt_device_count, self._focus_on = result
        bt_device_increased = self._bt_device_count > prev_bt_device_count
        if not self._has_polled_once:
            self._has_polled_once = True
        elif prev_wifi != self._wifi_up or prev_bt != self._bt_up or prev_focus != self._focus_on or bt_device_increased:
            self._notify_change()
        self._refresh_icons()

    def _refresh_icons(self) -> None:
        self.wifi_btn.setText("📶" if self._wifi_up else "📴")
        self.bt_btn.setText("🟦" if self._bt_up else "⬜")
        self.focus_btn.setText("🌙" if self._focus_on else "🔔")

    def _toggle_wifi(self) -> None:
        if not self._wifi_iface:
            self._open_setting("ms-settings:network-wifi")
            return
        action = "disable" if self._wifi_up else "enable"
        self._spawn_command(["netsh", "interface", "set", "interface", self._wifi_iface, action])
        QTimer.singleShot(900, self._poll_states_async)

    def _toggle_bt(self) -> None:
        if not self._bt_iface:
            self._open_setting("ms-settings:bluetooth")
            return
        action = "disable" if self._bt_up else "enable"
        self._spawn_command(["netsh", "interface", "set", "interface", self._bt_iface, action])
        QTimer.singleShot(900, self._poll_states_async)

    def _toggle_focus(self) -> None:
        target_focus = not self._focus_on
        target_toasts = "0x0" if target_focus else "0x1"
        output = self._run_command(
            [
                "reg",
                "add",
                r"HKCU\\Software\\Microsoft\\Windows\\CurrentVersion\\Notifications\\Settings",
                "/v",
                "NOC_GLOBAL_SETTING_TOASTS_ENABLED",
                "/t",
                "REG_DWORD",
                "/d",
                target_toasts,
                "/f",
            ]
        )
        if "error" in output.lower():
            self._open_setting("ms-settings:quiethours")
            return
        self._focus_on = target_focus
        self._refresh_icons()

    def on_expand(self) -> None:
        self.show()
        self._poll_states_async()

    def on_collapse(self) -> None:
        self.hide()

    def on_theme_changed(self, theme: str) -> None:
        color = "#f4f4f4" if theme == "dark" else "#1a1a1a"
        style = f"color:{color};background:transparent;border:none;font-size:12px;"
        self.wifi_btn.setStyleSheet(style)
        self.bt_btn.setStyleSheet(style)
        self.focus_btn.setStyleSheet(style)
