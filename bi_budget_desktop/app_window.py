from PySide6.QtWidgets import (
    QWidget,
    QMainWindow,
    QVBoxLayout,
    QLabel,
    QListWidget,
    QHBoxLayout,
)
from PySide6.QtCore import Qt, QTimer

from .screens.expenses_screen import ExpensesScreen
from .screens.pay_schedule_screen import PayScheduleScreen
from .screens.budget_screen import BudgetScreen
from .screens.settings_screen import SettingsScreen
from .screens.philosophy_screen import PhilosophyScreen
from .screens.timeline_screen import TimelineScreen
from .screens.dashboard_screen import DashboardScreen

# -------------------------
# DEBUG OVERLAY IMPORTS
# -------------------------
import bi_budget_desktop.app_flags as app_flags
from .debug_overlay import DebugOverlay
from datetime import date
from .forecast import find_earliest_three_check_cutoff, simulate_hold_back


class AppWindow(QMainWindow):
    def __init__(self, app_ref, debug_overlay):
        super().__init__()
        self.debug_overlay = debug_overlay

        from PySide6.QtGui import QIcon
        from .app_paths import app_root

        icon_path = app_root() / "icons" / "money.png"
        self.setWindowIcon(QIcon(str(icon_path)))

        self.app_ref = app_ref

        self.setWindowTitle("Bi-Budget Desktop")
        self.setMinimumSize(1200, 1000)
        self.resize(1200, 1000)

        container = QWidget()
        self.setCentralWidget(container)

        layout = QHBoxLayout(container)

        # -------------------------
        # SIDEBAR
        # -------------------------
        self.sidebar = QListWidget()
        self.sidebar.setFixedWidth(200)
        self.sidebar.setStyleSheet("""
            QListWidget { font-size: 18px; padding: 6px; }
            QListWidget::item { padding: 8px; }
        """)

        self.sidebar.addItem("Dashboard")
        self.sidebar.addItem("Timeline")
        self.sidebar.addItem("Expenses")
        self.sidebar.addItem("Income")
        self.sidebar.addItem("Savings")
        self.sidebar.addItem("Settings")
        self.sidebar.addItem("Philosophy")

        layout.addWidget(self.sidebar)

        # -------------------------
        # CONTENT AREA
        # -------------------------
        self.content = QWidget()
        self.content_layout = QVBoxLayout(self.content)
        layout.addWidget(self.content)

        self.sidebar.currentRowChanged.connect(self._safe_switch_screen)
        QTimer.singleShot(0, lambda: self.sidebar.setCurrentRow(0))

        # -------------------------
        # DEBUG OVERLAY SETUP
        # -------------------------
        if self.debug_overlay:
            self._position_debug_overlay()
            self.debug_overlay.show()
            self.debug_overlay.log("Debug overlay attached to AppWindow")
            self.update_debug_overlay()


    # -------------------------
    # POSITION OVERLAY
    # -------------------------
    def _position_debug_overlay(self):
        if self.debug_overlay:
            self.debug_overlay.move(self.x() + 10, self.y() + 10)

    # -------------------------
    # CLEAR CONTENT
    # -------------------------
    def clear_content(self):
        if self.debug_overlay:
            self.debug_overlay.log("Clearing content area")

        while self.content_layout.count():
            item = self.content_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.setParent(None)
                widget.deleteLater()
                continue
            layout = item.layout()
            if layout:
                self._clear_layout_recursive(layout)

    def _clear_layout_recursive(self, layout):
        while layout.count():
            child = layout.takeAt(0)
            if child.widget():
                child.widget().setParent(None)
                child.widget().deleteLater()
            elif child.layout():
                self._clear_layout_recursive(child.layout())
        layout.setParent(None)

    def _safe_switch_screen(self, index):
        if getattr(self, "_last_index", None) == index:
            return

        if self.debug_overlay:
            self.debug_overlay.log(f"Sidebar clicked → index {index}")

        self._last_index = index
        self.switch_screen(index)

    # -------------------------
    # SIDEBAR SWITCH
    # -------------------------
    def switch_screen(self, index):
        screen_names = [
            "Dashboard", "Timeline", "Expenses",
            "Income", "Savings", "Settings", "Philosophy"
        ]

        if self.debug_overlay:
            self.debug_overlay.log(f"Switching screen → {screen_names[index]}")

        if index == 0:
            self.show_dashboard()
        elif index == 1:
            self.show_timeline()
        elif index == 2:
            self.show_expenses()
        elif index == 3:
            self.show_pay_schedule()
        elif index == 4:
            self.show_budgets()
        elif index == 5:
            self.show_settings()
        elif index == 6:
            self.show_philosophy()

    # -------------------------
    # SCREENS
    # -------------------------
    def show_dashboard(self):
        self.clear_content()
        self.content_layout.addWidget(DashboardScreen())
        self.update_debug_overlay()

    def show_timeline(self):
        self.clear_content()
        self.content_layout.addWidget(TimelineScreen())
        self.update_debug_overlay()

    def show_expenses(self):
        self.clear_content()
        self.content_layout.addWidget(ExpensesScreen())
        self.update_debug_overlay()

    def show_pay_schedule(self):
        self.clear_content()
        self.content_layout.addWidget(PayScheduleScreen())
        self.update_debug_overlay()

    def show_budgets(self):
        self.clear_content()
        self.content_layout.addWidget(BudgetScreen())
        self.update_debug_overlay()

    def show_settings(self):
        self.clear_content()
        self.content_layout.addWidget(SettingsScreen(self.app_ref))
        self.update_debug_overlay()

    def show_philosophy(self):
        self.clear_content()
        self.content_layout.addWidget(PhilosophyScreen())
        self.update_debug_overlay()

    # -------------------------
    # DEBUG OVERLAY UPDATE
    # -------------------------
    def update_debug_overlay(self):
        if not self.debug_overlay:
            return

        today = date.today()

        try:
            cutoff = find_earliest_three_check_cutoff(today)
            hold_back = simulate_hold_back(today)

            if self.debug_overlay:
                self.debug_overlay.log("Forecast calculations updated")

        except Exception as e:
            cutoff = "ERR"
            hold_back = f"ERR: {e}"
            if self.debug_overlay:
                self.debug_overlay.log(f"Forecast error: {e}")

        text = (
            "DEBUG MODE\n"
            f"Today: {today}\n"
            f"Cutoff (3rd paycheck): {cutoff}\n"
            f"Hold Back Needed: {hold_back}\n"
            f"Active Screen Index: {self._last_index if hasattr(self, '_last_index') else 'None'}\n"
        )

        self.debug_overlay.update_text(text)

    # -------------------------
    # KEEP OVERLAY IN PLACE
    # -------------------------
    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self.debug_overlay:
            self.debug_overlay.log(f"Window resized → {self.width()}x{self.height()}")
        self._position_debug_overlay()

    def moveEvent(self, event):
        super().moveEvent(event)
        if self.debug_overlay:
            self.debug_overlay.log(f"Window moved → ({self.x()}, {self.y()})")
        self._position_debug_overlay()
