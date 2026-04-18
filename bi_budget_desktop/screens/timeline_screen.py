from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QTableWidget, QTableWidgetItem,
    QCheckBox, QHeaderView
)
from PySide6.QtCore import Qt
from datetime import date, timedelta

from ..database import (
    get_income_sources,
    get_expense_payment,
    set_expense_payment
)

from ..utils import (
    _biweekly_next_pay,
    _generate_biweekly_schedule,
    _expand_monthly_expenses_until
)


class TimelineScreen(QWidget):
    def __init__(self):
        super().__init__()

        layout = QVBoxLayout(self)

        title = QLabel("Timeline")
        title.setStyleSheet("font-size: 22px; font-weight: bold; margin-bottom: 10px;")
        layout.addWidget(title)

        self.table = QTableWidget()
        self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels(["Date", "Name", "Amount", "Paid"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        layout.addWidget(self.table)

        self.refresh_timeline()

    # ------------------------------------------------------------
    # MAIN TIMELINE LOGIC
    # ------------------------------------------------------------
    def refresh_timeline(self):
        today = date.today()

        # ------------------------------------------------------------
        # 1. Determine the most recent paycheck BEFORE today
        # ------------------------------------------------------------
        incomes = get_income_sources()
        most_recent_paycheck = None

        for income_id, amount, frequency, start_str, planned_savings in incomes:
            start_date = date.fromisoformat(start_str)

            first = _biweekly_next_pay(start_date, today - timedelta(days=60))
            paydates = _generate_biweekly_schedule(first, today + timedelta(days=60))

            past = [d for d in paydates if d <= today]
            if past:
                last_pay = max(past)
                if most_recent_paycheck is None or last_pay > most_recent_paycheck:
                    most_recent_paycheck = last_pay

        if most_recent_paycheck is None:
            return

        # ------------------------------------------------------------
        # 2. Determine the paycheck AFTER one month from today
        # ------------------------------------------------------------
        one_month_later = today + timedelta(days=30)
        next_pay_after_month = None

        for income_id, amount, frequency, start_str, planned_savings in incomes:
            start_date = date.fromisoformat(start_str)

            first = _biweekly_next_pay(start_date, today - timedelta(days=60))
            paydates = _generate_biweekly_schedule(first, today + timedelta(days=90))

            future = [d for d in paydates if d >= one_month_later]
            if future:
                next_pay = min(future)
                if next_pay_after_month is None or next_pay < next_pay_after_month:
                    next_pay_after_month = next_pay

        if next_pay_after_month is None:
            return

        # ------------------------------------------------------------
        # 3. Expand all expenses in the date range
        # ------------------------------------------------------------
        expanded = _expand_monthly_expenses_until(
            most_recent_paycheck,
            next_pay_after_month
        )

        # ------------------------------------------------------------
        # 4. Populate the table
        # ------------------------------------------------------------
        self.table.clear()
        self.table.setRowCount(len(expanded))
        self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels(["Date", "Name", "Amount", "Paid"])

        for row_index, (exp_id, name, amount, due_date) in enumerate(expanded):

            # Date
            self.table.setItem(
                row_index, 0,
                QTableWidgetItem(due_date.strftime("%Y-%m-%d"))
            )

            # Name
            self.table.setItem(row_index, 1, QTableWidgetItem(name))

            # Amount
            amt_item = QTableWidgetItem(f"${amount:.2f}")
            amt_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            self.table.setItem(row_index, 2, amt_item)

            # Paid checkbox
            paid = get_expense_payment(exp_id, due_date.isoformat())
            checkbox = QCheckBox()
            checkbox.setChecked(bool(paid))
            checkbox.stateChanged.connect(
                lambda state, e_id=exp_id, d=due_date:
                    self.toggle_paid(e_id, d, state)
            )
            self.table.setCellWidget(row_index, 3, checkbox)

        # ------------------------------------------------------------
        # 5. Make the "Paid" column narrow
        # ------------------------------------------------------------
        paid_col = self.table.columnCount() - 1
        self.table.setColumnWidth(paid_col, 55)

    # ------------------------------------------------------------
    # TOGGLE PAID STATE
    # ------------------------------------------------------------
    def toggle_paid(self, expense_id, due_date, state):
        set_expense_payment(expense_id, due_date.isoformat(), bool(state))
