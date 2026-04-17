from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QHBoxLayout,
    QPushButton, QLineEdit, QDateEdit
)
from PySide6.QtCore import QDate

from ..database import (
    load_pay_schedule, save_pay_schedule,
    get_income_sources, save_income_sources
)


def parse_money(text):
    """Convert '$1,200.50' → 1200.50 safely."""
    return float(text.replace("$", "").replace(",", "").strip() or 0)


class PayScheduleScreen(QWidget):
    def __init__(self):
        super().__init__()

        self.income_rows = []  # store row widgets

        layout = QVBoxLayout(self)

        title = QLabel("Pay Schedule")
        title.setStyleSheet("font-size: 20px; font-weight: bold;")
        layout.addWidget(title)

        # -------------------------
        # Income section
        # -------------------------
        income_title = QLabel("Income Sources (Bi‑Weekly)")
        income_title.setStyleSheet("font-size: 16px; font-weight: bold;")
        layout.addWidget(income_title)

        self.income_layout = QVBoxLayout()
        layout.addLayout(self.income_layout)

        add_btn = QPushButton("Add Income")
        add_btn.clicked.connect(self.add_income_row)
        layout.addWidget(add_btn)

        # -------------------------
        # Spending amount
        # -------------------------
        spend_title = QLabel("Average Spending Per Paycheck")
        spend_title.setStyleSheet("font-size: 16px; font-weight: bold; margin-top: 10px;")
        layout.addWidget(spend_title)

        spend_row = QHBoxLayout()
        self.spend_prefix = QLabel("$")
        self.spend_input = QLineEdit()
        spend_row.addWidget(self.spend_prefix)
        spend_row.addWidget(self.spend_input)
        layout.addLayout(spend_row)

        # -------------------------
        # Planned savings
        # -------------------------
        save_title = QLabel("Planned Savings Per Paycheck")
        save_title.setStyleSheet("font-size: 16px; font-weight: bold; margin-top: 10px;")
        layout.addWidget(save_title)

        save_row = QHBoxLayout()
        self.save_prefix = QLabel("$")
        self.save_input = QLineEdit()
        save_row.addWidget(self.save_prefix)
        save_row.addWidget(self.save_input)
        layout.addLayout(save_row)

        # -------------------------
        # Save button
        # -------------------------
        save_btn = QPushButton("Save")
        save_btn.clicked.connect(self.save_all)
        layout.addWidget(save_btn)

        layout.addStretch()

        # Load existing data
        self.load_existing()

    # -------------------------
    # Load existing data
    # -------------------------
    def load_existing(self):
        # Load spending + savings + pay dates
        schedule = load_pay_schedule()
        if schedule:
            last_pay, next_pay, spend_amount, planned_savings = schedule
            self.spend_input.setText(str(spend_amount))
            self.save_input.setText(str(planned_savings))

        # Load incomes
        incomes = get_income_sources()
        for income in incomes:
            _, amount, frequency, start_date = income
            # Frequency is ignored (always bi-weekly)
            self.add_income_row(amount, start_date)

    # -------------------------
    # Add income row
    # -------------------------
    def add_income_row(self, amount="", start_date=None):
        row = QHBoxLayout()

        # Amount
        amount_input = QLineEdit()
        amount_input.setText(str(amount))

        # Start date
        date_input = QDateEdit()
        date_input.setCalendarPopup(True)
        if start_date:
            date_input.setDate(QDate.fromString(start_date, "yyyy-MM-dd"))
        else:
            date_input.setDate(QDate.currentDate())

        # Delete button
        delete_btn = QPushButton("Delete")
        delete_btn.clicked.connect(lambda: self.remove_income_row(row))

        # Add widgets to row
        row.addWidget(amount_input)
        row.addWidget(date_input)
        row.addWidget(delete_btn)

        # Track row
        self.income_rows.append((row, amount_input, date_input))

        # Add to layout
        self.income_layout.addLayout(row)

    # -------------------------
    # Remove income row
    # -------------------------
    def remove_income_row(self, row_layout):
        for row, amount, date in self.income_rows:
            if row is row_layout:
                self.income_rows.remove((row, amount, date))
                break

        while row_layout.count():
            item = row_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()

    # -------------------------
    # Save everything
    # -------------------------
    def save_all(self):
        # Save spending + savings
        spend = parse_money(self.spend_input.text())
        planned_savings = parse_money(self.save_input.text())

        # Pay dates are not edited here — keep existing ones
        schedule = load_pay_schedule()
        if schedule:
            last_pay, next_pay, _, _ = schedule
        else:
            # fallback defaults
            last_pay = "2000-01-01"
            next_pay = "2000-01-01"

        save_pay_schedule(last_pay, next_pay, spend, planned_savings)

        # Save incomes (all bi-weekly)
        incomes = []
        for row, amount_input, date_input in self.income_rows:
            amount = parse_money(amount_input.text())
            start_date = date_input.date().toString("yyyy-MM-dd")
            incomes.append((amount, "bi-weekly", start_date))

        save_income_sources(incomes)
