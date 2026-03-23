import os
import sys

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

from src.ui.island_window import DynamicIslandWindow


def main() -> int:
    if sys.stdin is None:
        sys.stdin = open(os.devnull, "r")
    if sys.stdout is None:
        sys.stdout = open(os.devnull, "w")
    if sys.stderr is None:
        sys.stderr = open(os.devnull, "w")
    QApplication.setHighDpiScaleFactorRoundingPolicy(Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)
    app = QApplication(sys.argv)
    window = DynamicIslandWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
