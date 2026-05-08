from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QTableWidget, QTableWidgetItem,
    QCheckBox, QHeaderView,
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from datetime import date, timedelta
from dateutil.relativedelta import relativedelta

from ..database import (
    get_income_sources,
    set_expense_payment,
)
from ..forecast import (
    _biweekly_next_pay,
    _generate_biweekly_schedule,
    _expand_all_expenses,
)


class TimelineScreen(QWidget):
    def __init__(self):
        super().__init__()
        self.setLayout(QVBoxLayout())

        title = QLabel("Timeline — Last Paycheck → 3 Months Ahead")
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet("font-size: 20px; font-weight: bold; margin-bottom: 10px;")
        self.layout().addWidget(title)

        self.table = QTableWidget()
        self.table.setColumnCount(5)
        self.table.setHorizontalHeaderLabels(["Paid", "Date", "Type", "Name", "Amount"])
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.Stretch)
        self.table.setColumnWidth(0, 55)
        self.table.setColumnWidth(1, 90)
        self.table.setColumnWidth(2, 80)
        self.table.setColumnWidth(4, 100)
        self.layout().addWidget(self.table)

        self.refresh_timeline()

    def refresh_timeline(self):
        today    = date.today()
        incomes  = get_income_sources()

        # --- most-recent paycheck before today ---
        most_recent = None
        for income_id, amount, frequency, start_str, planned_savings in incomes:
            start     = date.fromisoformat(start_str)
            first     = _biweekly_next_pay(start, today - timedelta(days=90))
            paydates  = _generate_biweekly_schedule(first, today + timedelta(days=90))
            past      = [d for d in paydates if d <= today]
            if past:
                lp = max(past)
                if most_recent is None or lp > most_recent:
                    most_recent = lp

        if most_recent is None:
            self.table.setRowCount(0)
            return

        # --- paycheck just after 3 months from today ---
        three_months_out = today + relativedelta(months=3)
        window_end = None
        for income_id, amount, frequency, start_str, planned_savings in incomes:
            start    = date.fromisoformat(start_str)
            first    = _biweekly_next_pay(start, today)
            paydates = _generate_biweekly_schedule(first, three_months_out + timedelta(days=30))
            future   = [d for d in paydates if d > three_months_out]
            if future:
                np = min(future)
                if window_end is None or np < window_end:
                    window_end = np

        if window_end is None:
            window_end = three_months_out

        # --- build event list ---
        events = []

        # Income events
        for income_id, amount, frequency, start_str, planned_savings in incomes:
            start    = date.fromisoformat(start_str)
            first    = _biweekly_next_pay(start, most_recent)
            paydates = _generate_biweekly_schedule(first, window_end)
            for d in paydates:
                if most_recent <= d <= window_end:
                    events.append({
                        "date":       d,
                        "type":       "Income",
                        "name":       f"Paycheck #{income_id}",
                        "amount":     float(amount),
                        "expense_id": None,
                        "due_date":   None,
                        "paid":       None,
                    })

        # Expense events — all frequencies
        for exp_id, name, amount, due_date, frequency, category in _expand_all_expenses(
            most_recent, window_end, skip_paid=False
        ):
            from ..database import get_expense_payment
            paid_val = get_expense_payment(exp_id, due_date.isoformat())
            events.append({
                "date":       due_date,
                "type":       "Expense",
                "name":       f"{name} ({category})",
                "amount":     -abs(float(amount)),
                "expense_id": exp_id,
                "due_date":   due_date,
                "paid":       paid_val == 1,
            })

        events.sort(key=lambda e: (e["date"], 0 if e["type"] == "Income" else 1))

        # --- populate table ---
        self.table.setRowCount(len(events))
        today_str = today.isoformat()

        for row, ev in enumerate(events):
            date_str = ev["date"].strftime("%b %d, %Y")

            self.table.setItem(row, 1, QTableWidgetItem(date_str))
            self.table.setItem(row, 2, QTableWidgetItem(ev["type"]))
            self.table.setItem(row, 3, QTableWidgetItem(ev["name"]))

            amt = ev["amount"]
            amt_item = QTableWidgetItem(f"${amt:,.2f}" if amt >= 0 else f"-${abs(amt):,.2f}")
            self.table.setItem(row, 4, amt_item)

            # Colour rows
            if ev["type"] == "Income":
                for col in range(1, 5):
                    item = self.table.item(row, col)
                    if item:
                        item.setForeground(QColor("#4caf50"))
                self.table.setItem(row, 0, QTableWidgetItem(""))
            else:
                # Paid checkbox
                cb = QCheckBox()
                cb.setChecked(ev["paid"])

                if ev["paid"]:
                    self._grey_row(row)

                def make_handler(expense_id, due_date, checkbox, r=row):
                    def handler(state):
                        paid = checkbox.isChecked()
                        set_expense_payment(expense_id, due_date.isoformat(), paid)
                        if paid:
                            self._grey_row(r)
                        else:
                            self._ungrey_row(r)
                    return handler

                cb.stateChanged.connect(make_handler(ev["expense_id"], ev["due_date"], cb))
                self.table.setCellWidget(row, 0, cb)

            # Highlight today's date
            if ev["date"].isoformat() == today_str:
                for col in range(1, 5):
                    item = self.table.item(row, col)
                    if item:
                        item.setBackground(QColor("#3a3a5a"))

    def _grey_row(self, row):
        for col in range(1, 5):
            item = self.table.item(row, col)
            if item:
                item.setForeground(QColor("#666666"))

    def _ungrey_row(self, row):
        for col in range(1, 5):
            item = self.table.item(row, col)
            if item:
                item.setForeground(QColor("#cccccc"))
