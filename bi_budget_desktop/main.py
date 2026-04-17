from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QPalette, QColor
from PySide6.QtCore import Qt

from .database import init_db, load_setting_theme
from .app_window import AppWindow


import os
from PySide6.QtWidgets import QApplication

from .database import init_db, load_setting_theme
from .app_window import AppWindow


def apply_theme(app, theme_name):
    """
    Loads a QSS theme if available.
    Falls back to Fusion Light/Dark/System if no QSS file exists.
    """

    theme_path = os.path.join(os.path.dirname(__file__), "themes", f"{theme_name}.qss")

    # If a QSS file exists, load it
    if os.path.exists(theme_path):
        with open(theme_path, "r") as f:
            app.setStyleSheet(f.read())
        return

    # Otherwise fallback to Fusion palette
    from PySide6.QtGui import QPalette, QColor
    from PySide6.QtCore import Qt

    app.setStyle("Fusion")

    if theme_name == "dark":
        palette = QPalette()
        palette.setColor(QPalette.Window, QColor(53, 53, 53))
        palette.setColor(QPalette.WindowText, Qt.white)
        palette.setColor(QPalette.Base, QColor(35, 35, 35))
        palette.setColor(QPalette.AlternateBase, QColor(53, 53, 53))
        palette.setColor(QPalette.Text, Qt.white)
        palette.setColor(QPalette.Button, QColor(53, 53, 53))
        palette.setColor(QPalette.ButtonText, Qt.white)
        palette.setColor(QPalette.Highlight, QColor(142, 45, 197))
        palette.setColor(QPalette.HighlightedText, Qt.black)
        app.setPalette(palette)

    elif theme_name == "light":
        palette = app.style().standardPalette()
        app.setPalette(palette)

    else:
        # system default
        palette = app.style().standardPalette()
        app.setPalette(palette)

def main():
    init_db()

    app = QApplication([])

    # Attach theme function to the app instance
    app.apply_theme = lambda name: apply_theme(app, name)

    theme = load_setting_theme()
    apply_theme(app, theme)

    window = AppWindow(app)
    window.show()

    app.exec()
