import calendar
import datetime

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QGridLayout, QFrame, QSizePolicy,
    QScrollArea,
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QPalette

from ..database import (
    get_income_sources,
    get_expense_payment,
    set_expense_payment,
)
from ..forecast import (
    _biweekly_next_pay,
    _generate_biweekly_schedule,
    _expand_all_expenses,
)


class CalendarScreen(QWidget):
    def __init__(self):
        super().__init__()

        today = datetime.date.today()
        self._year  = today.year
        self._month = today.month

        layout = QVBoxLayout(self)

        # -------------------------
        # Navigation bar
        # -------------------------
        nav = QHBoxLayout()
        prev_btn = QPushButton("< Prev")
        prev_btn.clicked.connect(self._prev_month)
        nav.addWidget(prev_btn)

        self.month_label = QLabel("")
        self.month_label.setAlignment(Qt.AlignCenter)
        self.month_label.setStyleSheet("font-size: 18px; font-weight: bold;")
        nav.addWidget(self.month_label, stretch=1)

        next_btn = QPushButton("Next >")
        next_btn.clicked.connect(self._next_month)
        nav.addWidget(next_btn)

        layout.addLayout(nav)

        # Legend
        legend = QLabel(
            "  <span style='color:#4caf50'>■</span> Paycheck  "
            "<span style='color:#f44336'>■</span> Bill due  "
            "<span style='color:#888888'>■</span> Paid  "
            "[ today highlighted ]"
        )
        legend.setStyleSheet("font-size: 12px; margin-bottom: 4px;")
        layout.addWidget(legend)

        # -------------------------
        # Calendar grid inside a scroll area
        # -------------------------
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        layout.addWidget(scroll)

        self._grid_widget = QWidget()
        self._grid = QGridLayout(self._grid_widget)
        self._grid.setSpacing(4)
        scroll.setWidget(self._grid_widget)

        self.refresh()

    # ------------------------------------------------------------------

    def _prev_month(self):
        if self._month == 1:
            self._month = 12
            self._year -= 1
        else:
            self._month -= 1
        self.refresh()

    def _next_month(self):
        if self._month == 12:
            self._month = 1
            self._year += 1
        else:
            self._month += 1
        self.refresh()

    # ------------------------------------------------------------------

    def refresh(self):
        # Clear grid
        while self._grid.count():
            item = self._grid.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        today       = datetime.date.today()
        year        = self._year
        month       = self._month
        month_start = datetime.date(year, month, 1)
        _, days_in_month = calendar.monthrange(year, month)
        month_end   = datetime.date(year, month, days_in_month)

        self.month_label.setText(month_start.strftime("%B %Y"))

        # Day-of-week headers (Mon–Sun)
        day_names = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
        for col, name in enumerate(day_names):
            hdr = QLabel(name)
            hdr.setAlignment(Qt.AlignCenter)
            hdr.setStyleSheet("font-weight: bold; font-size: 13px;")
            self._grid.addWidget(hdr, 0, col)

        # Collect income paydays for the month
        incomes   = get_income_sources()
        pay_dates = set()
        for _id, amount, freq, start_str, ps in incomes:
            start = datetime.date.fromisoformat(start_str)
            first = _biweekly_next_pay(start, month_start - datetime.timedelta(days=14))
            for d in _generate_biweekly_schedule(first, month_end):
                if d.month == month and d.year == year:
                    pay_dates.add(d)

        # Collect expenses for the month
        expenses_by_day: dict = {}
        for exp_id, name, amount, due_date, frequency, category in _expand_all_expenses(
            month_start, month_end, skip_paid=False
        ):
            paid = get_expense_payment(exp_id, due_date.isoformat()) == 1
            expenses_by_day.setdefault(due_date.day, []).append(
                (exp_id, name, amount, due_date, paid)
            )

        # Build cells
        start_weekday = month_start.weekday()  # 0=Mon
        grid_row = 1
        grid_col = start_weekday

        for day_num in range(1, days_in_month + 1):
            cell_date = datetime.date(year, month, day_num)
            self._grid.addWidget(
                self._make_day_cell(
                    day_num, cell_date, today,
                    day_num in [d.day for d in pay_dates],
                    expenses_by_day.get(day_num, []),
                ),
                grid_row, grid_col,
            )
            grid_col += 1
            if grid_col > 6:
                grid_col = 0
                grid_row += 1

    # ------------------------------------------------------------------

    def _make_day_cell(self, day_num, cell_date, today, is_payday, expenses):
        frame = QFrame()
        frame.setFrameShape(QFrame.StyledPanel)
        frame.setMinimumSize(90, 80)
        frame.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        lay = QVBoxLayout(frame)
        lay.setContentsMargins(4, 4, 4, 4)
        lay.setSpacing(2)

        is_today = (cell_date == today)

        # Day number
        day_lbl = QLabel(str(day_num))
        if is_today:
            day_lbl.setStyleSheet(
                "font-weight: bold; font-size: 14px; "
                "background-color: #3a5a8a; border-radius: 10px; "
                "padding: 2px 6px;"
            )
        else:
            day_lbl.setStyleSheet("font-weight: bold; font-size: 14px;")
        lay.addWidget(day_lbl)

        # Paycheck
        if is_payday:
            pay_lbl = QLabel("Paycheck")
            pay_lbl.setStyleSheet(
                "color: #4caf50; font-size: 11px; font-weight: bold;"
            )
            lay.addWidget(pay_lbl)

        # Expenses
        for exp_id, name, amount, due_date, paid in expenses:
            short = name if len(name) <= 14 else name[:12] + "…"
            color = "#888888" if paid else "#f44336"
            style = f"color: {color}; font-size: 11px;"
            if paid:
                style += " text-decoration: line-through;"
            exp_lbl = QLabel(f"{short} ${amount:,.0f}")
            exp_lbl.setStyleSheet(style)
            exp_lbl.setToolTip(f"{name} — ${amount:,.2f}{'  [PAID]' if paid else ''}")
            lay.addWidget(exp_lbl)

        lay.addStretch()
        return frame
