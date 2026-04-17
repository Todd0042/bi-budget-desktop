from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QLineEdit, QSpinBox,
    QPushButton, QListWidget, QListWidgetItem, QHBoxLayout,
    QMessageBox, QComboBox
)
from PySide6.QtCore import Qt

from ..database import (
    get_expenses,
    save_expense,
    delete_expense,
    get_total_monthly_expenses
)


class ExpensesScreen(QWidget):
    def __init__(self):
        super().__init__()

        layout = QVBoxLayout(self)

        # -------------------------
        # Title
        # -------------------------
        title = QLabel("Monthly Expenses")
        title.setStyleSheet("font-size: 22px; font-weight: bold; margin-bottom: 10px;")
        layout.addWidget(title)

        # -------------------------
        # Expense list
        # -------------------------
        self.list_widget = QListWidget()
        layout.addWidget(self.list_widget)

        # -------------------------
        # Form fields
        # -------------------------
        form = QVBoxLayout()

        # Name
        name_label = QLabel("Name")
        name_label.setStyleSheet("font-weight: bold;")
        form.addWidget(name_label)

        self.name_input = QLineEdit()
        form.addWidget(self.name_input)

        # Amount
        amount_label = QLabel("Amount")
        amount_label.setStyleSheet("font-weight: bold;")
        form.addWidget(amount_label)

        self.amount_input = QLineEdit()
        form.addWidget(self.amount_input)

        # Due Day (1–31)
        due_day_label = QLabel("Due Day (1–31)")
        due_day_label.setStyleSheet("font-weight: bold;")
        form.addWidget(due_day_label)

        self.due_day_input = QSpinBox()
        self.due_day_input.setRange(1, 31)
        form.addWidget(self.due_day_input)

        # Frequency (locked to monthly for now)
        freq_label = QLabel("Frequency")
        freq_label.setStyleSheet("font-weight: bold;")
        form.addWidget(freq_label)

        self.frequency_dropdown = QComboBox()
        self.frequency_dropdown.addItems(["monthly"])
        form.addWidget(self.frequency_dropdown)

        layout.addLayout(form)

        # -------------------------
        # Buttons
        # -------------------------
        btn_row = QHBoxLayout()

        add_btn = QPushButton("Add / Update Expense")
        add_btn.clicked.connect(self.add_or_update_expense)
        btn_row.addWidget(add_btn)

        del_btn = QPushButton("Delete Selected")
        del_btn.clicked.connect(self.delete_selected)
        btn_row.addWidget(del_btn)

        layout.addLayout(btn_row)

        # -------------------------
        # Total Monthly Expenses
        # -------------------------
        self.total_label = QLabel("")
        self.total_label.setStyleSheet("font-size: 18px; font-weight: bold; margin-top: 15px;")
        layout.addWidget(self.total_label)

        layout.addStretch()

        # Load existing expenses
        self.selected_expense_id = None
        self.load_expenses()

        # When selecting an item, load it into the form
        self.list_widget.itemClicked.connect(self.load_into_form)

    # ---------------------------------------------------------
    # Update total monthly expenses
    # ---------------------------------------------------------
    def update_total(self):
        total = get_total_monthly_expenses()
        self.total_label.setText(f"Total Monthly Expenses: ${total:,.2f}")

    # ---------------------------------------------------------
    # Load expenses into the list
    # ---------------------------------------------------------
    def load_expenses(self):
        self.list_widget.clear()
        rows = get_expenses()

        for _id, name, amount, due_day, frequency in rows:
            item = QListWidgetItem(
                f"{name} — ${amount:.2f} — Due Day {due_day}"
            )
            item.setData(Qt.UserRole, _id)
            self.list_widget.addItem(item)

        # Update total after loading
        self.update_total()

    # ---------------------------------------------------------
    # Load selected expense into form for editing
    # ---------------------------------------------------------
    def load_into_form(self, item):
        expense_id = item.data(Qt.UserRole)
        rows = get_expenses()

        for _id, name, amount, due_day, frequency in rows:
            if _id == expense_id:
                self.selected_expense_id = _id
                self.name_input.setText(name)
                self.amount_input.setText(str(amount))
                self.due_day_input.setValue(due_day)
                self.frequency_dropdown.setCurrentText(frequency)
                break

    # ---------------------------------------------------------
    # Add or update an expense
    # ---------------------------------------------------------
    def add_or_update_expense(self):
        name = self.name_input.text().strip()
        amount_str = self.amount_input.text().strip()
        due_day = self.due_day_input.value()
        frequency = self.frequency_dropdown.currentText()

        if not name or not amount_str:
            QMessageBox.warning(self, "Missing Data", "Please enter a name and amount.")
            return

        try:
            amount = float(amount_str)
        except ValueError:
            QMessageBox.warning(self, "Invalid Amount", "Amount must be a number.")
            return

        save_expense(name, amount, due_day, frequency, self.selected_expense_id)

        # Reset form
        self.selected_expense_id = None
        self.name_input.clear()
        self.amount_input.clear()
        self.due_day_input.setValue(1)
        self.frequency_dropdown.setCurrentText("monthly")

        self.load_expenses()

    # ---------------------------------------------------------
    # Delete selected expense
    # ---------------------------------------------------------
    def delete_selected(self):
        item = self.list_widget.currentItem()
        if not item:
            return

        expense_id = item.data(Qt.UserRole)

        confirm = QMessageBox.question(
            self,
            "Delete Expense",
            "Are you sure you want to delete this expense?",
            QMessageBox.Yes | QMessageBox.No
        )

        if confirm == QMessageBox.Yes:
            delete_expense(expense_id)
            self.load_expenses()
