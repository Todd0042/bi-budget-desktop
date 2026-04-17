from PySide6.QtWidgets import (
    QWidget, QMainWindow, QVBoxLayout, QLabel,
    QListWidget, QHBoxLayout
)
from PySide6.QtCore import Qt

from .screens.expenses_screen import ExpensesScreen
from .screens.pay_schedule_screen import PayScheduleScreen
from .screens.budget_screen import BudgetScreen
from .screens.settings_screen import SettingsScreen
from .screens.philosophy_screen import PhilosophyScreen


from .database import load_savings_balance


class AppWindow(QMainWindow):
    def __init__(self, app_ref):
        super().__init__()
        self.app_ref = app_ref

        self.setWindowTitle("Bi-Budget Desktop")
        self.setMinimumSize(900, 600)
        self.resize(900, 1000)

        # Main container
        container = QWidget()
        self.setCentralWidget(container)

        layout = QHBoxLayout(container)

        # -------------------------
        # Sidebar
        # -------------------------
        self.sidebar = QListWidget()
        self.sidebar.setFixedWidth(200)
        self.sidebar.setStyleSheet("""
            QListWidget {
                font-size: 18px;
                padding: 6px;
            }
            QListWidget::item {
                padding: 8px;
            }
        """)

        self.sidebar.addItem("Dashboard")
        self.sidebar.addItem("Expenses")
        self.sidebar.addItem("Pay Schedule")
        self.sidebar.addItem("Budgets")
        self.sidebar.addItem("Settings")
        self.sidebar.addItem("Philosophy")

        self.sidebar.setCurrentRow(0)

        self.sidebar.currentRowChanged.connect(self.switch_screen)

        # -------------------------
        # Content area
        # -------------------------
        self.content = QWidget()
        self.content_layout = QVBoxLayout(self.content)

        layout.addWidget(self.sidebar)
        layout.addWidget(self.content)

        # Load initial screen
        self.show_dashboard()

    # ---------------------------------------------------------
    # Utility: clear content area
    # ---------------------------------------------------------
    def clear_content(self):
        while self.content_layout.count():
            item = self.content_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()

    # ---------------------------------------------------------
    # Sidebar navigation
    # ---------------------------------------------------------
    def switch_screen(self, index):
        if index == 0:
            self.show_dashboard()
        elif index == 1:
            self.show_expenses()
        elif index == 2:
            self.show_pay_schedule()
        elif index == 3:
            self.show_budgets()
        elif index == 4:
            self.show_settings()
        elif index == 5:  # whatever index it lands on
            self.show_philosophy()


    # ---------------------------------------------------------
    # Dashboard (FIXED — no duplicated upcoming paydays)
    # ---------------------------------------------------------
    def show_dashboard(self):
        from .forecast import (
            calculate_income_windows,
            calculate_combined_forecast,
            find_next_three_check_month,
        )

        self.clear_content()

        # Savings balance
        savings = load_savings_balance()
        savings_label = QLabel(f"Savings Balance: ${savings:,.2f}")
        savings_label.setStyleSheet("font-size: 20px; font-weight: bold; margin-bottom: 15px;")
        self.content_layout.addWidget(savings_label)

        title = QLabel("Dashboard")
        title.setStyleSheet("font-size: 22px; font-weight: bold; margin-bottom: 10px;")
        self.content_layout.addWidget(title)

        income_windows = calculate_income_windows()
        combined = calculate_combined_forecast()
        three = find_next_three_check_month()

        # -----------------------------------------------------
        # PER-INCOME BLOCKS (NO UPCOMING PAYDAYS HERE)
        # -----------------------------------------------------
        for idx, w in enumerate(income_windows, start=1):

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
                f"Window: {w.window_start} → {w.window_end}<br>"
                f"Expenses in This Window: ${w.total_expenses:,.2f}<br>"
                f"Hold Back Needed: ${w.hold_back:,.2f}"
                f"{three_text}<br><br>"
            )
            block.setStyleSheet("font-size: 15px; margin-bottom: 15px;")
            self.content_layout.addWidget(block)

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
        self.content_layout.addWidget(combined_label)

        # -----------------------------------------------------
        # UPCOMING PAY DAYS (ONLY ONCE, AT THE BOTTOM)
        # -----------------------------------------------------
        if income_windows:
            upcoming_title = QLabel("<b>Upcoming Pay Days</b>")
            upcoming_title.setStyleSheet("font-size: 16px; margin-top: 20px;")
            self.content_layout.addWidget(upcoming_title)

            lines = []
            for idx, w in enumerate(income_windows, start=1):
                lines.append(
                    f"Income Source #{idx}: {w.next_pay} — ${w.amount:,.2f}"
                )

            upcoming_label = QLabel("<br>".join(lines))
            upcoming_label.setStyleSheet("font-size: 14px;")
            self.content_layout.addWidget(upcoming_label)

    # ---------------------------------------------------------
    # Expenses
    # ---------------------------------------------------------
    def show_expenses(self):
        self.clear_content()
        self.content_layout.addWidget(ExpensesScreen())

    # ---------------------------------------------------------
    # Pay Schedule
    # ---------------------------------------------------------
    def show_pay_schedule(self):
        self.clear_content()
        self.content_layout.addWidget(PayScheduleScreen())

    # ---------------------------------------------------------
    # Budgets
    # ---------------------------------------------------------
    def show_budgets(self):
        self.clear_content()
        self.content_layout.addWidget(BudgetScreen())

    # ---------------------------------------------------------
    # Settings
    # ---------------------------------------------------------
    def show_settings(self):
        self.clear_content()
        self.content_layout.addWidget(SettingsScreen(self.app_ref))

    def show_philosophy(self):
        self.clear_content()
        self.content_layout.addWidget(PhilosophyScreen())
