from __future__ import annotations

import ctypes
import subprocess
from pathlib import Path

from PySide6.QtCore import Qt, QUrl, QTimer, QThread, Signal
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QVBoxLayout

from src.plugins.base import IslandPlugin

class MediaInfoFetcher(QThread):
    info_ready = Signal(str, str)
    
    def run(self):
        title, artist = "音乐", "等待播放..."
        try:
            cmd = "[Windows.Media.Control.GlobalSystemMediaTransportControlsSessionManager, Windows.Media, ContentType = WindowsRuntime] | Out-Null; Add-Type -AssemblyName System.Runtime.WindowsRuntime; try { $managerAsync = [Windows.Media.Control.GlobalSystemMediaTransportControlsSessionManager]::RequestAsync(); $managerAsync.AsTask().Wait(); $manager = $managerAsync.GetResults(); $session = $manager.GetCurrentSession(); if ($session) { $propsAsync = $session.TryGetMediaPropertiesAsync(); $propsAsync.AsTask().Wait(); $props = $propsAsync.GetResults(); $status = $session.GetPlaybackInfo().PlaybackStatus.ToString(); $title = $props.Title; if (-not $title) { $title = '音乐' }; Write-Output ($title + '|' + $props.Artist + '|' + $status) } } catch {}"
            result = subprocess.run(
                ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", cmd],
                capture_output=True,
                text=True,
                creationflags=subprocess.CREATE_NO_WINDOW,
                timeout=3
            )
            output = (result.stdout or "").strip()
            if not output or "|" not in output:
                ps_script = Path(__file__).resolve().with_name("get_media.ps1")
                if ps_script.is_file():
                    result = subprocess.run(
                        ["powershell.exe", "-ExecutionPolicy", "Bypass", "-File", str(ps_script)],
                        capture_output=True,
                        text=True,
                        creationflags=subprocess.CREATE_NO_WINDOW,
                        timeout=3
                    )
                    output = (result.stdout or "").strip()
            if output and "|" in output:
                parts = output.split("|")
                if len(parts) >= 2:
                    title = (parts[0] or "").strip() or "音乐"
                    artist = (parts[1] or "").strip() or "未知歌手"
                if len(parts) >= 3:
                    status = (parts[2] or "").strip()
                    if status == "Stopped" and (not title or title == "音乐"):
                        title, artist = "音乐", "等待播放..."
        except Exception:
            pass
            
        self.info_ready.emit(title, artist)

