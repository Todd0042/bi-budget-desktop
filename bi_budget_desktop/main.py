import os

from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QPalette, QColor
from PySide6.QtCore import Qt, QThread, Signal

from .database import init_db, load_setting_theme, DB_PATH
from .app_window import AppWindow
from . import sync as syncmod

from bi_budget_desktop.app_paths import app_root

# sync config + sidecar live next to the DB (never sent to the server)
SYNC_CONFIG = os.path.join(os.path.dirname(DB_PATH), "sync_config.json")


class _StartupSync(QThread):
    """Pull-if-newer at launch, off the UI thread so an unreachable server can't hang
    startup. Emits the result; the window reloads only if something was actually pulled."""
    done = Signal(str, str)

    def run(self):
        r = syncmod.sync(DB_PATH, SYNC_CONFIG, on_pulled=init_db, timeout=6)
        self.done.emit(r.get("status", ""), r.get("detail", ""))


def apply_theme(app, theme_name):
    """
    Loads a QSS theme if available.
    Falls back to Fusion Light/Dark/System if no QSS file exists.
    """

    # Build theme path using universal resolver
    theme_path = app_root() / "themes" / f"{theme_name}.qss"

    # If a QSS file exists, load it
    if theme_path.exists():
        try:
            with open(theme_path, "r") as f:
                app.setStyleSheet(f.read())
            return
        except Exception as e:
            print("Failed to load QSS theme:", e)

    # Otherwise fallback to Fusion palette
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

    # Auto pull-if-newer at launch (non-blocking). Reload the current screen on a real pull.
    def _on_synced(status, detail):
        if status in ("pulled", "pulled-conflict"):
            window.reload_current()
        if status not in ("disabled", "in-sync"):
            print(f"[sync] startup: {status} — {detail}")
    window._startup_sync = _StartupSync()          # keep a ref so it isn't GC'd
    window._startup_sync.done.connect(_on_synced)
    window._startup_sync.start()

    app.exec()
