from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QComboBox,
    QPushButton, QMessageBox
)
from PySide6.QtCore import Qt

from ..database import (
    load_setting_theme,
    save_setting_theme,
    reset_all_data
)

from bi_budget_desktop.app_paths import app_root


class SettingsScreen(QWidget):
    def __init__(self, app_ref):
        super().__init__()
        self.app_ref = app_ref  # QApplication reference for theme changes

        layout = QVBoxLayout(self)

        # -------------------------
        # Title
        # -------------------------
        title = QLabel("Settings")
        title.setStyleSheet("font-size: 22px; font-weight: bold; margin-bottom: 15px;")
        layout.addWidget(title)

        # -------------------------
        # Theme selection
        # -------------------------
        theme_label = QLabel("Theme")
        theme_label.setStyleSheet("font-size: 16px; font-weight: bold;")
        layout.addWidget(theme_label)

        self.theme_dropdown = QComboBox()
        self.theme_dropdown.addItems([
            "system",
            "light",
            "dark",
            "dracula",
            "nord",
            "solarized_dark",
            "solarized_light",
            "tokyo_night",
            "catppuccin_mocha",
            "catppuccin_latte"
        ])

        # Load saved theme
        current = load_setting_theme()
        if current in [
            "system", "light", "dark",
            "dracula", "nord",
            "solarized_dark", "solarized_light",
            "tokyo_night",
            "catppuccin_mocha", "catppuccin_latte"
        ]:
            self.theme_dropdown.setCurrentText(current)

        layout.addWidget(self.theme_dropdown)

        # Live preview
        self.theme_dropdown.currentTextChanged.connect(self.preview_theme)

        # Apply button
        apply_btn = QPushButton("Apply Theme")
        apply_btn.clicked.connect(self.apply_theme_clicked)
        layout.addWidget(apply_btn)

        # -------------------------
        # Reset data
        # -------------------------
        reset_btn = QPushButton("Reset All App Data")
        reset_btn.setStyleSheet("background-color: #b33a3a; color: white; font-weight: bold;")
        reset_btn.clicked.connect(self.reset_clicked)
        layout.addWidget(reset_btn)

        layout.addStretch()

    # ---------------------------------------------------------
    # Live theme preview (does NOT save)
    # ---------------------------------------------------------
    def preview_theme(self, theme_name):
        # Apply theme instantly without saving
        self.app_ref.apply_theme(theme_name)

    # ---------------------------------------------------------
    # Apply theme (saves + applies)
    # ---------------------------------------------------------
    def apply_theme_clicked(self):
        choice = self.theme_dropdown.currentText()
        save_setting_theme(choice)
        self.app_ref.apply_theme(choice)

        QMessageBox.information(self, "Theme Applied", "Theme updated successfully.")

    # ---------------------------------------------------------
    # Reset database
    # ---------------------------------------------------------
    def reset_clicked(self):
        confirm = QMessageBox.question(
            self,
            "Reset All Data",
            "Are you sure you want to reset all app data?\nThis cannot be undone.",
            QMessageBox.Yes | QMessageBox.No
        )

        if confirm == QMessageBox.Yes:
            reset_all_data()
            QMessageBox.information(self, "Reset Complete", "All data has been reset.")
