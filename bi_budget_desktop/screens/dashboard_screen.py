# dashboard_screen.py

from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel, QGridLayout, QSizePolicy
from PySide6.QtCore import Qt

from ..database import load_savings_balance
from ..forecast import (
    calculate_income_windows,
    calculate_combined_forecast,
    find_three_check_month_for_income,
)
from ..signals import signals


class DashboardScreen(QWidget):
    def __init__(self):
        super().__init__()

        self.layout_root = QVBoxLayout(self)
        signals.data_changed.connect(self.refresh)

        self.refresh()

    def refresh(self):
        # Clear layout
        while self.layout_root.count():
            item = self.layout_root.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()

        layout = self.layout_root

        # Savings balance
        savings = load_savings_balance()
        savings_label = QLabel(f"Savings Balance: ${savings:,.2f}")
        savings_label.setStyleSheet("font-size: 20px; font-weight: bold; margin-bottom: 15px;")
        savings_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        layout.addWidget(savings_label)

        # Title
        title = QLabel("Dashboard")
        title.setStyleSheet("font-size: 22px; font-weight: bold; margin-bottom: 10px;")
        title.setTextInteractionFlags(Qt.TextSelectableByMouse)
        layout.addWidget(title)

        # Forecast
        income_windows = calculate_income_windows()
        combined = calculate_combined_forecast()

        # -----------------------------------------------------
        # INCOME BLOCKS GRID
        # -----------------------------------------------------
        grid = QGridLayout()
        grid.setSpacing(15)

        for idx, w in enumerate(income_windows, start=1):
            name = (w.name or "").strip()
            display_name = name if name else f"Income Source #{idx}"

            # Per-income 3-check month
            three = find_three_check_month_for_income(
                w.window_start,  # start_date is embedded in forecast logic
                w.window_start
            )

            three_text = ""
            if three:
                dates_str = "<br>".join(str(d) for d in three["paydates"])
                three_text = (
                    f"<br><b>Next 3‑Check Month:</b> {three['month']}/{three['year']}<br>"
                    f"Pay Dates:<br>{dates_str}"
                )

            block = QLabel(
                f"<b>{display_name}</b><br>"
                f"Next Pay Date: {w.next_pay} (Amount: ${w.amount:,.2f})<br>"
                f"Window: {w.window_start} → {w.window_end}<br><br>"
                f"Expense Breakdown:<br>"
                f"  Per‑Check Expense Allocation: ${w.per_check_expense_allocation:,.2f}<br>"
                f"  Expenses in This Window: ${w.total_expenses:,.2f}<br>"
                f"{three_text}<br><br>"
            )
            block.setStyleSheet("font-size: 15px; margin-bottom: 5px; white-space: pre-wrap;")
            block.setTextInteractionFlags(Qt.TextSelectableByMouse)
            block.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Maximum)

            row = (idx - 1) // 2
            col = (idx - 1) % 2
            grid.addWidget(block, row, col)

        if income_windows:
            layout.addLayout(grid)

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
            f"Total Hold Back Needed: ${combined.total_hold_back:,.2f}<br><br>"
            f"Safe to Spend: ${combined.safe_to_spend:,.2f}<br>"
        )
        combined_label.setStyleSheet("font-size: 16px; margin-top: 20px;")
        combined_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        layout.addWidget(combined_label)
