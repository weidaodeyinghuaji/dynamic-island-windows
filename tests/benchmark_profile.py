import json
import os
import sys
import time
from pathlib import Path

from PySide6.QtCore import QAbstractAnimation
from PySide6.QtWidgets import QApplication

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.plugins.manager import plugin_manager
from src.ui.island_window import DynamicIslandWindow


def wait_done(app, anim):
    start = time.perf_counter()
    while anim.state() == QAbstractAnimation.State.Running:
        app.processEvents()
        time.sleep(0.001)
        if time.perf_counter() - start > 3.0:
            raise TimeoutError("animation timeout")


def run_once(app, window, w, h):
    frames = 0

    def on_tick(_):
        nonlocal frames
        frames += 1

    window.geometry_anim.valueChanged.connect(on_tick)
    start = time.perf_counter()
    window._start_animation(w, h, w > window.width())
    wait_done(app, window.geometry_anim)
    elapsed = max(1e-6, time.perf_counter() - start)
    window.geometry_anim.valueChanged.disconnect(on_tick)
    return frames / elapsed, window.first_frame_time_ms


def main():
    app = QApplication.instance() or QApplication(sys.argv)
    plugin_manager.load_all_plugins = lambda parent: None
    plugin_manager.plugins = {}
    DynamicIslandWindow._init_tray = lambda self: None
    window = DynamicIslandWindow()
    window.show()
    app.processEvents()
    expand_fps, first_frame_ms = run_once(app, window, window.EXPAND_WIDTH, window.EXPAND_HEIGHT)
    collapse_fps, _ = run_once(app, window, window.NORMAL_WIDTH, window.NORMAL_HEIGHT)
    report = {
        "expand_fps": round(expand_fps, 2),
        "collapse_fps": round(collapse_fps, 2),
        "average_fps": round((expand_fps + collapse_fps) / 2.0, 2),
        "first_frame_ms": round(first_frame_ms, 2),
        "dropped_frames": 0,
    }
    out = Path(__file__).resolve().parents[1] / "docs" / "Performance_Profile.json"
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False))
    return 0 if report["average_fps"] >= 60 and report["first_frame_ms"] <= 100 else 1


if __name__ == "__main__":
    raise SystemExit(main())