class MusicControlPlugin(IslandPlugin):
    plugin_name = "music"

    def __init__(self, parent=None):
        super().__init__(parent)
        self._is_muted = False
        
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)
        
        self.cover = QLabel("🎵", self)
        
        # 使用垂直布局展示歌曲名和歌手（及模拟歌词）
        self.info_layout = QVBoxLayout()
        self.info_layout.setContentsMargins(0, 0, 0, 0)
        self.info_layout.setSpacing(0)
        
        self.title = QLabel("音乐", self)
        self.artist = QLabel("等待播放...", self)
        
        self.title.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignBottom)
        self.artist.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        
        self.info_layout.addWidget(self.title)
        self.info_layout.addWidget(self.artist)
        
        self.prev_btn = QPushButton("⏮", self)
        self.play_btn = QPushButton("⏯", self)
        self.next_btn = QPushButton("⏭", self)
        self.vol_down_btn = QPushButton("🔉", self)
        self.vol_up_btn = QPushButton("🔊", self)
        self.mic_btn = QPushButton("🎤", self)
        
        # 防止按钮文字被挤压
        for btn in (self.prev_btn, self.play_btn, self.next_btn, self.vol_down_btn, self.vol_up_btn, self.mic_btn):
            btn.setSizePolicy(btn.sizePolicy().Policy.Minimum, btn.sizePolicy().Policy.Fixed)
            btn.setFixedWidth(28)
            
        self.title.setSizePolicy(self.title.sizePolicy().Policy.Expanding, self.title.sizePolicy().Policy.Fixed)
        self.artist.setSizePolicy(self.artist.sizePolicy().Policy.Expanding, self.artist.sizePolicy().Policy.Fixed)
        
        self.cover.setCursor(Qt.CursorShape.PointingHandCursor)
        self.cover.mousePressEvent = self._activate_media_app
        self.prev_btn.clicked.connect(lambda: self._send_media_key(0xB1))
        self.play_btn.clicked.connect(lambda: self._send_media_key(0xB3))
        self.next_btn.clicked.connect(lambda: self._send_media_key(0xB0))
        self.vol_down_btn.clicked.connect(lambda: self._send_media_key(0xAE))
        self.vol_up_btn.clicked.connect(lambda: self._send_media_key(0xAF))
        self.mic_btn.clicked.connect(self._toggle_mute)
        
        layout.addWidget(self.cover)
        layout.addLayout(self.info_layout)
        layout.addWidget(self.prev_btn)
        layout.addWidget(self.play_btn)
        layout.addWidget(self.next_btn)
        layout.addWidget(self.vol_down_btn)
        layout.addWidget(self.vol_up_btn)
        layout.addWidget(self.mic_btn)
        
        self.on_theme_changed("dark")
        
        # 歌词及媒体信息获取器
        self.fetcher = None
        
        # 定时更新媒体信息
        self.update_timer = QTimer(self)
        self.update_timer.timeout.connect(self._update_media_info)
        self.update_timer.start(2000)

    def _update_media_info(self):
        if self.fetcher is None or self.fetcher.isFinished():
            self.fetcher = MediaInfoFetcher(self)
            self.fetcher.info_ready.connect(self._on_info_ready)
            self.fetcher.start()

    def _on_info_ready(self, title: str, artist: str):
        is_playing = bool(title and title != "音乐" and title != "等待播放...")
        
        if is_playing:
            self.title.setText(title)
            self.artist.setText(artist)
        else:
            self.title.setText("音乐")
            self.artist.setText("等待播放...")
            
        # 通知主窗口更新快捷圆点
        if self.parent() and hasattr(self.parent(), "shortcut_dots"):
            self.parent().shortcut_dots.update_music_info(is_playing, title, artist)
            # 强制重新计算灵动岛宽度，以适应歌名的长度变化
            if hasattr(self.parent(), "_recalculate_expand_width"):
                self.parent()._recalculate_expand_width()

    @staticmethod
    def _send_media_key(vk_code: int) -> None:
        user32 = getattr(ctypes, "windll", None)
        if user32 is None:
            return
        user32.user32.keybd_event(vk_code, 0, 0, 0)
        user32.user32.keybd_event(vk_code, 0, 2, 0)

    def _toggle_mute(self) -> None:
        self._send_media_key(0xAD)
        self._is_muted = not self._is_muted
        self.mic_btn.setText("🔇" if self._is_muted else "🎤")

    @staticmethod
    def _activate_media_app(_) -> None:
        QDesktopServices.openUrl(QUrl("spotify:"))

    def on_expand(self) -> None:
        self.show()

    def on_collapse(self) -> None:
        self.hide()

    def on_theme_changed(self, theme: str) -> None:
        color = "#f4f4f4" if theme == "dark" else "#1a1a1a"
        artist_color = "#aaaaaa" if theme == "dark" else "#666666"
        style = f"color:{color};background:transparent;border:none;"
        self.title.setStyleSheet(f"color:{color};font-size:12px;font-weight:bold;")
        self.artist.setStyleSheet(f"color:{artist_color};font-size:10px;")
        self.prev_btn.setStyleSheet(style)
        self.play_btn.setStyleSheet(style)
        self.next_btn.setStyleSheet(style)
        self.vol_down_btn.setStyleSheet(style)
        self.vol_up_btn.setStyleSheet(style)
        self.mic_btn.setStyleSheet(style)
