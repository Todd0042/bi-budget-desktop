from PySide6.QtWidgets import (
    QWidget,
    QMainWindow,
    QVBoxLayout,
    QLabel,
    QListWidget,
    QHBoxLayout,
    QGridLayout,
    QSizePolicy,
)
from PySide6.QtCore import Qt, QTimer

from .screens.expenses_screen import ExpensesScreen
from .screens.pay_schedule_screen import PayScheduleScreen
from .screens.budget_screen import BudgetScreen
from .screens.settings_screen import SettingsScreen
from .screens.philosophy_screen import PhilosophyScreen
from .screens.timeline_screen import TimelineScreen   # ← NEW IMPORT

from .database import load_savings_balance

# IMPORTANT: import forecast functions at top so they stay fresh
from .forecast import (
    calculate_income_windows,
    calculate_combined_forecast,
    find_next_three_check_month_for_income,
)


class AppWindow(QMainWindow):
    def __init__(self, app_ref):
        super().__init__()
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
        self.sidebar.setStyleSheet(
            """
            QListWidget {
                font-size: 18px;
                padding: 6px;
            }
            QListWidget::item {
                padding: 8px;
            }
        """
        )

        self.sidebar.addItem("Dashboard")
        self.sidebar.addItem("Timeline")   # ← NEW
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

        # Connect AFTER layout is ready
        self.sidebar.currentRowChanged.connect(self._safe_switch_screen)

        # -------------------------
        # FIX: Delay initial dashboard load
        # -------------------------
        QTimer.singleShot(0, lambda: self.sidebar.setCurrentRow(0))


    # -------------------------
    # CLEAR CONTENT
    # -------------------------
    def clear_content(self):
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
        self._last_index = index
        self.switch_screen(index)

    # -------------------------
    # SIDEBAR SWITCH
    # -------------------------
    def switch_screen(self, index):
        if index == 0:
            self.show_dashboard()
        elif index == 1:
            self.show_timeline()       # ← NEW
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
    # DASHBOARD
    # -------------------------
    def show_dashboard(self):
        self.clear_content()

        from .database import debug_print_income_sources
        debug_print_income_sources()

        savings = load_savings_balance()
        savings_label = QLabel(f"Savings Balance: ${savings:,.2f}")
        savings_label.setStyleSheet("font-size: 20px; font-weight: bold; margin-bottom: 15px;")
        savings_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.content_layout.addWidget(savings_label)

        title = QLabel("Dashboard")
        title.setStyleSheet("font-size: 22px; font-weight: bold; margin-bottom: 10px;")
        title.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.content_layout.addWidget(title)

        # ALWAYS recalc forecast fresh
        income_windows = calculate_income_windows()
        combined = calculate_combined_forecast()

        # -----------------------------------------------------
        # INCOME BLOCKS GRID
        # -----------------------------------------------------
        grid = QGridLayout()
        grid.setSpacing(15)

        for idx, w in enumerate(income_windows, start=1):
            three = find_next_three_check_month_for_income(w.start_date)

            three_text = ""
            if three:
                dates_str = "<br>".join(str(d) for d in three.pay_dates)
                three_text = (
                    f"<br><b>Next 3‑Check Month:</b> {three.month}/{three.year}<br>"
                    f"Pay Dates:<br>{dates_str}"
                )

            block = QLabel(
                f"<b>Income Source #{idx}</b><br>"
                f"Next Pay Date: {w.next_pay} (Amount: ${w.amount:,.2f})<br>"
                f"Window: {w.window_start} → {w.window_end}<br><br>"
                f"Expense Breakdown:<br>"
                f"  Per‑Check Expense Allocation: ${w.per_check_expense_allocation:,.2f}<br>"
                f"  Expenses in This Window: ${w.total_expenses:,.2f}<br>"
                f"  Hold Back Needed: ${w.hold_back:,.2f}<br>"
                f"{three_text}<br><br>"
            )
            block.setStyleSheet("font-size: 15px; margin-bottom: 5px; white-space: pre-wrap;")
            block.setTextInteractionFlags(Qt.TextSelectableByMouse)
            block.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Maximum)

            row = (idx - 1) // 2
            col = (idx - 1) % 2
            grid.addWidget(block, row, col)

        if income_windows:
            self.content_layout.addLayout(grid)

        # -----------------------------------------------------
        # COMBINED FORECAST
        # -----------------------------------------------------
        combined_label = QLabel(
            f"<b>Combined Income & Expenses</b><br>"
            f"From {combined.start_date} to {combined.end_date}<br><br>"
            f"Total Income (all checks): ${combined.total_income:,.2f}<br>"
            f"Total Expenses (all windows): ${combined.total_expenses:,.2f}<br>"
            f"Average Spending (per paycheck): ${combined.average_spending:,.2f}<br>"
            f"Planned Savings (per paycheck): ${combined.planned_savings:,.2f}<br>"
            f"Total Hold Back (all windows): ${combined.total_hold_back:,.2f}<br><br>"
            f"Safe to Spend (after expenses, avg spending, savings): ${combined.safe_to_spend:,.2f}<br>"
        )
        combined_label.setStyleSheet("font-size: 16px; margin-top: 20px;")
        combined_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.content_layout.addWidget(combined_label)

        # -----------------------------------------------------
        # UPCOMING PAY DAYS
        # -----------------------------------------------------
        if income_windows:
            upcoming_title = QLabel("<b>Upcoming Pay Days</b>")
            upcoming_title.setStyleSheet("font-size: 16px; margin-top: 20px;")
            upcoming_title.setTextInteractionFlags(Qt.TextSelectableByMouse)
            self.content_layout.addWidget(upcoming_title)

            lines = [
                f"Income Source #{idx}: {w.next_pay} — ${w.amount:,.2f}"
                for idx, w in enumerate(income_windows, start=1)
            ]

            upcoming_label = QLabel("<br>".join(lines))
            upcoming_label.setStyleSheet("font-size: 14px;")
            upcoming_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
            self.content_layout.addWidget(upcoming_label)

    # -------------------------
    # OTHER SCREENS
    # -------------------------
    def show_timeline(self):   # ← NEW
        self.clear_content()
        self.content_layout.addWidget(TimelineScreen())

    def show_expenses(self):
        self.clear_content()
        self.content_layout.addWidget(ExpensesScreen())

    def show_pay_schedule(self):
        self.clear_content()
        self.content_layout.addWidget(PayScheduleScreen())

    def show_budgets(self):
        self.clear_content()
        self.content_layout.addWidget(BudgetScreen())

    def show_settings(self):
        self.clear_content()
        self.content_layout.addWidget(SettingsScreen(self.app_ref))

    def show_philosophy(self):
        self.clear_content()
        self.content_layout.addWidget(PhilosophyScreen())
