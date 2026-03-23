import winreg

from PySide6.QtCore import QObject, QTimer, Signal


class ThemeManager(QObject):
    theme_changed = Signal(str)

    def __init__(self):
        super().__init__()
        self._current_theme = self.get_system_theme()
        self._timer = QTimer(self)
        self._timer.setInterval(2500)
        self._timer.timeout.connect(self.poll_theme)
        self._timer.start()

    def get_system_theme(self) -> str:
        try:
            key = winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize",
            )
            value, _ = winreg.QueryValueEx(key, "AppsUseLightTheme")
            winreg.CloseKey(key)
            return "light" if value == 1 else "dark"
        except Exception:
            return "dark"

    def poll_theme(self) -> None:
        value = self.get_system_theme()
        if value != self._current_theme:
            self._current_theme = value
            self.theme_changed.emit(value)

    def set_theme(self, value: str) -> None:
        if value in {"light", "dark"} and value != self._current_theme:
            self._current_theme = value
            self.theme_changed.emit(value)

    @property
    def current_theme(self) -> str:
        return self._current_theme


theme_manager = ThemeManager()
