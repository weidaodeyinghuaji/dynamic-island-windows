from __future__ import annotations

import ctypes
import os
import subprocess

from PySide6.QtWidgets import QHBoxLayout, QPushButton

from src.plugins.base import IslandPlugin


class ProductivityToolsPlugin(IslandPlugin):
    plugin_name = "productivity_tools"

    def __init__(self, parent=None):
        super().__init__(parent)
        self._recording = False
        self._capture_dir = os.path.join(os.path.expanduser("~"), "Videos", "Captures")
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)
        self.snip_btn = QPushButton("✂", self)
        self.record_btn = QPushButton("⏺", self)
        self.folder_btn = QPushButton("📂", self)
        self.lock_btn = QPushButton("🔒", self)
        
        self.snip_btn.setToolTip("截屏")
        self.record_btn.setToolTip("录屏")
        self.folder_btn.setToolTip("录屏目录")
        self.lock_btn.setToolTip("锁屏")
        
        # 防止按钮文字被挤压
        for btn in (self.snip_btn, self.record_btn, self.folder_btn, self.lock_btn):
            btn.setSizePolicy(btn.sizePolicy().Policy.Minimum, btn.sizePolicy().Policy.Fixed)
            btn.setFixedWidth(32)
        self.snip_btn.clicked.connect(self._capture_area)
        self.record_btn.clicked.connect(self._toggle_recording)
        self.folder_btn.clicked.connect(self._open_capture_folder)
        self.lock_btn.clicked.connect(self._lock_screen)
        for btn in (self.snip_btn, self.record_btn, self.folder_btn, self.lock_btn):
            layout.addWidget(btn)
        self.record_btn.setToolTip(f"系统录屏保存目录：{self._capture_dir}")
        self.on_theme_changed("dark")

    @staticmethod
    def _send_hotkey(*codes: int) -> None:
        user32 = getattr(ctypes, "windll", None)
        if user32 is None:
            return
        for code in codes:
            user32.user32.keybd_event(code, 0, 0, 0)
        for code in reversed(codes):
            user32.user32.keybd_event(code, 0, 2, 0)

    def _capture_area(self) -> None:
        self._send_hotkey(0x5B, 0x10, 0x53)

    def _toggle_recording(self) -> None:
        self._recording = not self._recording
        self._send_hotkey(0x5B, 0x12, 0x52)
        self.record_btn.setText("🔴" if self._recording else "⏺")
        self.record_btn.setToolTip(f"录制中...\n系统录屏保存目录：{self._capture_dir}" if self._recording else f"录屏\n系统录屏保存目录：{self._capture_dir}")
        parent = self.parentWidget()
        if parent and hasattr(parent, "set_recording_mode"):
            parent.set_recording_mode(self._recording)

    def _open_capture_folder(self) -> None:
        os.makedirs(self._capture_dir, exist_ok=True)
        subprocess.Popen(["explorer.exe", self._capture_dir], shell=False)

    @staticmethod
    def _lock_screen() -> None:
        try:
            ctypes.windll.user32.LockWorkStation()
        except Exception:
            subprocess.Popen(["rundll32.exe", "user32.dll,LockWorkStation"], shell=False)

    def focus_tools(self) -> None:
        self.snip_btn.setFocus()

    def on_expand(self) -> None:
        self.show()

    def on_collapse(self) -> None:
        self.hide()

    def on_theme_changed(self, theme: str) -> None:
        color = "#f4f4f4" if theme == "dark" else "#1a1a1a"
        border = "#4a5264" if theme == "dark" else "#cdd4de"
        style = f"color:{color};background:transparent;border:1px solid {border};padding:2px 6px;border-radius:7px;"
        self.snip_btn.setStyleSheet(style)
        self.record_btn.setStyleSheet(style)
        self.folder_btn.setStyleSheet(style)
        self.lock_btn.setStyleSheet(style)
