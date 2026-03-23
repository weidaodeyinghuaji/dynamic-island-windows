import psutil
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QHBoxLayout, QLabel

from src.plugins.base import IslandPlugin


class BatteryHealthPlugin(IslandPlugin):
    plugin_name = "battery"

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)
        self.label = QLabel("🔋 --", self)
        self.label.setSizePolicy(self.label.sizePolicy().Policy.Minimum, self.label.sizePolicy().Policy.Fixed)
        self.detail = QLabel("", self)
        self.detail.setVisible(False)
        self._alert_level = 0
        self._theme = "dark"
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.mousePressEvent = self._toggle_detail
        layout.addWidget(self.label)
        layout.addWidget(self.detail)
        self.refresh()
        self.on_theme_changed(self._theme)

    def _format_time(self, sec_left: int) -> str:
        if sec_left in (-2, -1) or sec_left is None:
            return "--"
        hours = sec_left // 3600
        minutes = (sec_left % 3600) // 60
        if hours <= 0:
            return f"{minutes} 分钟"
        return f"{hours} 小时 {minutes} 分钟"

    def refresh(self) -> None:
        battery = psutil.sensors_battery()
        if battery is None:
            self.label.setText("🔋 N/A")
            self.detail.setText("剩余 -- | 健康 -- | 功耗 --")
            return
        percent = int(battery.percent)
        charging = bool(battery.power_plugged)
        icon = "⚡" if charging else "🔋"
        state = "充电中" if charging else "放电中"
        self.label.setText(f"{icon} {percent}%")
        self.detail.setText(f"{state} | 剩余 {self._format_time(int(battery.secsleft))} | 健康 -- | 功耗 --")
        if percent <= 10 and not charging:
            self._alert_level = 2
        elif percent <= 20 and not charging:
            self._alert_level = 1
        else:
            self._alert_level = 0
        self.on_theme_changed(self._theme)

    def _toggle_detail(self, _) -> None:
        self.detail.setVisible(not self.detail.isVisible())

    def on_expand(self) -> None:
        self.refresh()
        self.show()

    def on_collapse(self) -> None:
        self.hide()

    def on_theme_changed(self, theme: str) -> None:
        self._theme = theme
        color = "#f4f4f4" if theme == "dark" else "#1a1a1a"
        if self._alert_level == 2:
            color = "#ff5f57"
        elif self._alert_level == 1:
            color = "#ff9f43"
        self.label.setStyleSheet(f"color:{color};font-size:12px;")
        self.detail.setStyleSheet(f"color:{color};font-size:11px;")
