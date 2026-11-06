from pathlib import Path

import PyInstaller.__main__


def build():
    root = Path(__file__).resolve().parent
    params = [
        str(root / "DynamicIsland.spec"),
        "--noconfirm",
        "--clean",
    ]
    PyInstaller.__main__.run(params)


if __name__ == "__main__":
    build()
