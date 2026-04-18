from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QPalette, QColor
from PySide6.QtCore import Qt

from .database import init_db, load_setting_theme
from .app_window import AppWindow
from .app_paths import app_root
import bi_budget_desktop.app_flags as app_flags

# NEW
from .debug_overlay import DebugOverlay
import bi_budget_desktop.database as db


def apply_theme(app, theme_name):
    theme_path = app_root() / "themes" / f"{theme_name}.qss"

    if theme_path.exists():
        try:
            with open(theme_path, "r") as f:
                app.setStyleSheet(f.read())
            return
        except Exception as e:
            print("Failed to load QSS theme:", e)

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

    else:
        palette = app.style().standardPalette()
        app.setPalette(palette)


def launch_app():
    """Called by run.py — this is the real launcher."""

    # ---------------------------------------------------------
    # 1. Create QApplication FIRST (Qt requirement)
    # ---------------------------------------------------------
    app = QApplication([])

    # Attach theme function to the app instance
    app.apply_theme = lambda name: apply_theme(app, name)

    # ---------------------------------------------------------
    # 2. Create DebugOverlay (now safe)
    # ---------------------------------------------------------
    debug_overlay = None

    if app_flags.DEBUG_MODE:
        debug_overlay = DebugOverlay()
        debug_overlay.show()
        debug_overlay.log("Debug overlay created (main.py)")

        # Attach DB logger BEFORE init_db()
        db.DEBUG_LOGGER = debug_overlay
        debug_overlay.log("DB logger attached (main.py)")

    if app_flags.DEBUG_MODE:
        debug_overlay = DebugOverlay()

        # Force initial spawn position BEFORE show()
        debug_overlay.move(0, 0)

        debug_overlay.show()
        debug_overlay.raise_()
        debug_overlay.log("Debug overlay created (main.py)")

        db.DEBUG_LOGGER = debug_overlay

    # ---------------------------------------------------------
    # 3. Now it's safe to initialize the database
    # ---------------------------------------------------------
    init_db()

    # ---------------------------------------------------------
    # 4. Apply theme
    # ---------------------------------------------------------
    theme = load_setting_theme()
    apply_theme(app, theme)

    # ---------------------------------------------------------
    # 5. Create AppWindow and pass overlay
    # ---------------------------------------------------------
    window = AppWindow(app, debug_overlay)
    window.show()

    app.exec()
