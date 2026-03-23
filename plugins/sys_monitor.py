from __future__ import annotations

import ctypes
import gc
import subprocess
import time

import psutil
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QHBoxLayout, QLabel, QProgressBar, QPushButton, QVBoxLayout

from src.plugins.base import IslandPlugin
from src.utils.config import config_manager


class SystemMonitorPlugin(IslandPlugin):
    plugin_name = "sys_monitor"

    def __init__(self, parent=None):
        super().__init__(parent)
        thresholds = config_manager.get("performance_thresholds", {}) or {}
        self._cpu_alert = int(thresholds.get("cpu", 85))
        self._mem_alert = int(thresholds.get("memory", 90))
        self._gpu_alert = int(thresholds.get("gpu_temp", 85))
        self._last_alert_at = 0.0
        self._last_gpu_probe_at = 0.0
        self._gpu_temp = -1
        self._gpu_text = "N/A"
        self._timer = QTimer(self)
        self._timer.setInterval(1500)
        self._timer.timeout.connect(self.refresh)
        self._timer.start()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)
        row1 = QHBoxLayout()
        row2 = QHBoxLayout()
        self.cpu_label = QLabel("CPU 0%", self)
        self.mem_label = QLabel("MEM 0%", self)
        for label in (self.cpu_label, self.mem_label):
            label.setSizePolicy(label.sizePolicy().Policy.Minimum, label.sizePolicy().Policy.Fixed)
        self.gpu_label = QLabel("GPU N/A", self)
        self.cpu_bar = QProgressBar(self)
        self.mem_bar = QProgressBar(self)
        self.cpu_bar.setRange(0, 100)
        self.mem_bar.setRange(0, 100)
        self.cpu_bar.setFixedWidth(80)
        self.mem_bar.setFixedWidth(80)
        self.clean_btn = QPushButton("清理", self)
        self.task_btn = QPushButton("任务管理器", self)
        self.clean_btn.clicked.connect(self._clean_memory)
        self.task_btn.clicked.connect(lambda: subprocess.Popen(["taskmgr.exe"], shell=False))
        row1.addWidget(self.cpu_label)
        row1.addWidget(self.cpu_bar)
        row1.addWidget(self.mem_label)
        row1.addWidget(self.mem_bar)
        row1.addWidget(self.gpu_label)
        row2.addWidget(self.clean_btn)
        row2.addWidget(self.task_btn)
        layout.addLayout(row1)
        layout.addLayout(row2)
        self.refresh()
        self.on_theme_changed("dark")

    def _probe_gpu_temp(self) -> tuple[int, str]:
        now = time.monotonic()
        if now - self._last_gpu_probe_at < 8.0:
            return self._gpu_temp, self._gpu_text
        self._last_gpu_probe_at = now
        try:
            temps = psutil.sensors_temperatures(fahrenheit=False) or {}
            values = []
            for name, entries in temps.items():
                if any(k in name.lower() for k in ("gpu", "nv", "nvidia", "radeon", "amdgpu")):
                    for entry in entries:
                        if entry.current is not None:
                            values.append(float(entry.current))
            if values:
                self._gpu_temp = int(round(max(values)))
                self._gpu_text = f"{self._gpu_temp}°C"
            else:
                self._gpu_temp = -1
                self._gpu_text = "N/A"
        except Exception:
            self._gpu_temp = -1
            self._gpu_text = "N/A"
        return self._gpu_temp, self._gpu_text

    def _clean_memory(self) -> None:
        gc.collect()
        try:
            proc = ctypes.windll.kernel32.GetCurrentProcess()
            ctypes.windll.psapi.EmptyWorkingSet(proc)
        except Exception:
            pass
        self.refresh()

    def _notify_alert(self) -> None:
        now = time.monotonic()
        if now - self._last_alert_at < 20.0:
            return
        self._last_alert_at = now
        parent = self.parentWidget()
        if parent and hasattr(parent, "request_expand"):
            parent.request_expand()

    def refresh(self) -> None:
        cpu = int(psutil.cpu_percent(interval=None))
        mem = int(psutil.virtual_memory().percent)
        gpu_temp, gpu_text = self._probe_gpu_temp()
        self.cpu_label.setText(f"CPU {cpu}%")
        self.mem_label.setText(f"MEM {mem}%")
        self.gpu_label.setText(f"GPU {gpu_text}")
        self.cpu_bar.setValue(cpu)
        self.mem_bar.setValue(mem)
        if cpu >= self._cpu_alert or mem >= self._mem_alert or (gpu_temp >= 0 and gpu_temp >= self._gpu_alert):
            self._notify_alert()

    def on_expand(self) -> None:
        self.show()

    def on_collapse(self) -> None:
        self.hide()

    def on_theme_changed(self, theme: str) -> None:
        color = "#f4f4f4" if theme == "dark" else "#1a1a1a"
        bar_bg = "#2a2d35" if theme == "dark" else "#dfe4ed"
        bar_fg = "#4cc2ff" if theme == "dark" else "#2c7be5"
        style = f"QProgressBar{{border:none;background:{bar_bg};border-radius:4px;height:8px;}}QProgressBar::chunk{{background:{bar_fg};border-radius:4px;}}"
        self.cpu_label.setStyleSheet(f"color:{color};font-size:11px;")
        self.mem_label.setStyleSheet(f"color:{color};font-size:11px;")
        self.gpu_label.setStyleSheet(f"color:{color};font-size:11px;")
        self.cpu_bar.setStyleSheet(style)
        self.mem_bar.setStyleSheet(style)
        self.clean_btn.setStyleSheet(f"color:{color};background:transparent;border:1px solid {color};padding:1px 6px;border-radius:6px;")
        self.task_btn.setStyleSheet(f"color:{color};background:transparent;border:1px solid {color};padding:1px 6px;border-radius:6px;")
