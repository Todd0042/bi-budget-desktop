from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QPushButton,
    QLineEdit, QHBoxLayout, QListWidget, QListWidgetItem,
    QMessageBox, QScrollArea
)
from PySide6.QtCore import Qt

from ..database import (
    load_savings_balance,
    add_savings_event,
    get_savings_events
)

from ..forecast import (
    calculate_income_windows,
    calculate_combined_forecast
)


class BudgetScreen(QWidget):
    def __init__(self):
        super().__init__()

        layout = QVBoxLayout(self)

        # -------------------------
        # Title
        # -------------------------
        title = QLabel("Budget Overview")
        title.setStyleSheet("font-size: 22px; font-weight: bold; margin-bottom: 10px;")
        layout.addWidget(title)

        # -------------------------
        # Savings Balance
        # -------------------------
        bal_label = QLabel("Current Savings Balance")
        bal_label.setStyleSheet("font-size: 16px; font-weight: bold;")
        layout.addWidget(bal_label)

        self.balance_value = QLabel("$0.00")
        self.balance_value.setStyleSheet("font-size: 18px; margin-bottom: 10px;")
        layout.addWidget(self.balance_value)

        # -------------------------
        # Deposit / Withdrawal
        # -------------------------
        row = QHBoxLayout()

        self.amount_input = QLineEdit()
        self.amount_input.setPlaceholderText("Amount")
        row.addWidget(self.amount_input)

        deposit_btn = QPushButton("Deposit")
        deposit_btn.clicked.connect(self.deposit)
        row.addWidget(deposit_btn)

        withdraw_btn = QPushButton("Withdraw")
        withdraw_btn.clicked.connect(self.withdraw)
        row.addWidget(withdraw_btn)

        layout.addLayout(row)

        # -------------------------
        # Savings History (Scrollable)
        # -------------------------
        hist_label = QLabel("Savings History")
        hist_label.setStyleSheet("font-size: 16px; font-weight: bold; margin-top: 15px;")
        layout.addWidget(hist_label)

        self.history_list = QListWidget()
        layout.addWidget(self.history_list)

        # -------------------------
        # Forecast Section
        # -------------------------
        forecast_title = QLabel("Upcoming Paycheck Forecast")
        forecast_title.setStyleSheet("font-size: 16px; font-weight: bold; margin-top: 20px;")
        layout.addWidget(forecast_title)

        self.forecast_list = QListWidget()
        layout.addWidget(self.forecast_list)

        # Combined totals
        self.combined_label = QLabel("")
        self.combined_label.setStyleSheet("font-size: 14px; margin-top: 10px;")
        layout.addWidget(self.combined_label)

        layout.addStretch()

        # Load initial data
        self.refresh()

    # ---------------------------------------------------------
    # Refresh all UI sections
    # ---------------------------------------------------------
    def refresh(self):
        self.load_balance()
        self.load_history()
        self.load_forecast()

    # ---------------------------------------------------------
    # Savings Balance
    # ---------------------------------------------------------
    def load_balance(self):
        bal = load_savings_balance()
        self.balance_value.setText(f"${bal:,.2f}")

    # ---------------------------------------------------------
    # Savings History
    # ---------------------------------------------------------
    def load_history(self):
        self.history_list.clear()
        rows = get_savings_events()

        for amount, date_str, note, source in rows:
            sign = "+" if amount >= 0 else "-"
            item = QListWidgetItem(f"{date_str} — {sign}${abs(amount):.2f} — {note}")
            self.history_list.addItem(item)

    # ---------------------------------------------------------
    # Forecast
    # ---------------------------------------------------------
    def load_forecast(self):
        self.forecast_list.clear()

        windows = calculate_income_windows()
        combined = calculate_combined_forecast()

        # Per-paycheck windows
        for w in windows:
            item = QListWidgetItem(
                f"Paycheck on {w.next_pay} — Amount: ${w.amount:,.2f}\n"
                f"Window: {w.window_start} → {w.window_end}\n"
                f"Expenses: ${w.total_expenses:,.2f} | Hold Back: ${w.hold_back:,.2f}"
            )
            self.forecast_list.addItem(item)

        # Combined totals
        self.combined_label.setText(
            f"Total Income: ${combined.total_income:,.2f} | "
            f"Total Expenses: ${combined.total_expenses:,.2f} | "
            f"Hold Back: ${combined.total_hold_back:,.2f} | "
            f"Safe to Spend: ${combined.safe_to_spend:,.2f}"
        )

    # ---------------------------------------------------------
    # Deposit / Withdraw
    # ---------------------------------------------------------
    def deposit(self):
        self._apply_savings_change("deposit")

    def withdraw(self):
        self._apply_savings_change("withdraw")

    def _apply_savings_change(self, mode):
        amt_str = self.amount_input.text().strip()
        if not amt_str:
            QMessageBox.warning(self, "Missing Amount", "Enter an amount first.")
            return

        try:
            amt = float(amt_str)
        except ValueError:
            QMessageBox.warning(self, "Invalid Amount", "Amount must be a number.")
            return

        if mode == "withdraw":
            amt = -abs(amt)

        add_savings_event(amt, "Manual", mode)
        self.amount_input.clear()
        self.refresh()
