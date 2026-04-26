# pay_schedule_screen.py

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QHBoxLayout,
    QPushButton, QLineEdit, QDateEdit
)
from PySide6.QtCore import QDate, Qt
from datetime import date
from calendar import monthrange

from ..database import (
    load_pay_schedule, save_pay_schedule,
    get_income_sources, save_income_sources
)

from ..forecast import (
    _biweekly_next_pay,
    _generate_biweekly_schedule,
    find_three_check_month_for_income,
)


def parse_money(text):
    return float(text.replace("$", "").replace(",", "").strip() or 0)


class PayScheduleScreen(QWidget):
    def __init__(self):
        super().__init__()

        self.income_rows = []

        layout = QVBoxLayout(self)

        title = QLabel("Pay Schedule")
        title.setStyleSheet("font-size: 20px; font-weight: bold;")
        layout.addWidget(title)

        # Income section
        income_title = QLabel("Income Sources (Bi‑Weekly)")
        income_title.setStyleSheet("font-size: 16px; font-weight: bold;")
        layout.addWidget(income_title)

        self.income_layout = QVBoxLayout()
        layout.addLayout(self.income_layout)

        add_btn = QPushButton("Add Income")
        add_btn.clicked.connect(self.add_income_row)
        layout.addWidget(add_btn)

        # Spending
        spend_title = QLabel("Average Spending Per Paycheck")
        spend_title.setStyleSheet("font-size: 16px; font-weight: bold; margin-top: 10px;")
        layout.addWidget(spend_title)

        spend_row = QHBoxLayout()
        self.spend_prefix = QLabel("$")
        self.spend_input = QLineEdit()
        spend_row.addWidget(self.spend_prefix)
        spend_row.addWidget(self.spend_input)
        layout.addLayout(spend_row)

        # Save button
        save_btn = QPushButton("Save")
        save_btn.clicked.connect(self.save_all)
        layout.addWidget(save_btn)

        # Bottom totals
        self.total_income_label = QLabel("Total Income: $0.00")
        self.total_income_label.setAlignment(Qt.AlignCenter)
        self.total_income_label.setStyleSheet(
            "font-size: 22px; font-weight: bold; margin-top: 20px;"
        )
        layout.addWidget(self.total_income_label)

        layout.addStretch()

        self.load_existing()

    # Load existing data
    def load_existing(self):
        schedule = load_pay_schedule()
        if schedule:
            last_pay, next_pay, spend_amount, _ = schedule
            self.spend_input.setText(str(spend_amount))

        incomes = get_income_sources()
        for income in incomes:
            income_id, name, amount, frequency, start_date, planned_savings = income
            self.add_income_row(amount, start_date, name, planned_savings)

        self.update_total_income()

    # Add income row
    def add_income_row(self, amount="", start_date=None, name="", savings=""):
        row = QHBoxLayout()

        name_input = QLineEdit()
        name_input.setPlaceholderText("Name")
        name_input.setText(name)

        amount_input = QLineEdit()
        amount_input.setPlaceholderText("Amount")
        amount_input.setText(str(amount))

        date_input = QDateEdit()
        date_input.setCalendarPopup(True)
        if start_date:
            date_input.setDate(QDate.fromString(start_date, "yyyy-MM-dd"))
        else:
            date_input.setDate(QDate.currentDate())

        savings_input = QLineEdit()
        savings_input.setPlaceholderText("Savings")
        savings_input.setText(str(savings))

        delete_btn = QPushButton("Delete")
        delete_btn.clicked.connect(lambda: self.remove_income_row(row))

        row.addWidget(name_input)
        row.addWidget(amount_input)
        row.addWidget(date_input)
        row.addWidget(savings_input)
        row.addWidget(delete_btn)

        self.income_rows.append((row, name_input, amount_input, date_input, savings_input))
        self.income_layout.addLayout(row)

        self.update_total_income()

    # Remove income row
    def remove_income_row(self, row_layout):
        for row, name, amount, date, savings in self.income_rows:
            if row is row_layout:
                self.income_rows.remove((row, name, amount, date, savings))
                break

        while row_layout.count():
            item = row_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()

        self.update_total_income()

    # Save everything
    def save_all(self):
        spend = parse_money(self.spend_input.text())

        schedule = load_pay_schedule()
        if schedule:
            last_pay, next_pay, _, _ = schedule
        else:
            last_pay = "2000-01-01"
            next_pay = "2000-01-01"

        save_pay_schedule(last_pay, next_pay, spend, 0)

        incomes = []
        for row, name_input, amount_input, date_input, savings_input in self.income_rows:
            name = name_input.text().strip()
            amount = parse_money(amount_input.text())
            savings = parse_money(savings_input.text())

            # ⭐ FIX: Convert Qt string → Python string
            qt_str = date_input.date().toString("yyyy-MM-dd")
            start_date = str(qt_str)

            incomes.append((name, amount, "bi-weekly", start_date, savings))

        save_income_sources(incomes)
        self.update_total_income()

    # Update totals at bottom
    def update_total_income(self):
        today = date.today()

        # 1. Total per-check income
        total_per_check = 0.0
        income_sources = []
        for row, name_input, amount_input, date_input, savings_input in self.income_rows:
            amount = parse_money(amount_input.text())

            # ⭐ FIX: Convert Qt string → Python string before parsing
            qt_str = date_input.date().toString("yyyy-MM-dd")
            start_date = date.fromisoformat(str(qt_str))

            total_per_check += amount
            income_sources.append((amount, start_date))

        # 2. 2-check and 3-check month income
        income_2 = total_per_check * 2
        income_3 = total_per_check * 3

        # 3. Determine THIS month's check count
        first_day = date(today.year, today.month, 1)
        last_day = date(today.year, today.month, monthrange(today.year, today.month)[1])

        paydates = []
        for amount, start_date in income_sources:
            first = _biweekly_next_pay(start_date, first_day)
            paydates.extend(_generate_biweekly_schedule(first, last_day))

        this_month_count = sum(1 for d in paydates if first_day <= d <= last_day)

        # 4. Find earliest 3-check month across all incomes
        three_months = []
        for amount, start_date in income_sources:
            info = find_three_check_month_for_income(start_date, today)
            if info:
                three_months.append((info["year"], info["month"]))

        if three_months:
            three_months.sort()
            next_three_str = f"{three_months[0][1]}/{three_months[0][0]}"
        else:
            next_three_str = "None"

        # 5. Update label
        self.total_income_label.setText(
            f"2‑check month income: ${income_2:,.2f}\n"
            f"3‑check month income: ${income_3:,.2f}\n"
            f"This is currently a {this_month_count}‑check month\n"
            f"Next 3‑check month: {next_three_str}"
        )
