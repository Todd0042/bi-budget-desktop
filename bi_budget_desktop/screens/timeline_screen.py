# timeline_screen.py

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QTableWidget, QTableWidgetItem, QCheckBox
)
from PySide6.QtCore import Qt
from datetime import date, timedelta
from dateutil.relativedelta import relativedelta

from ..database import (
    get_income_sources,
    get_expenses,
    get_expense_payment,
    set_expense_payment,
)
from ..forecast import _biweekly_next_pay, _generate_biweekly_schedule


class TimelineScreen(QWidget):
    def __init__(self):
        super().__init__()
        self.setLayout(QVBoxLayout())

        title = QLabel("Timeline: Recent Paycheck → One Month Ahead")
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet("font-size: 20px; font-weight: bold; margin-bottom: 10px;")
        self.layout().addWidget(title)

        self.table = QTableWidget()
        self.table.setColumnCount(5)

        # ⭐ NEW COLUMN ORDER: Paid first
        self.table.setHorizontalHeaderLabels(["Paid", "Date", "Type", "Name", "Amount"])

        self.layout().addWidget(self.table)

        self.refresh_timeline()

    def refresh_timeline(self):
        today = date.today()

        # 1. Determine the most recent paycheck BEFORE today
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

        # 2. Determine the paycheck AFTER one month from today
        one_month_from_now = today + relativedelta(months=1)
        paycheck_after_one_month = None

        for income_id, amount, frequency, start_str, planned_savings in incomes:
            start_date = date.fromisoformat(start_str)
            first = _biweekly_next_pay(start_date, today)
            paydates = _generate_biweekly_schedule(first, one_month_from_now + timedelta(days=30))

            future = [d for d in paydates if d > one_month_from_now]
            if future:
                next_pay = min(future)
                if paycheck_after_one_month is None or next_pay < paycheck_after_one_month:
                    paycheck_after_one_month = next_pay

        if paycheck_after_one_month is None:
            return

        # 3. Build event list
        events = []

        # INCOME EVENTS
        for income_id, amount, frequency, start_str, planned_savings in incomes:
            start_date = date.fromisoformat(start_str)
            first = _biweekly_next_pay(start_date, most_recent_paycheck)
            paydates = _generate_biweekly_schedule(first, paycheck_after_one_month)

            for d in paydates:
                if most_recent_paycheck <= d <= paycheck_after_one_month:
                    events.append({
                        "date": d,
                        "type": "Income",
                        "name": f"Income #{income_id}",
                        "amount": float(amount),
                        "expense_id": None,
                        "due_date": None,
                        "paid": None,
                    })

        # EXPENSE EVENTS
        expenses = get_expenses()
        for exp_id, name, amount, due_day, frequency in expenses:
            try:
                exp_date = date(today.year, today.month, due_day)
            except ValueError:
                continue

            if most_recent_paycheck <= exp_date <= paycheck_after_one_month:
                paid = get_expense_payment(exp_id, exp_date.isoformat())
                events.append({
                    "date": exp_date,
                    "type": "Expense",
                    "name": name,
                    "amount": -abs(float(amount)),
                    "expense_id": exp_id,
                    "due_date": exp_date,
                    "paid": paid == 1,
                })

        # 4. Sort events
        events.sort(key=lambda e: (e["date"], 0 if e["type"] == "Income" else 1))

        # 5. Populate table
        self.table.setRowCount(len(events))

        for row, ev in enumerate(events):

            # ⭐ NEW COLUMN ORDER
            # Column 0 = Paid
            # Column 1 = Date
            # Column 2 = Type
            # Column 3 = Name
            # Column 4 = Amount

            self.table.setItem(row, 1, QTableWidgetItem(ev["date"].strftime("%b %d")))
            self.table.setItem(row, 2, QTableWidgetItem(ev["type"]))
            self.table.setItem(row, 3, QTableWidgetItem(ev["name"]))
            self.table.setItem(row, 4, QTableWidgetItem(f"${ev['amount']:,.2f}"))

            if ev["type"] == "Expense":
                cb = QCheckBox()
                cb.setChecked(ev["paid"])

                # Grey-out styling
                if ev["paid"]:
                    for col in range(1, 5):
                        item = self.table.item(row, col)
                        if item:
                            item.setForeground(Qt.gray)

                def make_handler(expense_id, due_date, checkbox, row=row):
                    def handler(state):
                        paid = checkbox.isChecked()
                        set_expense_payment(expense_id, due_date.isoformat(), paid)

                        for col in range(1, 5):
                            item = self.table.item(row, col)
                            if item:
                                item.setForeground(Qt.gray if paid else Qt.black)
                    return handler

                cb.stateChanged.connect(
                    make_handler(ev["expense_id"], ev["due_date"], cb)
                )

                self.table.setCellWidget(row, 0, cb)

            else:
                self.table.setItem(row, 0, QTableWidgetItem(""))

        # ⭐ FIXED WIDTH FOR PAID COLUMN
        self.table.setColumnWidth(0, 55)
