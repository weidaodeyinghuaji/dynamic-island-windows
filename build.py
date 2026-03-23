from pathlib import Path

import PyInstaller.__main__


def build():
    root = Path(__file__).resolve().parent
    main_script = str(root / "src" / "main.py")
    params = [
        main_script,
        "--name=DynamicIsland",
        "--windowed",
        "--noconfirm",
        "--clean",
        "--onefile",
        "--add-data=plugins;plugins",
        "--hidden-import=psutil",
    ]
    PyInstaller.__main__.run(params)


if __name__ == "__main__":
    build()
