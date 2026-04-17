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
        income_title.setStyleSheet("font-size: 16px; font-weight: bold; margin-top: 10px;")
        layout.addWidget(income_title)

        self.income_layout = QVBoxLayout()
        layout.addLayout(self.income_layout)

        add_btn = QPushButton("Add Income")
        add_btn.clicked.connect(self.add_income_row)
        layout.addWidget(add_btn)

        # -------------------------
        # Average Spending Per Paycheck
        # -------------------------
        spend_title = QLabel("Average Spending Per Paycheck")
        spend_title.setStyleSheet("font-size: 16px; font-weight: bold; margin-top: 20px;")
        layout.addWidget(spend_title)

        spend_row = QHBoxLayout()
        spend_row.addWidget(QLabel("Amount: $"))
        self.spend_input = QLineEdit()
        spend_row.addWidget(self.spend_input)
        layout.addLayout(spend_row)

        # -------------------------
        # Total Monthly Income
        # -------------------------
        self.total_income_label = QLabel("")
        self.total_income_label.setStyleSheet("font-size: 18px; font-weight: bold; margin-top: 15px;")
        layout.addWidget(self.total_income_label)

        # -------------------------
        # Save button
        # -------------------------
        save_btn = QPushButton("Save All")
        save_btn.clicked.connect(self.save_all)
        layout.addWidget(save_btn)

        layout.addStretch()

        # Load existing data
        self.load_existing()

    # -------------------------
    # Update total monthly income
    # -------------------------
    def update_total_income(self):
        rows = get_income_sources()

        # Convert bi-weekly → monthly (26 checks / 12 months)
        total = 0.0
        for _id, amount, freq, start_date, planned_savings in rows:
            monthly = float(amount) * 26 / 12
            total += monthly

        self.total_income_label.setText(f"Total Monthly Income: ${total:,.2f}")

    # -------------------------
    # Load existing data
    # -------------------------
    def load_existing(self):
        # Clear existing rows
        for row, amount, save_input, date in self.income_rows:
            while row.count():
                item = row.takeAt(0)
                widget = item.widget()
                if widget:
                    widget.deleteLater()
        self.income_rows.clear()

        # Load spending + pay dates
        schedule = load_pay_schedule()
        if schedule:
            last_pay, next_pay, spend_amount, _legacy_planned_savings = schedule
            self.spend_input.setText(str(spend_amount))

        # Load incomes
        incomes = get_income_sources()
        for income in incomes:
            income_id, amount, frequency, start_date, planned_savings = income
            self.add_income_row(amount, start_date, planned_savings)

        # Update total after loading
        self.update_total_income()

    # -------------------------
    # Add income row
    # -------------------------
    def add_income_row(self, amount="", start_date=None, planned_savings=0.0):
        row = QHBoxLayout()

        # Labels
        row.addWidget(QLabel("Amount: $"))
        amount_input = QLineEdit()
        amount_input.setText(str(amount))
        amount_input.textChanged.connect(self.update_total_income)
        row.addWidget(amount_input)

        row.addWidget(QLabel("Save Per Check: $"))
        save_input = QLineEdit()
        save_input.setText(str(planned_savings))
        row.addWidget(save_input)

        row.addWidget(QLabel("Next Pay Date:"))
        date_input = QDateEdit()
        date_input.setCalendarPopup(True)
        if start_date:
            date_input.setDate(QDate.fromString(start_date, "yyyy-MM-dd"))
        else:
            date_input.setDate(QDate.currentDate())
        row.addWidget(date_input)

        # Delete button
        delete_btn = QPushButton("Delete")
        delete_btn.clicked.connect(lambda: self.remove_income_row(row))
        row.addWidget(delete_btn)

        # Track row
        self.income_rows.append((row, amount_input, save_input, date_input))

        # Add to layout
        self.income_layout.addLayout(row)

        # Update total after adding
        self.update_total_income()

    # -------------------------
    # Remove income row
    # -------------------------
    def remove_income_row(self, row_layout):
        for row, amount, save_input, date in self.income_rows:
            if row is row_layout:
                self.income_rows.remove((row, amount, save_input, date))
                break

        while row_layout.count():
            item = row_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()

        # Update total after removing
        self.update_total_income()

    # -------------------------
    # Save everything
    # -------------------------
    def save_all(self):
        print(">>> SAVE_ALL FIRED")

        # Save spending
        spend = parse_money(self.spend_input.text())

        # Pay dates are not edited here — keep existing ones
        schedule = load_pay_schedule()
        if schedule:
            last_pay, next_pay, _, _ = schedule
        else:
            last_pay = "2000-01-01"
            next_pay = "2000-01-01"

        save_pay_schedule(last_pay, next_pay, spend, 0.0)

        # Save incomes (all bi-weekly)
        incomes = []
        for row, amount_input, save_input, date_input in self.income_rows:
            amount = parse_money(amount_input.text())
            per_income_savings = parse_money(save_input.text())
            start_date = date_input.date().toString("yyyy-MM-dd")
            incomes.append((amount, "bi-weekly", start_date, per_income_savings))

        save_income_sources(incomes)

        # Update total after saving
        self.update_total_income()
