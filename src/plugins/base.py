from PySide6.QtWidgets import QWidget


class IslandPlugin(QWidget):
    plugin_name = "base"

    def on_expand(self) -> None:
        pass

    def on_collapse(self) -> None:
        pass

    def on_theme_changed(self, theme: str) -> None:
        pass
