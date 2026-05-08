from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QLineEdit, QSpinBox,
    QPushButton, QListWidget, QListWidgetItem, QHBoxLayout,
    QMessageBox, QComboBox, QDateEdit, QStackedWidget, QFrame,
    QScrollArea,
)
from PySide6.QtCore import Qt, QDate

from ..database import (
    get_expenses,
    save_expense,
    delete_expense,
    get_total_monthly_expenses,
    EXPENSE_CATEGORIES,
    EXPENSE_FREQUENCIES,
    MONTH_NAMES,
)


class ExpensesScreen(QWidget):
    def __init__(self):
        super().__init__()

        outer = QVBoxLayout(self)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        outer.addWidget(scroll)

        inner = QWidget()
        scroll.setWidget(inner)
        layout = QVBoxLayout(inner)

        # -------------------------
        # Title
        # -------------------------
        title = QLabel("Expenses")
        title.setStyleSheet("font-size: 22px; font-weight: bold; margin-bottom: 10px;")
        layout.addWidget(title)

        # -------------------------
        # Expense list
        # -------------------------
        self.list_widget = QListWidget()
        self.list_widget.setMinimumHeight(180)
        layout.addWidget(self.list_widget)

        # -------------------------
        # Form — static fields
        # -------------------------
        form = QVBoxLayout()

        form.addWidget(self._bold("Name"))
        self.name_input = QLineEdit()
        form.addWidget(self.name_input)

        form.addWidget(self._bold("Amount ($)"))
        self.amount_input = QLineEdit()
        form.addWidget(self.amount_input)

        form.addWidget(self._bold("Category"))
        self.category_dropdown = QComboBox()
        self.category_dropdown.addItems(EXPENSE_CATEGORIES)
        form.addWidget(self.category_dropdown)

        form.addWidget(self._bold("Frequency"))
        self.frequency_dropdown = QComboBox()
        self.frequency_dropdown.addItems(EXPENSE_FREQUENCIES)
        self.frequency_dropdown.currentTextChanged.connect(self._on_frequency_changed)
        form.addWidget(self.frequency_dropdown)

        # -------------------------
        # Stacked date widgets — swap based on frequency
        # -------------------------
        self.date_stack = QStackedWidget()

        # Page 0: Monthly — just a due-day spinner
        monthly_page = QWidget()
        mp_lay = QVBoxLayout(monthly_page)
        mp_lay.setContentsMargins(0, 0, 0, 0)
        mp_lay.addWidget(self._bold("Due Day (1–31)"))
        self.due_day_spin = QSpinBox()
        self.due_day_spin.setRange(1, 31)
        mp_lay.addWidget(self.due_day_spin)
        self.date_stack.addWidget(monthly_page)   # index 0

        # Page 1: Quarterly / Annual — due day + starting month
        recurring_page = QWidget()
        rp_lay = QVBoxLayout(recurring_page)
        rp_lay.setContentsMargins(0, 0, 0, 0)
        rp_lay.addWidget(self._bold("Due Day (1–31)"))
        self.due_day_spin2 = QSpinBox()
        self.due_day_spin2.setRange(1, 31)
        rp_lay.addWidget(self.due_day_spin2)
        rp_lay.addWidget(self._bold("Starting Month"))
        self.due_month_combo = QComboBox()
        self.due_month_combo.addItems(MONTH_NAMES)
        rp_lay.addWidget(self.due_month_combo)
        self.date_stack.addWidget(recurring_page)  # index 1

        # Page 2: One-time — full date picker
        onetime_page = QWidget()
        ot_lay = QVBoxLayout(onetime_page)
        ot_lay.setContentsMargins(0, 0, 0, 0)
        ot_lay.addWidget(self._bold("Due Date"))
        self.one_time_date = QDateEdit()
        self.one_time_date.setCalendarPopup(True)
        self.one_time_date.setDate(QDate.currentDate())
        ot_lay.addWidget(self.one_time_date)
        self.date_stack.addWidget(onetime_page)    # index 2

        form.addWidget(self.date_stack)
        layout.addLayout(form)

        # -------------------------
        # Buttons
        # -------------------------
        btn_row = QHBoxLayout()

        add_btn = QPushButton("Add / Update")
        add_btn.clicked.connect(self.add_or_update_expense)
        btn_row.addWidget(add_btn)

        clear_btn = QPushButton("Clear Form")
        clear_btn.clicked.connect(self._clear_form)
        btn_row.addWidget(clear_btn)

        del_btn = QPushButton("Delete Selected")
        del_btn.clicked.connect(self.delete_selected)
        btn_row.addWidget(del_btn)

        layout.addLayout(btn_row)

        # -------------------------
        # Total
        # -------------------------
        self.total_label = QLabel("")
        self.total_label.setStyleSheet(
            "font-size: 16px; font-weight: bold; margin-top: 12px;"
        )
        layout.addWidget(self.total_label)

        layout.addStretch()

        # -------------------------
        # State
        # -------------------------
        self.selected_expense_id = None
        self.load_expenses()
        self.list_widget.itemClicked.connect(self.load_into_form)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _bold(self, text):
        lbl = QLabel(text)
        lbl.setStyleSheet("font-weight: bold;")
        return lbl

    def _on_frequency_changed(self, freq):
        if freq == "monthly":
            self.date_stack.setCurrentIndex(0)
        elif freq in ("quarterly", "annual"):
            self.date_stack.setCurrentIndex(1)
        else:  # one-time
            self.date_stack.setCurrentIndex(2)

    def _clear_form(self):
        self.selected_expense_id = None
        self.name_input.clear()
        self.amount_input.clear()
        self.due_day_spin.setValue(1)
        self.due_day_spin2.setValue(1)
        self.due_month_combo.setCurrentIndex(0)
        self.one_time_date.setDate(QDate.currentDate())
        self.frequency_dropdown.setCurrentText("monthly")
        self.category_dropdown.setCurrentText("General")
        self.list_widget.clearSelection()

    # ------------------------------------------------------------------
    # Load list
    # ------------------------------------------------------------------

    def load_expenses(self):
        self.list_widget.clear()
        rows = get_expenses()

        for _id, name, amount, due_day, due_month, due_date_full, frequency, category in rows:
            if frequency == "monthly":
                date_str = f"Day {due_day}"
            elif frequency in ("quarterly", "annual"):
                month_name = MONTH_NAMES[due_month - 1] if 1 <= due_month <= 12 else "?"
                date_str = f"{month_name} {due_day}"
            else:
                date_str = due_date_full or "?"

            item = QListWidgetItem(
                f"{name} — ${amount:,.2f} — {frequency.title()} — {date_str} — {category}"
            )
            item.setData(Qt.UserRole, _id)
            self.list_widget.addItem(item)

        self._update_total()

    def _update_total(self):
        total = get_total_monthly_expenses()
        self.total_label.setText(f"Monthly Equivalent Total: ${total:,.2f}")

    # ------------------------------------------------------------------
    # Load into form for editing
    # ------------------------------------------------------------------

    def load_into_form(self, item):
        expense_id = item.data(Qt.UserRole)
        for _id, name, amount, due_day, due_month, due_date_full, frequency, category in get_expenses():
            if _id != expense_id:
                continue
            self.selected_expense_id = _id
            self.name_input.setText(name)
            self.amount_input.setText(str(amount))
            self.category_dropdown.setCurrentText(category)
            self.frequency_dropdown.setCurrentText(frequency)

            if frequency == "monthly":
                self.due_day_spin.setValue(due_day)
            elif frequency in ("quarterly", "annual"):
                self.due_day_spin2.setValue(due_day)
                idx = max(0, due_month - 1)
                self.due_month_combo.setCurrentIndex(idx)
            else:
                if due_date_full:
                    qd = QDate.fromString(due_date_full, "yyyy-MM-dd")
                    self.one_time_date.setDate(qd if qd.isValid() else QDate.currentDate())
            break

    # ------------------------------------------------------------------
    # Add / update
    # ------------------------------------------------------------------

    def add_or_update_expense(self):
        name     = self.name_input.text().strip()
        amt_str  = self.amount_input.text().strip()
        freq     = self.frequency_dropdown.currentText()
        category = self.category_dropdown.currentText()

        if not name or not amt_str:
            QMessageBox.warning(self, "Missing Data", "Enter a name and amount.")
            return
        try:
            amount = float(amt_str)
        except ValueError:
            QMessageBox.warning(self, "Invalid Amount", "Amount must be a number.")
            return

        if freq == "monthly":
            due_day       = self.due_day_spin.value()
            due_month     = 1
            due_date_full = ""
        elif freq in ("quarterly", "annual"):
            due_day       = self.due_day_spin2.value()
            due_month     = self.due_month_combo.currentIndex() + 1
            # Build the anchor date from the chosen month/day for current or next year
            import datetime
            today = datetime.date.today()
            try:
                anchor = datetime.date(today.year, due_month, due_day)
            except ValueError:
                anchor = datetime.date(today.year, due_month, 28)
            if anchor < today:
                anchor = anchor.replace(year=today.year + 1)
            due_date_full = anchor.isoformat()
        else:  # one-time
            due_day       = 1
            due_month     = 1
            due_date_full = self.one_time_date.date().toString("yyyy-MM-dd")

        save_expense(
            name, amount, due_day, due_month, due_date_full,
            freq, category, self.selected_expense_id,
        )
        self._clear_form()
        self.load_expenses()

    # ------------------------------------------------------------------
    # Delete
    # ------------------------------------------------------------------

    def delete_selected(self):
        item = self.list_widget.currentItem()
        if not item:
            return
        confirm = QMessageBox.question(
            self, "Delete Expense",
            "Delete this expense?",
            QMessageBox.Yes | QMessageBox.No,
        )
        if confirm == QMessageBox.Yes:
            delete_expense(item.data(Qt.UserRole))
            self._clear_form()
            self.load_expenses()
