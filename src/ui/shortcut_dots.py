from __future__ import annotations

import ctypes
import subprocess
import webbrowser
from pathlib import Path

from PySide6.QtCore import QMimeData, QTimer, QUrl, Signal, Qt
from PySide6.QtGui import QColor, QDragEnterEvent, QDropEvent
from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QWidget

from src.utils.config import config_manager


class DotButton(QPushButton):
    long_pressed = Signal(int)
    shortcut_dropped = Signal(int, str, str)

    def __init__(self, index: int, color: str, parent=None):
        super().__init__(parent)
        self.index = index
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.setInterval(500)
        self._timer.timeout.connect(lambda: self.long_pressed.emit(self.index))
        self.setAcceptDrops(True)
        self.setFixedSize(16, 16)
        self.setStyleSheet(
            f"border:none;border-radius:8px;background:{color};"
        )

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._timer.start()
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event):
        self._timer.stop()
        super().mouseReleaseEvent(event)

    def dragEnterEvent(self, event: QDragEnterEvent):
        owner = self.parent()
        resolver = getattr(owner, "_resolve_drop_payload", None)
        payload = resolver(event.mimeData()) if callable(resolver) else None
        if payload:
            event.acceptProposedAction()
            return
        event.ignore()

    def dropEvent(self, event: QDropEvent):
        owner = self.parent()
        resolver = getattr(owner, "_resolve_drop_payload", None)
        payload = resolver(event.mimeData()) if callable(resolver) else None
        if payload:
            mode, target = payload
            self.shortcut_dropped.emit(self.index, mode, target)
            event.acceptProposedAction()
            return
        event.ignore()


