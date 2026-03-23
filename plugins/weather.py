from __future__ import annotations

import json
import threading
import time
from urllib.parse import urlencode
from urllib.request import urlopen

from PySide6.QtCore import Signal, Qt, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import QHBoxLayout, QLabel

from src.plugins.base import IslandPlugin


class WeatherPlugin(IslandPlugin):
    plugin_name = "weather"
    weather_updated = Signal(str, str, str, str)

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)
        self.icon = QLabel("🌤", self)
        self.label = QLabel("加载天气中...", self)
        self.label.setSizePolicy(self.label.sizePolicy().Policy.Minimum, self.label.sizePolicy().Policy.Fixed)
        self.aqi = QLabel("AQI --", self)
        self.icon.setCursor(Qt.CursorShape.PointingHandCursor)
        self.label.setCursor(Qt.CursorShape.PointingHandCursor)
        self.aqi.setCursor(Qt.CursorShape.PointingHandCursor)
        layout.addWidget(self.icon)
        layout.addWidget(self.label)
        layout.addWidget(self.aqi)
        self._latest_city = ""
        self._refresh_lock = threading.Lock()
        self._refreshing = False
        self._last_refresh_at = 0.0
        self._refresh_interval_sec = 90.0
        self.weather_updated.connect(self._apply_weather)
        self.icon.mousePressEvent = self._open_weather_app
        self.label.mousePressEvent = self._open_weather_app
        self.aqi.mousePressEvent = self._open_weather_app
        self.on_theme_changed("dark")

    def refresh(self) -> None:
        self.refresh_async(force=True)

    def refresh_async(self, force: bool = False) -> None:
        if not force and (time.monotonic() - self._last_refresh_at) < self._refresh_interval_sec:
            return
        with self._refresh_lock:
            if self._refreshing:
                return
            self._refreshing = True
        worker = threading.Thread(target=self._refresh_worker, daemon=True)
        worker.start()

    def _refresh_worker(self) -> None:
        try:
            geo_data = self._fetch_json("https://ipapi.co/json/")
            lat = float(geo_data.get("latitude", 39.9))
            lon = float(geo_data.get("longitude", 116.4))
            city = str(geo_data.get("city", "")).strip()
            weather_qs = urlencode(
                {
                    "latitude": lat,
                    "longitude": lon,
                    "current": "temperature_2m,weather_code",
                    "timezone": "auto",
                }
            )
            aqi_qs = urlencode({"latitude": lat, "longitude": lon, "current": "us_aqi", "timezone": "auto"})
            weather_data = self._fetch_json(f"https://api.open-meteo.com/v1/forecast?{weather_qs}")
            aqi_data = self._fetch_json(f"https://air-quality-api.open-meteo.com/v1/air-quality?{aqi_qs}")
            current = weather_data.get("current", {})
            weather_code = int(current.get("weather_code", 0))
            temp = round(float(current.get("temperature_2m", 0.0)))
            aqi_value = int(round(float(aqi_data.get("current", {}).get("us_aqi", 0))))
            icon = self._weather_icon(weather_code)
            city_prefix = f"{city} " if city else ""
            self.weather_updated.emit(icon, f"{city_prefix}{temp}°C", f"AQI {aqi_value}", city)
        except Exception:
            self.weather_updated.emit("🌥", "天气获取失败", "AQI --", "")

    def _apply_weather(self, icon: str, label: str, aqi: str, city: str) -> None:
        self._latest_city = city
        self.icon.setText(icon)
        self.label.setText(label)
        self.aqi.setText(aqi)
        self._last_refresh_at = time.monotonic()
        with self._refresh_lock:
            self._refreshing = False

    @staticmethod
    def _fetch_json(url: str) -> dict:
        with urlopen(url, timeout=0.8) as resp:
            payload = resp.read().decode("utf-8", errors="ignore")
        data = json.loads(payload)
        return data if isinstance(data, dict) else {}

    @staticmethod
    def _weather_icon(code: int) -> str:
        if code in (0, 1):
            return "☀️"
        if code in (2, 3):
            return "⛅"
        if code in (45, 48):
            return "🌫"
        if code in (51, 53, 55, 61, 63, 65, 80, 81, 82):
            return "🌧"
        if code in (71, 73, 75, 77, 85, 86):
            return "❄️"
        if code in (95, 96, 99):
            return "⛈"
        return "🌥"

    def _open_weather_app(self, _) -> None:
        if not QDesktopServices.openUrl(QUrl("msnweather:")):
            QDesktopServices.openUrl(QUrl("https://www.msn.com/weather"))

    def on_expand(self) -> None:
        self.show()
        self.refresh_async()

    def on_collapse(self) -> None:
        self.hide()

    def on_theme_changed(self, theme: str) -> None:
        color = "#f4f4f4" if theme == "dark" else "#1a1a1a"
        self.icon.setStyleSheet(f"font-size:13px;color:{color};")
        self.label.setStyleSheet(f"color:{color};font-size:12px;")
        self.aqi.setStyleSheet("color:#ff9f0a;font-size:11px;padding:2px 6px;background:rgba(255,159,10,0.15);border-radius:6px;")
