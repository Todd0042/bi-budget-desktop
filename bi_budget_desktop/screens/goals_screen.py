import datetime

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QMessageBox, QDateEdit, QProgressBar,
    QScrollArea, QFrame, QSizePolicy,
)
from PySide6.QtCore import Qt, QDate

from ..database import (
    get_goals, save_goal, delete_goal, add_to_goal,
    get_income_sources,
)


def _paychecks_until(deadline_str: str) -> int:
    try:
        deadline = datetime.date.fromisoformat(deadline_str)
        today    = datetime.date.today()
        days     = (deadline - today).days
        return max(0, days // 14)
    except Exception:
        return 0


def _total_planned_savings_per_check() -> float:
    total = 0.0
    for _id, amount, frequency, start_date, planned_savings in get_income_sources():
        total += float(planned_savings)
    return total


class GoalsScreen(QWidget):
    def __init__(self):
        super().__init__()

        outer = QVBoxLayout(self)

        title = QLabel("Savings Goals")
        title.setStyleSheet("font-size: 22px; font-weight: bold; margin-bottom: 10px;")
        outer.addWidget(title)

        # Savings per paycheck hint
        self.savings_hint = QLabel("")
        self.savings_hint.setStyleSheet("font-size: 13px; color: #aaaaaa; margin-bottom: 8px;")
        outer.addWidget(self.savings_hint)

        # -------------------------
        # Goals list (scrollable)
        # -------------------------
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        outer.addWidget(scroll)

        self.goals_container = QWidget()
        self.goals_layout = QVBoxLayout(self.goals_container)
        self.goals_layout.setAlignment(Qt.AlignTop)
        scroll.setWidget(self.goals_container)

        # -------------------------
        # Add goal form
        # -------------------------
        form_frame = QFrame()
        form_frame.setFrameShape(QFrame.StyledPanel)
        form_lay = QVBoxLayout(form_frame)

        form_lay.addWidget(self._bold("New Goal"))

        row1 = QHBoxLayout()
        row1.addWidget(QLabel("Name:"))
        self.name_input = QLineEdit()
        row1.addWidget(self.name_input)
        form_lay.addLayout(row1)

        row2 = QHBoxLayout()
        row2.addWidget(QLabel("Target ($):"))
        self.target_input = QLineEdit()
        row2.addWidget(self.target_input)
        row2.addWidget(QLabel("Deadline:"))
        self.deadline_input = QDateEdit()
        self.deadline_input.setCalendarPopup(True)
        self.deadline_input.setDate(
            QDate.currentDate().addMonths(6)
        )
        row2.addWidget(self.deadline_input)
        form_lay.addLayout(row2)

        add_btn = QPushButton("Add Goal")
        add_btn.clicked.connect(self._add_goal)
        form_lay.addWidget(add_btn)

        outer.addWidget(form_frame)

        self.refresh()

    # ------------------------------------------------------------------

    def _bold(self, text):
        lbl = QLabel(text)
        lbl.setStyleSheet("font-weight: bold; font-size: 15px;")
        return lbl

    # ------------------------------------------------------------------

    def refresh(self):
        # Clear existing goal cards
        while self.goals_layout.count():
            item = self.goals_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        goals = get_goals()
        per_check = _total_planned_savings_per_check()
        self.savings_hint.setText(
            f"Total planned savings per paycheck across all income sources: ${per_check:,.2f}"
        )

        if not goals:
            lbl = QLabel("No goals yet. Add one below.")
            lbl.setStyleSheet("color: #888888; margin: 20px;")
            self.goals_layout.addWidget(lbl)
            return

        for goal_id, name, target, deadline, saved in goals:
            self.goals_layout.addWidget(
                self._make_goal_card(goal_id, name, target, deadline, saved, per_check)
            )

    def _make_goal_card(self, goal_id, name, target, deadline, saved, per_check):
        frame = QFrame()
        frame.setFrameShape(QFrame.StyledPanel)
        lay = QVBoxLayout(frame)

        # Title row
        title_row = QHBoxLayout()
        name_lbl = QLabel(f"<b>{name}</b>")
        name_lbl.setStyleSheet("font-size: 16px;")
        title_row.addWidget(name_lbl)
        title_row.addStretch()

        del_btn = QPushButton("Delete")
        del_btn.setFixedWidth(70)
        del_btn.clicked.connect(lambda checked=False, gid=goal_id: self._delete_goal(gid))
        title_row.addWidget(del_btn)
        lay.addLayout(title_row)

        # Progress bar
        pct = min(100, int((saved / target * 100) if target > 0 else 0))
        bar = QProgressBar()
        bar.setMinimum(0)
        bar.setMaximum(100)
        bar.setValue(pct)
        bar.setFormat(f"${saved:,.2f} / ${target:,.2f}  ({pct}%)")
        bar.setTextVisible(True)
        lay.addWidget(bar)

        # Stats
        remaining    = max(0.0, target - saved)
        checks_left  = _paychecks_until(deadline)
        per_check_needed = (remaining / checks_left) if checks_left > 0 else remaining

        try:
            dl = datetime.date.fromisoformat(deadline)
            dl_str = dl.strftime("%B %d, %Y")
        except Exception:
            dl_str = deadline

        on_track = per_check <= 0 or per_check_needed <= 0 or per_check >= per_check_needed
        track_text = "On track" if on_track else f"Need ${per_check_needed:,.2f}/check (have ${per_check:,.2f} allocated)"
        track_color = "#4caf50" if on_track else "#f44336"

        stats = QLabel(
            f"Deadline: {dl_str}  |  Remaining: ${remaining:,.2f}  |  "
            f"Paychecks left: {checks_left}  |  "
            f"<span style='color:{track_color}'>{track_text}</span>"
        )
        stats.setStyleSheet("font-size: 13px;")
        lay.addWidget(stats)

        # Deposit row
        dep_row = QHBoxLayout()
        dep_input = QLineEdit()
        dep_input.setPlaceholderText("Deposit amount")
        dep_input.setFixedWidth(140)
        dep_row.addWidget(dep_input)

        dep_btn = QPushButton("Add to Goal")
        dep_btn.clicked.connect(
            lambda checked=False, gid=goal_id, inp=dep_input: self._deposit(gid, inp)
        )
        dep_row.addWidget(dep_btn)
        dep_row.addStretch()
        lay.addLayout(dep_row)

        return frame

    # ------------------------------------------------------------------

    def _add_goal(self):
        name   = self.name_input.text().strip()
        target = self.target_input.text().strip()
        if not name or not target:
            QMessageBox.warning(self, "Missing Data", "Enter a name and target amount.")
            return
        try:
            target_amt = float(target)
        except ValueError:
            QMessageBox.warning(self, "Invalid Amount", "Target must be a number.")
            return

        deadline = self.deadline_input.date().toString("yyyy-MM-dd")
        save_goal(name, target_amt, deadline)
        self.name_input.clear()
        self.target_input.clear()
        self.deadline_input.setDate(QDate.currentDate().addMonths(6))
        self.refresh()

    def _deposit(self, goal_id, inp):
        amt_str = inp.text().strip()
        if not amt_str:
            return
        try:
            amt = float(amt_str)
        except ValueError:
            QMessageBox.warning(self, "Invalid Amount", "Enter a valid number.")
            return
        add_to_goal(goal_id, amt)
        inp.clear()
        self.refresh()

    def _delete_goal(self, goal_id):
        confirm = QMessageBox.question(
            self, "Delete Goal", "Delete this goal?",
            QMessageBox.Yes | QMessageBox.No,
        )
        if confirm == QMessageBox.Yes:
            delete_goal(goal_id)
            self.refresh()
