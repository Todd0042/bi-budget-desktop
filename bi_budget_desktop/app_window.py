import datetime

from PySide6.QtWidgets import (
    QWidget, QMainWindow, QVBoxLayout, QLabel, QListWidget,
    QHBoxLayout, QGridLayout, QSizePolicy, QScrollArea, QFrame,
)
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QIcon

from .screens.expenses_screen    import ExpensesScreen
from .screens.pay_schedule_screen import PayScheduleScreen
from .screens.budget_screen      import BudgetScreen
from .screens.settings_screen    import SettingsScreen
from .screens.philosophy_screen  import PhilosophyScreen
from .screens.timeline_screen    import TimelineScreen
from .screens.goals_screen       import GoalsScreen
from .screens.spending_log_screen import SpendingLogScreen
from .screens.calendar_screen    import CalendarScreen
from .screens.balance_screen     import BalanceScreen

from .database import load_savings_balance
from .forecast import (
    calculate_income_windows,
    calculate_combined_forecast,
    find_next_three_check_month,
    find_next_three_check_month_for_income,
)
from .app_paths import app_root


class AppWindow(QMainWindow):
    def __init__(self, app_ref):
        super().__init__()

        icon_path = app_root() / "icons" / "money.png"
        self.setWindowIcon(QIcon(str(icon_path)))

        self.app_ref = app_ref
        self.setWindowTitle("Bi-Budget Desktop")
        self.setMinimumSize(1280, 900)
        self.resize(1280, 900)

        container = QWidget()
        self.setCentralWidget(container)
        layout = QHBoxLayout(container)

        # -------------------------
        # SIDEBAR
        # -------------------------
        self.sidebar = QListWidget()
        self.sidebar.setFixedWidth(160)
        self.sidebar.setStyleSheet("""
            QListWidget            { font-size: 15px; padding: 4px; }
            QListWidget::item      { padding: 7px 6px; }
            QListWidget::item:selected { font-weight: bold; }
        """)

        for label in [
            "Dashboard",
            "Balance",
            "Timeline",
            "Calendar",
            "Expenses",
            "Income",
            "Savings",
            "Goals",
            "Spending Log",
            "Settings",
            "Philosophy",
        ]:
            self.sidebar.addItem(label)

        layout.addWidget(self.sidebar)

        # -------------------------
        # CONTENT AREA
        # -------------------------
        self.content = QWidget()
        self.content_layout = QVBoxLayout(self.content)
        layout.addWidget(self.content)

        self.sidebar.currentRowChanged.connect(self._safe_switch_screen)
        QTimer.singleShot(0, lambda: self.sidebar.setCurrentRow(0))

    # ------------------------------------------------------------------
    # Layout helpers
    # ------------------------------------------------------------------

    def clear_content(self):
        while self.content_layout.count():
            item = self.content_layout.takeAt(0)
            w = item.widget()
            if w:
                w.setParent(None)
                w.deleteLater()
                continue
            lay = item.layout()
            if lay:
                self._clear_layout_recursive(lay)

    def _clear_layout_recursive(self, layout):
        while layout.count():
            child = layout.takeAt(0)
            if child.widget():
                child.widget().setParent(None)
                child.widget().deleteLater()
            elif child.layout():
                self._clear_layout_recursive(child.layout())
        layout.setParent(None)

    def _safe_switch_screen(self, index):
        if getattr(self, "_last_index", None) == index:
            return
        self._last_index = index
        self.switch_screen(index)

    # ------------------------------------------------------------------
    # Routing
    # ------------------------------------------------------------------

    def switch_screen(self, index):
        dispatch = {
            0:  self.show_dashboard,
            1:  self.show_balance,
            2:  self.show_timeline,
            3:  self.show_calendar,
            4:  self.show_expenses,
            5:  self.show_income,
            6:  self.show_savings,
            7:  self.show_goals,
            8:  self.show_spending_log,
            9:  self.show_settings,
            10: self.show_philosophy,
        }
        fn = dispatch.get(index)
        if fn:
            fn()

    # ------------------------------------------------------------------
    # DASHBOARD
    # ------------------------------------------------------------------

    def show_dashboard(self):
        self.clear_content()

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        self.content_layout.addWidget(scroll)

        inner = QWidget()
        scroll.setWidget(inner)
        lay = QVBoxLayout(inner)
        lay.setAlignment(Qt.AlignTop)

        # ---- Header ----
        header_row = QHBoxLayout()
        title = QLabel("Dashboard")
        title.setStyleSheet("font-size: 24px; font-weight: bold;")
        header_row.addWidget(title)
        header_row.addStretch()

        savings = load_savings_balance()
        sav_lbl = QLabel(f"Savings: ${savings:,.2f}")
        sav_lbl.setStyleSheet(
            "font-size: 16px; font-weight: bold; color: #4caf50;"
        )
        header_row.addWidget(sav_lbl)
        lay.addLayout(header_row)

        income_windows = calculate_income_windows()
        combined       = calculate_combined_forecast()

        # ---- Per-paycheck allocation cards ----
        if income_windows:
            lay.addWidget(self._section_label("Paycheck Allocation"))
            grid = QGridLayout()
            grid.setSpacing(12)

            for idx, w in enumerate(income_windows):
                free  = max(0.0, w.amount - w.total_expenses - w.hold_back - w.planned_savings)
                three = find_next_three_check_month_for_income(w.start_date)
                three_html = ""
                if three:
                    dates_str = ", ".join(d.strftime("%b %d") for d in three.pay_dates)
                    three_html = (
                        f"<br><span style='color:#f0a040'>"
                        f"3-Check Month: {three.month}/{three.year} "
                        f"({dates_str})"
                        f"</span>"
                    )

                block = QLabel(
                    f"<b>Income #{idx + 1}</b> — Next pay: {w.next_pay}<br>"
                    f"<table style='margin-top:4px;'>"
                    f"<tr><td>Paycheck amount</td><td align='right'><b>${w.amount:,.2f}</b></td></tr>"
                    f"<tr><td>Bills this window</td><td align='right' style='color:#f44336'>−${w.total_expenses:,.2f}</td></tr>"
                    f"<tr><td>Hold-back reserve</td><td align='right' style='color:#f44336'>−${w.hold_back:,.2f}</td></tr>"
                    f"<tr><td>Planned savings</td><td align='right' style='color:#f44336'>−${w.planned_savings:,.2f}</td></tr>"
                    f"<tr><td><b>Free to spend</b></td><td align='right'><b style='color:#4caf50'>${free:,.2f}</b></td></tr>"
                    f"</table>"
                    f"{three_html}"
                )
                block.setStyleSheet(
                    "font-size: 14px; padding: 10px; "
                    "border: 1px solid #444; border-radius: 6px;"
                )
                block.setTextFormat(Qt.RichText)
                block.setTextInteractionFlags(Qt.TextSelectableByMouse)
                block.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Maximum)

                row = idx // 2
                col = idx % 2
                grid.addWidget(block, row, col)

            lay.addLayout(grid)

        # ---- Combined forecast ----
        lay.addWidget(self._section_label("Combined Overview"))
        combined_lbl = QLabel(
            f"<table>"
            f"<tr><td>Window</td><td>{combined.start_date} → {combined.end_date}</td></tr>"
            f"<tr><td>Total income</td><td><b>${combined.total_income:,.2f}</b></td></tr>"
            f"<tr><td>Total expenses</td><td>${combined.total_expenses:,.2f}</td></tr>"
            f"<tr><td>Avg spending allocation</td><td>${combined.average_spending:,.2f}</td></tr>"
            f"<tr><td>Planned savings</td><td>${combined.planned_savings:,.2f}</td></tr>"
            f"<tr><td>Total hold-back</td><td>${combined.total_hold_back:,.2f}</td></tr>"
            f"<tr><td><b>Safe to spend</b></td>"
            f"<td><b style='color:#4caf50'>${combined.safe_to_spend:,.2f}</b></td></tr>"
            f"</table>"
        )
        combined_lbl.setTextFormat(Qt.RichText)
        combined_lbl.setTextInteractionFlags(Qt.TextSelectableByMouse)
        combined_lbl.setStyleSheet("font-size: 14px;")
        lay.addWidget(combined_lbl)

        # ---- 3-check month action plan ----
        three_combined = find_next_three_check_month()
        if three_combined:
            months_away = (
                (three_combined.year - datetime.date.today().year) * 12
                + three_combined.month - datetime.date.today().month
            )
            if months_away <= 4:
                lay.addWidget(self._section_label("3-Check Month Action Plan"))
                dates_str = ", ".join(d.strftime("%B %d") for d in three_combined.pay_dates)
                extra_amt = income_windows[0].amount if income_windows else 0.0
                action_lbl = QLabel(
                    f"<b style='color:#f0a040'>You have a 3-paycheck month coming up!</b><br>"
                    f"Month: <b>{three_combined.month}/{three_combined.year}</b>  "
                    f"({months_away} month{'s' if months_away != 1 else ''} away)<br>"
                    f"Pay dates: {dates_str}<br><br>"
                    f"The extra paycheck (~${extra_amt:,.2f}) is a great opportunity:<br>"
                    f"• Pay down high-interest debt ahead of schedule<br>"
                    f"• Boost your emergency fund<br>"
                    f"• Make progress on a savings goal<br>"
                    f"• Pre-pay a large upcoming annual or quarterly expense"
                )
                action_lbl.setTextFormat(Qt.RichText)
                action_lbl.setWordWrap(True)
                action_lbl.setStyleSheet(
                    "font-size: 14px; padding: 10px; "
                    "border: 1px solid #f0a040; border-radius: 6px;"
                )
                lay.addWidget(action_lbl)

        lay.addStretch()

    def _section_label(self, text):
        lbl = QLabel(text)
        lbl.setStyleSheet(
            "font-size: 16px; font-weight: bold; "
            "margin-top: 16px; margin-bottom: 6px;"
        )
        return lbl

    # ------------------------------------------------------------------
    # OTHER SCREENS
    # ------------------------------------------------------------------

    def show_balance(self):
        self.clear_content()
        self.content_layout.addWidget(BalanceScreen())

    def show_timeline(self):
        self.clear_content()
        self.content_layout.addWidget(TimelineScreen())

    def show_calendar(self):
        self.clear_content()
        self.content_layout.addWidget(CalendarScreen())

    def show_expenses(self):
        self.clear_content()
        self.content_layout.addWidget(ExpensesScreen())

    def show_income(self):
        self.clear_content()
        self.content_layout.addWidget(PayScheduleScreen())

    def show_savings(self):
        self.clear_content()
        self.content_layout.addWidget(BudgetScreen())

    def show_goals(self):
        self.clear_content()
        self.content_layout.addWidget(GoalsScreen())

    def show_spending_log(self):
        self.clear_content()
        self.content_layout.addWidget(SpendingLogScreen())

    def show_settings(self):
        self.clear_content()
        self.content_layout.addWidget(SettingsScreen(self.app_ref))

    def show_philosophy(self):
        self.clear_content()
        self.content_layout.addWidget(PhilosophyScreen())
