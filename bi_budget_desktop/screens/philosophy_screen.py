from PySide6.QtWidgets import (
    QWidget, QLabel, QVBoxLayout, QHBoxLayout,
    QScrollArea, QFrame
)
from PySide6.QtGui import QPixmap
from PySide6.QtCore import Qt

from bi_budget_desktop.app_paths import app_root


class PhilosophyScreen(QWidget):
    def __init__(self):
        super().__init__()

        # Outer layout
        outer = QVBoxLayout(self)

        # Scroll area wrapper
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        outer.addWidget(scroll)

        # Content widget inside scroll area
        content = QWidget()
        scroll.setWidget(content)

        layout = QVBoxLayout(content)
        layout.setSpacing(32)  # space between sections

        # ---------------------------------------------------------
        # Helper to add a section
        # ---------------------------------------------------------
        def add_section(title, text, icon_filename):
            section = QWidget()
            s_layout = QVBoxLayout(section)
            s_layout.setSpacing(8)

            # Row: icon + title
            row = QWidget()
            row_layout = QHBoxLayout(row)
            row_layout.setSpacing(16)
            row_layout.setContentsMargins(0, 0, 0, 0)

            # Build full icon path using app_root()
            icon_path = app_root() / "icons" / icon_filename

            # Icon
            pix = QPixmap(str(icon_path)).scaled(
                48, 48,
                Qt.KeepAspectRatio,
                Qt.SmoothTransformation
            )
            icon_label = QLabel()
            icon_label.setPixmap(pix)

            # Title
            title_label = QLabel(title)
            title_label.setStyleSheet("""
                font-size: 20px;
                font-weight: bold;
            """)

            row_layout.addWidget(icon_label)
            row_layout.addWidget(title_label)
            row_layout.addStretch()

            # Body text
            body = QLabel(text)
            body.setWordWrap(True)
            body.setStyleSheet("font-size: 14px; line-height: 1.4;")

            # Divider line
            divider = QFrame()
            divider.setFrameShape(QFrame.HLine)
            divider.setFrameShadow(QFrame.Sunken)
            divider.setStyleSheet("color: #ccc;")

            # Add to section
            s_layout.addWidget(row)
            s_layout.addWidget(body)
            s_layout.addWidget(divider)

            layout.addWidget(section)

        # ---------------------------------------------------------
        # Sections
        # ---------------------------------------------------------
        add_section(
            "Bi‑Weekly Paychecks Are the Foundation",
            "Most people are paid every two weeks — not twice a month. "
            "Paychecks drift across the calendar, and that’s normal. "
            "What matters is the 14‑day cycle, not the exact date.",
            "money.png"
        )

        add_section(
            "Monthly Bills Are Predictable Enough",
            "Bills might shift by a day due to weekends or holidays, "
            "but the amount and timing stay consistent.",
            "calendar.png"
        )

        add_section(
            "Your Average Spending Is the Key Number",
            "Instead of tracking every transaction, Bi‑Budget uses your "
            "average spending per paycheck to forecast how much you can safely spend.",
            "brain.png"
        )

        add_section(
            "Savings Handles the Irregular Stuff",
            "Life throws curveballs — car repairs, holidays, school clothes, vet bills, yearly subscriptions. "
            "Savings is the buffer that absorbs these without stress.",
            "piggybank.png"
        )

        add_section(
            "Safety and Stability",
            "Your system should protect your essentials first — rent, utilities, food — "
            "before discretionary spending.",
            "shield.png"
        )

        add_section(
            "Multiple Incomes Are Treated Independently",
            "Each income source has its own bi‑weekly cycle. "
            "Bi‑Budget calculates each one separately, then combines them.",
            "people.png"
        )

        add_section(
            "Forecasting Keeps You Ahead",
            "Bi‑Budget doesn’t sync with banks or categorize transactions. "
            "It answers the one question that matters: "
            "How much can I safely spend this paycheck?",
            "chart.png"
        )

        add_section(
            "Focus on What Actually Matters",
            "No categories. No daily budgets. No transaction logs. No overwhelm. "
            "Just a clean, simple system that keeps you ahead of your bills.",
            "target.png"
        )

        layout.addStretch()

        # Disclaimer footer (outside scroll area)
        disclaimer = QLabel(
            "Disclaimer: Bi‑Budget is a personal budgeting tool and does not provide financial advice. "
            "How you choose to use the app is your own responsibility."
        )
        disclaimer.setWordWrap(True)
        disclaimer.setAlignment(Qt.AlignCenter)
        disclaimer.setStyleSheet("font-size: 12px; color: #666; padding: 12px;")

        outer.addWidget(disclaimer)

        # Version.
        versioning = QLabel(
            "Version 1.0a"
        )
        versioning.setWordWrap(True)
        versioning.setAlignment(Qt.AlignCenter)
        versioning.setStyleSheet("font-size: 12px; color: #666; padding: 12px;")

        outer.addWidget(versioning)
