from __future__ import annotations

import ctypes

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QHBoxLayout, QLabel, QPushButton

from src.plugins.base import IslandPlugin


class ClipboardHistoryPlugin(IslandPlugin):
    plugin_name = "clipboard"

    def __init__(self, parent=None):
        super().__init__(parent)
        self.items: list[str] = []
        self._selected_index = 0
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)
        self.label = QLabel("📋 空", self)
        self.label.setSizePolicy(self.label.sizePolicy().Policy.Minimum, self.label.sizePolicy().Policy.Fixed)
        self.label.setMinimumWidth(120)
        self.clear_btn = QPushButton("🗑", self)
        self.clear_btn.clicked.connect(self.clear_items)
        layout.addWidget(self.label)
        layout.addWidget(self.clear_btn)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self._clipboard = QApplication.clipboard()
        self._clipboard.dataChanged.connect(self._capture_clipboard)
        self._capture_clipboard()
        self.on_theme_changed("dark")

    def _capture_clipboard(self) -> None:
        text = self._clipboard.text().strip()
        if not text:
            self._refresh_label()
            return
        if self.items and self.items[0] == text:
            self._refresh_label()
            return
        self.items = [text] + [item for item in self.items if item != text]
        self.items = self.items[:5]
        self._selected_index = 0
        self._refresh_label()

    def _refresh_label(self) -> None:
        if not self.items:
            self.label.setText("📋 空")
            return
        previews = []
        for idx, item in enumerate(self.items):
            clipped = item.replace("\n", " ")
            clipped = clipped[:14] + "…" if len(clipped) > 14 else clipped
            previews.append(f"[{clipped}]" if idx == self._selected_index else clipped)
        self.label.setText("📋 " + " | ".join(previews[:3]))

    def clear_items(self) -> None:
        self.items = []
        self._selected_index = 0
        self._refresh_label()

    def activate_panel(self) -> None:
        self.setFocus()
        self._refresh_label()

    @staticmethod
    def _send_ctrl_v() -> None:
        user32 = getattr(ctypes, "windll", None)
        if user32 is None:
            return
        ctrl = 0x11
        v_key = 0x56
        user32.user32.keybd_event(ctrl, 0, 0, 0)
        user32.user32.keybd_event(v_key, 0, 0, 0)
        user32.user32.keybd_event(v_key, 0, 2, 0)
        user32.user32.keybd_event(ctrl, 0, 2, 0)

    def keyPressEvent(self, event) -> None:
        if not self.items:
            super().keyPressEvent(event)
            return
        key = event.key()
        if key == Qt.Key.Key_Up:
            self._selected_index = (self._selected_index - 1) % len(self.items)
            self._refresh_label()
            return
        if key == Qt.Key.Key_Down:
            self._selected_index = (self._selected_index + 1) % len(self.items)
            self._refresh_label()
            return
        if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            self._clipboard.setText(self.items[self._selected_index])
            self._send_ctrl_v()
            return
        super().keyPressEvent(event)

    def on_expand(self) -> None:
        self._refresh_label()
        self.show()

    def on_collapse(self) -> None:
        self.hide()

    def on_theme_changed(self, theme: str) -> None:
        color = "#f4f4f4" if theme == "dark" else "#1a1a1a"
        self.label.setStyleSheet(f"color:{color};font-size:12px;")
        self.clear_btn.setStyleSheet(f"color:{color};background:transparent;border:none;")