class ShortcutDots(QWidget):
    edit_requested = Signal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._buttons: list[DotButton] = []
        self._recording_mode = False
        self._music_title = ""
        self._music_artist = ""
        self._is_playing_music = False
        self._layout = QHBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setSpacing(8)
        self._compact_mode = False
        
        self.dots_container = QWidget(self)
        self._dots_layout = QHBoxLayout(self.dots_container)
        self._dots_layout.setContentsMargins(0, 0, 0, 0)
        self._dots_layout.setSpacing(8)
        
        for index, color in enumerate(("#ff5f57", "#febc2e", "#28c840")):
            button = DotButton(index, color, self.dots_container)
            button.clicked.connect(lambda _, i=index: self.execute_shortcut(i))
            button.long_pressed.connect(self.edit_requested.emit)
            button.shortcut_dropped.connect(self._apply_dropped_shortcut)
            self._dots_layout.addWidget(button)
            self._buttons.append(button)
            
        self.red_dot = self._buttons[0]
        self.yellow_dot = self._buttons[1]
        self.green_dot = self._buttons[2]
        
        self.music_label = QLabel(self)
        self.music_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.music_label.setStyleSheet("color: white; font-size: 12px; font-weight: bold;")
        self.music_label.hide()
        
        self._layout.addWidget(self.dots_container)
        self._layout.addWidget(self.music_label)
        
        self.setFixedSize(64, 18)
        
    def update_music_info(self, is_playing: bool, title: str = "", artist: str = ""):
        self._is_playing_music = is_playing
        self._music_title = title
        self._music_artist = artist
        
        parent = self.parent()
        if parent is not None and hasattr(parent, "_is_expanded") and not bool(getattr(parent, "_is_expanded")):
            is_playing = False
        if is_playing and title and title != "音乐" and not self._compact_mode:
            self.dots_container.hide()
            self.music_label.setText(f"🎵 {title}")
            self.music_label.show()
            self.setFixedSize(160, 18)  # 增加宽度以显示歌名
        else:
            self.music_label.hide()
            self.dots_container.show()
            self.setFixedSize(54 if self._compact_mode else 64, 18)
            
        # 通知父窗口重新计算位置
        if parent:
            if hasattr(parent, "_position_shortcut_dots"):
                parent._position_shortcut_dots()
            if hasattr(parent, "update"):
                parent.update()

    def set_compact_mode(self, compact: bool) -> None:
        compact = bool(compact)
        if self._compact_mode == compact:
            return
        self._compact_mode = compact
        self.music_label.hide()
        self.dots_container.show()
        self._layout.setSpacing(4 if compact else 8)
        self._dots_layout.setSpacing(4 if compact else 8)
        size = 14 if compact else 16
        for btn in self._buttons:
            btn.setFixedSize(size, size)
            btn.setStyleSheet(btn.styleSheet().replace("border-radius:8px;", f"border-radius:{int(size/2)}px;"))
        self.setFixedSize(54 if compact else 64, 18)

    def execute_shortcut(self, index: int) -> None:
        presets = config_manager.get("shortcut_presets", [{}, {}, {}])
        preset = presets[index] if index < len(presets) else {}
        mode = preset.get("type")
        target = preset.get("target")
        if not mode:
            return
        if mode == "url":
            if not target:
                return
            webbrowser.open(target)
            return
        if mode == "exe":
            if not target:
                return
            subprocess.Popen([target], shell=False)
            return
        if mode == "script":
            if not target:
                return
            path = Path(target)
            if path.suffix.lower() == ".py":
                subprocess.Popen(["py", "-3", str(path)], shell=False)
            else:
                subprocess.Popen([str(path)], shell=True)
            return
        if mode == "hotkey" and target:
            self._send_hotkey(str(target))

    def _apply_dropped_shortcut(self, index: int, mode: str, target: str) -> None:
        presets = config_manager.get("shortcut_presets", [{}, {}, {}])
        if not isinstance(presets, list):
            presets = [{}, {}, {}]
        while len(presets) < 3:
            presets.append({})
        if not (0 <= index < len(presets)):
            return
        presets[index] = {"type": mode, "target": target}
        config_manager.set("shortcut_presets", presets)

    @staticmethod
    def _resolve_drop_payload(mime_data: QMimeData) -> tuple[str, str] | None:
        if mime_data.hasUrls():
            for url in mime_data.urls():
                payload = ShortcutDots._resolve_from_url(url)
                if payload:
                    return payload
        if mime_data.hasText():
            return ShortcutDots._resolve_from_text(mime_data.text())
        return None

    @staticmethod
    def _resolve_from_url(url: QUrl) -> tuple[str, str] | None:
        if not url.isValid():
            return None
        if url.isLocalFile():
            return ShortcutDots._resolve_from_local_path(url.toLocalFile())
        value = url.toString().strip()
        if value.lower().startswith(("http://", "https://")):
            return "url", value
        return None

    @staticmethod
    def _resolve_from_text(value: str) -> tuple[str, str] | None:
        text = value.strip()
        if not text:
            return None
        url = QUrl(text)
        if url.isValid() and url.isLocalFile():
            return ShortcutDots._resolve_from_local_path(url.toLocalFile())
        if text.lower().startswith(("http://", "https://")):
            return "url", text
        return ShortcutDots._resolve_from_local_path(text)

    @staticmethod
    def _resolve_from_local_path(value: str) -> tuple[str, str] | None:
        path = Path(str(value).strip())
        normalized = str(path)
        suffix = path.suffix.lower()
        if suffix == ".url":
            try:
                for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
                    if line.lower().startswith("url="):
                        target = line.split("=", 1)[1].strip()
                        if target:
                            return "url", target
            except OSError:
                return "exe", normalized
        if suffix in {".py", ".bat", ".cmd", ".ps1", ".vbs"}:
            return "script", normalized
        return "exe", normalized

    def set_recording_indicator(self, active: bool) -> None:
        self._recording_mode = bool(active)
        color = "#ff3b30" if self._recording_mode else "#ff5f57"
        self.red_dot.setStyleSheet(f"border:none;border-radius:8px;background:{color};")

    @staticmethod
    def _send_hotkey(combo: str) -> bool:
        user32 = getattr(ctypes, "windll", None)
        if user32 is None:
            return False
        parts = [part.strip().lower() for part in combo.split("+") if part.strip()]
        if not parts:
            return False
        mod_map = {"ctrl": 0x11, "control": 0x11, "alt": 0x12, "shift": 0x10, "win": 0x5B, "meta": 0x5B}
        key_map = {
            "enter": 0x0D,
            "tab": 0x09,
            "esc": 0x1B,
            "space": 0x20,
            "left": 0x25,
            "up": 0x26,
            "right": 0x27,
            "down": 0x28,
        }
        for idx in range(1, 13):
            key_map[f"f{idx}"] = 0x6F + idx
        mods = []
        key_code = None
        for part in parts:
            if part in mod_map:
                mods.append(mod_map[part])
                continue
            if part in key_map:
                key_code = key_map[part]
                continue
            if len(part) == 1 and part.isalnum():
                key_code = ord(part.upper())
        if key_code is None:
            return False
        for mod in mods:
            user32.user32.keybd_event(mod, 0, 0, 0)
        user32.user32.keybd_event(key_code, 0, 0, 0)
        user32.user32.keybd_event(key_code, 0, 2, 0)
        for mod in reversed(mods):
            user32.user32.keybd_event(mod, 0, 2, 0)
        return True

    @staticmethod
    def dot_palette(theme: str) -> tuple[QColor, QColor, QColor]:
        if theme == "light":
            return QColor("#ff5f57"), QColor("#febc2e"), QColor("#28c840")
        return QColor("#ff6b63"), QColor("#ffc53d"), QColor("#32d74b")
