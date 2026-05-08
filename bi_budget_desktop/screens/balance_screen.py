from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QTableWidget, QTableWidgetItem, QHeaderView, QFrame,
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor

import datetime as _dt

from ..database import load_account_balance, save_account_balance
from ..forecast import calculate_running_balance


class BalanceScreen(QWidget):
    def __init__(self):
        super().__init__()

        layout = QVBoxLayout(self)

        title = QLabel("Running Balance Projection")
        title.setStyleSheet("font-size: 22px; font-weight: bold; margin-bottom: 8px;")
        layout.addWidget(title)

        subtitle = QLabel(
            "Enter your current checking account balance to project it forward 8 weeks. "
            "Income adds to the balance; unpaid bills subtract from it."
        )
        subtitle.setWordWrap(True)
        subtitle.setStyleSheet("font-size: 13px; color: #aaaaaa; margin-bottom: 12px;")
        layout.addWidget(subtitle)

        # -------------------------
        # Balance input
        # -------------------------
        bal_frame = QFrame()
        bal_frame.setFrameShape(QFrame.StyledPanel)
        bal_row = QHBoxLayout(bal_frame)

        bal_row.addWidget(QLabel("Current Account Balance ($):"))
        self.balance_input = QLineEdit()
        self.balance_input.setFixedWidth(140)
        saved = load_account_balance()
        self.balance_input.setText(f"{saved:.2f}")
        bal_row.addWidget(self.balance_input)

        refresh_btn = QPushButton("Refresh Projection")
        refresh_btn.clicked.connect(self._refresh)
        bal_row.addWidget(refresh_btn)

        bal_row.addStretch()
        layout.addWidget(bal_frame)

        # -------------------------
        # Summary labels
        # -------------------------
        self.summary_label = QLabel("")
        self.summary_label.setStyleSheet("font-size: 14px; margin: 8px 0;")
        layout.addWidget(self.summary_label)

        # -------------------------
        # Projection table
        # -------------------------
        self.table = QTableWidget()
        self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels(["Date", "Event", "Amount", "Balance"])
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.table.setColumnWidth(0, 90)
        self.table.setColumnWidth(2, 90)
        self.table.setColumnWidth(3, 100)
        layout.addWidget(self.table)

        # -------------------------
        # Color legend
        # -------------------------
        legend = QLabel(
            "<span style='color:#4caf50'>■</span> Income  "
            "<span style='color:#f44336'>■</span> Expense  "
            "<span style='color:#ff9800'>■</span> Negative balance"
        )
        legend.setStyleSheet("font-size: 12px; margin-top: 4px;")
        layout.addWidget(legend)

        self._refresh()

    # ------------------------------------------------------------------

    def _refresh(self):
        try:
            bal = float(self.balance_input.text().replace(",", "").strip())
        except ValueError:
            bal = 0.0

        save_account_balance(bal)
        events = calculate_running_balance(bal)

        self.table.setRowCount(len(events))
        today_str = _dt.date.today().isoformat()

        low_balance = bal
        for row_idx, ev in enumerate(events):
            low_balance = min(low_balance, ev.balance)

            date_str = ev.date.strftime("%b %d, %Y")
            amt_str  = f"+${ev.amount:,.2f}" if ev.amount >= 0 else f"-${abs(ev.amount):,.2f}"
            bal_str  = f"${ev.balance:,.2f}"

            self.table.setItem(row_idx, 0, QTableWidgetItem(date_str))
            self.table.setItem(row_idx, 1, QTableWidgetItem(ev.description))
            self.table.setItem(row_idx, 2, QTableWidgetItem(amt_str))
            self.table.setItem(row_idx, 3, QTableWidgetItem(bal_str))

            # Row colour
            if ev.balance < 0:
                row_color = QColor("#5a2a0a")   # deep orange-red for overdraft
            elif ev.event_type == "income":
                row_color = QColor("#1a3a1a")   # dark green
            else:
                row_color = QColor("#3a1a1a")   # dark red

            for col in range(4):
                item = self.table.item(row_idx, col)
                if item:
                    item.setBackground(row_color)

            # Highlight today's events
            if ev.date.isoformat() == today_str:
                for col in range(4):
                    item = self.table.item(row_idx, col)
                    if item:
                        font = item.font()
                        font.setBold(True)
                        item.setFont(font)

        # Summary
        if events:
            final = events[-1].balance
            warning = ""
            if low_balance < 0:
                warning = f"  ⚠  Balance goes negative (lowest: ${low_balance:,.2f})"
            self.summary_label.setText(
                f"Starting balance: ${bal:,.2f}  →  "
                f"Balance in 8 weeks: ${final:,.2f}"
                f"{warning}"
            )
        else:
            self.summary_label.setText(
                "No income sources configured. Add them on the Income screen."
            )
