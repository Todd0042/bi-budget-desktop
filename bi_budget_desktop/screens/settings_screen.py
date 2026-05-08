import csv
import os
from datetime import date

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QComboBox,
    QPushButton, QMessageBox, QFileDialog,
)
from PySide6.QtCore import Qt

from ..database import (
    load_setting_theme,
    save_setting_theme,
    reset_all_data,
    get_expenses,
    get_income_sources,
    get_savings_events,
    get_goals,
    get_spending_log,
    load_pay_schedule,
)
from bi_budget_desktop.app_paths import app_root


class SettingsScreen(QWidget):
    def __init__(self, app_ref):
        super().__init__()
        self.app_ref = app_ref

        layout = QVBoxLayout(self)

        title = QLabel("Settings")
        title.setStyleSheet("font-size: 22px; font-weight: bold; margin-bottom: 15px;")
        layout.addWidget(title)

        # -------------------------
        # Theme selection
        # -------------------------
        layout.addWidget(self._section("Theme"))

        valid_themes = [
            "system", "light", "dark",
            "dracula", "nord",
            "solarized_dark", "solarized_light",
            "tokyo_night",
            "catppuccin_mocha", "catppuccin_latte",
            "gruvbox_dark", "everforest_dark",
            "monokai_pro", "one_dark",
            "material_ocean", "night_owl",
            "ayu_dark", "oxide_dark",
            "military_olive_dark",
        ]

        self.theme_dropdown = QComboBox()
        self.theme_dropdown.addItems(valid_themes)

        current = load_setting_theme()
        if current in valid_themes:
            self.theme_dropdown.setCurrentText(current)

        layout.addWidget(self.theme_dropdown)
        self.theme_dropdown.currentTextChanged.connect(self.preview_theme)

        apply_btn = QPushButton("Apply Theme")
        apply_btn.clicked.connect(self.apply_theme_clicked)
        layout.addWidget(apply_btn)

        # -------------------------
        # CSV export
        # -------------------------
        layout.addWidget(self._section("Data Export"))

        export_btn = QPushButton("Export All Data to CSV…")
        export_btn.clicked.connect(self.export_csv)
        layout.addWidget(export_btn)

        # -------------------------
        # Reset
        # -------------------------
        layout.addWidget(self._section("Danger Zone"))

        reset_btn = QPushButton("Reset All App Data")
        reset_btn.setStyleSheet(
            "background-color: #b33a3a; color: white; font-weight: bold;"
        )
        reset_btn.clicked.connect(self.reset_clicked)
        layout.addWidget(reset_btn)

        layout.addStretch()

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _section(self, text):
        lbl = QLabel(text)
        lbl.setStyleSheet(
            "font-size: 16px; font-weight: bold; margin-top: 18px; margin-bottom: 4px;"
        )
        return lbl

    # ------------------------------------------------------------------
    # Theme
    # ------------------------------------------------------------------

    def preview_theme(self, theme_name):
        self.app_ref.apply_theme(theme_name)

    def apply_theme_clicked(self):
        choice = self.theme_dropdown.currentText()
        save_setting_theme(choice)
        self.app_ref.apply_theme(choice)
        QMessageBox.information(self, "Theme Applied", "Theme updated successfully.")

    # ------------------------------------------------------------------
    # CSV export
    # ------------------------------------------------------------------

    def export_csv(self):
        default_name = f"bibudget_export_{date.today().isoformat()}.csv"
        path, _ = QFileDialog.getSaveFileName(
            self, "Save CSV Export", default_name, "CSV Files (*.csv)"
        )
        if not path:
            return

        try:
            with open(path, "w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)

                # --- Expenses ---
                writer.writerow(["# EXPENSES"])
                writer.writerow(["ID", "Name", "Amount", "Due Day", "Due Month",
                                  "Due Date (one-time)", "Frequency", "Category"])
                for row in get_expenses():
                    writer.writerow(row)
                writer.writerow([])

                # --- Income Sources ---
                writer.writerow(["# INCOME SOURCES"])
                writer.writerow(["ID", "Amount", "Frequency", "Start Date", "Planned Savings/Check"])
                for row in get_income_sources():
                    writer.writerow(row)
                writer.writerow([])

                # --- Pay Schedule ---
                writer.writerow(["# PAY SCHEDULE"])
                writer.writerow(["Last Pay", "Next Pay", "Avg Spend/Check", "Planned Savings"])
                sched = load_pay_schedule()
                if sched:
                    writer.writerow(sched)
                writer.writerow([])

                # --- Savings Events ---
                writer.writerow(["# SAVINGS HISTORY"])
                writer.writerow(["Amount", "Date", "Note", "Source"])
                for row in get_savings_events():
                    writer.writerow(row)
                writer.writerow([])

                # --- Goals ---
                writer.writerow(["# GOALS"])
                writer.writerow(["ID", "Name", "Target", "Deadline", "Saved So Far"])
                for row in get_goals():
                    writer.writerow(row)
                writer.writerow([])

                # --- Spending Log ---
                writer.writerow(["# SPENDING LOG"])
                writer.writerow(["ID", "Amount", "Date", "Note", "Category"])
                for row in get_spending_log(limit=10000):
                    writer.writerow(row)

            QMessageBox.information(
                self, "Export Complete",
                f"Data exported to:\n{path}",
            )
        except Exception as e:
            QMessageBox.critical(self, "Export Failed", str(e))

    # ------------------------------------------------------------------
    # Reset
    # ------------------------------------------------------------------

    def reset_clicked(self):
        confirm = QMessageBox.question(
            self,
            "Reset All Data",
            "Are you sure you want to reset all app data?\nThis cannot be undone.",
            QMessageBox.Yes | QMessageBox.No,
        )
        if confirm == QMessageBox.Yes:
            reset_all_data()
            QMessageBox.information(self, "Reset Complete", "All data has been reset.")
