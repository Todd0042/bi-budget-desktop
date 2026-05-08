from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QComboBox, QTableWidget, QTableWidgetItem,
    QMessageBox, QHeaderView, QFrame,
)
from PySide6.QtCore import Qt

from ..database import (
    get_spending_log,
    add_spending_entry,
    delete_spending_entry,
    get_spending_by_category,
    SPENDING_CATEGORIES,
    load_pay_schedule,
)
from ..forecast import _biweekly_next_pay, _parse_date
import datetime


def _current_paycheck_start() -> datetime.date:
    """Best estimate of when the current paycheck period started."""
    from ..database import get_income_sources
    today   = datetime.date.today()
    incomes = get_income_sources()
    if not incomes:
        return today - datetime.timedelta(days=14)
    earliest_last = None
    for _id, amount, freq, start_str, ps in incomes:
        start    = _parse_date(start_str)
        next_pay = _biweekly_next_pay(start, today)
        last_pay = next_pay - datetime.timedelta(days=14)
        if earliest_last is None or last_pay > earliest_last:
            earliest_last = last_pay
    return earliest_last or (today - datetime.timedelta(days=14))


class SpendingLogScreen(QWidget):
    def __init__(self):
        super().__init__()

        layout = QVBoxLayout(self)

        title = QLabel("Spending Log")
        title.setStyleSheet("font-size: 22px; font-weight: bold; margin-bottom: 10px;")
        layout.addWidget(title)

        # -------------------------
        # Add entry form
        # -------------------------
        form_frame = QFrame()
        form_frame.setFrameShape(QFrame.StyledPanel)
        form_lay = QHBoxLayout(form_frame)

        form_lay.addWidget(QLabel("Amount ($):"))
        self.amount_input = QLineEdit()
        self.amount_input.setFixedWidth(100)
        form_lay.addWidget(self.amount_input)

        form_lay.addWidget(QLabel("Category:"))
        self.category_combo = QComboBox()
        self.category_combo.addItems(SPENDING_CATEGORIES)
        form_lay.addWidget(self.category_combo)

        form_lay.addWidget(QLabel("Note:"))
        self.note_input = QLineEdit()
        self.note_input.setPlaceholderText("Optional description")
        form_lay.addWidget(self.note_input)

        add_btn = QPushButton("Add Entry")
        add_btn.clicked.connect(self._add_entry)
        form_lay.addWidget(add_btn)

        layout.addWidget(form_frame)

        # -------------------------
        # Period summary
        # -------------------------
        self.period_label = QLabel("")
        self.period_label.setStyleSheet("font-size: 14px; margin-top: 8px;")
        layout.addWidget(self.period_label)

        # -------------------------
        # Category breakdown
        # -------------------------
        self.breakdown_label = QLabel("")
        self.breakdown_label.setStyleSheet("font-size: 13px; color: #aaaaaa;")
        self.breakdown_label.setWordWrap(True)
        layout.addWidget(self.breakdown_label)

        # -------------------------
        # Recent entries table
        # -------------------------
        layout.addWidget(QLabel("Recent Entries:"))

        self.table = QTableWidget()
        self.table.setColumnCount(5)
        self.table.setHorizontalHeaderLabels(["Date", "Category", "Amount", "Note", ""])
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.Stretch)
        self.table.setColumnWidth(0, 90)
        self.table.setColumnWidth(1, 120)
        self.table.setColumnWidth(2, 80)
        self.table.setColumnWidth(4, 70)
        layout.addWidget(self.table)

        self.refresh()

    # ------------------------------------------------------------------

    def _add_entry(self):
        amt_str  = self.amount_input.text().strip()
        category = self.category_combo.currentText()
        note     = self.note_input.text().strip()

        if not amt_str:
            QMessageBox.warning(self, "Missing Amount", "Enter an amount.")
            return
        try:
            amt = float(amt_str)
        except ValueError:
            QMessageBox.warning(self, "Invalid Amount", "Amount must be a number.")
            return

        add_spending_entry(amt, note, category)
        self.amount_input.clear()
        self.note_input.clear()
        self.refresh()

    # ------------------------------------------------------------------

    def refresh(self):
        rows = get_spending_log(limit=200)

        # Period summary
        period_start = _current_paycheck_start()
        period_str   = period_start.strftime("%b %d")
        today_str    = datetime.date.today().strftime("%b %d")

        period_total = sum(
            amt for _id, amt, date_str, note, cat in rows
            if date_str >= period_start.isoformat()
        )
        self.period_label.setText(
            f"This paycheck period ({period_str} – {today_str}): ${period_total:,.2f} spent"
        )

        # Category breakdown (last 14 days)
        breakdown = get_spending_by_category(days=14)
        if breakdown:
            parts = [f"{cat}: ${total:,.2f}" for cat, total in breakdown]
            self.breakdown_label.setText("Last 14 days by category — " + "  |  ".join(parts))
        else:
            self.breakdown_label.setText("No spending entries in the last 14 days.")

        # Table
        self.table.setRowCount(len(rows))
        for row_idx, (entry_id, amt, date_str, note, cat) in enumerate(rows):
            self.table.setItem(row_idx, 0, QTableWidgetItem(date_str))
            self.table.setItem(row_idx, 1, QTableWidgetItem(cat))
            self.table.setItem(row_idx, 2, QTableWidgetItem(f"${amt:,.2f}"))
            self.table.setItem(row_idx, 3, QTableWidgetItem(note))

            del_btn = QPushButton("Delete")
            del_btn.setFixedWidth(60)
            del_btn.clicked.connect(
                lambda checked=False, eid=entry_id: self._delete_entry(eid)
            )
            self.table.setCellWidget(row_idx, 4, del_btn)

    def _delete_entry(self, entry_id):
        delete_spending_entry(entry_id)
        self.refresh()
